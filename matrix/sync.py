"""Keycloak-Gruppen -> Matrix-Räume. Poll, kein Event-Bus."""
from __future__ import annotations

import logging
import os
import time
import urllib.parse
from pathlib import Path

import requests
import yaml

log = logging.getLogger("matrix-sync")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

KC = os.environ["KEYCLOAK_URL"].rstrip("/")
REALM = os.environ.get("KEYCLOAK_REALM", "aeneas")
KC_ID = os.environ["KEYCLOAK_SYNC_CLIENT_ID"]
KC_SECRET = os.environ["KEYCLOAK_SYNC_CLIENT_SECRET"]
HS = os.environ["MATRIX_HOMESERVER"].rstrip("/")
SERVER = os.environ["MATRIX_SERVER_NAME"]
BOT_USER = os.environ["MATRIX_SYNC_USER"]
BOT_PASS = os.environ["MATRIX_SYNC_PASSWORD"]
INTERVAL = int(os.environ.get("INTERVAL", "60"))
MAP_FILE = os.environ.get("GROUPS_FILE", "/app/groups.yml")


def load_map() -> tuple[set[str], dict[str, list[str]]]:
    data = yaml.safe_load(Path(MAP_FILE).read_text())
    gate = set(data.get("gate") or [])
    rooms = {}
    for name, extra in (data.get("rooms") or {}).items():
        rooms[f"#{name}:{SERVER}"] = list(extra or [])
    return gate, rooms


def kc_token() -> str:
    r = requests.post(
        f"{KC}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": KC_ID,
            "client_secret": KC_SECRET,
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def kc_users(token: str) -> list[dict]:
    out, first = [], 0
    while True:
        r = requests.get(
            f"{KC}/admin/realms/{REALM}/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"first": first, "max": 100, "enabled": True},
            timeout=20,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        first += len(batch)
    return out


def kc_groups(token: str, user_id: str) -> set[str]:
    r = requests.get(
        f"{KC}/admin/realms/{REALM}/users/{user_id}/groups",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    r.raise_for_status()
    return {g["name"] for g in r.json()}


def _kc_group_page(token: str, parent: str | None, first: int) -> list[dict]:
    if parent:
        url = f"{KC}/admin/realms/{REALM}/groups/{parent}/children"
    else:
        url = f"{KC}/admin/realms/{REALM}/groups"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"briefRepresentation": "false", "first": first, "max": 100},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def kc_iter_groups(token: str):
    seen: set[str] = set()

    def walk(parent: str | None = None):
        first = 0
        while True:
            batch = _kc_group_page(token, parent, first)
            if not batch:
                break
            for g in batch:
                gid = g.get("id") or ""
                if not gid or gid in seen:
                    continue
                seen.add(gid)
                yield g
                yield from walk(gid)
            if len(batch) < 100:
                break
            first += len(batch)

    yield from walk()


def matrix_aliases(attrs: dict | None) -> list[str]:
    out = []
    for raw in (attrs or {}).get("matrix") or []:
        for part in str(raw).replace(";", ",").split(","):
            name = part.strip().lstrip("#").split(":")[0].strip()
            if name:
                out.append(name)
    return out


def merge_kc_rooms(token: str, rooms: dict[str, list[str]]) -> None:
    """Attribut matrix an der Keycloak-Gruppe: Aliase, Komma getrennt."""
    for g in kc_iter_groups(token):
        gname = (g.get("name") or "").strip()
        if not gname:
            continue
        for local in matrix_aliases(g.get("attributes")):
            alias = f"#{local}:{SERVER}"
            extra = rooms.setdefault(alias, [])
            if gname not in extra:
                extra.append(gname)


def mx_login() -> str:
    r = requests.post(
        f"{HS}/_matrix/client/v3/login",
        json={
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": BOT_USER},
            "password": BOT_PASS,
        },
        timeout=20,
    )
    if r.status_code == 429:
        raise requests.HTTPError("429 login rate-limit", response=r)
    r.raise_for_status()
    return r.json()["access_token"]


def mx(method: str, path: str, token: str, **kwargs):
    kwargs.setdefault("timeout", 20)
    headers = kwargs.setdefault("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, HS + path, **kwargs)
    if r.status_code >= 500:
        log.error("%s %s -> %s %s", method, path, r.status_code, r.text[:200])
    return r


def q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def resolve(alias: str, token: str) -> str | None:
    r = mx("GET", f"/_matrix/client/v3/directory/room/{q(alias)}", token)
    if r.status_code != 200:
        return None
    return r.json().get("room_id")


def joined(mxid: str, token: str) -> set[str]:
    r = mx("GET", f"/_synapse/admin/v1/users/{q(mxid)}/joined_rooms", token)
    if r.status_code != 200:
        return set()
    return set(r.json().get("joined_rooms") or [])


def user_exists(mxid: str, token: str) -> bool:
    return mx("GET", f"/_synapse/admin/v2/users/{q(mxid)}", token).status_code == 200


def force_join(mxid: str, alias: str, token: str) -> None:
    mx("POST", f"/_synapse/admin/v1/join/{q(alias)}", token, json={"user_id": mxid})


def make_admin(mxid: str, room_id: str, token: str) -> None:
    mx(
        "POST",
        f"/_synapse/admin/v1/rooms/{q(room_id)}/make_room_admin",
        token,
        json={"user_id": mxid},
    )


def client_join(room_id: str, token: str) -> None:
    mx("POST", f"/_matrix/client/v3/join/{q(room_id)}", token)


def kick(mxid: str, room_id: str, token: str) -> None:
    mx(
        "POST",
        f"/_matrix/client/v3/rooms/{q(room_id)}/kick",
        token,
        json={"user_id": mxid, "reason": "Keycloak-Gruppe fehlt"},
    )


def allowed(groups: set[str], gate: set[str], extra: list[str]) -> bool:
    if gate and not gate <= groups:
        return False
    if extra and not any(g in groups for g in extra):
        return False
    return True


def skip_kc_user(name: str) -> bool:
    return (not name) or name == BOT_USER or name.startswith("service-account-")


def ensure_bot(alias: str, room_id: str, bot: str, token: str) -> bool:
    """Privater Raum: erst Raum-Admin impersonieren (Invite), dann selbst joinen."""
    make_admin(bot, room_id, token)
    client_join(room_id, token)
    if room_id in joined(bot, token):
        return True
    log.warning(
        "Bot nicht in %s — in Element einladen: %s",
        alias,
        bot,
    )
    return False


def cycle(token: str) -> None:
    gate, room_map = load_map()
    merge_kc_rooms(kc_token(), room_map)
    bot = f"@{BOT_USER}:{SERVER}"
    alias_to_id: dict[str, str] = {}
    for alias in room_map:
        rid = resolve(alias, token)
        if not rid:
            log.warning("Raum %s fehlt — in Element anlegen, Alias setzen", alias)
            continue
        alias_to_id[alias] = rid
        if not ensure_bot(alias, rid, bot, token):
            alias_to_id.pop(alias)

    n_skip = n_matrix = n_join = n_kick = 0
    kc = kc_token()
    for u in kc_users(kc):
        name = (u.get("username") or "").strip()
        if skip_kc_user(name):
            continue
        mxid = f"@{name}:{SERVER}"
        if not user_exists(mxid, token):
            n_skip += 1
            continue
        n_matrix += 1
        groups = kc_groups(kc, u["id"])
        have = joined(mxid, token)
        for alias, extra in room_map.items():
            rid = alias_to_id.get(alias)
            if not rid:
                continue
            want = allowed(groups, gate, extra)
            in_room = rid in have
            if want and not in_room:
                force_join(mxid, alias, token)
                n_join += 1
            elif not want and in_room:
                kick(mxid, rid, token)
                n_kick += 1
    log.info(
        "cycle rooms=%s matrix=%s join=%s kick=%s kein_konto=%s",
        len(alias_to_id),
        n_matrix,
        n_join,
        n_kick,
        n_skip,
    )


def main() -> None:
    if not KC_SECRET or not BOT_PASS:
        raise SystemExit("KEYCLOAK_SYNC_CLIENT_SECRET und MATRIX_SYNC_PASSWORD setzen")
    log.info("start server=%s interval=%ss", SERVER, INTERVAL)
    token = None
    while True:
        try:
            if not token:
                token = mx_login()
            cycle(token)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            token = None
            if code == 429:
                log.warning("Synapse Login-Limit, 2 Minuten Pause")
                time.sleep(120)
                continue
            log.exception("cycle")
        except (requests.ConnectionError, requests.Timeout):
            token = None
            log.warning("Synapse noch nicht erreichbar, warte")
        except Exception:
            log.exception("cycle")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
