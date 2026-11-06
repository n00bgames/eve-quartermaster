# Application updates from Settings

The host account can select **Check for updates and install** under **Settings → Application Update**, above **SDE Maintenance**. The helper checks `origin/main` for the configured EQM checkout, runs the existing platform update script when a rebuild is needed, and keeps the status through container restarts. A successful install refreshes the tab that started it once the frontend, API and worker are running the requested revision.

## Enable the host helper

Run the normal EQM update once, then run the setup launcher from the checkout on the machine running Docker. Use the same OS account that normally runs EQM. The launcher assumes a running Git-based EQM install with Docker Compose v2.

On Windows, double-click **install-update-helper.bat**, or run it from PowerShell:

```powershell
.\install-update-helper.bat
```

On Linux or macOS, run:

```sh
sh ./install-update-helper.sh
```

Setup reuses Python 3.10 or later. If it is missing, the launcher can install Python with WinGet on Windows, apt or dnf on Linux, or Homebrew on macOS when Homebrew is already installed. The helper uses Python’s standard library. [WinGet install](https://learn.microsoft.com/en-us/windows/package-manager/winget/install) · [Homebrew Python](https://formulae.brew.sh/formula/python@3.13).

The installer enables the Compose overlay in `.env`, preserving the existing configuration, and briefly restarts the backend to apply it. It registers a Windows scheduled task or macOS LaunchAgent for sign-in, or a Linux systemd user service. Linux setup attempts to enable user lingering so the service can keep running after logout. The launcher prints a message if the OS requires you to enable it separately. [systemd user lingering](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html).

After setup reports that the helper is ready, sign in as the EQM host and open **Settings → Application Update**. If the frontend uses a custom local port, pass `--frontend-url http://127.0.0.1:PORT` to the launcher.

## Manual setup

Use these steps for a custom installation or a host without a supported startup manager. Install Python 3.10 or later on the machine that runs Git and Docker. Run one helper per checkout using the checkout owner’s Git and Docker access. Windows uses `update-eqm.bat`. Linux, macOS and WSL use `update-eqm.sh`.

1. Install this EQM version once using your normal host update process.
2. Start the helper from the checkout. It creates its state directories and runs continuously.

   Linux, macOS or WSL

   ```sh
   python3 scripts/eqm_update_agent.py
   ```

   Windows PowerShell

   ```powershell
   py -3 scripts\eqm_update_agent.py
   ```

3. Add the opt-in Compose overlay to the checkout's existing `.env`. Preserve any other Compose files and append `compose.app-update.yml` to the list. For a standard install the entire line is:

   Linux, macOS or WSL

   ```dotenv
   COMPOSE_FILE=docker-compose.yml:compose.app-update.yml
   ```

   Windows

   ```dotenv
   COMPOSE_FILE=docker-compose.yml;compose.app-update.yml
   ```

4. Apply the overlay once with `docker compose up -d --no-deps backend`. Open Settings as the EQM host and look for the enabled update button. Keep the helper running separately from Compose. For persistent operation, run the same command as the checkout owner in a Linux systemd service, macOS LaunchAgent, or Windows Task Scheduler at sign-in. Set its working directory to the checkout. With a custom Compose frontend port, pass `--frontend-url http://127.0.0.1:PORT`.

The helper requires a clean `main` checkout that can fast-forward to its configured `origin/main`. The first check may rebuild the current revision if the running services have no revision recorded. A failed build can be retried after fixing the host problem even if Git has already advanced. The latest build output is in `.eqm-update/update.log` on the host.

The opt-in overlay mounts a writable request inbox and a separate read-only status directory into the API container. The host helper owns Git and Docker access. The API accepts a request ID from the host account and the helper decides which revision and script to run. Removing the overlay and recreating the backend disables the web control.

If EQM remains unavailable after a build, inspect `.eqm-update/update.log` and `docker compose ps` on the host. Check for a still-running update process before retrying an interrupted job. Use the existing host deployment process for upgrades that require changes to the server or Compose configuration.
