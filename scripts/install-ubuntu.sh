#!/usr/bin/env bash
set -euo pipefail
if [ "${EUID:-$(id -u)}" -ne 0 ]; then command -v sudo >/dev/null 2>&1 || { echo "sudo fehlt."; exit 1; }; exec sudo -E bash "$0" "$@"; fi
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT_DIR"
[ -r /etc/os-release ] || exit 1
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo "AI3 One-Click benötigt Ubuntu."; exit 1; }
MAJOR="${VERSION_ID%%.*}"; MINOR="${VERSION_ID#*.}"
case "$MAJOR" in 24|25|26) ;; *) echo "Nicht unterstützte Ubuntu-Version: ${VERSION_ID:-unbekannt}. Unterstützt werden aktuelle Ubuntu-Releases ab 24.04."; exit 1;; esac
if [ "$MAJOR" -eq 24 ] && [ "${MINOR%%.*}" -lt 4 ]; then echo "Ubuntu ${VERSION_ID} ist zu alt. Unterstützt werden Ubuntu 24.04+."; exit 1; fi

echo "AI3: Ubuntu ${VERSION_ID} erkannt."

# Pull in every host dependency AI3 itself requires. This is safe to run again
# during later installs/repairs: it installs missing packages but does not
# overwrite the user's AI3 data.
chmod +x scripts/ensure-host-deps.sh
./scripts/ensure-host-deps.sh

docker compose version >/dev/null
docker info >/dev/null
GPU_COMPOSE_READY=0
if command -v nvidia-smi >/dev/null 2>&1 && command -v nvidia-ctk >/dev/null 2>&1; then
  if docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then GPU_COMPOSE_READY=1; fi
fi
export AI3_USE_GPU="$GPU_COMPOSE_READY"
mkdir -p openclaw runtime
chmod +x scripts/*.sh 2>/dev/null || true
./scripts/setup-local.sh
# Run exactly one training backend: CUDA GPU when available, otherwise CPU+RAM.
if [ "$GPU_COMPOSE_READY" -eq 1 ]; then
  docker compose --profile cpu down --remove-orphans ai3-training-worker-cpu >/dev/null 2>&1 || true
  docker compose --profile gpu up -d --build ai3-training-worker
  echo "AI3 Training: NVIDIA GPU + system RAM/CPU available."
else
  docker compose --profile gpu down --remove-orphans ai3-training-worker >/dev/null 2>&1 || true
  docker compose --profile cpu up -d --build ai3-training-worker-cpu
  echo "AI3 Training: CPU + system RAM mode."
fi
./scripts/doctor.sh || true
./scripts/open-web-ui.sh || true
echo "AI3 One-Click abgeschlossen. Control Center wurde geöffnet, sofern eine grafische Ubuntu-Sitzung vorhanden ist."
