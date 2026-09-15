# Aeneas Infra

Docker Compose für die Aeneas-Landschaft. Kein Kubernetes.

Erwartete Nachbarn auf der Platte (gleiche Ebene wie dieser Ordner):

- `aeneas_portal`
- `aeneas_cav`

## Start (Linux-Server oder Docker Desktop)

```bash
cp .env.example .env
# DOMAIN und Passwörter in .env setzen

docker compose up -d
```

Damit laufen Traefik, PostgreSQL, Redis und Keycloak.

Portal und CAV (baut die Geschwister-Repos):

```bash
docker compose -f compose.yml -f compose.apps.yml up -d --build
```

Hosts in `/etc/hosts` oder DNS, je nach `DOMAIN` in `.env`:

| Host | Dienst |
| --- | --- |
| `id.DOMAIN` | Keycloak |
| `www.DOMAIN` | Portal (nur mit compose.apps.yml) |
| `cav.DOMAIN` | CAV-Kern (nur mit compose.apps.yml) |
| `traefik.DOMAIN` | Traefik-Dashboard |

Keycloak-Admin: `KC_BOOTSTRAP_ADMIN_USERNAME` / `KC_BOOTSTRAP_ADMIN_PASSWORD` aus `.env`.

Zammad, Moodle, Matrix, Nextcloud kommen später als weitere Compose-Dateien in diesem Repo — nicht als eigene GitHub-Repos. Offizielle Images, eigene `.env`.

## Postgres

Ein Server, mehrere Datenbanken (siehe `postgres/init/01-databases.sql`): `keycloak`, `portal`, `cav`.
