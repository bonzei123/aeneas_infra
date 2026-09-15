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
   | `traefik.<DOMAIN>` | Traefik-Dashboard — nicht öffentlich, intern oder VPN |

3. In `aeneas_infra`: `.env` aus `.env.example`. `DOMAIN` auf die öffentliche Domain setzen. Alle Passwörter durch produktive Secrets ersetzen; `.env` nicht committen.
4. Vor öffentlichem Traffic: TLS an Traefik (Let’s Encrypt). Die aktuelle Compose-Datei ist HTTP-first; TLS gehört in die Produktiv-Konfiguration.
5. `docker compose up -d`. Warten, bis der Postgres-Healthcheck erfolgreich ist und Keycloak lauscht (erster Start ca. 1 Minute).

### Nur lokal

Entwicklung ohne öffentliches DNS und ohne Zertifikat:

- Docker Desktop. Traefik **v3.6+** (Docker Engine neuerer Desktop-Versionen: Traefik 3.3 kann die Docker-API nicht lesen, Router aus Labels fehlen, alle Hosts antworten 404).
- `DOMAIN=aeneas.test` in `.env`. Default-Passwörter aus `.env.example` nur lokal.
- Windows-Hosts-Datei (Administrator) `C:\Windows\System32\drivers\etc\hosts`:

  ```
  127.0.0.1 id.aeneas.test www.aeneas.test cav.aeneas.test traefik.aeneas.test
  ```

- Port 80 muss frei sein. Andernfalls in `compose.yml` z. B. `"8080:80"` und URLs mit `:8080`.
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

Zwei Achsen, kein Kreuzprodukt `Verein × Rolle`:

| Gruppe | Achse | Verwendung |
| --- | --- | --- |
| `mitgliedschaft:aktiv` | Funktion | beitragsfähiges Mitglied |
| `rolle:vorstand` | Funktion | Vorstand |
| `rolle:ap` | Funktion | Ansprechpartner |
| `rolle:praevb` | Funktion | Präventionsbeauftragte |
| `rolle:ausgabe` | Funktion | Ausgabe (CAV-Abgabe) |
| `backoffice` | Funktion | Gesamtverein-Mitarbeiter (Nextcloud-Client später auf diese Gruppe beschränkt) |
| `verein:<slug>` | Organisation | ein Zweigverein = ein Tenant; nicht `:mitglied`/`:vorstand` anhängen |

Bei 180 Zweigvereinen: 180 `verein:*` plus das feste Funktionsset, nicht 360 oder 540. `verein:*` später aus dem CAV-Mandantenstamm, nicht alle per Hand. Schema: Planung `docs/sso-matrix.md`.

**Nur lokal:** eine Testgruppe `verein:demo`. Bereits angelegte `verein:demo:mitglied` / `verein:demo:vorstand` bzw. `amt:*` durch `verein:demo` plus `rolle:*` ersetzen.

---

## 4. Erster User im Realm `aeneas`

Nicht im Realm `master`. Realm-Auswahl: **aeneas**.

1. **Users** → **Create new user**.
2. Username und E-Mail.
3. **Create**.
4. **Credentials:** Passwort setzen; **Temporary** aus, wenn kein Zwangswechsel beim ersten Login gewünscht ist.
5. **Groups:** mindestens `mitgliedschaft:aktiv` plus genau eine `verein:<slug>`-Gruppe. Vorstand zusätzlich `rolle:vorstand`.

Das Konto ist ein Realm-User, kein Master-Admin. Realm-Verwaltung bleibt beim Master-Admin.

**Nur lokal:** z. B. User `anna`, **Email verified**, Gruppen `mitgliedschaft:aktiv` und `verein:demo`.

---

## 5. Nächste Schritte (Produktion)

OIDC-Clients für Portal und CAV erst anlegen, wenn Redirect-URIs und Client-Secrets in den Anwendungen konfiguriert sind.

Reihenfolge:

1. Linux, Traefik (TLS), Keycloak, Realm, Gruppen
2. Portal: OIDC-Login, Einstiegsseite
3. CAV: Mandant und Rolle aus Token
4. Zammad, Moodle, Matrix, Nextcloud
5. SMTP, Themes, MFA, Offsite-Backup (restic/borg)

```bash
cd aeneas_infra
docker compose up -d
docker compose ps
docker compose logs -f keycloak
docker compose down          # stoppt Container, Volumes bleiben
```

Portal und CAV (Repositories `aeneas_portal` und `aeneas_cav` eine Verzeichnisebene höher):

```bash
docker compose -f compose.yml -f compose.apps.yml up -d --build
```

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
