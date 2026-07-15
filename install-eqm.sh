#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "This installer needs sudo to install missing Linux prerequisites."
    exit 1
  fi
fi

echo
echo "EVE Quartermaster installer"
echo "=========================="
echo

prompt_yes_no() {
  printf "%s [y/N] " "$1"
  read answer || answer=""
  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

find_compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
    return 0
  fi

  if [ -n "$SUDO" ] && command -v docker >/dev/null 2>&1 && $SUDO docker compose version >/dev/null 2>&1; then
    COMPOSE="$SUDO docker compose"
    return 0
  fi

  return 1
}

install_base_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y git curl ca-certificates
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y git curl ca-certificates
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y git curl ca-certificates
  elif command -v zypper >/dev/null 2>&1; then
    $SUDO zypper --non-interactive install git curl ca-certificates
  elif command -v pacman >/dev/null 2>&1; then
    $SUDO pacman -Sy --needed --noconfirm git curl ca-certificates
  elif command -v apk >/dev/null 2>&1; then
    $SUDO apk add --no-cache git curl ca-certificates
  else
    echo "No supported package manager found. Install git, curl, Docker Engine, and Docker Compose manually."
    exit 1
  fi
}

install_docker_engine() {
  if find_compose; then
    return 0
  fi

  if ! command -v curl >/dev/null 2>&1; then
    install_base_packages
  fi

  echo
  echo "Installing Docker Engine and Docker Compose plugin using Docker's official convenience script..."
  tmp_docker_script="$(mktemp)"
  curl -fsSL https://get.docker.com -o "$tmp_docker_script"
  $SUDO sh "$tmp_docker_script"
  rm -f "$tmp_docker_script"

  if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable --now docker >/dev/null 2>&1 || $SUDO systemctl start docker >/dev/null 2>&1 || true
  elif command -v service >/dev/null 2>&1; then
    $SUDO service docker start >/dev/null 2>&1 || true
  fi

  if [ -n "$SUDO" ] && [ -n "${USER:-}" ] && command -v getent >/dev/null 2>&1 && getent group docker >/dev/null 2>&1; then
    $SUDO usermod -aG docker "$USER" >/dev/null 2>&1 || true
    echo "Added $USER to the docker group. Open a new terminal after install to use docker without sudo."
  fi
}

ensure_linux_prereqs() {
  missing=""

  if ! command -v git >/dev/null 2>&1; then
    missing="$missing git"
  fi

  if ! find_compose; then
    missing="$missing Docker-Engine-and-Compose"
  fi

  if [ -z "$missing" ]; then
    return 0
  fi

  echo "Missing prerequisites:$missing"
  echo
  echo "This installer can try to install them now."
  echo "Supported package managers for Git/curl: apt, dnf, yum, zypper, pacman, apk."
  echo "Docker will be installed with Docker's official Linux convenience script when needed."
  echo

  if ! prompt_yes_no "Install missing Linux prerequisites now?"; then
    echo "Install cancelled. Install git and Docker Compose, then rerun this script."
    exit 1
  fi

  if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
    install_base_packages
  fi

  if ! find_compose; then
    install_docker_engine
  fi

  if ! find_compose; then
    echo "Docker Compose still was not found. Start Docker, open a new terminal if group membership changed, then rerun this script."
    exit 1
  fi
}

ensure_linux_prereqs

if ! find_compose; then
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
echo "2. Add EVE Developer Client ID/Secret to .env for live ESI sync."
echo "3. Run ./sde-fetch.sh to download the latest SDE to ./sde."
echo "4. Import the SDE from Settings -> SDE Import; see README.md for scope and SDE details."
echo
