# AI3 — eigener Token-Server für KI & KI-Agenten

AI3 ist ein kleiner, selbst gehosteter Authentifizierungsdienst für KI-Anwendungen und KI-Agenten. Der Server benötigt für Tokenverwaltung und Authentifizierung keinen kostenpflichtigen Cloud-Dienst und keine externe Datenbank.

## Funktionen

- Eigene opaque API-Tokens mit `ai3_`-Prefix
- Tokens werden nur als SHA-256-Hash gespeichert
- Benutzer, KI-Agenten und Services als Principals
- Scopes pro Token
- Token-Ablauf und Widerruf
- `/v1/me` zur Identitätsprüfung
- geschützte Agenten-API
- SQLite ohne externen Datenbankdienst
- Docker/Ubuntu-freundlich
- automatisierte Tests mit pytest und GitHub Actions

## Kosten

Der Token-Server selbst verwendet nur Open-Source-Komponenten und ruft keinen kostenpflichtigen KI- oder Zahlungsdienst auf. Bei lokalem Betrieb entstehen daher keine API-Kosten für den Token-Server.

Wichtig: Ein gemieteter VPS, Strom, Internetzugang oder eine separat angebundene kostenpflichtige KI-API kann natürlich eigene Kosten verursachen. AI3 selbst erzwingt keine solchen Dienste.

## Start mit Docker

```bash
cp .env.example .env
# AI3_ADMIN_KEY in .env durch einen langen zufälligen Wert ersetzen
docker compose up -d --build
```

Healthcheck:

```bash
curl http://localhost:8080/health
```

## Ersten KI-Agenten anlegen

```bash
curl -X POST http://localhost:8080/v1/principals \
  -H "X-AI3-Admin-Key: DEIN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"assistant-01","kind":"agent"}'
```

Danach Token ausstellen:

```bash
curl -X POST http://localhost:8080/v1/tokens \
  -H "X-AI3-Admin-Key: DEIN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"principal":"assistant-01","name":"production","scopes":["ai:inference","agents:read"]}'
```

Das Token wird **nur bei der Ausstellung** im Klartext zurückgegeben. Danach liegt nur sein Hash in der Datenbank.

Identität testen:

```bash
curl http://localhost:8080/v1/me \
  -H "Authorization: Bearer DEIN_AI3_TOKEN"
```

## Tests

Lokal:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Der Workflow `.github/workflows/test.yml` führt die Tests bei Pushes auf `main` und bei Pull Requests automatisch aus.

## Architektur

```text
KI-App / KI-Agent
       |
       | Bearer ai3_...
       v
+---------------------+
|     AI3 Gateway     |
| Auth / Scopes / TTL |
+----------+----------+
           |
           v
     +-----------+
     | SQLite DB |
     +-----------+
```

## Sicherheit

Für den produktiven Betrieb sollte der Dienst hinter HTTPS (z. B. Nginx/Caddy) betrieben werden. Der Admin-Key gehört ausschließlich in eine Secret-Variable und niemals in Git. Tokens sollten möglichst kurze Ablaufzeiten haben und bei Verdacht sofort widerrufen werden.

## API

- `GET /health` — Healthcheck
- `POST /v1/principals` — Principal anlegen (Admin)
- `POST /v1/tokens` — Token ausstellen (Admin)
- `POST /v1/tokens/revoke?token_prefix=...` — Token widerrufen (Admin)
- `GET /v1/me` — aktuelles Token prüfen
- `GET /v1/agents` — aktive Principals lesen, benötigt `agents:read` oder `admin`

Die eigentliche KI-Inferenz kann anschließend über denselben Gateway angebunden werden; der Token-Server bleibt dabei für Identität, Berechtigungen und Zugriffskontrolle zuständig.
