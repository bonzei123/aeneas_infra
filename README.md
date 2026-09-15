# Aeneas Infra

Docker Compose für die Aeneas-Landschaft. Kein Kubernetes.

Schritt für Schritt (Produktion, lokale Extra-Schritte markiert): [SETUP.md](SETUP.md).

Erwartete Nachbarn auf der Platte (gleiche Ebene wie dieser Ordner):

- `aeneas_portal`
- `aeneas_cav`

Traefik ist nur der **Reverse-Proxy**: von außen ein Port 80, innen verteilt er nach dem Hostnamen (`id.…`, `www.…`, …) an Keycloak, Portal, CAV. Kein DNS-Anbieter, kein Zertifikat nötig, solange ihr HTTP lokal nutzt.

## Lokal ohne echte Domain

`DOMAIN=aeneas.test` in `.env` lassen. Docker Desktop muss laufen. In der **Hosts-Datei** (Windows: `C:\Windows\System32\drivers\etc\hosts`, als Admin):

```
127.0.0.1 id.aeneas.test www.aeneas.test cav.aeneas.test traefik.aeneas.test
```

Dann:

```bash
cd aeneas_infra
cp .env.example .env
docker compose up -d
```

Browser: `http://id.aeneas.test` (Keycloak), `http://traefik.aeneas.test` (Dashboard). Portal/CAV wie oben mit `compose.apps.yml`.

Port 80 muss frei sein. Wenn etwas anderes ihn blockiert, in `compose.yml` z. B. `"8080:80"` setzen und `http://id.aeneas.test:8080` aufrufen.

## Start (später mit richtiger Domain)

```bash
cp .env.example .env
# optional: Passwörter in .env ändern — ohne .env nutzt Compose lokale Defaults

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

Keycloak hat auf `/` keine Seite (404 ist normal). Admin-Konsole: `http://id.aeneas.test/admin/`

Lokal braucht Traefik **v3.6+**: neuere Docker Desktop spricht eine Docker-API, mit der Traefik 3.3 die Labels nicht mehr liest — dann ist alles 404.

Zammad, Moodle, Matrix, Nextcloud kommen später als weitere Compose-Dateien in diesem Repo — nicht als eigene GitHub-Repos. Offizielle Images, eigene `.env`.

## Postgres

Ein Server, mehrere Datenbanken (siehe `postgres/init/01-databases.sql`): `keycloak`, `portal`, `cav`.
