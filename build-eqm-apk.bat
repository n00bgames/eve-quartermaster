@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ANDROID_PROJECT=%ROOT%android-eqm"
set "APK_SOURCE=%ANDROID_PROJECT%\app\build\outputs\apk\debug\app-debug.apk"
set "APK_DEST=%ROOT%EQM.apk"

if "%EQM_URL%"=="" set "EQM_URL=http://192.168.0.20:5173/"

if "%ANDROID_HOME%"=="" (
  if not "%LOCALAPPDATA%"=="" if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
)

if "%ANDROID_HOME%"=="" (
  if exist "%USERPROFILE%\AppData\Local\Android\Sdk" set "ANDROID_HOME=%USERPROFILE%\AppData\Local\Android\Sdk"
)

if "%ANDROID_SDK_ROOT%"=="" (
  if not "%ANDROID_HOME%"=="" set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
)

if "%ANDROID_HOME%"=="" (
  echo Android SDK was not found.
  echo Install Android Studio or set ANDROID_HOME to your Android SDK folder.
  exit /b 1
)

if "%COMPILE_SDK%"=="" (
  for /f "tokens=2 delims=-" %%S in ('dir /b /ad "%ANDROID_HOME%\platforms\android-*" 2^>nul ^| findstr /r /c:"^android-[0-9][0-9]*$" ^| sort /r') do if not defined COMPILE_SDK set "COMPILE_SDK=%%S"
)

if "%COMPILE_SDK%"=="" (
  echo No stable integer Android SDK platform was found under:
  echo %ANDROID_HOME%\platforms
  echo Open Android Studio SDK Manager and install a stable Android SDK Platform such as API 35 or 36.
  echo You can also force one with: set COMPILE_SDK=35
  exit /b 1
)

if "%TARGET_SDK%"=="" set "TARGET_SDK=%COMPILE_SDK%"
set "GRADLE_OFFLINE=--offline"
if /I "%EQM_ONLINE%"=="1" set "GRADLE_OFFLINE="

where gradle >nul 2>nul
if errorlevel 1 (
  echo Gradle was not found on PATH.
  echo Install Gradle or run this from an Android Studio terminal with Gradle available.
  exit /b 1
)

where java >nul 2>nul
if errorlevel 1 (
  echo Java was not found on PATH.
  echo Install JDK 17 or newer, then run this again.
  exit /b 1
)

echo Building EVE Quartermaster APK...
echo URL: %EQM_URL%
echo Android SDK: %ANDROID_HOME%
echo Compile SDK: %COMPILE_SDK%
echo.

pushd "%ANDROID_PROJECT%" || exit /b 1
call gradle %GRADLE_OFFLINE% assembleDebug -PEQM_URL="%EQM_URL%" -PCOMPILE_SDK=%COMPILE_SDK% -PTARGET_SDK=%TARGET_SDK%
set "BUILD_EXIT=%ERRORLEVEL%"
popd

if not "%BUILD_EXIT%"=="0" (
  echo.
  echo APK build failed. If Gradle dependencies are missing, rerun with:
  echo set EQM_ONLINE=1
  echo .\build-eqm-apk.bat
  exit /b %BUILD_EXIT%
)

if not exist "%APK_SOURCE%" (
  echo Build finished, but the APK was not found at:
  echo %APK_SOURCE%
  exit /b 1
)

copy /Y "%APK_SOURCE%" "%APK_DEST%" >nul
if errorlevel 1 exit /b 1

echo.
echo Built: %APK_DEST%
endlocal