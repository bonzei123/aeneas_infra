# Setup — Schritt für Schritt

Ziel ist der **produktive Release** (Linux-Server, echte Domain, HTTPS, echte Passwörter). Dieselben Keycloak-Schritte gelten dort und auf dem Rechner.

Abschnitte und Zeilen mit **Nur lokal** gelten nur zum Üben auf dem Windows-Rechner. Auf dem Produktivserver überspringen.

---

## Begriffe

| Wort | Bedeutung |
| --- | --- |
| Traefik | Türsteher. Schaut auf den Hostnamen und schickt den Request an den richtigen Container. |
| Realm | Ein abgeschlossenes Login-Haus. `master` = Hausmeister. `aeneas` = Mitglieder und Apps. |
| Client | Eine App, die sich bei Keycloak anmelden darf (Portal, CAV, …). |
| Gruppe | Stempel auf dem Konto (`mitgliedschaft:aktiv`, `verein:…:vorstand`). Apps lesen das. |

Keycloak hat auf `/` **keine Startseite** (404 ist normal). Immer die Admin-Konsole: `https://id.<DOMAIN>/admin/`

**Nur lokal:** `http://id.aeneas.test/admin/` (kein HTTPS, Domain aus der Hosts-Datei).

---

## 0. Server und Domain

### Produktion

1. Linux-Host (Debian oder Ubuntu LTS), Docker Compose, Firewall.
2. Echte Domain kaufen bzw. nutzen. DNS **A/AAAA** (kein Eintrag in einer Hosts-Datei):

   | Host | Dienst |
   | --- | --- |
   | `id.<DOMAIN>` | Keycloak |
   | `www.<DOMAIN>` | Portal |
   | `cav.<DOMAIN>` | CAV-Kern |
   | `traefik.<DOMAIN>` | Traefik-Dashboard — **nicht öffentlich**, nur intern oder VPN |

3. In `aeneas_infra`: `.env` aus `.env.example` anlegen. `DOMAIN` auf die echte Domain. **Alle** Passwörter durch starke ersetzen, Datei nicht committen.
4. Vor dem öffentlichen Go-Live: HTTPS an Traefik (Let’s Encrypt). Die Compose-Datei ist derzeit HTTP-first; TLS gehört in die Produktiv-Compose, nicht als Hosts-Trick.
5. `docker compose up -d` — warten, bis Postgres **healthy** und Keycloak läuft (erster Start ~1 Minute).

### Nur lokal

Zum Üben **ohne** DNS und Zertifikat:

- Docker Desktop muss laufen. Traefik **v3.6+** (neuere Docker Desktop: mit Traefik 3.3 sind alle Hosts 404).
- `DOMAIN=aeneas.test` in `.env` lassen. Dummy-Passwörter aus `.env.example` sind nur für den Rechner.
- Hosts-Datei (Windows, als Administrator) `C:\Windows\System32\drivers\etc\hosts`:

  ```
  127.0.0.1 id.aeneas.test www.aeneas.test cav.aeneas.test traefik.aeneas.test
  ```

- Port 80 muss frei sein. Sonst in `compose.yml` z. B. `"8080:80"` und URLs mit `:8080`.
- Start: `cp .env.example .env` und `docker compose up -d`.

---

## 1. Master-Admin (immer)

Der User aus `KC_BOOTSTRAP_ADMIN_*` ist nur ein **temporärer** Bootstrap. Sofort einen **richtigen Admin in `master` anlegen** und behalten. Den letzten Master-Admin nicht löschen.

1. Admin-Konsole öffnen (`/admin/`).
2. Mit Bootstrap einloggen.
3. In `master` einen dauerhaften Admin anlegen, Passwort notieren (Passwortmanager).
4. Bootstrap nicht als Dauer-Konto behandeln.

**Nur lokal:** Login `admin` / `changeme-keycloak`, solange `.env` unverändert ist.

---

## 2. Realm `aeneas` (immer)

Oben links steht **master**. Das ist das Technik-Haus. Mitglieder kommen hier nicht hin — weder lokal noch in Produktion.

1. Oben links auf **master** klicken (Realm-Auswahl).
2. **Create realm**.
3. **Realm name:** `aeneas` (klein, ohne Leerzeichen — technische ID, in Prod und lokal gleich).
4. **Enabled** an.
5. **Create**.

Oben links muss **aeneas** stehen. Wenn da noch `master` steht, bist du im falschen Haus.

### Realm-Einstellungen

Links **Realm settings**:

- **General:** Display name z. B. der Vereinsname.
- **Login:** User registration **aus** (Mitglieder legt ihr an, nicht das Internet).
- **Localization:** Default locale `de`. Internationalization an, Locale `de`.

**Produktion:** SMTP hinterlegen (Passwort vergessen, Bestätigung). Forgot password erst einschalten, wenn SMTP wirklich zustellt. MFA für Admins, Vorstände, Agenten.

**Nur lokal:** Forgot password aus lassen. Ohne SMTP bei Test-Usern **Email verified** manuell an, sonst Nerv.

Themes (Logo/Farben) später, Planung `ci-cd.md`.

---

## 3. Gruppen-Skelett (immer)

Links **Groups** → **Create group**. Führend ist Keycloak, nicht Nextcloud oder Matrix. Namen klein, genau so:

| Gruppe | Wofür |
| --- | --- |
| `mitgliedschaft:aktiv` | beitragsfähiges Mitglied |
| `backoffice` | Gesamtverein-Mitarbeiter (später Nextcloud) |
| `amt:ausgabe` | Beispiel-Amt; weitere Ämter analog `amt:…` |

Ortsvereine nach dem Muster `verein:<slug>:mitglied` und `verein:<slug>:vorstand`. Details: Planung `docs/sso-matrix.md`.

**Nur lokal:** zum Klicken die Demo-Gruppen `verein:demo:mitglied` und `verein:demo:vorstand`. In Produktion echte Slugs, kein `demo` als Dauerzustand.

---

## 4. Erster User im Realm `aeneas` (immer)

Nicht in `master`. Oben links wirklich **aeneas**.

1. **Users** → **Create new user**.
2. Username und echte E-Mail.
3. **Create**.
4. Reiter **Credentials:** Passwort setzen, **Temporary** aus, wenn die Person das Passwort nicht sofort selbst setzen soll.
5. Reiter **Groups:** die passenden Gruppen (mindestens `mitgliedschaft:aktiv` plus Ortsverein).

Das ist ein Mitglied, kein Admin. Realms verwalten bleibt der Master-Admin.

**Nur lokal:** User z. B. `anna`, **Email verified** an, Gruppen `mitgliedschaft:aktiv` und `verein:demo:mitglied`.

---

## 5. Danach (Produktion, nicht überspringen wenn ihr live geht)

OIDC-**Clients** für Portal und CAV erst, wenn die Apps Redirect-URL und Secret wirklich nutzen.

Reihenfolge:

1. Linux, Traefik (HTTPS), Keycloak, Realm, Gruppen ← du bist hier, sobald Schritt 0–3 in Prod stehen
2. Portal: Login + Linktree
3. CAV: Mandant aus Token
4. Zammad, Moodle, Matrix, Nextcloud
5. SMTP, Themes, MFA, Backup nach außen (restic/borg)

Compose Alltag:

```bash
cd aeneas_infra
docker compose up -d
docker compose ps
docker compose logs -f keycloak
docker compose down          # stoppen, Daten bleiben
```

Portal und CAV, wenn die Geschwister-Repos daneben liegen:

```bash
docker compose -f compose.yml -f compose.apps.yml up -d --build
```

---

## Reset

Bootstrap-Admin entsteht **nur** bei leerer Keycloak-Datenbank. Container neu starten reicht nicht.

**Produktion:** Datenbank nicht droppen, um einen Admin zu retten. Stattdessen: Postgres-Backup, zweiten Master-Admin vorher anlegen, oder Keycloak-Admin-CLI gegen die bestehende DB. `docker compose down -v` auf dem Live-Server ist Datenverlust.

**Nur lokal:** Keycloak-DB leeren (Portal-/CAV-DBs bleiben):

```bash
cd aeneas_infra
docker compose stop keycloak
docker compose exec -T postgres psql -U aeneas -d postgres -c "DROP DATABASE IF EXISTS keycloak;"
docker compose exec -T postgres psql -U aeneas -d postgres -c "CREATE DATABASE keycloak;"
docker compose start keycloak
```

Warten auf Logzeile `Created temporary admin user with username admin`. Dann `/admin/` → Bootstrap-Login → sofort wieder einen richtigen Master-Admin anlegen.

Kompletter Übungs-Reset (alles weg): `docker compose down -v` und wieder `docker compose up -d`.
