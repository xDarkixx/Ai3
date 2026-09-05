# AI3 eigener Mailserver

AI3 kann Mail vollständig selbst hosten. Der Maildienst ist als optionale lokale Infrastruktur gedacht und benötigt keinen SMTP-Anbieter.

Geplant für den automatischen Stack:

- SMTP Submission
- IMAP/IMAPS
- lokale Mailboxen
- DKIM-Schlüssel lokal erzeugen
- SPF/DKIM/DMARC-Konfiguration als lokale DNS-Vorlage
- automatische TLS-Zertifikate über Caddy/ACME bei öffentlicher Domain
- AI3-Systemmail für Registrierung, Verifizierung und Passwort-Reset
- keine externen Mail-APIs

## Wichtige Voraussetzung

Ein eigener Mailserver kann ohne Mailanbieter betrieben werden, aber für öffentlich zustellbare Mail benötigt die Domain passende DNS-Einträge sowie eine erreichbare öffentliche IP. PTR/rDNS und Port 25 werden vom Internetanschluss bzw. Hoster kontrolliert und können nicht von AI3 selbst erzwungen werden.

AI3 darf deshalb niemals so tun, als sei Mailzustellung garantiert. Der Installer prüft die lokale Konfiguration und zeigt fehlende DNS-/Netzwerkvoraussetzungen an.
