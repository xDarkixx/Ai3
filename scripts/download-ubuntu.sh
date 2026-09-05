#!/usr/bin/env bash
set -euo pipefail

# Official Ubuntu Server image helper for the AI3 target platform.
# Downloads only from releases.ubuntu.com and verifies SHA256 before accepting the ISO.
VERSION="24.04.4"
ARCH="amd64"
BASE="https://releases.ubuntu.com/24.04"
ISO="ubuntu-${VERSION}-live-server-${ARCH}.iso"
OUT_DIR="${1:-$PWD/downloads}"
mkdir -p "$OUT_DIR"

command -v curl >/dev/null 2>&1 || { echo "Fehlt: curl"; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo "Fehlt: sha256sum"; exit 1; }

cd "$OUT_DIR"
echo "Ubuntu Server ${VERSION} ${ARCH}"
echo "Quelle: ${BASE}/${ISO}"

echo "[1/2] Lade SHA256SUMS ..."
curl -fL --retry 3 --retry-delay 2 -o SHA256SUMS "${BASE}/SHA256SUMS"

echo "[2/2] Lade ISO ..."
curl -fL --retry 3 --retry-delay 2 -o "$ISO" "${BASE}/${ISO}"

echo "Prüfe SHA256 ..."
grep "  ${ISO}$" SHA256SUMS | sha256sum -c -

echo
echo "Fertig und verifiziert: $OUT_DIR/$ISO"
