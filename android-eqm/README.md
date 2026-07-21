# EVE Quartermaster Android Wrapper

This is a minimal sideloadable Android WebView shell for EVE Quartermaster. It loads the hosted EQM site and keeps the mobile entry point branded as **EVE Quartermaster**.

On first launch, enter the URL where the device can reach EQM. The app stores that URL locally. Use the settings button in the upper-right corner at any time to switch to another installation without rebuilding the APK.

## Build

From the repository root on Windows:

```bat
build-eqm-apk.bat
```

The script copies the debug APK to:

```text
EQM.apk
```

## Optional overrides

Build against a different EQM URL:

```bat
set EQM_URL=https://your-eqm-host.example/
build-eqm-apk.bat
```

The build-time URL is now the first-launch default, not a permanent lock. It is also available through **Build default** in Server Settings.

Allow Gradle to download missing dependencies instead of using the local cache only:

```bat
set EQM_ONLINE=1
build-eqm-apk.bat
```

Force a specific installed Android SDK platform:

```bat
set COMPILE_SDK=35
set TARGET_SDK=35
build-eqm-apk.bat
```