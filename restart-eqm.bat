@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 exit /b 1

set "SERVICES=backend frontend"
if /I "%~1"=="--help" goto help
if /I "%~1"=="-h" goto help
if /I "%~1"=="--worker" (
  set "SERVICES=backend frontend worker"
) else if not "%~1"=="" (
  call :usage
  exit /b 2
)
if not "%~2"=="" (
  call :usage
  exit /b 2
)

if not exist "docker-compose.yml" goto incomplete
if not exist "scripts\check-eqm-ready.py" goto incomplete
where docker >nul 2>nul
if errorlevel 1 (
  echo Docker was not found. Install and start Docker Desktop first.
  exit /b 1
)
call :find_compose
if errorlevel 1 exit /b 1
docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is unavailable. Check Docker Desktop and your Docker permissions.
  exit /b 1
)

for %%S in (%SERVICES%) do (
  call :check_service %%S
  if errorlevel 1 exit /b 1
)

echo Restarting EQM: %SERVICES% ^(30-second stop grace period^).
%COMPOSE_CMD% restart -t 30 %SERVICES%
if errorlevel 1 (
  echo Restart failed. Inspect docker compose ps --all and the selected service logs.
  exit /b 1
)
%COMPOSE_CMD% exec -T backend python -u - < "scripts\check-eqm-ready.py"
if errorlevel 1 (
  echo Containers were restarted, but EQM readiness could not be confirmed.
  echo Inspect docker compose ps --all and docker compose logs --tail=100 backend frontend.
  exit /b 1
)
echo EQM restart complete. Frontend: http://localhost:5173
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
echo Docker Compose was not found.
exit /b 1

:check_service
set "CONTAINER_ID="
for /f "delims=" %%I in ('%COMPOSE_CMD% ps -a -q "%~1"') do set "CONTAINER_ID=%%I"
if not defined CONTAINER_ID (
  echo No existing %~1 container. Use install/rebuild to create the stack.
  exit /b 1
)
exit /b 0

:incomplete
echo Run this helper from a complete EQM installation.
exit /b 1

:help
call :usage
exit /b 0

:usage
echo Usage: restart-eqm.bat [--worker]
echo Restart existing backend and frontend containers without pulling or rebuilding.
echo --worker also restarts the queue worker and can interrupt its current job.
echo PostgreSQL and Redis are left running.
exit /b 0
