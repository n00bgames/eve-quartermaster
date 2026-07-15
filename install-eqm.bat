@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
echo.
echo EVE Quartermaster installer
echo ==========================
echo.

call :ensure_windows_prereqs
if errorlevel 1 exit /b 1

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
echo 2. Add EVE Developer Client ID/Secret to .env for live ESI sync.
echo 3. Run sde-fetch.bat to download the latest SDE to .\sde.
echo 4. Import the SDE from Settings -^> SDE Import; see README.md for scope and SDE details.
echo.
exit /b 0

:ensure_windows_prereqs
set "NEED_GIT="
set "NEED_WSL="
set "NEED_DOCKER="
set "MISSING_PREREQS="

where git >nul 2>nul
if errorlevel 1 (
  set "NEED_GIT=1"
  set "MISSING_PREREQS=!MISSING_PREREQS! Git"
)

where wsl >nul 2>nul
if errorlevel 1 (
  set "NEED_WSL=1"
  set "MISSING_PREREQS=!MISSING_PREREQS! WSL2"
) else (
  wsl --status >nul 2>nul
  if errorlevel 1 (
    set "NEED_WSL=1"
    set "MISSING_PREREQS=!MISSING_PREREQS! WSL2"
  )
)

where docker >nul 2>nul
if errorlevel 1 (
  set "NEED_DOCKER=1"
  set "MISSING_PREREQS=!MISSING_PREREQS! Docker-Desktop"
) else (
  docker compose version >nul 2>nul
  if errorlevel 1 (
    docker-compose version >nul 2>nul
    if errorlevel 1 (
      set "NEED_DOCKER=1"
      set "MISSING_PREREQS=!MISSING_PREREQS! Docker-Desktop"
    )
  )
)

if not defined MISSING_PREREQS exit /b 0

echo Missing prerequisites:!MISSING_PREREQS!
echo.
echo This installer can try to install them now:
echo   - Git via winget package Git.Git
echo   - WSL2 via wsl --install
echo   - Docker Desktop via winget package Docker.DockerDesktop
echo.
echo Docker Desktop and WSL may require Administrator approval and a Windows restart.
choice /C YN /N /M "Install missing prerequisites now? [Y/N] "
if errorlevel 2 (
  echo.
  echo Install cancelled. Install the missing prerequisites, start Docker Desktop, then run this script again.
  exit /b 1
)

where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo winget was not found. Install App Installer from Microsoft Store, then rerun this script.
  echo https://learn.microsoft.com/windows/package-manager/winget/
  exit /b 1
)

if defined NEED_GIT (
  call :winget_install Git.Git "Git"
  if errorlevel 1 exit /b 1
)

if defined NEED_WSL (
  call :install_wsl
  if errorlevel 1 exit /b 1
)

if defined NEED_DOCKER (
  call :winget_install Docker.DockerDesktop "Docker Desktop"
  if errorlevel 1 exit /b 1
)

echo.
echo Prerequisite install commands completed.
echo Restart Windows if WSL or Docker Desktop requested it, then open Docker Desktop and rerun this installer.
exit /b 1

:winget_install
set "PACKAGE_ID=%~1"
set "PACKAGE_LABEL=%~2"
echo.
echo Installing %PACKAGE_LABEL%...
winget install --id %PACKAGE_ID% -e --source winget --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
  echo Failed to install %PACKAGE_LABEL% with winget.
  exit /b 1
)
exit /b 0

:install_wsl
echo.
echo Installing WSL2. This may require Administrator approval and a restart.
wsl --install
if errorlevel 1 (
  echo WSL install did not complete. Try running this script as Administrator, or run: wsl --install
  exit /b 1
)
wsl --set-default-version 2 >nul 2>nul
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
