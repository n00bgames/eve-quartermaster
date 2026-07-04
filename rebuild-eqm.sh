#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose was not found. Install Docker, start it, then run this script again."
  exit 1
fi

echo
echo "Rebuilding EVE Quartermaster containers..."
$COMPOSE up --build -d

echo
echo "Rebuild complete."
echo "Frontend: http://localhost:5173"
echo "Backend health: http://localhost:8000/api/health"
echo
