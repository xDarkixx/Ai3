# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehosteter Gateway für lokale KI-Modelle, KI-Agenten und OpenAI-kompatible Anwendungen. **Branding: xDarkixx. Copyright © 2026 xDarkixx.** Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

## Für andere Nutzer / Clients

AI3 ist dafür gebaut, dass **andere Personen, Agents und Programme** ihn wie einen normalen KI-Provider benutzen können:

```text
Client / OpenClaw / Open WebUI / Bot / App
                    |
                    | HTTPS + AI3 Bearer Token
                    v
             https://DEIN-HOST/v1
                    |
                    v
             AI3 Gateway
                    |
             lokales Backend
                    |
                 Modell
```

Jeder Nutzer/Agent/Service bekommt eine eigene Identität und einen eigenen Token. Dadurch muss kein gemeinsamer Admin-Schlüssel verteilt werden. OpenClaw unterstützt genau solche benutzerdefinierten OpenAI-kompatiblen Provider mit `baseUrl`, API-Key und `openai-completions`. citeturn0search0turn0search4

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
- **optionale kostenpflichtige externe Modelle** über einen OpenAI-kompatiblen Upstream
- API Playground in der Weboberfläche
- Usage-/Latenz-/Fehlerstatistik
- automatische Modellinitialisierung beim Docker-Start
- SQLite ohne externe Datenbank
- Admin-Datenbank-Backups
- Live-Limits und Quoten
- modernes responsives Command-Center-Design
- Copyright-/Rechtshinweise direkt in der Oberfläche
- HTTPS-Deployment mit einem kostenlosen Let's-Encrypt-Zertifikat möglich

## Lokale oder kostenpflichtige Modelle

AI3 ist nicht auf kostenlose lokale Modelle festgelegt. Wenn lokale Inferenz nicht ausreicht, kann der Betreiber einen **OpenAI-kompatiblen externen Anbieter** als Upstream konfigurieren, z. B. einen Dienst mit `/v1/models` und `/v1/chat/completions`. AI3 reicht die Anfrage über den konfigurierten Upstream weiter; der jeweilige Anbieter rechnet nach dessen Tarif ab.

Beispiel in `.env`:

```env
AI3_LLM_BASE_URL=https://DEIN-PROVIDER/v1
AI3_LLM_API_KEY=DEIN_PROVIDER_KEY
AI3_LLM_TIMEOUT=300
```

Damit bleiben die AI3-Client-Tokens von den geheimen Upstream-Zugangsdaten getrennt. **Der externe Provider-Key gehört nur auf den AI3-Server und darf niemals an Nutzer/Agents weitergegeben werden.** OpenClaw kann AI3 anschließend als eigenen OpenAI-kompatiblen Provider verwenden. citeturn0search0turn0search3

## Limits und „unbegrenzt"

In **System → Limits & Kontingente** können die Laufzeitlimits eingestellt werden:

- Requests pro Minute
- Requests pro 24 Stunden

**`0 = unbegrenzt`.** Die Änderungen werden ohne Neustart für neue Requests übernommen. Mit **„Alles unbegrenzt“** werden die beiden aktiven Limits auf 0 gesetzt.

Für einen öffentlichen Server wird empfohlen, Limits zu aktivieren. Für einen privaten Server kann 0/unbegrenzt verwendet werden. Infrastrukturressourcen bleiben natürlich trotzdem begrenzt durch CPU, RAM, GPU, Speicher und Netzwerk.

## Branding und Rechtliches

AI3 trägt sichtbar die Kennzeichnung **„AI3 — BY XDARKIXX“** sowie **© 2026 xDarkixx — AI3**. Zusätzlich gibt es in der Weboberfläche eine Seite **„Rechtliches“** und im Repository `LEGAL.md`.

Die dortigen Hinweise sind keine Rechtsberatung. Für eine öffentliche Instanz müssen insbesondere Betreiberangaben/Impressum, Datenschutzerklärung, Aufbewahrungs- und Löschregeln sowie die Lizenzen verwendeter Modelle und Drittanbieter geprüft und an den konkreten Betreiber angepasst werden.

## Kosten

AI3 kann vollständig lokal mit Open-Source-Modellen betrieben werden, sodass kein bezahlter KI-API-Anbieter notwendig ist. Das ist **0 € für den KI-Provider**, nicht automatisch 0 € Gesamtbetriebskosten. Hardware, Strom, Internet, Hosting, Domain und gegebenenfalls Modell-/Softwarelizenzen können Kosten verursachen.

Bei einem externen kostenpflichtigen Upstream entstehen zusätzlich dessen normale Nutzungsgebühren. AI3 selbst benötigt dafür keinen separaten SaaS-Abrechnungsdienst.

## Schnellstart

```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

Oder manuell:

```bash
cp .env.example .env
docker compose up -d --build
```

Standardmäßig wird `llama3.2:3b` geladen. Weboberfläche und API sind anschließend unter dem AI3-Host erreichbar.

## OpenAI-kompatible Endpunkte

- `GET /v1/models`
- `GET /v1/models/{id}`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

## OpenClaw

```json5
{
  models: {
    providers: {
      ai3: {
        baseUrl: "https://DEIN-AI3-HOST/v1",
        apiKey: "YOUR_AI3_TOKEN",
        api: "openai-completions",
        models: [{ id: "llama3.2:3b", name: "AI3 Local" }]
      }
    }
  }
}
```

OpenClaw dokumentiert benutzerdefinierte Provider und lokale OpenAI-kompatible Backends offiziell. citeturn0search0turn0search10

## OAuth2-artige Tokenverwaltung

- `POST /v1/admin/oauth/clients` — OAuth-Client anlegen
- `POST /oauth/token` — `client_credentials` oder `refresh_token`
- `POST /oauth/revoke` — Token widerrufen
- `GET /v1/admin/oauth/clients` — Clients verwalten
- `DELETE /v1/admin/oauth/clients/{client_id}` — Client deaktivieren

Access Tokens sind standardmäßig 15 Minuten gültig; Refresh Tokens 30 Tage und werden bei Verwendung rotiert.

## Backups

```text
POST /v1/admin/backup
GET  /v1/admin/backups
```

Backups landen standardmäßig unter `/data/backups` im persistenten AI3-Datenvolume.

## Sicherheit für Internetbetrieb

1. Nur AI3 `:8080` über HTTPS veröffentlichen.
2. `:8090` niemals öffentlich freigeben.
3. Ollama niemals öffentlich freigeben.
4. Pro Nutzer/Agent einen eigenen Token verwenden.
5. Minimale Scopes vergeben.
6. Rate-Limit und Tagesquota aktivieren.
7. Secrets niemals committen.
8. Backups nicht über die Weboberfläche öffentlich ausliefern.
9. Für echte öffentliche Angebote die rechtlichen Hinweise an den konkreten Betreiber anpassen.

## Lizenz- und Drittanbieterhinweise

Drittanbieter-Software, Modelle und Datensätze behalten ihre jeweiligen Lizenzen. Vor Weitergabe oder kommerzieller Nutzung sind diese separat zu prüfen.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Die Tests prüfen jetzt Passwort-Hashing, getrennte Nutzer-/Token-Identitäten, Token-Widerruf, Health/API-Oberfläche und die Unlimited-Limit-Grundeinstellung. Vor einer öffentlichen Freigabe sollte zusätzlich ein echter Docker-Smoke-Test mit Ollama und – bei Nutzung eines externen Anbieters – ein Upstream-Test durchgeführt werden.
