#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
RUNTIME_DIR="$ROOT_DIR/runtime"
STATUS_FILE="$RUNTIME_DIR/update-status.json"
CONFIG_FILE="$RUNTIME_DIR/update-config.json"
REQUEST_FILE="$RUNTIME_DIR/update-request"
LOCK_FILE="$RUNTIME_DIR/.update.lock"
BRANCH="${AI3_UPDATE_BRANCH:-main}"

mkdir -p "$RUNTIME_DIR"
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

write_status() {
  local state="$1" message="$2" current="${3:-}" remote="${4:-}"
  python3 - "$STATUS_FILE" "$state" "$message" "$current" "$remote" <<'PY'
import json,sys
from datetime import datetime,timezone
path,state,message,current,remote=sys.argv[1:]
data={"state":state,"message":message,"current_sha":current,"remote_sha":remote,"updated_at":datetime.now(timezone.utc).isoformat()}
open(path,"w",encoding="utf-8").write(json.dumps(data,indent=2)+"\n")
PY
}

current_sha="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
write_status "checking" "Prüfe GitHub auf ein neues AI3-Release." "$current_sha" ""

if ! git diff --quiet || ! git diff --cached --quiet; then
  write_status "blocked" "Lokale Änderungen erkannt. Automatisches Update wurde sicher übersprungen." "$current_sha" ""
  exit 0
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  write_status "error" "Git-Remote 'origin' fehlt." "$current_sha" ""
  exit 1
fi

if ! git fetch --quiet origin "$BRANCH"; then
  write_status "error" "GitHub konnte nicht erreicht werden." "$current_sha" ""
  exit 1
fi

remote_sha="$(git rev-parse "origin/$BRANCH")"
if [ "$current_sha" = "$remote_sha" ]; then
  rm -f "$REQUEST_FILE"
  write_status "up-to-date" "AI3 ist bereits aktuell." "$current_sha" "$remote_sha"
  exit 0
fi

auto_enabled=0
if [ -f "$CONFIG_FILE" ]; then
  auto_enabled="$(python3 - "$CONFIG_FILE" <<'PY'
import json,sys
try:
    print(1 if json.load(open(sys.argv[1],encoding='utf-8')).get('auto_update',False) else 0)
except Exception:
    print(0)
PY
  )"
fi
if [ ! -f "$REQUEST_FILE" ] && [ "$auto_enabled" != "1" ]; then
  write_status "available" "Ein Update ist verfügbar. Automatische Updates sind deaktiviert." "$current_sha" "$remote_sha"
  exit 0
fi

previous_sha="$current_sha"
write_status "updating" "Update von $previous_sha auf $remote_sha wird installiert." "$current_sha" "$remote_sha"

if ! git pull --ff-only origin "$BRANCH"; then
  git reset --hard "$previous_sha" >/dev/null 2>&1 || true
  write_status "error" "Git-Update fehlgeschlagen; vorheriger Stand wurde wiederhergestellt." "$previous_sha" "$remote_sha"
  exit 1
fi

if ! docker compose config -q; then
  git reset --hard "$previous_sha" >/dev/null 2>&1 || true
  write_status "error" "Docker-Compose-Konfiguration ungültig; Rollback ausgeführt." "$previous_sha" "$remote_sha"
  exit 1
fi

if ! docker compose up -d --build; then
  git reset --hard "$previous_sha" >/dev/null 2>&1 || true
  docker compose up -d --build >/dev/null 2>&1 || true
  write_status "error" "Docker-Stack konnte nach dem Update nicht gestartet werden; Rollback ausgeführt." "$previous_sha" "$remote_sha"
  exit 1
fi

# Keep exactly one training backend active. The installer may have selected GPU
# mode, while older installations may only expose the hardware at update time.
TRAINING_MODE="cpu"
if [ "${AI3_USE_GPU:-}" = "1" ]; then
  TRAINING_MODE="gpu"
elif [ "${AI3_USE_GPU:-}" != "0" ] && command -v nvidia-smi >/dev/null 2>&1; then
  if docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then
    TRAINING_MODE="gpu"
  fi
fi

if [ "$TRAINING_MODE" = "gpu" ]; then
  docker compose --profile cpu stop ai3-training-worker-cpu >/dev/null 2>&1 || true
  docker compose --profile cpu rm -f ai3-training-worker-cpu >/dev/null 2>&1 || true
  if ! docker compose --profile gpu up -d --build ai3-training-worker; then
    git reset --hard "$previous_sha" >/dev/null 2>&1 || true
    docker compose --profile gpu up -d --build ai3-training-worker >/dev/null 2>&1 || true
    write_status "error" "GPU-Training-Worker konnte nach dem Update nicht gestartet werden; Rollback ausgeführt." "$previous_sha" "$remote_sha"
    exit 1
  fi
else
  docker compose --profile gpu stop ai3-training-worker >/dev/null 2>&1 || true
  docker compose --profile gpu rm -f ai3-training-worker >/dev/null 2>&1 || true
  if ! docker compose --profile cpu up -d --build ai3-training-worker-cpu; then
    git reset --hard "$previous_sha" >/dev/null 2>&1 || true
    docker compose --profile cpu up -d --build ai3-training-worker-cpu >/dev/null 2>&1 || true
    write_status "error" "CPU-Training-Worker konnte nach dem Update nicht gestartet werden; Rollback ausgeführt." "$previous_sha" "$remote_sha"
    exit 1
  fi
fi

healthy=0
for _ in $(seq 1 36); do
  if curl -kfsS --max-time 3 https://localhost/health >/dev/null 2>&1; then healthy=1; break; fi
  sleep 5
done

if [ "$healthy" -ne 1 ]; then
  git reset --hard "$previous_sha" >/dev/null 2>&1 || true
  docker compose up -d --build >/dev/null 2>&1 || true
  write_status "error" "Healthcheck nach dem Update fehlgeschlagen; Rollback ausgeführt." "$previous_sha" "$remote_sha"
  exit 1
fi

rm -f "$REQUEST_FILE"
new_sha="$(git rev-parse HEAD)"
write_status "updated" "AI3 wurde erfolgreich aktualisiert ($TRAINING_MODE-Training)." "$new_sha" "$new_sha"
