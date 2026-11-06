@echo off
setlocal EnableExtensions DisableDelayedExpansion

if not defined EQM_UPDATE_ROOT set "EQM_UPDATE_ROOT=%~dp0"
cd /d "%EQM_UPDATE_ROOT%" || exit /b 1
echo.
echo Updating EVE Quartermaster from GitHub...
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo Git was not found. Install Git, then run this script again.
  exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
  echo This folder is not a Git checkout. Clone https://github.com/n00bgames/eve-quartermaster first.
  exit /b 1
)

call :find_compose
if errorlevel 1 exit /b 1

if defined EQM_UPDATE_TARGET (
  git merge --ff-only -- "%EQM_UPDATE_TARGET%"
) else (
  git pull --ff-only
)
if errorlevel 1 (
  echo.
  echo Update stopped because Git could not fast-forward cleanly.
  exit /b 1
)

set "EQM_UPDATE_REVISION="
for /f "delims=" %%R in ('git rev-parse HEAD') do set "EQM_UPDATE_REVISION=%%R"
if not defined EQM_UPDATE_REVISION exit /b 1
%COMPOSE_CMD% up --build -d
if errorlevel 1 exit /b %errorlevel%

echo.
echo Update complete.
echo Frontend: http://localhost:5173
echo Backend health: http://localhost:8000/api/health
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
exit /b 1
