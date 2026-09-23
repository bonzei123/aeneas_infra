# Setup

Weg von einem leeren Linux-Host zum laufenden Stack. Dieselbe Reihenfolge gilt für eine neue Domain. Nachträgliche Änderungen gehören in diese Datei (bzw. `matrix.md` / `MAIL.md`), nicht in Einmal-Skripte.

Abschnitte **Nur lokal** überspringst du in Produktion.

Planung (warum, nicht Klickweg): `aeneas` → `docs/`. Mail: [MAIL.md](MAIL.md). Matrix-Details: [matrix.md](matrix.md). Portal-Code: `aeneas_portal/README.md`.

---

## Endziel (was „fertig“ hier heißt)

Ein Keycloak-Konto im Realm `aeneas`. Das Portal ist der Einstieg. Aufnahme ohne Login: Formular → internes Zammad-Ticket → Amt setzt Verein + „Konto anlegen“ + Tag `freigabe` → Portal legt den Keycloak-User an und schickt die Passwort-Mail. Chat nur nach Gruppenabgleich, niemand ohne Gruppe in einem verwalteten Raum. 1:1-Anrufe in Element über TURN, kein extra Jitsi-Login. Zammad-Agentenrechte kommen aus Keycloak-Gruppen, nicht per Hand in der Zammad-UI.

Noch nicht in diesem Weg: Frappe Learning, Nextcloud, CAV-Fachlogik. Overlays liegen bereit, Start nur mit deren `.md`.

```
Linux + DNS
  → Traefik + Postgres + Keycloak
  → Gruppen + Operator-User + Mail
  → OIDC-Clients
  → Portal
  → Zammad (Queues, OIDC, Aufnahme-Webhook)
  → Matrix (OIDC, Worker, TURN)
```

Produktion, alle laufenden Overlays:

```bash
cd aeneas_infra
docker compose \
  -f compose.yml -f compose.tls.yml \
  -f compose.apps.yml -f compose.zammad.yml -f compose.matrix.yml \
  up -d --build
```

`--remove-orphans` nicht verwenden, wenn Dateien in dem Aufruf fehlen — sonst stoppt Compose die weggelassenen Container.

---

## Begriffe

| Begriff | Bedeutung |
| --- | --- |
| Traefik | Reverse-Proxy. Routet HTTP anhand des Host-Headers. TLS: Overlay `compose.tls.yml`. |
| Realm | Isolierte Identity-Domain. `master` = Admin. `aeneas` = Benutzer, Gruppen, Clients. |
| Client | OIDC-App (portal, zammad, matrix, matrix-sync). |
| Gruppe | Keycloak-Gruppe im Token-Claim `groups`. Führendes Verzeichnis, nicht Zammad/Matrix. |

Keycloak auf `/` ist leer.

- Realm **master**: `https://id.<DOMAIN>/admin/`
- Realm **aeneas**: `https://id.<DOMAIN>/admin/aeneas/console/`

`/admin/` ohne Realm ist die Master-Konsole. Gruppen aus `aeneas` gelten dort nicht.

**Nur lokal:** `http://id.aeneas.test/admin/`

---

## 0. Server, Domain, `.env`

### Produktion

1. Debian/Ubuntu LTS, Docker Compose, Firewall. Repos `aeneas_infra`, `aeneas_portal`, `aeneas_cav` nebeneinander.
2. A-Records (kein `/etc/hosts`):

   | Host | Dienst |
   | --- | --- |
   | `id.<DOMAIN>` | Keycloak |
   | `portal.<DOMAIN>` und `www.<DOMAIN>` | Portal |
   | `cav.<DOMAIN>` | CAV (Stub) |
   | `help.<DOMAIN>` | Zammad |
   | `chat.<DOMAIN>` | Synapse + Element |
   | `learn.<DOMAIN>` | Frappe, erst mit [frappe.md](frappe.md) |
   | `cloud.<DOMAIN>` | Nextcloud, erst mit [nextcloud.md](nextcloud.md) |
   | `traefik.<DOMAIN>` | Dashboard — nicht öffentlich |

3. `.env` aus `.env.example`. `DOMAIN`, `ACME_EMAIL`, `PUBLIC_SCHEME=https`, `KC_HOSTNAME=https://id.<DOMAIN>`, `PORTAL_PUBLIC_URL=https://portal.<DOMAIN>`. Alle Passwörter neu. `.env` nicht committen.
4. Traefik auf **80 und 443**, Let’s Encrypt HTTP-01: Overlay `compose.tls.yml`. `TRAEFIK_PORTS` nicht setzen.
5. Host-Firewall und ggf. Cloud-Firewall (Hetzner): `22`, `80`, `443`. TURN später in [matrix.md](matrix.md) (`3478`, UDP-Relay).
6. Hetzner sperrt SMTP **25**. Keycloak/Zammad senden über mailbox.org **465/587**, siehe [MAIL.md](MAIL.md).
7. Hinter einem **bestehenden** Caddy (Port 80 schon belegt) statt Traefik-TLS: `TRAEFIK_PORTS=127.0.0.1:8080:80`, ohne `compose.tls.yml`, Caddy terminiert TLS. Das ist die Ausnahme, nicht der Normalweg.

```bash
docker compose -f compose.yml -f compose.tls.yml up -d
```

Warten, bis Postgres healthy ist und Keycloak lauscht (erster Start etwa eine Minute).

### Nur lokal

- Docker Desktop. Traefik **v3.6+**.
- `DOMAIN=aeneas.test`, `PUBLIC_SCHEME=http`, `KC_HOSTNAME=http://id.aeneas.test`. Kein `compose.tls.yml`.
- Hosts-Datei: `id`, `www`, `portal`, `cav`, `help`, `chat`, `traefik` → `127.0.0.1`.
- Overlays in Git erwarten `websecure` (Produktion). Lokal den Kern ohne Apps/Zammad/Matrix testen, oder Hosts + öffentliche Domain nutzen.

---

## 1. Master-Admin

`KC_BOOTSTRAP_ADMIN_*` ist nur der erste Start. Danach einen dauerhaften Admin im Realm `master` anlegen. Den letzten Master-Admin nicht löschen.

1. `https://id.<DOMAIN>/admin/`
2. Login Bootstrap.
3. Im Realm `master` dauerhaften Admin anlegen, Passwortmanager.
4. Bootstrap nicht als Betriebskonto.

**Nur lokal:** `admin` / `changeme-keycloak`, solange `.env` die Defaults hat.

---

## 2. Realm `aeneas`

Oben links steht der aktuelle Realm. `master` ist falsch für User, Gruppen, Clients.

1. **Create realm**, Name `aeneas`, Enabled, Create.
2. **Realm settings → Login:** User registration aus.
3. **Localization:** Default `de`.
4. SMTP (Abschnitt 5) bevor Forgot-Password oder `UPDATE_PASSWORD`-Mails.

---

## 3. Gruppen

**Groups → Create group.** Namen lowercase, exakt. Kein Kreuzprodukt `Verein × Rolle`.

Vier Fach-Achsen (Planung `docs/sso-matrix.md`) plus Technik:

| Gruppe | Achse | Wirkung |
| --- | --- | --- |
| `mitgliedschaft:pending` | Status | geplant für Antrag; Aufnahme-Hook legt aktuell `aktiv` an |
| `mitgliedschaft:aktiv` | Status | Mitglied; Matrix-Gate in `groups.yml` |
| `mitgliedschaft:beendet` | Status | ex-Mitglied |
| `rolle:vorstand` | Amt | Vorstand; Matrix Vorstandsräume |
| `rolle:ap` | Amt | Ansprechpartner |
| `rolle:praevb` | Amt | Prävention |
| `rolle:ausgabe` | Dienst | Abgabe |
| `rolle:anbau` | Dienst | Anbau |
| `backoffice` | Dienst | Gesamtverein; Portal-Kachel Cloud später |
| `verein:<slug>` | Tenant | ein Verein; Starter: `demo`, `wanne-eickel`, `worms` |
| `schulung:onboarding` | Nachweis | später CAV |
| `schulung:praevention` | Nachweis | später CAV |
| `schulung:chat` | Nachweis | Matrix-Räume `aeneas` / `allgemein` / `hilfe` |
| `schulung:ausgabe` | Nachweis | zusätzlich zu `rolle:ausgabe` |
| `admin:keycloak` | Technik | Admin-Konsole Realm `aeneas` (Rollen am Gruppe, unten) |
| `admin:matrix` | Technik | Portal `/sync-admin/` (Chat-Räume) |
| `admin:zammad` | Technik | Zammad Agent + Queue Users |
| `zammad:support` | Technik | Zammad Agent + Queue Support |
| `zammad:hr` | Technik | Zammad Agent + Queue HR |
| `zammad:admin` | Technik | Zammad Admin + Agent + alle drei Queues |

`verein:*` später aus dem CAV, nicht 180-mal per Hand.

### Rechte an die Gruppe hängen (nicht an einzelne User)

**`admin:keycloak`:** Groups → `admin:keycloak` → **Role mapping** → Assign role → Filter **clients** → Client `realm-management`:

`view-users`, `query-users`, `manage-users`, `query-groups`, `view-realm`, `view-clients`, `query-clients`, `query-realms`, `view-identity-providers`

Ohne `view-clients` / `query-clients` bleibt die Konsole leer, auch wenn der User in der Gruppe ist. URL: `/admin/aeneas/console/`.

**Zammad:** kein Mapping in der Keycloak-UI. Overlay `zammad/initializers/aeneas_oidc_agent.rb` liest `groups` beim OIDC-Login und setzt Rollen/Queues. Queues müssen in Zammad existieren (Abschnitt 8).

**Matrix:** `matrix/groups.yml` + Worker. UI nur `admin:matrix`.

**Portal-Kacheln:** Cloud bei `backoffice` oder `rolle:*`. Chat-Räume bei `admin:matrix`.

---

## 4. Erster Operator im Realm `aeneas`

Nicht in `master`.

1. Users → Create: Username, E-Mail, Create.
2. Credentials: Passwort; Temporary aus, wenn kein Zwangswechsel.
3. Groups mindestens: `mitgliedschaft:aktiv`, eine `verein:*`, `schulung:chat` (Chat testen), plus die `admin:*` / `zammad:*`, die der Operator braucht.

**Nur lokal:** User `anna`, Email verified, `mitgliedschaft:aktiv` + `verein:demo`.

---

## 5. Mail

Ohne SMTP keine Passwort-Mails (Aufnahme) und kein Forgot-Password. [MAIL.md](MAIL.md) bis Keycloak **Test connection** grün. Forgot password erst danach an.

`execute-actions-email` nur mit Action-Liste (`UPDATE_PASSWORD`). `client_id` + `redirect_uri` an den Keycloak-26-Admin-Endpunkt nicht mitsenden (Internal Server Error).

---

## 6. OIDC-Clients (Realm `aeneas`)

Überall denselben **Group Membership**-Mapper: Claim `groups`, Full group path **aus**, ID-Token + Access-Token + Userinfo an.

### `portal` — confidential

Client authentication **On**, Standard flow, PKCE **S256**.

| Feld | Produktion |
| --- | --- |
| Valid redirect URIs | `https://portal.<DOMAIN>/auth/callback` und `https://www.<DOMAIN>/auth/callback` |
| Valid post logout redirect URIs | `https://portal.<DOMAIN>/*` |
| Web origins | `+` |

Secret → `.env` `PORTAL_OIDC_CLIENT_SECRET`. `PORTAL_PUBLIC_URL` muss zur Login-URL passen (Demo: `https://portal.<DOMAIN>`).

### `zammad` — public

Client authentication **Off**, Standard flow, PKCE **S256**.

| Feld | Produktion |
| --- | --- |
| Valid redirect URIs | `https://help.<DOMAIN>/auth/openid_connect/callback` |
| Valid post logout redirect URIs | `https://help.<DOMAIN>/*` |
| Backchannel logout | `https://help.<DOMAIN>/auth/openid_connect/backchannel_logout` |

### `matrix` — confidential

Synapse-OIDC. Redirect: `https://chat.<DOMAIN>/_synapse/client/oidc/callback`. Secret in `homeserver.yaml` (nicht Git). Siehe [matrix.md](matrix.md).

### `matrix-sync` — confidential, Service account

Service accounts **On**. Service-Account-Rollen (`realm-management`): `view-users`, `query-groups`, `view-realm`, **`manage-users`**.

Derselbe Client legt nach Zammad-Freigabe Keycloak-User an. Ohne `manage-users` schlägt Aufnahme-Hook und Sync-UI fehl.

Secret → `.env` `KEYCLOAK_SYNC_CLIENT_SECRET`.

---

## 7. Portal

```bash
docker compose -f compose.yml -f compose.tls.yml -f compose.apps.yml up -d --build
```

Browser: `https://portal.<DOMAIN>` → Anmelden → User aus Realm `aeneas`. Gruppen müssen auf der Startseite stehen.

Token-Exchange intern `http://keycloak:8080`, Browser nur `id.<DOMAIN>`.

Nach Änderungen an `requirements.txt` (z. B. `python-multipart` für `POST /aufnahme`) Image neu bauen, nicht nur Container neu starten.

Aufnahme-Env (Abschnitt 8 füllt die Werte): `ZAMMAD_API_TOKEN`, `ZAMMAD_WEBHOOK_TOKEN`, `ZAMMAD_TICKET_GROUP`, `ZAMMAD_TICKET_CUSTOMER`, plus `KEYCLOAK_SYNC_CLIENT_*`.

---

## 8. Zammad

Eigenes Overlay, eigene Postgres-Instanz. Rolle `zammad` ≠ Superuser; Infra-`POSTGRES_USER` nicht verwenden.

```bash
docker compose -f compose.yml -f compose.tls.yml -f compose.apps.yml -f compose.zammad.yml up -d
```

Erststart mehrere Minuten. Dann `https://help.<DOMAIN>` — Setup-Wizard, **lokaler Insel-Admin** (nicht Keycloak).

### OIDC in Zammad

**Admin → Settings → Security → Third-party Applications → OpenID Connect**

| Feld | Produktion |
| --- | --- |
| Display name | Keycloak |
| Identifier | `zammad` |
| Issuer | `https://id.<DOMAIN>/realms/aeneas` |

`KC_HOSTNAME` = dieselbe URL. Automatic account link: yes. Password Login / User creation aus; Mitglieder nur OpenID. Insel-Admin: Link „Request the password login here“.

**Nur lokal:** Issuer `http://id.aeneas.test/realms/aeneas`. Initializer `swd_http_oidc.rb` nur bei `ZAMMAD_HTTP_TYPE=http`.

### Queues

In Zammad anlegen (UI): **Users** (Default), **Support**, **HR**. Der OIDC-Initializer mappt darauf. Ohne Queue kein Agent-Zugriff auf die Tickets.

### Funktionsuser Helpdesk

Ticket-API nicht mit dem persönlichen Konto. User **Helpdesk** (Mail z. B. `help@<DOMAIN>`), Rolle Agent, Queue Users voll. API-Token **portal-tickets** mit `ticket.agent` (Token-`preferences.permission` darf nicht leer sein). Token → `.env` `ZAMMAD_API_TOKEN`. `ZAMMAD_TICKET_CUSTOMER` = dieselbe Helpdesk-Mail (sonst bekommt der Antragsteller Auto-Mails; Ersteller des Tickets wäre sonst der Token-Besitzer).

Portal neu starten, nachdem `.env` steht.

### Ticket-Felder (Aufnahme)

**Admin → Objects → Ticket:**

| Name (intern) | Typ | Werte |
| --- | --- | --- |
| `aufnahme_verein` | Select | `demo`, `wanne-eickel`, `worms` (gleiche Slugs wie Keycloak `verein:*`) |
| `aufnahme_ok` | Boolean | Anzeige z. B. „Konto anlegen?“ |

Ohne beide Felder setzt der Hook nur eine interne Notiz, keinen User.

### Webhook + Trigger + Makro

Zammad hat keinen Ja/Nein-Dialog auf Makros. Speichern = **Aktualisieren**.

1. Webhook: POST `http://portal:8000/hooks/zammad-aufnahme?token=<ZAMMAD_WEBHOOK_TOKEN>` (Docker-DNS `portal`, Token lang und zufällig, derselbe Wert in `.env`).
2. Trigger „Aufnahme Freigabe → Portal“:
   - Activator: Action (Ticket-Update)
   - **Execution: always**, nicht selective — sonst ignoriert Zammad den Tag, den nur das Makro setzt
   - Bedingung: Tags enthalten `freigabe`
   - Aktion: Webhook
3. Makro „Aufnahme freigeben“: Tag `freigabe` setzen.

Amt: Verein wählen, „Konto anlegen“ an, Makro oder Tag, dann **Aktualisieren**. Titel muss `Aufnahme:` enthalten (so legt das Portal das Ticket an).

Fehler: interne Notiz im Ticket („Kein Keycloak-User…“). Logs: `docker compose logs portal`.

---

## 9. Matrix

OIDC von Anfang an, keine offene Registration, kein Auto-Join. Mitglieder kommen nur über Keycloak + Worker in Räume. 1:1 Sprache/Video = TURN (coturn), nicht Jitsi.

Kompletter Klick- und Dateiweg: [matrix.md](matrix.md).

Kurz: `generate` → `homeserver.yaml` (OIDC, `turn_uris`, Federation aus) → Client `matrix` + User `matrix-sync` → Aliase der Default-Räume → `groups.yml` → Compose inkl. coturn → Firewall TURN → Element hart neu laden.

---

## 10. Check

- [ ] `https://id.<DOMAIN>/admin/aeneas/console/` mit User in `admin:keycloak`
- [ ] Portal-Login, Gruppen sichtbar
- [ ] `/aufnahme` erzeugt Ticket als Helpdesk in Queue Users
- [ ] Freigabe mit Verein + Haken + Aktualisieren → Keycloak-User + Passwort-Mail
- [ ] Zammad-Login: `zammad:admin` sieht Admin + Queues, ohne Gruppe nur Kunde
- [ ] Element-Login per Keycloak, Räume erst mit `mitgliedschaft:aktiv` (+ Mapping in `groups.yml`)
- [ ] 1:1-Anruf: Telefon-Symbol, kein zweites Login
- [ ] Keine Secrets in Git

Als Nächstes: [frappe.md](frappe.md), [nextcloud.md](nextcloud.md), CAV-Fachkern.

---

## Reset

Bootstrap-Admin nur bei leerer Keycloak-Datenbank. Container-Restart reicht nicht.

**Produktion:** Keycloak-DB nicht droppen. Backup, zweiten Master-Admin, oder Admin-CLI. `docker compose down -v` löscht Volumes.

**Nur lokal:**

```bash
cd aeneas_infra
docker compose stop keycloak
docker compose exec -T postgres psql -U aeneas -d postgres -c "DROP DATABASE IF EXISTS keycloak;"
docker compose exec -T postgres psql -U aeneas -d postgres -c "CREATE DATABASE keycloak;"
docker compose start keycloak
```

Logzeile `Created temporary admin user` → `/admin/` → dauerhaften Master-Admin.

Alles lokal: `docker compose down -v`, dann `up -d`.
