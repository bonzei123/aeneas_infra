# Aeneas Infra

Docker Compose für die Aeneas-Dienste. Kein Kubernetes.

Ablauf (Produktion; lokale Abweichungen in SETUP markiert): [SETUP.md](SETUP.md).

Benötigte Repositories auf derselben Verzeichnisebene:

- `aeneas_portal`
- `aeneas_cav`

Traefik ist der Reverse-Proxy: eingehend Port 80, intern Routing über `Host()`-Regeln (`id.…`, `www.…`, …) zu Keycloak, Portal, CAV. Lokal ohne TLS; öffentliches DNS und Zertifikate sind für Produktion vorgesehen, nicht für `*.aeneas.test`.

## Lokal ohne öffentliche Domain

`DOMAIN=aeneas.test` in `.env`. Docker Desktop muss laufen. Hosts-Datei (Windows: `C:\Windows\System32\drivers\etc\hosts`, Administrator):

```
127.0.0.1 id.aeneas.test www.aeneas.test cav.aeneas.test traefik.aeneas.test
```

```bash
cd aeneas_infra
cp .env.example .env
docker compose up -d
```

| URL | Dienst |
| --- | --- |
| `http://id.aeneas.test/admin/` | Keycloak Admin-Konsole |
| `http://traefik.aeneas.test` | Traefik-Dashboard |

Portal/CAV: Overlay `compose.apps.yml`.

Port 80 muss frei sein. Sonst in `compose.yml` z. B. `"8080:80"` und URLs mit `:8080`.

Lokal Traefik **v3.6+**: neuere Docker Desktop spricht eine Docker-API, mit der Traefik 3.3 die Container-Labels nicht liest — dann fehlen die Router, alle Hosts antworten 404.

## Start (Produktion, öffentliche Domain)

```bash
cp .env.example .env
# DOMAIN und Secrets in .env setzen; ohne .env interpoliert Compose die Defaults aus compose.yml

docker compose up -d
```

Dienste: Traefik, PostgreSQL, Redis, Keycloak.

Portal und CAV (Build der Nachbar-Repositories):

```bash
docker compose -f compose.yml -f compose.apps.yml up -d --build
```

Routing über DNS bzw. lokal `/etc/hosts`, abhängig von `DOMAIN` in `.env`:

| Host | Dienst |
| --- | --- |
| `id.DOMAIN` | Keycloak |
| `www.DOMAIN` | Portal (nur mit `compose.apps.yml`) |
| `cav.DOMAIN` | CAV-Kern (nur mit `compose.apps.yml`) |
| `traefik.DOMAIN` | Traefik-Dashboard |

Keycloak liefert auf `/` keinen Content. Admin-Konsole: `https://id.DOMAIN/admin/` (lokal HTTP: `http://id.aeneas.test/admin/`).

Zammad, Moodle, Matrix, Nextcloud: spätere Compose-Dateien in diesem Repository, keine eigenen GitHub-Repos. Offizielle Images, eigene `.env`.

## Postgres

Eine Instanz, getrennte Datenbanken (siehe `postgres/init/01-databases.sql`): `keycloak`, `portal`, `cav`.
