# AI3 — eigener Token-, API- und KI-Agent-Server

AI3 ist ein selbst gehosteter Token-, API- und KI-Gateway-Server für Benutzer, KI-Agenten und Services. Es benötigt für den lokalen Standardbetrieb keinen kostenpflichtigen Token-Dienst und keine kostenpflichtige Cloud-KI-API.

## Architektur

```text
Browser / OpenClaw / KI-Agent / eigene App
              |
              v
       +--------------+
       | AI3 Web UI   |  :8080
       | Token + Auth  |
       | OpenAI API    |
       +------+-------+
              |
       +------+----------------+
       |                       |
       v                       v
  SQLite DB              AI3 API Server :8090
       |                       |
       +-----------+-----------+
                   |
                   v
             Ollama :11434
                   |
                   v
          lokales KI-Modell
```

Die SQLite-Datenbank liegt persistent im Docker-Volume `ai3-data`. Sie enthält Principals, Token-Metadaten, Modellstatus und API-Ereignisse. Geheimnisse der Tokens werden nicht im Klartext gespeichert.

## Weboberfläche

Die integrierte Oberfläche läuft unter:

```text
http://localhost:8080/
```

Sie enthält Dashboard, AI-Chat, Benutzer/Agents, Tokenverwaltung, Modelle und Verbindungsinformationen.

## Eigener API-Server

Zusätzlich gibt es jetzt einen eigenständigen AI3-API-Dienst auf Port `8090`:

- `GET /health`
- `GET /api/v1/status`
- `GET /api/v1/models` — Token-geschützt
- `POST /api/v1/models/pull` — Admin-Key geschützt

Der API-Server verwendet dieselbe SQLite-Datenbank und denselben lokalen Ollama-Dienst wie AI3. Dadurch können eigene Programme und Agenten eine getrennte API-Adresse verwenden, ohne einen externen Tokenserver zu benötigen.

## Automatische Modelle

Beim Start lädt Docker Compose automatisch das in `AI3_MODEL` konfigurierte Modell herunter. Standardmäßig ist `llama3.2:3b` eingestellt.

Zusätzlich kann der eigene API-Server ein Modell bei Ollama anfordern:

```bash
curl -X POST http://localhost:8090/api/v1/models/pull \
  -H "X-AI3-Admin-Key: DEIN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"llama3.2:3b"}'
```

Der Modellstatus wird in der Datenbank erfasst. Das Ollama-Volume bleibt persistent, sodass bereits geladene Modelle erhalten bleiben.

## Token- und Agentensystem

AI3 verwendet eigene Tokens mit `ai3_`-Prefix. Ein Token kann einem `user`, `agent` oder `service` gehören und Scopes besitzen, z. B.:

- `ai:inference`
- `agents:read`
- `admin`

Tokens können Ablaufzeiten besitzen und vom Admin widerrufen werden. Ein vollständiger Tokenwert wird nur bei der Erstellung zurückgegeben.

## OpenAI-kompatible KI-API

AI3 stellt unter `/v1` unter anderem bereit:

- `GET /v1/models`
- `GET /v1/models/{model}`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

Damit können OpenAI-kompatible Clients und lokale KI-Agenten gegen den eigenen AI3-Server arbeiten.

## OpenClaw

OpenClaw kann eigene OpenAI-kompatible Provider mit `baseUrl`, `apiKey` und `api: "openai-completions"` verwenden. citeturn0search1turn0search2

Die vorhandene Vorlage befindet sich unter:

```text
openclaw/ai3-provider.example.json5
```

Das Setup-Skript erzeugt automatisch eine lokale Konfiguration mit dem eigenen AI3-Token.

## Ohne kostenpflichtige KI-APIs

Der Standardstack besteht aus AI3 + Ollama + lokalem Modell. Ollama bietet eine OpenAI-kompatible API und kann lokal per Docker betrieben werden. citeturn0search0turn0search9

Damit fallen für die KI-Nutzung keine Gebühren eines externen KI-API-Anbieters an. Natürlich können Strom-, Hardware-, Internet- oder Serverkosten entstehen.

## Schnellstart

```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

Danach:

```text
Web UI:   http://localhost:8080/
API:      http://localhost:8090/
AI API:   http://localhost:8080/v1
```

Das Setup startet Ollama, lädt das Standardmodell, startet AI3 und erstellt den ersten Agenten samt AI3-Token.

## Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Ollama ist standardmäßig nur im internen Docker-Netzwerk erreichbar. Nach außen werden AI3 und der separate API-Server bereitgestellt.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Die GitHub-Actions-Pipeline führt die automatisierten Tests bei Änderungen an `main` aus.

## Sicherheit

- Tokenwerte werden als SHA-256-Hash gespeichert.
- Der Admin-Key wird nicht in Git gespeichert.
- Generierte OpenClaw-Credentials werden ignoriert.
- Ollama muss nicht öffentlich erreichbar sein.
- Für einen öffentlichen Server HTTPS und eine Firewall/Reverse-Proxy verwenden.
- Für produktive Agenten eigene Tokens mit minimalen Scopes verwenden.

AI3 ist damit die zentrale eigene Schicht für **Authentifizierung, Tokens, Agenten, API-Zugriff, lokale Modelle und Webverwaltung** — ohne einen vorgeschalteten kostenpflichtigen Tokenserver.
