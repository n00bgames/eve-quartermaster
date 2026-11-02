#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

usage() {
  echo "Usage: sh restart-eqm.sh [--worker]"
  echo "Restart existing backend and frontend containers without pulling or rebuilding."
  echo "--worker also restarts the queue worker and can interrupt its current job."
  echo "PostgreSQL and Redis are left running."
}

services="backend frontend"
case "${1:-}" in
  --help|-h) usage; exit 0 ;;
  --worker) services="$services worker" ;;
  "") ;;
  *) usage >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then usage >&2; exit 2; fi

if [ ! -f docker-compose.yml ] || [ ! -f scripts/check-eqm-ready.py ]; then
  echo "Run this helper from a complete EQM installation." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Install and start Docker first." >&2
  exit 1
fi
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose was not found." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is unavailable. Check the daemon and your Docker permissions." >&2
  exit 1
fi

# Validate every selected service before restarting any of them.
for service in $services; do
  container_id=$($COMPOSE ps -a -q "$service")
  if [ -z "$container_id" ]; then
    echo "No existing $service container. Use install/rebuild to create the stack." >&2
    exit 1
  fi
done

echo "Restarting EQM: $services (30-second stop grace period)."
if ! $COMPOSE restart -t 30 $services; then
  echo "Restart failed. Inspect 'docker compose ps --all' and the selected service logs." >&2
  exit 1
fi

# Run the host checkout's probe inside the existing backend: no host Python required.
if ! $COMPOSE exec -T backend python -u - < scripts/check-eqm-ready.py; then
  echo "Containers were restarted, but EQM readiness could not be confirmed." >&2
  echo "Inspect 'docker compose ps --all' and 'docker compose logs --tail=100 backend frontend'." >&2
  exit 1
fi
echo "EQM restart complete. Frontend: http://localhost:5173"
