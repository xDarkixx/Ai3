# AI3 — eigener universeller KI-, Agent-, Token- und Mail-Gateway

AI3 ist ein selbst gehosteter Gateway für lokale KI-Modelle, KI-Agenten, OpenAI-kompatible Anwendungen und einen eigenen Maildienst. **Branding: xDarkixx. Copyright © 2026 xDarkixx.**

## Vollautomatischer Betrieb

Der empfohlene Zielbetrieb ist Ubuntu Server 24.04 LTS mit Docker. `scripts/install-ubuntu.sh` und `scripts/setup-local.sh` richten Docker, CPU/GPU-Erkennung, Ollama, lokales Modell, Verschlüsselung, eigene AI3-PKI, AI3 Own Verification, HTTPS, OpenClaw und den eigenen Mailserver ein. Die Mailkomponente wird über `scripts/setup-mail.sh` gestartet.

```bash
chmod +x scripts/install-ubuntu.sh
./scripts/install-ubuntu.sh
```

## Eigener Mailserver

AI3 kann ohne externen SMTP-Provider betrieben werden. Der Mailstack stellt SMTP, Submission, IMAP/IMAPS, POP3/POP3S, Sieve, Spamfilter und Webmail/Administration bereit. Das Webinterface ist über `https://mail.<deinedomain>` erreichbar.

Automatisch freigegebene Standardports:

- TCP 25 — Server-zu-Server SMTP
- TCP 465 — SMTPS
- TCP 587 — Submission/STARTTLS
- TCP 110/995 — POP3/POP3S
- TCP 143/993 — IMAP/IMAPS
- TCP 4190 — Sieve

Für öffentliche Mail müssen zusätzlich MX, A/AAAA, SPF, DKIM, DMARC und PTR/rDNS korrekt eingerichtet sein. Port 25 kann ein eigener Internetanschluss oder Hoster blockieren; AI3 kann eine solche externe Netzsperre nicht umgehen. Ein eigener Mailserver kann außerdem trotz korrekter Konfiguration wegen IP-Reputation oder Empfängerregeln im Spam landen. citeturn0search0turn0search1turn0search7

## HTTPS automatisch

AI3 verwendet Caddy als Open-Source-Reverse-Proxy. Bei einem öffentlichen Domainnamen kann Caddy automatisch ACME-Zertifikate beziehen und erneuern; dafür müssen DNS und die extern erreichbaren Ports 80/443 korrekt auf den Server zeigen. citeturn0search0turn0search1

## AI3 eigene PKI

AI3 erzeugt automatisch eine eigene Root-CA. Der CA-Private-Key wird mit dem AI3-Datengeheimnis verschlüsselt gespeichert. Interne Server-, Client- und Agent-Zertifikate können über die Admin-API ausgestellt und widerrufen werden.

## AI3 Own Verification

Die Identitätsprüfung ist vollständig selbst gehostet. Es gibt keinen eID-, EUDI- oder kommerziellen KYC-Anbieter. Nachweise werden verschlüsselt gespeichert und nach der konfigurierten Aufbewahrungsfrist gelöscht.

**Wichtig:** Die AI3-Prüfung ist eine Betreiberprüfung und keine staatliche Identitätsbestätigung.

## Lokale KI

Ollama läuft lokal. Dadurch benötigt AI3 im Standardbetrieb keine kostenpflichtige KI-API. Hardware, Strom, Internet und eine optionale Domain bleiben eigene Infrastrukturkosten.

## Für andere Nutzer / Clients

```text
Client / OpenClaw / Bot / App
          |
          | HTTPS + AI3 Token
          v
       Caddy :443
       /          \
      v            v
 AI3 Gateway    Mail Center
      |
      v
 Ollama / lokales Modell
```

## OpenAI-kompatible Endpunkte

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

## Professionelle Weboberfläche

Das AI3 Control Center bündelt KI Studio, Agents, Token Hub, Model Hub, API Playground, Usage, System und Mail Center in einer responsiven Oberfläche. Das separate Mail Center zeigt Mailstatus, Ports und die benötigten DNS-Einträge.

## Kosten

Der Standardbetrieb ist auf **0 € für externe KI-, KYC- und SMTP-Dienste** ausgelegt. Open-Source-Komponenten werden selbst betrieben. Unvermeidbare Infrastrukturkosten wie Hardware, Strom, Internet und ggf. eine Domain bleiben bestehen.

## Sicherheit

Aktiviert sind unter anderem verschlüsselte Chat-/Profildaten, DDoS-/Rate-Limits auf Anwendungsebene, Token-Scopes, Ablaufzeiten, Admin-Sessions, eigene PKI, Zertifikatswiderruf und sichere HTTP-Header. Für einen öffentlichen Server sollte zusätzlich die Firewall restriktiv konfiguriert und das Betriebssystem aktuell gehalten werden.
