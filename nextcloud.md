# Nextcloud — Overlay, noch nicht starten

Host: `cloud.${DOMAIN}`. Nur Backoffice (`rolle:*` / `backoffice`). Mitglieder bekommen kein Konto. Kein Paperless daneben. Collabora später, nicht in der ersten `up`.

OIDC (Client `nextcloud`, Gruppen-Mapper `groups`) ist **nicht** verdrahtet.

## Dateien

`compose.nextcloud.yml` — App + eigener Postgres (wie Zammad, nicht der Infra-Cluster).

## Bevor `up`

1. A-Record `cloud.${DOMAIN}`.
2. In `.env` setzen: `NEXTCLOUD_POSTGRES_PASS` (neues Secret).
3. Demo-TLS-Labels an Router `nextcloud` wie bei Keycloak/Portal.
4. Nach dem ersten Start: Admin in der NC-UI, Trusted Domain `cloud.${DOMAIN}`, `overwriteprotocol` = `https`.

```bash
docker compose -f compose.yml -f compose.nextcloud.yml up -d
```

Group Folders = Amts-Ablage. Rechnungen: Ticket in Zammad, PDF in Nextcloud — nicht Flow als Buchhaltung.

## Danach

- Keycloak-Client, User-Restriction auf Amtsgruppen
- Collabora (`collabora/code`) als zweiter Service
- Kalender nur Amt
