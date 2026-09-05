# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehosteter Gateway für lokale KI-Modelle, KI-Agenten und OpenAI-kompatible Anwendungen. Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

## Was AI3 kann

- OpenAI-kompatible `/v1` API für Chat, Models, Responses und Embeddings
- eigene `ai3_...` API-Tokens mit Scopes und Ablaufzeiten
- kurzlebige OAuth2-artige Access Tokens und rotierende Refresh Tokens
- OAuth-Clients mit eigenem Client-ID/Secret
- Revocation und Security-Event-Protokoll
- Benutzer, Agents und Services als eigene Identitäten
- Agent-Konfiguration mit Modell und Backend
- lokale Modelle über Ollama
- vorbereitete Backend-Abstraktion für Ollama, vLLM und llama.cpp
- API Playground in der Weboberfläche
- Usage-/Latenz-/Fehlerstatistik
- OpenClaw-, Open WebUI- und Python/OpenAI-SDK-Verbindungsbeispiele
- automatische Modellinitialisierung beim Docker-Start
- SQLite ohne externe Datenbank
- Admin-Datenbank-Backups über SQLite Online Backup
- HTTPS-Deployment kann mit kostenloser Let's-Encrypt-Zertifikatsausstellung erfolgen

## Architektur

```text
Internet / LAN
      |
      | HTTPS
      v
+-------------------------+
| AI3 Gateway :8080       |
| Auth + Tokens + API     |
| Web Command Center      |
+------------+------------+
             |
       OpenAI / Agent API
             |
     +-------+--------+
     |                |
 OpenClaw         Open WebUI
 Apps / Bots      / Clients
     |                |
     +-------+--------+
             |
          AI3 Token
             |
      +------+------+
      | Local Model |
      |   Ollama    |
      +-------------+
```

Der interne Verwaltungsdienst `8090` ist nicht als öffentlicher Client-Endpunkt gedacht. Ollama bleibt intern. Für Internetbetrieb sollte ausschließlich der AI3-Gateway-Port über einen HTTPS-Reverse-Proxy veröffentlicht werden.

## Schnellstart — lokal und ohne externe KI-Gebühren

```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

Oder manuell:

```bash
cp .env.example .env
docker compose up -d --build
```

Standardmäßig wird `llama3.2:3b` geladen. Die Modelle liegen persistent im Docker-Volume `ollama-data`.

Weboberfläche:

```text
http://localhost:8080/
```

OpenAI-kompatible API:

```text
http://localhost:8080/v1
```

## OpenAI-kompatible Endpunkte

AI3 stellt diese zentrale Kompatibilitätsfläche bereit:

- `GET /v1/models`
- `GET /v1/models/{id}`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

Diese Oberfläche passt zu aktuellen OpenClaw-Custom-Provider-Konfigurationen mit `baseUrl`, Bearer-Key und `openai-completions`. citeturn0search0turn0search4

Beispiel:

```bash
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer YOUR_AI3_TOKEN"
```

## Python / OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="YOUR_AI3_TOKEN",
)

result = client.chat.completions.create(
    model="llama3.2:3b",
    messages=[{"role": "user", "content": "Hallo AI3"}],
)

print(result.choices[0].message.content)
```

## OpenClaw

OpenClaw unterstützt benutzerdefinierte Provider mit Base-URL, API-Key und OpenAI-Kompatibilität. Für lokale oder selbst gehostete `/v1`-Backends ist `openai-completions` der passende Adapter. citeturn0search0turn0search6

AI3 stellt dafür eine Vorlage bereit:

```text
openclaw/ai3-provider.example.json5
```

Beispielprinzip:

```json5
{
  models: {
    providers: {
      ai3: {
        baseUrl: "https://DEIN-AI3-HOST/v1",
        apiKey: "YOUR_AI3_TOKEN",
        api: "openai-completions",
        models: [
          { id: "llama3.2:3b", name: "AI3 Local" }
        ]
      }
    }
  }
}
```

## OAuth2-artige Tokenverwaltung

Zusätzlich zu den direkten `ai3_...` API-Tokens besitzt AI3 jetzt einen eigenen OAuth2-artigen Tokenfluss für Maschinen und Agenten:

- `POST /v1/admin/oauth/clients` — OAuth-Client anlegen
- `POST /oauth/token` — `client_credentials` oder `refresh_token`
- `POST /oauth/revoke` — Access-/Refresh-Token widerrufen
- `GET /v1/admin/oauth/clients` — Clients verwalten
- `DELETE /v1/admin/oauth/clients/{client_id}` — Client deaktivieren
- `GET /v1/admin/security/events` — Security-Aktivitäten prüfen

Access Tokens sind standardmäßig 15 Minuten gültig. Refresh Tokens sind standardmäßig 30 Tage gültig und werden bei jeder Verwendung rotiert; das alte Refresh Token wird sofort ungültig. Diese Rotation entspricht einer empfohlenen Schutzmaßnahme gegen Replay von Refresh Tokens. citeturn0search2

Die Tokenwerte werden nur bei Ausstellung ausgegeben; in SQLite werden Hashwerte gespeichert. Für OpenClaw kann weiterhin direkt ein AI3-Bearer-Key als Custom Provider verwendet werden, was OpenClaw offiziell für benutzerdefinierte OpenAI-kompatible Provider unterstützt. citeturn0search0

## Backups

Admin-only:

```text
POST /v1/admin/backup
GET  /v1/admin/backups
```

Die Sicherung verwendet SQLite Online Backup und landet standardmäßig unter `/data/backups`. Der Ordner gehört zum persistenten `ai3-data`-Volume.

Für zusätzliche externe Sicherungen sollte `/data/backups` regelmäßig auf ein anderes Speichermedium kopiert werden.

## Open WebUI

Open WebUI kann OpenAI-kompatible Server als Provider verwenden. Dadurch kann AI3 als eigene Backend-URL vor Open WebUI stehen.

```text
URL:      https://DEIN-AI3-HOST/v1
API-Key:  YOUR_AI3_TOKEN
Modell:   dein lokales Modell
```

## Agents

Jeder Agent kann eine eigene Identität und ein eigenes Token erhalten. Zusätzlich kann AI3 pro Agent folgende Routingdaten speichern:

- Modell
- Backend: `ollama`, `vllm`, `llamacpp` oder `openai-compatible`
- System-Prompt

Die Konfiguration ist absichtlich von der Authentifizierung getrennt, damit ein Agent mehrere Clients bedienen kann, ohne dass dessen geheimes Token in der Modellkonfiguration gespeichert werden muss.

## Usage

AI3 protokolliert intern:

- Endpoint
- HTTP-Status
- Latenz
- zugeordneten Principal, sofern ein AI3-Bearer-Token verwendet wurde

Die Weboberfläche zeigt daraus Requests, Fehlerquote, durchschnittliche Latenz und Endpoint-Nutzung.

## Internetbetrieb

Für einen öffentlichen AI3-Server:

1. eigene Maschine oder eigenen Server verwenden
2. AI3 intern auf `8080` betreiben
3. HTTPS-Reverse-Proxy davor setzen
4. Port `8090` und Ollama **nicht** öffentlich freigeben
5. einen langen zufälligen `AI3_ADMIN_KEY` verwenden
6. pro Agent eigene Tokens mit minimalen Scopes erzeugen
7. Rate-Limiting und Firewall aktivieren
8. keine Secrets in Git committen
9. Backups nicht öffentlich ausliefern und regelmäßig extern sichern

Ein eigener Domainname ist praktisch, aber nicht zwingend für das Protokoll. Die tatsächlichen Kosten hängen von Hardware, Strom, Internetanschluss und einer eventuell verwendeten Domain ab. Für die KI selbst ist im lokalen Betrieb kein bezahlter KI-API-Dienst erforderlich.

## Backend-Strategie

**Ollama** ist der Standard, weil es lokal einfach zu betreiben ist. Für leistungsfähigere GPUs kann später ein OpenAI-kompatibler **vLLM**-Server als Backend verwendet werden; vLLM stellt ebenfalls einen OpenAI-kompatiblen HTTP-Server bereit. citeturn0search9

Die AI3-API bleibt dabei gleich:

```text
Client → AI3 → Backend → Modell
```

Ein Client muss also nicht wissen, ob dahinter Ollama, vLLM, llama.cpp oder ein anderer kompatibler Server läuft.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Die GitHub-Actions-Pipeline testet die Python-Anwendung automatisch. Zusätzlich sollte vor einer öffentlichen Freigabe ein echter Docker-Smoke-Test mit Ollama durchgeführt werden.

## Sicherheit

AI3 speichert Tokenwerte nicht im Klartext, sondern als Hash. Der vollständige Token wird nur bei der Erstellung ausgegeben. Der Admin-Key ist ausschließlich für Verwaltung gedacht und darf nicht als Client-API-Key verwendet werden.

Für öffentlich erreichbare Installationen gilt: **HTTPS + Firewall + Rate-Limit + minimale Token-Scopes**. OpenAI-kompatible Agent-Gateways können weitreichende Fähigkeiten bereitstellen; deshalb sollte ein Internet-Gateway niemals ohne Authentifizierung veröffentlicht werden. Bearer Tokens sollten auf eine konkrete Zielressource begrenzt werden; für langlebige Refresh Tokens ist Rotation eine empfohlene Schutzmaßnahme. citeturn0search2
