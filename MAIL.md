# Mail: mailbox.org → Zammad und Keycloak

Kein Mailserver auf dem Host. Postfach beim Anbieter, Apps holen und senden nur.

Planung (warum, Aliasse, kein Newsletter): `aeneas_planung` → `docs/mail.md`.

Demo-Werte unten: Domain `aeneas-solutions.de`, Postfach `admin@aeneas-solutions.de`. Andere Domain: Adressen ersetzen.

## 0. Postfach (einmal)

Privat **Standard** (nicht Light, nicht Business-Silber). Eigene Domain als **externes Alias**, nicht über einen Menüpunkt „Domain“.

1. mailbox.org → Standard-Konto. Sofort nutzbar: `…@mailbox.org` (reicht für Let’s Encrypt `ACME_EMAIL`).
2. Zahnrad → **Alle Einstellungen** → **E-Mail-Adressen** → **E-Mail-Aliasse** → **Externes Alias hinzufügen** → z. B. `admin@aeneas-solutions.de` → Speichern.
3. Den angezeigten **Sicherheitsschlüssel** beim Registrar (hier: netcup) als **TXT**. Host = erster Teil ohne Domain, Ziel = zweiter Teil. Warten, Alias erneut speichern.
4. Erst wenn der Alias steht: **MX** (fremde MX löschen):

| Typ | Host | Prio | Ziel |
| --- | --- | --- | --- |
| MX | `@` | 10 | `mxext1.mailbox.org.` |
| MX | `@` | 10 | `mxext2.mailbox.org.` |
| MX | `@` | 10 | `mxext3.mailbox.org.` |
| MX | `@` | 10 | `mxext4.mailbox.org.` |

Gleiche Prio nicht erlaubt: 10, 20, 30, 40.

5. Test: Mail von einem **fremden** Konto an `admin@…` — muss im Webmail ankommen.
6. Aliasse auf dasselbe Fach, z. B. `info@`, `vorstand@`, `praevention@`. Keine Extra-Postfächer.
7. SPF/DKIM/DMARC: Werte **aus der mailbox-Oberfläche** übernehmen, nicht raten. SPF typisch `v=spf1 include:mailbox.org ~all`, DKIM als von mailbox gelieferter TXT/CNAME. DMARC erst `p=none`.

## 1. App-Passwort

Zahnrad → Alle Einstellungen → **Sicherheit** → **E-Mail-App-Passwörter**.

Name z. B. `zammad`. Protokolle **IMAP** und **SMTP**. Passwort generieren, in den Passwortmanager — nicht ins Git, nicht in die `.env` (Zammad und Keycloak speichern in ihrer UI).

IMAP/SMTP-Login = die **Hauptadresse**, mit der das Webmail öffnet (oft noch `…@mailbox.org`, nicht zwingend der Alias).

| | Server | Port | TLS |
| --- | --- | --- | --- |
| IMAP | `imap.mailbox.org` | 993 | SSL/TLS |
| SMTP | `smtp.mailbox.org` | 465 | SSL/TLS |
| SMTP alternativ | `smtp.mailbox.org` | 587 | STARTTLS |

## 2. Zammad: Postausgang und Posteingang

Als **Zammad-Insel-Admin** (Password-Link), nicht als OIDC-Kunde.

**Admin → Channels → Email** (deutsch: **Kanäle → E-Mail**).

### Ausgang (SMTP)

Neues Konto / SMTP:

| Feld | Wert |
| --- | --- |
| Host | `smtp.mailbox.org` |
| Port | `465` (SSL) oder `587` (STARTTLS) |
| User | Hauptadresse |
| Passwort | App-Passwort |
| Absender | `Aeneas <admin@aeneas-solutions.de>` |

Speichern. Testmail an eine Adresse, die du liest.

### Eingang (IMAP)

| Feld | Wert |
| --- | --- |
| Host | `imap.mailbox.org` |
| Port | `993` SSL |
| User | Hauptadresse |
| Passwort | dasselbe App-Passwort |
| Ordner | `INBOX` |
| Nach Abholen | auf dem Server lassen oder nach `Zammad` verschieben — einmal festlegen, nicht mischen |

Zammad legt aus jeder neuen Mail ein Ticket. Gruppe vorerst **Users** / Default. Sortierung nach `To:` (`info@` vs `vorstand@`) später über Filter, nicht über fünf IMAP-Konten.

Test: Mail an `admin@aeneas-solutions.de` oder `info@…` → Ticket. Antwort aus Zammad → Empfänger sieht `admin@` (oder den gesetzten Absender), nicht die Privatadresse.

## 3. Keycloak: SMTP

Realm **aeneas** (nicht `master`) → **Realm settings** → **Email**.

| Feld | Wert |
| --- | --- |
| From | `admin@aeneas-solutions.de` |
| From display name | `Aeneas` |
| Host | `smtp.mailbox.org` |
| Port | `465` |
| Encryption | SSL |
| Authentication | an |
| Username | Hauptadresse |
| Password | App-Passwort (eigenes oder dasselbe) |

**Test connection**. Wenn der Test ankommt: **Realm settings → Login → Forgot password** an. Vorher aus lassen.

Master-Realm: eigenes From nur wenn Master-Admins Reset brauchen — nicht dasselbe wie Mitglieder-Mails vermischen, oder bewusst dieselbe Absenderadresse.

## 4. Check

- [ ] Fremde Mail kommt im Webmail an
- [ ] Zammad-Testmail kommt an
- [ ] Mail an Funktionsadresse wird Ticket
- [ ] Ticket-Antwort kommt als Vereinsabsender an
- [ ] Keycloak Test connection kommt an
- [ ] Kein Postfach-Passwort in Git / Chat

Newsletter und Massenmail nicht über dieses Postfach. Listmonk später, anderer Versandweg.
