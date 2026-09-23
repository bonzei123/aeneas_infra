# Matrix / Element — Overlay, noch nicht starten

Host: `chat.${DOMAIN}`. Federation aus. Join nur mit `mitgliedschaft:aktiv` **und** `schulung:chat` — das macht später der Gruppenabgleich, nicht Synapse von allein.

OIDC gegen Keycloak (Client `matrix` oder MAS) ist **nicht** in dieser Datei verdrahtet.

## Dateien

- `compose.matrix.yml`
- `matrix/element.json` — Homeserver-URL, beim Start `DOMAIN` anpassen

## Bevor `up`

1. A-Record `chat.${DOMAIN}`.
2. Synapse-Config erzeugen (einmal, legt Signing-Keys an):

```bash
mkdir -p matrix/data
docker run --rm -e SYNAPSE_SERVER_NAME=chat.aeneas-solutions.de \
  -e SYNAPSE_REPORT_STATS=no \
  -v "$(pwd)/matrix/data:/data" \
  matrixdotorg/synapse:v1.128.0 generate
```

3. In `homeserver.yaml`: `public_baseurl`, Listener 8008, Federation `false` / `allow_public_rooms_over_federation: false`.
4. Postgres: eigene DB `synapse` (nicht den Infra-Cluster zwingen — Overlay hat sqlite nur zum ersten Test; Produktion = Postgres).
5. Demo mit Let’s Encrypt: an den Traefik-Routern

```
- traefik.http.routers.element.entrypoints=websecure
- traefik.http.routers.element.tls.certresolver=le
```

dasselbe für `synapse` (Client-API `chat.${DOMAIN}`).

## Start (später)

```bash
docker compose -f compose.yml -f compose.matrix.yml up -d
```

Element: `https://chat.${DOMAIN}`. Synapse well-known später, sonst Handy-Clients raten falsch.

## Danach

- Keycloak-Client, OIDC oder MAS
- Gruppenabgleich (kleiner Worker, eigenes Code, kein fünftes Repo)
- Kein öffentliches Raumverzeichnis
