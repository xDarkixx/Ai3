# AI3 – deutsche Online-Ausweisfunktion

AI3 enthält jetzt die technische Anbindung für die deutsche Online-Ausweisfunktion (AusweisApp/eID). **AI3 fälscht keine Identitätsprüfung.** Die kryptografische Prüfung des Ausweises muss durch einen konformen eID-Server erfolgen.

## Architektur

```text
AI3 Web/Dashboard
       |
       | AusweisApp Client URL
       v
AusweisApp auf dem Gerät
       |
       | TR-03124 / eID-Protokoll
       v
AI3 eID-Server (separater, gehärteter Dienst)
       |
       v
Deutsche eID-Infrastruktur
       |
       v
AI3 Callback / Konto
```

Die AusweisApp ist der offizielle eID-Client des Bundes. Für einen Diensteanbieter ist zusätzlich eine Anbindung an einen eID-Server erforderlich. Ein eigener eID-Server benötigt die vorgeschriebene Berechtigungs-/Zertifikatsinfrastruktur.

## AI3-Konfiguration

```text
AI3_PUBLIC_BASE_URL=https://ai3.example.com
AI3_EID_SERVER_URL=https://eid.example.com
AI3_EID_TC_TOKEN_URL=https://eid.example.com/api/eid/start
AI3_IDENTITY_CALLBACK_SECRET=<zufälliges-langes-secret>
```

`AI3_EID_TC_TOKEN_URL` muss auf den echten TC-Token-Endpunkt des eigenen eID-Servers zeigen. Dieser Endpunkt darf **nicht** durch einen einfachen AI3-Testendpoint ersetzt werden.

## AusweisApp

AI3 erzeugt die korrekten Desktop- und Mobile-Client-URLs. Auf Desktop-Systemen wird der lokale eID-Client verwendet; auf Mobilgeräten wird das `eid://`-Schema verwendet.

## Produktionsbetrieb

1. HTTPS für die gesamte öffentliche AI3-Webseite verwenden.
2. Einen konformen eID-Server selbst betreiben oder einen eID-Service nutzen.
3. Die notwendigen Berechtigungszertifikate beim zuständigen Verfahren beantragen.
4. Die erforderlichen Attribute minimal beantragen.
5. Schlüssel und Zertifikate nicht in Git, `.env` oder Docker-Images speichern.
6. eID-Server separat vom AI3-API-Prozess isolieren.
7. Callback nur über TLS und mit kryptografischer Signatur akzeptieren.
8. Keine PIN oder privaten Ausweisdaten in AI3 speichern.
9. Vor dem Livebetrieb Konformitäts-, Sicherheits- und Datenschutzanforderungen prüfen.

## Testbetrieb

Für Entwicklung kann ein zugelassener eID-Testserver verwendet werden. Ein erfolgreicher Testlauf bedeutet **nicht**, dass AI3 bereits als produktiver Diensteanbieter für die deutsche Online-Ausweisfunktion zugelassen ist.

## Warum AI3 keinen eigenen Ausweisprüfer implementiert

Die Online-Ausweisfunktion basiert auf gegenseitiger Authentisierung, Berechtigungszertifikaten und dem eID-Server-Protokoll. Eine selbst erfundene JSON-API, die einfach `verified=true` zurückgibt, wäre keine echte Identitätsprüfung und wird von AI3 deshalb nicht akzeptiert.

### Offizielle technische Grundlagen

- AusweisApp – Diensteanbieter: https://www.ausweisapp.bund.de/fuer-diensteanbieter
- AusweisApp – technische Hinweise: https://www.ausweisapp.bund.de/fuer-diensteanbieter/leitfaden/technische-hinweise
- BSI TR-03124 – eID-Client
- BSI TR-03130 – eID-Server
