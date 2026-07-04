#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

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
git pull --ff-only

echo
echo "Rebuilding containers..."
$COMPOSE up --build -d

echo
echo "Update complete."
echo "Frontend: http://localhost:5173"
echo "Backend health: http://localhost:8000/api/health"
echo
