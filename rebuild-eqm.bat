@echo off
setlocal EnableExtensions

cd /d "%~dp0"
echo.
echo Rebuilding EVE Quartermaster containers...
echo.

call :find_compose
if errorlevel 1 exit /b 1

%COMPOSE_CMD% up --build -d
if errorlevel 1 exit /b 1

echo.
echo Rebuild complete.
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
