# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehosteter Gateway für lokale KI-Modelle, KI-Agenten und OpenAI-kompatible Anwendungen. **Branding: xDarkixx. Copyright © 2026 xDarkixx.** Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

## Vollautomatischer Betrieb

Der empfohlene Zielbetrieb ist Ubuntu Server 24.04 LTS mit Docker. `scripts/install-ubuntu.sh` und `scripts/setup-local.sh` richten die komplette lokale Installation ein: Docker, CPU/GPU-Erkennung, Ollama, lokales Modell, Datenverschlüsselung, eigene AI3-PKI, AI3 Own Verification, OpenClaw-Konfiguration und HTTPS-Reverse-Proxy.

```bash
chmod +x scripts/install-ubuntu.sh
./scripts/install-ubuntu.sh
```

### HTTPS automatisch

AI3 verwendet Caddy als kostenlosen Open-Source-Reverse-Proxy. Bei `AI3_DOMAIN=localhost` wird lokales HTTPS automatisch mit einer lokalen CA bereitgestellt. Bei einem echten öffentlichen Domainnamen versucht Caddy automatisch ein öffentlich vertrauenswürdiges ACME-Zertifikat zu beziehen und später zu erneuern. Dafür müssen DNS und die extern erreichbaren Ports 80/443 korrekt auf den Server zeigen. citeturn0search0turn0search1

Let's Encrypt ist eine kostenlose automatisierte CA. Die öffentliche Zertifikatsausstellung benötigt allerdings weiterhin einen echten Domainnamen und die übliche ACME-Domainvalidierung. citeturn0search3

## AI3 eigene PKI

AI3 erzeugt beim ersten Start automatisch eine eigene Root-CA. Der CA-Private-Key wird verschlüsselt mit dem AI3-Datengeheimnis gespeichert. Admins können interne Server-, Client- und Agent-Zertifikate über die API ausstellen und widerrufen.

- `GET /v1/pki/ca`
- `POST /v1/admin/pki/certificates`
- `GET /v1/admin/pki/certificates`
- `POST /v1/admin/pki/revoke/{serial}`

Die AI3-CA ist eine private Vertrauensdomäne. Sie macht eine öffentliche Website nicht automatisch browservertrauenswürdig; dafür übernimmt Caddy die öffentliche HTTPS-Zertifizierung.

## AI3 Own Verification

Die Identitätsprüfung ist vollständig selbst gehostet. Es gibt keinen eID-, EUDI- oder kommerziellen KYC-Anbieter.

Der Host kann verschlüsselte Nachweise prüfen und eine Prüfung auf `pending`, `verified` oder `rejected` setzen. Nachweise werden automatisch nach der konfigurierten Aufbewahrungsfrist gelöscht.

**Wichtig:** Eine eigene Host-Prüfung ist keine staatliche Identitätsbestätigung. Das System darf gegenüber Nutzern nicht behaupten, eine behördlich zertifizierte Identität zu liefern.

## Lokale KI = keine KI-API-Gebühr

Ollama läuft lokal. Bei CPU-Betrieb oder kompatibler NVIDIA-GPU werden keine externen KI-API-Aufrufe benötigt. Das spart Providergebühren. Hardware, Strom, Internet und eine optionale Domain bleiben eigene Betriebskosten.

## Für andere Nutzer / Clients

```text
Client / OpenClaw / Bot / App
          |
          | HTTPS + AI3 Token
          v
       Caddy :443
          |
          v
     AI3 Gateway
          |
          v
   Ollama / lokales Modell
```

Jeder Nutzer, Agent und Service kann eine eigene Identität und einen eigenen AI3-Token erhalten.

## OpenAI-kompatible Endpunkte

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

## OpenClaw

Nach der Installation wird automatisch `openclaw/ai3-provider.generated.json5` mit einem lokalen AI3-Token erzeugt. Diese Datei ist geheim und wird nicht in Git eingecheckt.

## Kosten

Der AI3-Standardbetrieb ist auf **0 € für externe KI- und KYC-Dienste** ausgelegt. Open-Source-Komponenten werden lokal betrieben. Unvermeidbare Infrastrukturkosten wie eigene Hardware, Strom, Internet und ggf. Domain sind davon getrennt.

## Sicherheit

Aktiviert sind unter anderem verschlüsselte Chat-/Profildaten, DDoS-/Rate-Limits, Token-Scopes, Ablaufzeiten, Admin-Sessions, eigene PKI, Zertifikatswiderruf und sichere HTTP-Header. Für einen öffentlich erreichbaren Server sollte zusätzlich die Firewall restriktiv konfiguriert und das Betriebssystem aktuell gehalten werden.
