@echo off
setlocal EnableExtensions

cd /d "%~dp0"
echo.
echo EVE Quartermaster installer
echo ==========================
echo.

call :find_compose
if errorlevel 1 exit /b 1

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker was not found. Install Docker Desktop, start it, then run this script again.
  echo https://www.docker.com/products/docker-desktop/
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example.
  ) else (
    echo .env.example was not found. Cannot create local configuration.
    exit /b 1
  )
) else (
  echo Existing .env found; leaving it unchanged.
)

if not exist "sde" (
  mkdir "sde"
  echo Created local sde folder.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='.env'; $t=Get-Content $p -Raw; function New-Key { $bytes = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes); [Convert]::ToBase64String($bytes) }; if ($t -match 'AUTH_SECRET_KEY=change-me') { $t=$t -replace 'AUTH_SECRET_KEY=change-me', ('AUTH_SECRET_KEY=' + (New-Key)) }; if ($t -match 'TOKEN_ENCRYPTION_KEY=\r?\n') { $t=$t -replace 'TOKEN_ENCRYPTION_KEY=\r?\n', ('TOKEN_ENCRYPTION_KEY=' + (New-Key) + [Environment]::NewLine) }; Set-Content -Path $p -Value $t -NoNewline"

echo.
echo Building and starting EQM containers...
%COMPOSE_CMD% up --build -d
if errorlevel 1 (
  echo.
  echo Install failed while starting Docker containers.
  exit /b 1
)

echo.
echo EVE Quartermaster is starting.
echo Frontend: http://localhost:5173
echo Backend health: http://localhost:8000/api/health
echo API docs: http://localhost:8000/docs
echo.
echo Next steps:
echo 1. Open the frontend and create the first admin account.
echo 2. Edit .env with EVE SSO credentials if you want live ESI sync.
echo 3. Put the extracted EVE SDE in .\sde, then import it from Settings.
echo.
exit /b 0

:find_compose
docker compose version >nul 2>nul
if not errorlevel 1 (
  set "COMPOSE_CMD=docker compose"
  exit /b 0
)
docker-compose version >nul 2>nul
if not errorlevel 1 (
  set "COMPOSE_CMD=docker-compose"
  exit /b 0
)
echo Docker Compose was not found. Install Docker Desktop, start it, then run this script again.
echo https://www.docker.com/products/docker-desktop/
exit /b 1
