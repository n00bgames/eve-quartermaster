@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "DEFAULT_SDE_URL=https://developers.eveonline.com/static-data/eve-online-static-data-latest-yaml.zip"
if not defined SDE_URL set "SDE_URL=%DEFAULT_SDE_URL%"
if not defined SDE_DIR set "SDE_DIR=sde"
if not defined SDE_ZIP_NAME set "SDE_ZIP_NAME=sde.zip"
set "SDE_ZIP_PATH=%SDE_DIR%\%SDE_ZIP_NAME%"
set "EXTRACT_SDE=0"
set "HELP_REQUESTED=0"

if /i "%~1"=="extract" set "EXTRACT_SDE=1"
if /i "%~1"=="--extract" set "EXTRACT_SDE=1"
if /i "%~1"=="/extract" set "EXTRACT_SDE=1"
if /i "%~1"=="-x" set "EXTRACT_SDE=1"
if /i "%~1"=="help" set "HELP_REQUESTED=1" & goto :usage
if /i "%~1"=="--help" set "HELP_REQUESTED=1" & goto :usage
if /i "%~1"=="/help" set "HELP_REQUESTED=1" & goto :usage

if not "%~2"=="" goto :usage
if not "%~1"=="" if "%EXTRACT_SDE%"=="0" goto :usage

echo.
echo EVE Quartermaster SDE fetch
echo ============================
echo Source: %SDE_URL%
echo Target: %SDE_ZIP_PATH%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $dir = $env:SDE_DIR; $zip = $env:SDE_ZIP_PATH; New-Item -ItemType Directory -Force -Path $dir | Out-Null; Invoke-WebRequest -Uri $env:SDE_URL -OutFile $zip; if ($env:EXTRACT_SDE -eq '1') { Expand-Archive -Path $zip -DestinationPath $dir -Force }"
if errorlevel 1 (
  echo.
  echo SDE download failed.
  exit /b 1
)

echo.
echo SDE zip saved to %SDE_ZIP_PATH%.
if "%EXTRACT_SDE%"=="1" (
  echo Extracted SDE files into %SDE_DIR%.
  echo Import path in EQM: /sde
) else (
  echo Import path in EQM: /sde/%SDE_ZIP_NAME%
  echo Optional extract mode: sde-fetch.bat extract
)
echo.
exit /b 0

:usage
echo.
echo Usage: sde-fetch.bat [extract]
echo.
echo Downloads the latest Tranquility EVE SDE zip into .\sde by default.
echo.
echo Optional environment overrides:
echo   SDE_URL       Download URL. Default: %DEFAULT_SDE_URL%
echo   SDE_DIR       Target folder. Default: sde
echo   SDE_ZIP_NAME  Target zip filename. Default: sde.zip
echo.
if "%HELP_REQUESTED%"=="1" exit /b 0
exit /b 1
