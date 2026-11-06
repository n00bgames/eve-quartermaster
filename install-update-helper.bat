@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1

call :find_python
if not defined EQM_SETUP_PYTHON (
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Install Python 3.10 or newer from https://www.python.org/downloads/ and run this again.
    goto failed
  )
  echo Installing Python for the EQM update helper...
  winget install --id Python.Python.3.13 --exact --source winget --scope user
  call :find_python
)
if not defined EQM_SETUP_PYTHON (
  echo Python 3.10 or newer was not found. Open a new terminal and run this installer again.
  goto failed
)
"%EQM_SETUP_PYTHON%" scripts\setup_eqm_update.py %*
if errorlevel 1 goto failed
echo.
pause
exit /b 0

:failed
echo.
pause
exit /b 1

:find_python
set "EQM_SETUP_PYTHON="
where py >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable) if sys.version_info >= (3, 10) else None" 2^>nul') do call :check_python "%%P"
)
if defined EQM_SETUP_PYTHON exit /b 0
call :check_python "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if defined EQM_SETUP_PYTHON exit /b 0
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
  if /i not "%%~dpP"=="%LOCALAPPDATA%\Microsoft\WindowsApps\" call :check_python "%%P"
)
exit /b 0

:check_python
if defined EQM_SETUP_PYTHON exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if not errorlevel 1 set "EQM_SETUP_PYTHON=%~1"
exit /b 0
