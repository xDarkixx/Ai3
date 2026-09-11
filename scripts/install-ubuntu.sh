#!/usr/bin/env bash
set -euo pipefail
if [ "${EUID:-$(id -u)}" -ne 0 ]; then command -v sudo >/dev/null 2>&1 || { echo "sudo fehlt."; exit 1; }; exec sudo -E bash "$0" "$@"; fi
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT_DIR"
[ -r /etc/os-release ] || exit 1
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || { echo "AI3 One-Click benötigt Ubuntu 24.04 LTS."; exit 1; }
apt-get update
apt-get install -y ca-certificates curl git python3 gnupg2 iproute2 xdg-utils
if ! command -v docker >/dev/null 2>&1; then
 install -m 0755 -d /etc/apt/keyrings
 curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
 chmod a+r /etc/apt/keyrings/docker.asc
 tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
 apt-get update
 apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker compose version >/dev/null
docker info >/dev/null
GPU_COMPOSE_READY=0
if command -v nvidia-smi >/dev/null 2>&1; then
 if ! command -v nvidia-ctk >/dev/null 2>&1; then
  mkdir -p /usr/share/keyrings
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  apt-get update && apt-get install -y nvidia-container-toolkit || true
 fi
 if command -v nvidia-ctk >/dev/null 2>&1 && nvidia-ctk runtime configure --runtime=docker; then systemctl restart docker; fi
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
