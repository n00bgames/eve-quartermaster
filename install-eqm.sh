#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

echo
echo "EVE Quartermaster installer"
echo "=========================="
echo

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose was not found. Install Docker Desktop or Docker Engine with Compose, then run this script again."
  echo "https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Install Docker, start it, then run this script again."
  exit 1
fi

if [ ! -f ".env" ]; then
  if [ ! -f ".env.example" ]; then
    echo ".env.example was not found. Cannot create local configuration."
    exit 1
  fi
  cp ".env.example" ".env"
  echo "Created .env from .env.example."
else
  echo "Existing .env found; leaving it unchanged."
fi

mkdir -p sde

make_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())'
  else
    date | cksum | awk '{print $1}'
  fi
}

AUTH_KEY="$(make_key)"
TOKEN_KEY="$(make_key)"
tmp_env="$(mktemp)"
awk -v auth="$AUTH_KEY" -v token="$TOKEN_KEY" '
  /^AUTH_SECRET_KEY=change-me$/ { print "AUTH_SECRET_KEY=" auth; next }
  /^TOKEN_ENCRYPTION_KEY=$/ { print "TOKEN_ENCRYPTION_KEY=" token; next }
  { print }
' .env > "$tmp_env"
mv "$tmp_env" .env

echo
echo "Building and starting EQM containers..."
$COMPOSE up --build -d

echo
echo "EVE Quartermaster is starting."
echo "Frontend: http://localhost:5173"
echo "Backend health: http://localhost:8000/api/health"
echo "API docs: http://localhost:8000/docs"
echo
echo "Next steps:"
echo "1. Open the frontend and create the first admin account."
echo "2. Edit .env with EVE SSO credentials if you want live ESI sync."
echo "3. Put the extracted EVE SDE in ./sde, then import it from Settings."
echo
