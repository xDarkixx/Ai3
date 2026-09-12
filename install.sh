#!/usr/bin/env bash
set -euo pipefail

# AI3 self-bootstrapping installer.
# Run this on a fresh Ubuntu machine; it downloads the current repository,
# installs missing host dependencies, and starts the normal AI3 installer.

REPO_URL="${AI3_REPO_URL:-https://github.com/xDarkixx/Ai3.git}"
BRANCH="${AI3_INSTALL_BRANCH:-main}"
TARGET="${AI3_INSTALL_DIR:-/opt/ai3}"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { echo "AI3: sudo fehlt."; exit 1; }
  exec sudo -E bash "$0" "$@"
fi

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

apt-get update
apt-get install -y ca-certificates curl git

if [ -d "$TARGET/.git" ]; then
  git -C "$TARGET" fetch --quiet origin "$BRANCH"
  git -C "$TARGET" checkout -q "$BRANCH"
  git -C "$TARGET" reset --hard "origin/$BRANCH"
else
  mkdir -p "$(dirname "$TARGET")"
  rm -rf "$TARGET"
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$TARGET"
fi

cd "$TARGET"
chmod +x scripts/*.sh install.sh 2>/dev/null || true
exec "$TARGET/scripts/install-ubuntu.sh"
