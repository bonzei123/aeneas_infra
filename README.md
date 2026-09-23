# Aeneas Infra

Docker Compose, kein Kubernetes. **Weg zum laufenden Stack:** [SETUP.md](SETUP.md).

Nachbar-Repos auf derselben Ebene: `aeneas_portal`, `aeneas_cav`.

| Datei | Wann |
| --- | --- |
| [SETUP.md](SETUP.md) | Host → Keycloak → Gruppen → Portal → Zammad → Matrix |
| [MAIL.md](MAIL.md) | mailbox.org, SMTP/IMAP, Keycloak-Mail |
| [matrix.md](matrix.md) | Synapse, Element, Worker, TURN |
| [frappe.md](frappe.md) | LMS, noch nicht starten |
| [nextcloud.md](nextcloud.md) | Cloud nur Amt, noch nicht starten |

## Hosts

`DOMAIN` in `.env`. Produktion: A-Records. Traefik + Let’s Encrypt: Overlay `compose.tls.yml`.

| Host | Dienst | Overlay |
| --- | --- | --- |
| `id.<DOMAIN>` | Keycloak | `compose.yml` |
| `portal.<DOMAIN>`, `www.<DOMAIN>` | Portal | `compose.apps.yml` |
| `cav.<DOMAIN>` | CAV-Stub | `compose.apps.yml` |
| `help.<DOMAIN>` | Zammad | `compose.zammad.yml` |
| `chat.<DOMAIN>` | Synapse + Element | `compose.matrix.yml` |
| `learn.<DOMAIN>` | Frappe | `compose.frappe.yml` — [frappe.md](frappe.md) |
| `cloud.<DOMAIN>` | Nextcloud | `compose.nextcloud.yml` — [nextcloud.md](nextcloud.md) |
| `traefik.<DOMAIN>` | Dashboard | nicht öffentlich |

Keycloak auf `/` ist leer. Realm `aeneas`: `https://id.<DOMAIN>/admin/aeneas/console/`. Master: `https://id.<DOMAIN>/admin/`.

## Produktion

```bash
cp .env.example .env
# DOMAIN, ACME_EMAIL, Secrets, PUBLIC_SCHEME=https, KC_HOSTNAME, PORTAL_PUBLIC_URL

docker compose \
  -f compose.yml -f compose.tls.yml \
  -f compose.apps.yml -f compose.zammad.yml -f compose.matrix.yml \
  up -d --build
```

`--remove-orphans` nicht, wenn Dateien im Aufruf fehlen.

Postgres in `compose.yml`: Datenbanken `keycloak`, `portal`, `cav` (`postgres/init/01-databases.sql`). Zammad hat eine eigene Instanz.

Ausnahme: Port 80 schon durch Caddy belegt — `TRAEFIK_PORTS=127.0.0.1:8080:80`, ohne `compose.tls.yml`, TLS bleibt bei Caddy (`caddy/aeneas.caddy`).

## Nur lokal

`DOMAIN=aeneas.test`, kein `compose.tls.yml`. Docker Desktop, Traefik **v3.6+** (3.3 liest neuere Docker-APIs nicht → 404 auf allen Hosts). Hosts-Datei:

```
127.0.0.1 id.aeneas.test www.aeneas.test portal.aeneas.test cav.aeneas.test help.aeneas.test chat.aeneas.test traefik.aeneas.test
```

```bash
cp .env.example .env
docker compose up -d
```

Overlays in Git sind auf Demo-TLS (`websecure`) ausgelegt. Lokal zuerst den Kern, den Rest nach [SETUP.md](SETUP.md).
