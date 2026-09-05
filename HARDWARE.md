# AI3 Hardware-Empfehlungen

AI3 ist für **Ubuntu Server 24.04 LTS (64-bit)** als einheitliches Zielsystem ausgelegt. Ubuntu 24.04 LTS ist bis Juni 2029 im Standard-Support; für AI3 sollte möglichst die aktuelle 24.04.x Server-Installation verwendet werden.

## Kurzempfehlung

| Einsatz | CPU | RAM | GPU/VRAM | Speicher |
|---|---:|---:|---:|---:|
| Test / 1 Benutzer | 4 Kerne | 8 GB | keine | 50 GB SSD |
| Kleiner privater AI3 | 6–8 Kerne | 16 GB | optional 8 GB VRAM | 100 GB NVMe |
| Mehrere Agents | 8–16 Kerne | 32 GB | 12–16 GB VRAM | 250 GB NVMe |
| Größere lokale Modelle | 12–24 Kerne | 64 GB+ | 24 GB+ VRAM | 500 GB+ NVMe |

Das sind **AI3-Praxisempfehlungen**, keine Mindestanforderungen von Ubuntu oder Ollama. Das tatsächlich benötigte RAM/VRAM hängt stark von Modellgröße, Quantisierung, Kontextlänge und Anzahl paralleler Anfragen ab.

## GPU oder CPU?

### NVIDIA-GPU

Für lokale Inferenz ist eine NVIDIA-GPU mit ausreichend VRAM die bevorzugte Variante. Mehr VRAM ermöglicht größere Modelle und/oder längere Kontexte.

Grobe Orientierung:

- 6–8 GB VRAM: kleine Modelle
- 12–16 GB VRAM: gute Allround-Klasse
- 24 GB VRAM: große lokale Modelle und mehr Reserven
- 48 GB+ VRAM: größere Modelle / höhere Parallelität

AI3 erkennt NVIDIA automatisch. Der Installer prüft zuerst den Host und anschließend den GPU-Zugriff aus Docker. Nur wenn dieser Test erfolgreich ist, wird die GPU-Konfiguration verwendet.

### Keine GPU

CPU-Inferenz funktioniert ebenfalls. Für kleine Modelle und wenige Benutzer ist das sinnvoll, aber deutlich langsamer als eine passende GPU.

Empfehlung ohne GPU:

- mindestens 4 CPU-Kerne
- besser 8+ moderne CPU-Kerne
- 16 GB RAM für einen komfortablen privaten Betrieb
- NVMe/SSD statt HDD

## RAM und VRAM

RAM und VRAM sind nicht einfach durch eine einzelne Zahl festgelegt. Als Faustregel gilt: Ein größeres Modell benötigt mehr Speicher; zusätzlich kommen Kontext, KV-Cache, Ollama, Docker und das Betriebssystem hinzu.

Plane daher Reserve ein. Ein System, das gerade so ein Modell laden kann, ist für mehrere Agents nicht automatisch geeignet.

## Speicher

Modelldateien können mehrere GB bis deutlich mehr benötigen. Deshalb:

- SSD/NVMe verwenden
- mindestens 100 GB für einen normalen AI3-Server einplanen
- bei mehreren/großen Modellen 250–500 GB oder mehr einplanen
- Docker- und AI3-Daten nicht auf eine fast volle Systempartition legen

AI3 und Ollama verwenden persistente Docker-Volumes.

## Netzwerk

Für die erstmalige Einrichtung werden Docker-Images und das konfigurierte Ollama-Modell aus dem Internet geladen. Für einen öffentlichen AI3-Server sollte zusätzlich ein Reverse Proxy mit HTTPS eingesetzt werden.

## Empfohlene Konfigurationen

### Preisbewusst / CPU

- Ubuntu Server 24.04 LTS amd64
- 6–8 CPU-Kerne
- 16 GB RAM
- 100 GB NVMe
- keine GPU

### Preis/Leistung mit GPU

- Ubuntu Server 24.04 LTS amd64
- 8–12 CPU-Kerne
- 32 GB RAM
- NVIDIA GPU mit 12–16 GB VRAM
- 250 GB NVMe

### Leistungsstarker lokaler AI3-Server

- Ubuntu Server 24.04 LTS amd64
- 12–24 CPU-Kerne
- 64 GB RAM oder mehr
- NVIDIA GPU mit 24 GB+ VRAM
- 500 GB+ NVMe

## Was der Installer macht

`scripts/install-ubuntu.sh` und `scripts/setup-local.sh` sind so aufgebaut, dass nicht zwei getrennte AI3-Systeme gepflegt werden müssen:

1. Ubuntu/Docker werden geprüft.
2. NVIDIA wird erkannt.
3. Bei NVIDIA wird der Docker-GPU-Zugriff getestet.
4. Bei erfolgreichem Test wird `docker-compose.gpu.yml` zusätzlich verwendet.
5. Ohne funktionierenden GPU-Zugriff läuft AI3 im CPU-Modus.
6. Ollama wird gestartet.
7. Das konfigurierte Modell wird geladen.
8. AI3 wird gestartet und per Health-Endpunkt geprüft.
9. Ein initialer Agent und Token werden erstellt.
10. Eine OpenClaw-Konfiguration wird erzeugt.

## Ressourcen und Limits

`0 = unbegrenzt` bedeutet bei AI3, dass das jeweilige AI3-Anfragelimit nicht künstlich begrenzt wird. Es bedeutet **nicht**, dass CPU, RAM, VRAM, Speicher oder Netzwerk unendlich sind.

Auf schwächerer Hardware sollten RPM-/Tageslimits und die Anzahl paralleler Anfragen begrenzt werden.

## Offizielle Ubuntu-Basis

Ubuntu nennt für Server 24.04 amd64 sehr niedrige System-Minima, weist aber darauf hin, dass der tatsächliche Bedarf vom Einsatz abhängt. AI3 mit lokaler KI benötigt deshalb deutlich mehr Ressourcen als ein nacktes Ubuntu-System.
