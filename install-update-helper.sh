#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if [ "$(id -u)" -eq 0 ]; then
  echo "Run this launcher as the account that normally runs EQM, without sudo." >&2
  exit 1
fi

python_ready() {
  command -v "$1" >/dev/null 2>&1 &&
    "$1" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'
}

as_root() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Install Python 3.10 or newer using your system package manager, then run this again." >&2
    exit 1
  fi
}

for python in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
  if python_ready "$python"; then
    exec "$python" scripts/setup_eqm_update.py "$@"
  fi
done

echo "Installing Python for the EQM update helper..."
if [ "$(uname -s)" = Darwin ]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Install Python 3.10 or newer from https://www.python.org/downloads/ and run this again." >&2
    exit 1
  fi
  brew install python@3.13
  exec "$(brew --prefix python@3.13)/bin/python3.13" scripts/setup_eqm_update.py "$@"
elif command -v apt-get >/dev/null 2>&1; then
  as_root apt-get update
  as_root apt-get install -y python3
elif command -v dnf >/dev/null 2>&1; then
  as_root dnf install -y python3
else
  echo "Install Python 3.10 or newer using your system package manager, then run this again." >&2
  exit 1
fi

if ! python_ready python3; then
  echo "Your package manager did not provide Python 3.10 or newer. Install a supported Python and run this again." >&2
  exit 1
fi
exec python3 scripts/setup_eqm_update.py "$@"
