# Frappe Learning — Overlay, noch nicht starten

Host: `learn.${DOMAIN}`. Nicht Moodle, nicht ERPNext. Kurse + Quiz; Türen (`schulung:*`) schreibt später der CAV, nicht das LMS.

Es gibt **kein** offizielles One-Container-Image. Der Stack kommt aus [frappe_docker](https://github.com/frappe/frappe_docker) (MariaDB, Redis, websocket, workers, frontend). `compose.frappe.yml` legt nur MariaDB + Redis an — die App-Container kommen beim Anbinden von frappe_docker dazu.

OIDC-Client `learn` im Realm `aeneas`, nur `mitgliedschaft:aktiv`.

## Bevor irgendein `up`

1. A-Record `learn.${DOMAIN}`.
2. `FRAPPE_MARIADB_ROOT` in `.env`.
3. Site anlegen nach frappe_docker-Doku, Image **pinnen**.
4. Traefik-Host `learn.${DOMAIN}`, Demo: `entrypoints=websecure` + `tls.certresolver=le`.

Nicht `docker compose -f compose.frappe.yml up` als fertiges LMS erwarten.

## Danach

- Katalog: Onboarding, Prävention, Chat-Regeln, Ausgabe
- Webhook → CAV → Keycloak-Gruppe
- Branding in Frappe-Settings
