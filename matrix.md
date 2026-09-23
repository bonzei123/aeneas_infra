# Matrix / Element

Host `chat.<DOMAIN>`. Matrix-IDs: `@name:chat.<DOMAIN>`. Federation aus. Mitglieder nur über Keycloak-OIDC. Kein Auto-Join, keine offene Registration. 1:1-Anrufe: TURN (coturn), kein Jitsi.

Vorher in [SETUP.md](SETUP.md): Realm, Gruppen, Client `matrix` + `matrix-sync`, Mail. Hier nur der Matrix-Teil.

`element.json`: `default_server_config` auf `chat.<DOMAIN>` stellen.

---

## 0. DNS und Firewall

A-Record `chat.<DOMAIN>` → öffentliche IPv4 des Hosts.

Host-Firewall und Cloud-Firewall (Hetzner):

| Port | Wofür |
| --- | --- |
| `80`, `443` | Traefik |
| `3478/tcp` und `3478/udp` | TURN |
| `49160:49200/udp` | TURN-Relay |

Ohne Relay-UDP bleiben Anrufe hinter NAT oft schwarz.

---

## 1. Config erzeugen (einmal)

```bash
cd aeneas_infra
mkdir -p matrix/data
chown -R 991:991 matrix/data
docker run --rm \
  -e SYNAPSE_SERVER_NAME=chat.<DOMAIN> \
  -e SYNAPSE_REPORT_STATS=no \
  -v "$(pwd)/matrix/data:/data" \
  matrixdotorg/synapse:v1.128.0 generate
```

UID 991 = Synapse im Image. `homeserver.yaml` und Signing Keys liegen unter `matrix/data/` (nicht Git).

---

## 2. homeserver.yaml

Listener bleibt HTTP `:8008` (TLS macht Traefik). Sqlite in `/data` reicht für die Demo.

```yaml
public_baseurl: https://chat.<DOMAIN>/
serve_server_wellknown: true
enable_registration: false
allow_public_rooms_over_federation: false
federation_domain_whitelist: []
auto_join_rooms: []

oidc_providers:
  - idp_id: keycloak
    idp_name: "Aeneas"
    issuer: "https://id.<DOMAIN>/realms/aeneas"
    client_id: "matrix"
    client_secret: "<Secret aus Keycloak-Client matrix>"
    scopes: ["openid", "profile"]
    user_mapping_provider:
      config:
        localpart_template: "{{ user.preferred_username }}"
        display_name_template: "{{ user.name }}"
        email_template: "{{ user.email }}"

turn_uris:
  - "turn:chat.<DOMAIN>:3478?transport=udp"
  - "turn:chat.<DOMAIN>:3478?transport=tcp"
turn_shared_secret: "<derselbe Wert wie TURN_SHARED_SECRET>"
turn_user_lifetime: 86400000
turn_allow_guests: false
```

Keycloak-Client `matrix`: confidential, Redirect `https://chat.<DOMAIN>/_synapse/client/oidc/callback`, Group-Mapper wie die anderen Clients (Synapse braucht die Gruppen nicht im Token; der Worker liest Keycloak direkt).

E2EE für Mitglieder aus: in `matrix/element.json` `io.element.e2ee.force_disable` und `UIFeature.advancedEncryption: false`. Gruppen-Konferenz (viele im Raum) aus: `feature_group_calls: false` — das wäre Element Call / LiveKit, nicht dieser Weg.

---

## 3. TURN-Datei

`.env`: `TURN_SHARED_SECRET=` (lang, zufällig, z. B. `openssl rand -hex 32`).

```bash
# PUBLIC_IPV4 = IPv4 des Hosts, CHAT_HOST = chat.<DOMAIN>
sed \
  -e "s/__TURN_SHARED_SECRET__/${TURN_SHARED_SECRET}/" \
  -e "s/__PUBLIC_IPV4__/${PUBLIC_IPV4}/" \
  -e "s/__CHAT_HOST__/chat.<DOMAIN>/" \
  matrix/turnserver.conf.example > matrix/turnserver.conf
```

`matrix/turnserver.conf` nicht committen (steht in `.gitignore`). Secret in `homeserver.yaml` und `.env` identisch.

---

## 4. matrix-sync User (Synapse-Admin)

Ein lokales Synapse-Konto nur für den Worker, nicht für Mitglieder:

```bash
docker compose -f compose.yml -f compose.matrix.yml exec synapse \
  register_new_matrix_user -c /data/homeserver.yaml -a http://localhost:8008
```

Username `matrix-sync`, Passwort → `.env` `MATRIX_SYNC_PASSWORD`. Admin-Flag ja (`-a`).

Keycloak-Client `matrix-sync`: SETUP Abschnitt 6 (`manage-users`).

---

## 5. Räume

Spaces/Räume mit Alias (genau so in `matrix/groups.yml`):

`aeneas`, `allgemein`, `hilfe`, `vorstand`, `vorstands-chat`, `demo-verein`, `demo-chat`.

Worker joined/kickt. Gate: `mitgliedschaft:aktiv`. Ohne die Gruppe in `groups.yml` kein verwalteter Raum. Wer nie per SSO in Matrix war: Skip. Gruppe weg: Kick.

UI: `https://portal.<DOMAIN>/sync-admin/` nur mit `admin:matrix`. matrix-admin hängt nicht an Traefik. HTTP Basic nur intern Portal → Worker (`MATRIX_ADMIN_*` in `.env`).

---

## 6. Start

```bash
docker compose \
  -f compose.yml -f compose.tls.yml \
  -f compose.apps.yml -f compose.zammad.yml -f compose.matrix.yml \
  up -d --build
```

Element: `https://chat.<DOMAIN>` → Keycloak, kein Passwort-Formular für Mitglieder.

Nach Config-Änderungen: `synapse` und `element` neu starten, coturn wenn `turnserver.conf` neu ist.

---

## 7. Anrufe in Element

Sprache und Video sind derselbe WebRTC-Anruf (Kamera an/aus). Kein extra Login.

1. Nutzer öffnen (1:1, nicht den Vereinsraum).
2. Telefon-Symbol. Browser: Mikrofon/Kamera erlauben. Beide online.
3. Hard-Reload nach dem ersten TURN-Deploy (Strg+Umschalt+R).

Gruppen-Konferenz (viele im Raum gleichzeitig) ist nicht dieser Stack.
