#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

DEFAULT_SDE_URL="https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip"
SDE_URL="${SDE_URL:-$DEFAULT_SDE_URL}"
SDE_DIR="${SDE_DIR:-sde}"
SDE_ZIP_NAME="${SDE_ZIP_NAME:-sde.zip}"
SDE_ZIP_PATH="$SDE_DIR/$SDE_ZIP_NAME"
EXTRACT_SDE=0

usage() {
  echo
  echo "Usage: ./sde-fetch.sh [extract]"
  echo
  echo "Downloads the latest Tranquility EVE SDE zip into ./sde by default."
  echo
  echo "Optional environment overrides:"
  echo "  SDE_URL       Download URL. Default: $DEFAULT_SDE_URL"
  echo "  SDE_DIR       Target folder. Default: sde"
  echo "  SDE_ZIP_NAME  Target zip filename. Default: sde.zip"
  echo
}

case "${1:-}" in
  "") ;;
  extract|--extract|-x) EXTRACT_SDE=1 ;;
  help|--help|-h) usage; exit 0 ;;
  *) usage; exit 1 ;;
esac

if [ "${2:-}" != "" ]; then
  usage
  exit 1
fi

echo
echo "EVE Quartermaster SDE fetch"
echo "============================"
echo "Source: $SDE_URL"
echo "Target: $SDE_ZIP_PATH"
echo

mkdir -p "$SDE_DIR"

if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 --retry-delay 2 "$SDE_URL" -o "$SDE_ZIP_PATH"
elif command -v wget >/dev/null 2>&1; then
  wget -O "$SDE_ZIP_PATH" "$SDE_URL"
else
  echo "curl or wget is required to download the SDE."
  exit 1
fi

if [ "$EXTRACT_SDE" = "1" ]; then
  if command -v unzip >/dev/null 2>&1; then
    unzip -o "$SDE_ZIP_PATH" -d "$SDE_DIR"
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$SDE_ZIP_PATH" "$SDE_DIR" <<'PY'
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
target = Path(sys.argv[2])
with zipfile.ZipFile(zip_path) as archive:
    archive.extractall(target)
PY
  else
    echo "unzip or python3 is required for extract mode. The zip was still downloaded."
    exit 1
  fi
fi

echo
echo "SDE zip saved to $SDE_ZIP_PATH."
if [ "$EXTRACT_SDE" = "1" ]; then
  echo "Extracted SDE files into $SDE_DIR."
  echo "Import path in EQM: /sde"
else
  echo "Import path in EQM: /sde/$SDE_ZIP_NAME"
  echo "Optional extract mode: ./sde-fetch.sh extract"
fi
echo
