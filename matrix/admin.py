"""
Kleines Web-UI für den Matrix-Worker (matrix-sync).

Absicht
=======
Element kann bei privaten Spaces oft kein lokales Alias setzen.
Keycloak-Attribute per Hand sind umständlich.

Diese Datei ist genau eine Seite:
  1. zeigt Gruppen und ihre Matrix-Aliase
  2. speichert das Attribut ``matrix`` an einer Keycloak-Gruppe
  3. legt optional Space + Raum an (privat, unverschlüsselt, lokales Alias)

Der Worker (sync.py) bleibt unverändert der Poll-Loop. Er liest dasselbe
Attribut ``matrix`` und joined/kickt. Hier wird nur konfiguriert.

Aufruf: python -u /app/admin.py
Auth: nicht öffentlich. Nur Docker-Netz + HTTP Basic (Passwort aus .env).
Der Browser geht über das Portal (Keycloak-Session, Amt-Gruppen).
"""
from __future__ import annotations

import base64
import hmac
import html
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import requests

# Dieselben Hilfen wie der Worker — eine Quelle für Login/Aliase/Gruppenliste.
import sync as w

LISTEN = ("0.0.0.0", int(os.environ.get("ADMIN_PORT", "8090")))
ADMIN_USER = os.environ.get("MATRIX_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("MATRIX_ADMIN_PASSWORD", "")

# Alias: klein, Zahlen, Bindestrich. Kein # und kein Servername — den hängt
# sync.py selbst an (z.B. #wanne-eickel:chat.example.de).
ALIAS_OK = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")


def need_auth(handler: BaseHTTPRequestHandler) -> bool:
    """True = Request darf weiter. False = 401 wurde schon gesendet."""
    if not ADMIN_PASSWORD:
        handler.send_error(503, "MATRIX_ADMIN_PASSWORD fehlt")
        return False
    raw = handler.headers.get("Authorization", "")
    if not raw.startswith("Basic "):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="matrix-sync"')
        handler.end_headers()
        return False
    try:
        user, pw = base64.b64decode(raw.split(" ", 1)[1]).decode().split(":", 1)
    except Exception:
        handler.send_error(401)
        return False
    user_ok = hmac.compare_digest(user, ADMIN_USER)
    pw_ok = hmac.compare_digest(pw, ADMIN_PASSWORD)
    if not (user_ok and pw_ok):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="matrix-sync"')
        handler.end_headers()
        return False
    return True


def parse_aliases(text: str) -> list[str]:
    """'wanne-eickel, wanne-eickel-chat' -> ['wanne-eickel', 'wanne-eickel-chat']"""
    out = []
    for part in text.replace(";", ",").split(","):
        name = part.strip().lstrip("#").split(":")[0].strip().lower()
        if not name:
            continue
        if not ALIAS_OK.match(name):
            raise ValueError(f"ungültiger Alias: {name}")
        if name not in out:
            out.append(name)
    return out


def kc_get_group(token: str, gid: str) -> dict:
    r = requests.get(
        f"{w.KC}/admin/realms/{w.REALM}/groups/{gid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def kc_set_matrix(token: str, gid: str, aliases: list[str]) -> None:
    """Schreibt nur das Attribut matrix, andere Attribute bleiben."""
    g = kc_get_group(token, gid)
    attrs = dict(g.get("attributes") or {})
    if aliases:
        attrs["matrix"] = [",".join(aliases)]
    else:
        attrs.pop("matrix", None)
    body = {"name": g["name"], "attributes": attrs}
    r = requests.put(
        f"{w.KC}/admin/realms/{w.REALM}/groups/{gid}",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=20,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Keycloak Gruppe speichern: {r.status_code} {r.text[:300]}")


def kc_create_group(token: str, name: str) -> str:
    r = requests.post(
        f"{w.KC}/admin/realms/{w.REALM}/groups",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
        timeout=20,
    )
    if r.status_code not in (201, 204):
        raise RuntimeError(f"Keycloak Gruppe anlegen: {r.status_code} {r.text[:300]}")
    # Location: .../groups/{uuid}
    loc = r.headers.get("Location") or ""
    gid = loc.rstrip("/").split("/")[-1]
    if not gid:
        for g in w.kc_iter_groups(token):
            if g.get("name") == name:
                return g["id"]
        raise RuntimeError("Gruppe angelegt, id nicht gefunden")
    return gid


def mx_set_alias(mx_token: str, alias_local: str, room_id: str) -> None:
    """Lokales Alias, ohne öffentliches Verzeichnis (Element-UI kann das bei
    privaten Spaces oft nicht)."""
    full = f"#{alias_local}:{w.SERVER}"
    r = w.mx(
        "PUT",
        f"/_matrix/client/v3/directory/room/{w.q(full)}",
        mx_token,
        json={"room_id": room_id},
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Alias {full}: {r.status_code} {r.text[:300]}")


def mx_create_space(mx_token: str, name: str, alias: str) -> str:
    # creation_content.type = m.space macht aus dem Raum einen Space.
    # Kein m.room.encryption — sonst wieder Schlüssel-Dialog.
    r = w.mx(
        "POST",
        "/_matrix/client/v3/createRoom",
        mx_token,
        json={
            "name": name,
            "preset": "private_chat",
            "visibility": "private",
            "room_version": "10",
            "creation_content": {"type": "m.space", "m.federate": False},
            "initial_state": [
                {
                    "type": "m.room.join_rules",
                    "content": {"join_rule": "invite"},
                },
                {
                    "type": "m.room.guest_access",
                    "content": {"guest_access": "forbidden"},
                },
                {
                    "type": "m.room.history_visibility",
                    "content": {"history_visibility": "shared"},
                },
            ],
            "power_level_content_override": {
                "events": {"m.room.encryption": 100}
            },
        },
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Space anlegen: {r.status_code} {r.text[:300]}")
    room_id = r.json()["room_id"]
    mx_set_alias(mx_token, alias, room_id)
    return room_id


def mx_create_room(mx_token: str, name: str, alias: str, space_id: str) -> str:
    # join_rule restricted: wer im Space ist, darf in den Raum (wie Vorstand/Demo).
    r = w.mx(
        "POST",
        "/_matrix/client/v3/createRoom",
        mx_token,
        json={
            "name": name,
            "preset": "private_chat",
            "visibility": "private",
            "room_version": "10",
            "creation_content": {"m.federate": False},
            "initial_state": [
                {
                    "type": "m.room.join_rules",
                    "content": {
                        "join_rule": "restricted",
                        "allow": [
                            {"type": "m.room_membership", "room_id": space_id}
                        ],
                    },
                },
                {
                    "type": "m.room.guest_access",
                    "content": {"guest_access": "forbidden"},
                },
                {
                    "type": "m.room.history_visibility",
                    "content": {"history_visibility": "shared"},
                },
                {
                    "type": "m.space.parent",
                    "state_key": space_id,
                    "content": {"canonical": True, "via": [w.SERVER]},
                },
            ],
            "power_level_content_override": {
                "invite": 50,
                "events": {"m.room.encryption": 100},
            },
        },
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Raum anlegen: {r.status_code} {r.text[:300]}")
    room_id = r.json()["room_id"]
    mx_set_alias(mx_token, alias, room_id)
    # Space-Baum: Kind am Space eintragen.
    r = w.mx(
        "PUT",
        f"/_matrix/client/v3/rooms/{w.q(space_id)}/state/m.space.child/{w.q(room_id)}",
        mx_token,
        json={"via": [w.SERVER], "suggested": False},
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Space-Kind: {r.status_code} {r.text[:300]}")
    return room_id


def alias_status(mx_token: str, local: str) -> str:
    rid = w.resolve(f"#{local}:{w.SERVER}", mx_token)
    return "da" if rid else "fehlt"


def page(msg: str = "", err: str = "") -> bytes:
    kc = w.kc_token()
    mx_token = w.mx_login()
    groups = sorted(w.kc_iter_groups(kc), key=lambda g: (g.get("name") or ""))
    _gate, yml_rooms = w.load_map()

    rows = []
    for g in groups:
        name = html.escape(g.get("name") or "")
        gid = html.escape(g.get("id") or "")
        aliases = w.matrix_aliases(g.get("attributes"))
        bits = []
        for a in aliases:
            st = alias_status(mx_token, a)
            bits.append(f"{html.escape(a)} ({st})")
        alias_txt = ", ".join(bits) if bits else "—"
        rows.append(
            f"<tr><td>{name}</td><td>{alias_txt}</td>"
            f"<td><code>{gid}</code></td></tr>"
        )

    yml_bits = []
    for alias, extra in yml_rooms.items():
        local = alias.split(":")[0].lstrip("#")
        st = alias_status(mx_token, local)
        yml_bits.append(
            f"<li><code>{html.escape(local)}</code> ({st}) ← "
            f"{html.escape(', '.join(extra) or 'nur Gate')}</li>"
        )

    opts = []
    for g in groups:
        n = g.get("name") or ""
        opts.append(f'<option value="{html.escape(g["id"])}">{html.escape(n)}</option>')

    note = f'<p class="ok">{html.escape(msg)}</p>' if msg else ""
    if err:
        note += f'<p class="err">{html.escape(err)}</p>'

    body = f"""<!doctype html>
<html lang="de"><head>
<meta charset="utf-8">
<title>Matrix-Sync</title>
<style>
 body {{ font-family: sans-serif; max-width: 52rem; margin: 1.5rem auto; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td, th {{ border: 1px solid #ccc; padding: .35rem .5rem; text-align: left; }}
 fieldset {{ margin: 1.2rem 0; }}
 label {{ display: block; margin-top: .6rem; }}
 input[type=text] {{ width: 100%; max-width: 28rem; }}
 .ok {{ color: #060; }}
 .err {{ color: #a00; white-space: pre-wrap; }}
 code {{ font-size: .9em; }}
</style>
</head><body>
<h1>Matrix-Sync</h1>
<p>Gate bleibt <code>mitgliedschaft:aktiv</code> (groups.yml). Der Worker pollt
alle 60s. Private Spaces: Alias wird hier gesetzt, nicht in Element.</p>
{note}

<h2>Keycloak → Matrix</h2>
<table>
<thead><tr><th>Gruppe</th><th>Aliase (matrix-Attribut)</th><th>id</th></tr></thead>
<tbody>
{"".join(rows) or "<tr><td colspan=3>keine Gruppen</td></tr>"}
</tbody>
</table>

<h2>Fest in groups.yml</h2>
<ul>{"".join(yml_bits)}</ul>

<fieldset>
<legend>1. Nur Zuordnung speichern</legend>
<p>Attribut <code>matrix</code> an der Gruppe. Aliase müssen schon existieren.</p>
<form method="post" action="/sync-admin/save">
  <label>Gruppe
    <select name="group_id" required>{"".join(opts)}</select>
  </label>
  <label>Aliase (Komma, ohne #)
    <input type="text" name="aliases" placeholder="wanne-eickel,wanne-eickel-chat" required>
  </label>
  <p><button type="submit">Speichern</button></p>
</form>
</fieldset>

<fieldset>
<legend>2. Space + Raum anlegen und zuordnen</legend>
<p>Legt einen privaten Space und einen Chat ohne Verschlüsselung an,
setzt lokale Aliase, schreibt das Keycloak-Attribut.</p>
<form method="post" action="/sync-admin/create">
  <label>Bestehende Gruppe
    <select name="group_id">
      <option value="">— bestehende wählen —</option>
      {"".join(opts)}
    </select>
  </label>
  <label>Oder neue Gruppe (Name, z.B. verein:xy)
    <input type="text" name="new_group" placeholder="leer = bestehende nehmen">
  </label>
  <label>Space-Name
    <input type="text" name="space_name" required placeholder="Wanne-Eickel Verein">
  </label>
  <label>Space-Alias
    <input type="text" name="space_alias" required placeholder="wanne-eickel">
  </label>
  <label>Raum-Name
    <input type="text" name="room_name" required placeholder="Wanne-Eickel Chat">
  </label>
  <label>Raum-Alias
    <input type="text" name="room_alias" required placeholder="wanne-eickel-chat">
  </label>
  <p><button type="submit">Anlegen</button></p>
</form>
</fieldset>
</body></html>
"""
    return body.encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s\n" % (fmt % args))

    def _send_html(self, blob: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def _redirect(self, hint: str) -> None:
        # 303: POST nicht wiederholen beim Reload.
        self.send_response(303)
        self.send_header("Location", "/sync-admin/?ok=" + hint)
        self.end_headers()

    def do_GET(self) -> None:
        if not need_auth(self):
            return
        path = self.path.split("?", 1)[0]
        if path in ("/sync-admin", "/sync-admin/"):
            q = ""
            if "?" in self.path:
                q = parse_qs(self.path.split("?", 1)[1]).get("ok", [""])[0]
            try:
                self._send_html(page(msg=q))
            except Exception as e:
                self._send_html(page(err=str(e)), 500)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if not need_auth(self):
            return
        n = int(self.headers.get("Content-Length") or "0")
        fields = parse_qs(self.rfile.read(n).decode(), keep_blank_values=True)

        def f(key: str) -> str:
            return (fields.get(key) or [""])[0].strip()

        path = self.path.split("?", 1)[0]
        try:
            if path == "/sync-admin/save":
                aliases = parse_aliases(f("aliases"))
                kc_set_matrix(w.kc_token(), f("group_id"), aliases)
                self._redirect("Zuordnung gespeichert")
                return
            if path == "/sync-admin/create":
                space_alias = parse_aliases(f("space_alias"))
                room_alias = parse_aliases(f("room_alias"))
                if len(space_alias) != 1 or len(room_alias) != 1:
                    raise ValueError("je ein Alias für Space und Raum")
                kc = w.kc_token()
                gid = f("new_group")
                if gid:
                    gid = kc_create_group(kc, gid)
                else:
                    gid = f("group_id")
                if not gid:
                    raise ValueError("Gruppe wählen oder neuen Namen angeben")
                mx_token = w.mx_login()
                space_id = mx_create_space(mx_token, f("space_name"), space_alias[0])
                mx_create_room(mx_token, f("room_name"), room_alias[0], space_id)
                # Bestehende Aliase der Gruppe behalten und die neuen anhängen.
                existing = w.matrix_aliases(kc_get_group(kc, gid).get("attributes"))
                merged = list(existing)
                for a in space_alias + room_alias:
                    if a not in merged:
                        merged.append(a)
                kc_set_matrix(kc, gid, merged)
                self._redirect("Space+Raum angelegt, Zuordnung gespeichert")
                return
        except Exception as e:
            self._send_html(page(err=str(e)), 400)
            return
        self.send_error(404)


def main() -> None:
    if not ADMIN_PASSWORD:
        raise SystemExit("MATRIX_ADMIN_PASSWORD setzen")
    httpd = ThreadingHTTPServer(LISTEN, Handler)
    print(f"matrix-admin http://{LISTEN[0]}:{LISTEN[1]}/sync-admin/", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
