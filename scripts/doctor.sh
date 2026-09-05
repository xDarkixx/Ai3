#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
fail=0
check(){ local label="$1"; shift; if "$@" >/dev/null 2>&1; then echo "[OK]   $label"; else echo "[FAIL] $label"; fail=1; fi; }
check "Docker erreichbar" docker info
check "Docker Compose verfügbar" docker compose version
check "Compose CPU-Konfiguration" docker compose -f docker-compose.yml config -q
check "Compose GPU-Konfiguration" docker compose -f docker-compose.yml -f docker-compose.gpu.yml config -q
check "Mail Compose-Konfiguration" docker compose -f mail/docker-compose.yml config -q
check "AI3 Health" curl -fsS http://localhost:8080/health
if docker compose ps --services --filter status=running 2>/dev/null | grep -qx 'ollama'; then check "Ollama erreichbar" docker compose exec -T ollama ollama list; else echo "[FAIL] Ollama-Container läuft nicht"; fail=1; fi
if docker compose -f mail/docker-compose.yml ps --services --filter status=running 2>/dev/null | grep -qx 'poste-mail'; then echo "[OK]   Eigener Mailserver läuft"; else echo "[WARN] Eigener Mailserver läuft nicht"; fi
if docker network inspect ai3-public >/dev/null 2>&1; then echo "[OK]   Gemeinsames AI3-Netzwerk vorhanden"; else echo "[WARN] ai3-public Netzwerk fehlt"; fi
for p in 25 465 587 993 995; do if (command -v ss >/dev/null 2>&1 && ss -lnt | grep -q ":$p ") || docker compose -f mail/docker-compose.yml ps 2>/dev/null | grep -q poste-mail; then echo "[INFO] Mailport $p konfiguriert"; else echo "[WARN] Mailport $p nicht sichtbar"; fi; done
if command -v nvidia-smi >/dev/null 2>&1; then if docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then echo "[OK]   NVIDIA GPU in Docker erreichbar"; else echo "[INFO] NVIDIA-Treiber vorhanden, Docker-GPU-Test nicht erfolgreich"; fi; else echo "[INFO] Keine NVIDIA-GPU – CPU-Modus ist normal"; fi
if [ -f .env ]; then perms="$(stat -c '%a' .env 2>/dev/null || true)"; if [ "$perms" = "600" ]; then echo "[OK]   .env ist geschützt (600)"; else echo "[WARN] .env hat Rechte $perms; empfohlen ist 600"; fi; else echo "[WARN] .env fehlt"; fi
if [ -f openclaw/ai3-provider.generated.json5 ]; then echo "[OK]   OpenClaw-Konfiguration vorhanden"; else echo "[WARN] OpenClaw-Konfiguration fehlt"; fi
if [ "$fail" -ne 0 ]; then echo ""; echo "AI3-Diagnose: mindestens eine Pflichtprüfung ist fehlgeschlagen."; echo "Logs: docker compose logs --tail=150"; exit 1; fi
echo ""; echo "AI3-Diagnose: Pflichtprüfungen erfolgreich. Warnungen bitte vor öffentlicher Mailzustellung prüfen."
