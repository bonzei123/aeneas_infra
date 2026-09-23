# Setup

Ziel: produktives Deployment (Linux, öffentliche Domain, TLS, produktive Secrets). Dieselben Keycloak-Schritte gelten lokal und in Produktion.

Abschnitte und Zeilen mit **Nur lokal** gelten ausschließlich für die lokale Entwicklungsumgebung. In Produktion überspringen.

---

## Begriffe

| Begriff | Bedeutung |
| --- | --- |
| Traefik | Reverse-Proxy. Routet HTTP anhand des Host-Headers (`Host()`-Regeln) an den jeweiligen Container. |
| Realm | Isolierte Identity-Domain in Keycloak. `master` = Admin-Realm. `aeneas` = Anwendungs-Realm (Benutzer, Gruppen, OIDC-Clients). |
| Client | OIDC-/OAuth2-Client (Portal, CAV, …). |
| Gruppe | Keycloak-Gruppe; Abbildungen in Token bzw. Userinfo (`mitgliedschaft:aktiv`, `verein:…:vorstand`). |

Keycloak liefert auf `/` keinen Content. Admin-Konsole: `https://id.<DOMAIN>/admin/`

**Nur lokal:** `http://id.aeneas.test/admin/` (HTTP, Name über Hosts-Datei).

---

## 0. Server und Domain

### Produktion

1. Linux-Host (Debian oder Ubuntu LTS), Docker Compose, Firewall.
2. Öffentliche Domain. DNS-Records **A/AAAA** (kein `/etc/hosts`):

   | Host | Dienst |
   | --- | --- |
   | `id.<DOMAIN>` | Keycloak |
   | `www.<DOMAIN>` | Portal |
   | `cav.<DOMAIN>` | CAV-Kern |
   | `help.<DOMAIN>` | Zammad |
   | `traefik.<DOMAIN>` | Traefik-Dashboard — nicht öffentlich, intern oder VPN |

3. In `aeneas_infra`: `.env` aus `.env.example`. `DOMAIN` auf die öffentliche Domain setzen. Alle Passwörter durch produktive Secrets ersetzen; `.env` nicht committen.
4. **Bestehendes Caddy (z. B. Stoat) bleibt auf 80/443.** Traefik nicht auf 80 binden:

   ```
   TRAEFIK_PORTS=127.0.0.1:8080:80
   PUBLIC_SCHEME=https
   KC_HOSTNAME=https://id.<DOMAIN>
   PORTAL_PUBLIC_URL=https://www.<DOMAIN>
   ```

   Caddy-Site-Blöcke auf dem Host (TLS bleibt bei Caddy). Traefik nur intern HTTP, Host-Header durchreichen.
5. `docker compose up -d`. Warten, bis der Postgres-Healthcheck erfolgreich ist und Keycloak lauscht (erster Start ca. 1 Minute).

### Nur lokal

Entwicklung ohne öffentliches DNS und ohne Zertifikat:

- Docker Desktop. Traefik **v3.6+** (Docker Engine neuerer Desktop-Versionen: Traefik 3.3 kann die Docker-API nicht lesen, Router aus Labels fehlen, alle Hosts antworten 404).
- `DOMAIN=aeneas.test` in `.env`. Default-Passwörter aus `.env.example` nur lokal.
- Windows-Hosts-Datei (Administrator) `C:\Windows\System32\drivers\etc\hosts`:

  ```
  127.0.0.1 id.aeneas.test www.aeneas.test cav.aeneas.test help.aeneas.test traefik.aeneas.test
  ```

- Port 80 muss frei sein, **außer** ein anderer Proxy (Caddy) bleibt davor — dann `TRAEFIK_PORTS=127.0.0.1:8080:80`.
- Start: `cp .env.example .env` und `docker compose up -d`.

---

## 1. Master-Admin

`KC_BOOTSTRAP_ADMIN_*` erzeugt nur einen temporären Bootstrap-User. Unmittelbar danach einen dauerhaften Admin im Realm `master` anlegen. Den letzten Master-Admin nicht löschen.

1. Admin-Konsole (`/admin/`).
2. Login mit Bootstrap-Credentials.
3. Im Realm `master` einen dauerhaften Admin anlegen; Credentials im Passwortmanager ablegen.
4. Bootstrap-User nicht als Betriebs-Konto verwenden.

**Nur lokal:** `admin` / `changeme-keycloak`, solange `.env` die Defaults enthält.

---

## 2. Realm `aeneas`

Der aktuelle Realm steht oben links. `master` ist der Admin-Realm. Endbenutzer und Anwendungs-Clients gehören nicht dorthin.

1. Realm-Auswahl oben links → aktuell `master`.
2. **Create realm**.
3. **Realm name:** `aeneas` (lowercase, ohne Leerzeichen; Realm-ID lokal und in Produktion identisch).
4. **Enabled**.
5. **Create**.

Die Realm-Auswahl muss **aeneas** zeigen. Steht dort `master`, sind nachfolgende User/Gruppen/Clients im Admin-Realm.

### Realm-Einstellungen

**Realm settings**:

- **General:** Display name (Organisationsname).
- **Login:** User registration aus (kein Self-Registration).
- **Localization:** Default locale `de`. Internationalization an, Locale `de`.

**Produktion:** SMTP konfigurieren (Password-Reset, E-Mail-Verifikation). Forgot password erst aktivieren, wenn SMTP zustellt. MFA für Admins, Vorstände, Zammad-Agenten.

**Nur lokal:** Forgot password aus. Ohne SMTP bei Test-Usern **Email verified** setzen, sonst bleibt die Verifikation ausstehend.

Login-Theme später; Planung `ci-cd.md`.

---

## 3. Gruppen

**Groups** → **Create group**. Führendes Verzeichnis ist Keycloak, nicht Nextcloud oder Matrix. Namen lowercase, exakt.

Vier Achsen, kein Kreuzprodukt `Verein × Rolle`:

| Gruppe | Achse | Verwendung |
| --- | --- | --- |
| `mitgliedschaft:pending` | Status | Antrag, Login ohne Abgabe |
| `mitgliedschaft:aktiv` | Status | beitragsfähiges Mitglied |
| `mitgliedschaft:beendet` | Status | ex-Mitglied, Belege/Tickets |
| `rolle:vorstand` | Funktion | Vorstand |
| `rolle:ap` | Funktion | Ansprechpartner |
| `rolle:praevb` | Funktion | Präventionsbeauftragte |
| `rolle:ausgabe` | Funktion | Ausgabe (CAV-Abgabe) |
| `rolle:anbau` | Funktion | Anbauteam |
| `backoffice` | Funktion | Gesamtverein-Mitarbeiter (Nextcloud-Client später auf diese Gruppe beschränkt) |
| `verein:<slug>` | Organisation | ein Zweigverein = ein Tenant; nicht `:mitglied`/`:vorstand` anhängen |
| `schulung:onboarding` | Nachweis | CAV nach LMS-Abschluss, nicht per Hand |
| `schulung:praevention` | Nachweis | Prävention / Jahreskurs |
| `schulung:chat` | Nachweis | Voraussetzung Matrix |
| `schulung:ausgabe` | Nachweis | zusätzlich zu `rolle:ausgabe` |

Bei 180 Zweigvereinen: 180 `verein:*` plus Status-, Funktions- und Schulungsset, nicht 180×Rollen. `verein:*` später aus dem CAV-Mandantenstamm, nicht alle per Hand. `schulung:*` nur der CAV nach Kursabschluss. Schema: Planung `docs/sso-matrix.md` und `docs/schulungen.md`.

**Nur lokal:** eine Testgruppe `verein:demo`. Bereits angelegte `verein:demo:mitglied` / `verein:demo:vorstand` bzw. `amt:*` durch `verein:demo` plus `rolle:*` ersetzen.

---

## 4. Erster User im Realm `aeneas`

Nicht im Realm `master`. Realm-Auswahl: **aeneas**.

1. **Users** → **Create new user**.
2. Username und E-Mail.
3. **Create**.
4. **Credentials:** Passwort setzen; **Temporary** aus, wenn kein Zwangswechsel beim ersten Login gewünscht ist.
5. **Groups:** genau eine `mitgliedschaft:*` (`pending` / `aktiv` / `beendet`) plus genau eine `verein:<slug>`-Gruppe. Vorstand zusätzlich `rolle:vorstand`.

Das Konto ist ein Realm-User, kein Master-Admin. Realm-Verwaltung bleibt beim Master-Admin.

**Nur lokal:** z. B. User `anna`, **Email verified**, Gruppen `mitgliedschaft:aktiv` und `verein:demo`.

---

## 5. Portal-OIDC

Voraussetzung: Client `portal` im Realm `aeneas`, Redirect `http://www.<DOMAIN>/auth/callback`, Group-Membership-Mapper Claim `groups` (Full group path aus). Secret in `.env` als `PORTAL_OIDC_CLIENT_SECRET`.

```bash
docker compose -f compose.yml -f compose.apps.yml up -d --build
```

Browser: `http://www.aeneas.test` → **Anmelden** → User aus Realm `aeneas` (nicht Master-Admin). Nach Login müssen die Keycloak-Gruppen unter der Einstiegsseite stehen.

Token-Exchange geht intern an `http://keycloak:8080`, der Browser nur an `id.<DOMAIN>`.

## 6. Zammad

Eigenes Overlay, offizielle Images. Eigenes Postgres (Rolle `zammad` ≠ Superuser); nicht die Infra-Variable `POSTGRES_USER`.

**Nur lokal:** `help.aeneas.test` in die Hosts-Datei (siehe Abschnitt 0). Elasticsearch braucht `vm.max_map_count=262144` (Docker Desktop: in der Linux-VM / WSL).

```bash
docker compose -f compose.yml -f compose.zammad.yml up -d
```

Erststart dauert mehrere Minuten (Images, `zammad-init`, Rails-Healthcheck). Danach `http://help.aeneas.test` — Setup-Wizard, **lokaler Zammad-Admin** (nicht der Keycloak-Master-Admin).

OIDC nach dem Wizard. Zammad holt die Discovery-URL vom Issuer; der Rails-Container löst `id.<DOMAIN>` über `extra_hosts`/`host-gateway` auf.

Offizielle Zammad-Doku verlangt HTTPS zwischen Zammad und dem OP. **Nur lokal:** HTTP testen. Produktion nur mit TLS.

### Keycloak-Client `zammad` (Realm `aeneas`)

1. **Clients** → **Create client**, OpenID Connect, Client ID `zammad`.
2. **Client authentication:** Off (public Client).
3. Nur **Standard flow**.
4. Login settings:

| Feld | Wert (lokal) |
| --- | --- |
| Valid redirect URIs | `http://help.aeneas.test/auth/openid_connect/callback` |
| Valid post logout redirect URIs | `http://help.aeneas.test/*` |
| Web origins | `+` |

5. **Advanced:** PKCE code challenge method **S256**.
6. Dedicated Mapper **Group Membership**, Claim `groups`, Full group path aus; ID token, access token, userinfo an. Introspection aus.
7. Backchannel-Logout lokal weglassen (Keycloak erreicht `help.aeneas.test` sonst nicht). Produktion: `https://help.<DOMAIN>/auth/openid_connect/backchannel_logout`.

### Zammad (als Zammad-Admin)

**Admin → Settings → Security → Third-party Applications → Authentication via OpenID Connect**

| Feld | Wert (lokal) |
| --- | --- |
| Display name | Keycloak |
| Identifier | `zammad` |
| Issuer | `http://id.aeneas.test/realms/aeneas` |

`KC_HOSTNAME` muss dieselbe Schema-URL sein (`http://id.aeneas.test`). Ohne `http://` liefert die Discovery `https://…:443` — lokal Connection refused.

Zammad selbst defaultet OIDC-Discovery trotzdem auf HTTPS (`SWD.url_builder = URI::HTTPS`). Overlay mountet `zammad/initializers/swd_http_oidc.rb`, solange `ZAMMAD_HTTP_TYPE=http`. Ohne den Initializer: `Connection refused … port 443` nach dem OIDC-Klick.

Speichern. **Automatic account link on initial logon:** yes (sonst zweites Konto neben dem Zammad-Admin).

Mitglieder-Login: **Settings → Security → Base** — Password Login aus, Lost Password aus, User creation / „Als neuer Kunde registrieren“ aus. Dann nur noch der OpenID-Button. Zammad hat **keinen** Auto-Redirect auf OIDC (POST/CSRF). Nach Portal-SSO ist Keycloak schon eingeloggt — ein Klick auf den Button, kein Passwort.

Zammad-Admin (Inselkonto): Password Login aus blendet das Formular. Auf der Login-Seite Link **Request the password login here** / Einmal-Login als Admin. Nicht denselben User wie Keycloak `anna` verwenden.

Test mit `anna` (Realm `aeneas`). Zammad legt den User als **Kunde** an. Agenten später per Zammad-Rolle.

SMTP/IMAP: [MAIL.md](MAIL.md). Overlay-Dateien (noch nicht starten): [frappe.md](frappe.md), [matrix.md](matrix.md), [nextcloud.md](nextcloud.md).

## 7. Nächste Schritte (Produktion)

CAV-OIDC analog. Frappe Learning (nicht Moodle), Matrix, Nextcloud; Themes, MFA, Offsite-Backup. Aufnahmeformular im Portal; Chat erst nach `schulung:chat`.
---

## Reset

Der Bootstrap-Admin wird nur bei leerer Keycloak-Datenbank erzeugt. Ein Container-Restart reicht nicht.

**Produktion:** Keycloak-Datenbank nicht droppen, um einen Admin wiederherzustellen. Stattdessen: Postgres-Backup, zweiten Master-Admin vorab anlegen, oder Keycloak-Admin-CLI gegen die bestehende Datenbank. `docker compose down -v` auf dem Produktivsystem löscht Volumes.

**Nur lokal:** Keycloak-Datenbank neu anlegen (Datenbanken `portal` und `cav` bleiben):

```bash
cd aeneas_infra
docker compose stop keycloak
docker compose exec -T postgres psql -U aeneas -d postgres -c "DROP DATABASE IF EXISTS keycloak;"
docker compose exec -T postgres psql -U aeneas -d postgres -c "CREATE DATABASE keycloak;"
docker compose start keycloak
```

Logzeile `Created temporary admin user with username admin` abwarten. `/admin/` → Bootstrap-Login → dauerhaften Master-Admin anlegen.

Vollständiger lokaler Reset (alle Volumes): `docker compose down -v`, danach `docker compose up -d`.
