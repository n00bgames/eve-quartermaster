#!/usr/bin/env sh
set -eu

cd "${EQM_UPDATE_ROOT:-$(dirname "$0")}"

if [ "$(id -u)" -eq 0 ]; then
  echo "Run EQM updates as the checkout owner, without sudo or root." >&2
  exit 1
fi

# Check all source parents and Git metadata before a merge can partly apply.
EQM_CHECK_PYTHON=${EQM_UPDATE_PYTHON:-python3}
if ! command -v "$EQM_CHECK_PYTHON" >/dev/null 2>&1; then
  echo "Python 3.10+ is required for the checkout permission check. Install it and retry." >&2
  exit 1
fi
"$EQM_CHECK_PYTHON" scripts/eqm_checkout.py

if ! command -v git >/dev/null 2>&1; then
  echo "Git was not found. Install Git, then run this script again."
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "This folder is not a Git checkout. Clone https://github.com/n00bgames/eve-quartermaster first."
  exit 1
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose was not found. Install Docker, start it, then run this script again."
  exit 1
fi

echo
echo "Updating EVE Quartermaster from GitHub..."
if [ -n "${EQM_UPDATE_TARGET:-}" ]; then
  git merge --ff-only -- "$EQM_UPDATE_TARGET"
else
  git pull --ff-only
fi
EQM_UPDATE_REVISION=$(git rev-parse HEAD)
export EQM_UPDATE_REVISION

echo
echo "Rebuilding containers..."
$COMPOSE up --build -d

echo
echo "Update complete."
echo "Frontend: http://localhost:5173"
echo "Backend health: http://localhost:8000/api/health"
echo
