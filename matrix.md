# Matrix / Element

Host `chat.${DOMAIN}`. Matrix-IDs: `@name:chat.aeneas-solutions.de`. Federation aus. OIDC/Keycloak und Gruppenabgleich (`schulung:chat`) kommen danach, nicht in diesem Start.

## 0. DNS

A-Record `chat.aeneas-solutions.de` → Server-IPv4 (`46.225.123.251`). Check: `dig +short chat.aeneas-solutions.de`.

## 1. Config erzeugen (einmal)

```bash
cd ~/aeneas/aeneas_infra
mkdir -p matrix/data
chown -R 991:991 matrix/data
docker run --rm \
  -e SYNAPSE_SERVER_NAME=chat.aeneas-solutions.de \
  -e SYNAPSE_REPORT_STATS=no \
  -v "$(pwd)/matrix/data:/data" \
  matrixdotorg/synapse:v1.128.0 generate
```

UID 991 = Synapse im Image.

## 2. homeserver.yaml

In `matrix/data/homeserver.yaml` setzen bzw. ergänzen:

```yaml
public_baseurl: https://chat.aeneas-solutions.de/
serve_server_wellknown: true
enable_registration: false
allow_public_rooms_over_federation: false
federation_domain_whitelist: []
```

Listener bleibt HTTP `:8008` (TLS macht Traefik). Sqlite in `/data` reicht für die Demo.

## 3. Start

```bash
docker compose -f compose.yml -f compose.apps.yml -f compose.zammad.yml -f compose.matrix.yml up -d
```

Element: `https://chat.aeneas-solutions.de`

Ersten User (ohne offene Registration):

```bash
docker compose -f compose.yml -f compose.matrix.yml exec synapse \
  register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008
```

## Danach

Keycloak-OIDC oder MAS, Registration zu, Join nur mit `schulung:chat`. Learn (Frappe) erst wenn Chat steht.
