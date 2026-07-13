<p align="center">
  <img src="static/eqm-logo.png" alt="EVE Quartermaster" width="900">
</p>

<p align="center">
  <a href="https://github.com/n00bgames/eve-quartermaster"><img alt="Project" src="https://img.shields.io/badge/project-eve--quartermaster-e8b84d?style=for-the-badge"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.7--beta-4fb3c7?style=for-the-badge">
  <img alt="License" src="https://img.shields.io/badge/license-AGPL--3.0--or--later-70c894?style=for-the-badge">
</p>

<p align="center">
  <img alt="Backend" src="https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square">
  <img alt="Frontend" src="https://img.shields.io/badge/frontend-React%20%2B%20Vite-646cff?style=flat-square">
  <img alt="Database" src="https://img.shields.io/badge/database-PostgreSQL-4169e1?style=flat-square">
  <img alt="Runtime" src="https://img.shields.io/badge/runtime-Docker%20Compose-2496ed?style=flat-square">
  <img alt="EVE ESI" src="https://img.shields.io/badge/EVE-ESI%20SSO-c23b22?style=flat-square">
  <img alt="Android" src="https://img.shields.io/badge/android-WebView%20APK-3ddc84?style=flat-square">
</p>

# EVE Quartermaster

**EVE is Excel in a flight suit.**

EVE Quartermaster is a containerized, database-first EVE Online quartermaster and alliance operations tool. It tracks characters, corporations, assets, blueprints, recipes, skills, standings/contact sync, wallet snapshots, permissions, audit events, and long-term analytics from EVE ESI plus imported SDE data.

This is an early beta candidate for private/public testing. It is already useful, but the data model and API surface are still moving quickly.

See [CHANGELOG.md](CHANGELOG.md) for version-by-version release notes.

## Current Capabilities

- Account login, first-admin bootstrap, role management, one-time invite links, and per-section permissions.
- EVE SSO linking for characters, with linked-character ownership, unlinking, scope checks, and privacy controls.
- Character asset sync, corporation asset sync, corporation blueprint sync, corporation wallet division sync, and skill sync.
- Asset ledger with sortable columns, fast dropdown filters, partial search, click-to-filter cells, CSV export, and Janice-friendly copy output.
- Blueprint and recipe views powered by SDE import, with BPO/BPC filters, ME/TE badges, owner filters, sortable blueprint lists, and recipe detail modals.
- Corporation page with enrolled corporations, CEO/member metadata where available, sync status, wallet divisions, and eligible sync characters.
- Roster page for corporation-grouped character display.
- Contact/standing propagation tools using writable ESI character contacts.
- Notifications, private messages, and admin audit log for sync transparency.
- Historical analytics foundation with snapshot runs, metric metadata/versioning, baseline-aware deltas, exports, and composable widgets.
- Navigation suite with SDE-backed route planning, gatecheck summaries, operational starmap rendering, and security-status color coding.
- Hauling intelligence widgets for industrial kill heat, PvP system intel, smartbomb indicators, and Local Threat analysis with background queue progress for large systems.
- Jump Capable Ship Plotter with JDC/JFC fuel math, station/cyno guidance, nearby operational map context, and 24-hour industrial kill visibility per jump.
- Sideloadable Android WebView wrapper build script that outputs `EQM.apk`.

## Screenshots

A quick tour of the current beta surface, ordered roughly the way a new Quartermaster operator would encounter the tool.

### Command Center

| Overview | Analytics Platform |
| --- | --- |
| ![Quartermaster overview](static/ss/overview.png) | ![Analytics platform](static/ss/analytics.png) |

### Assets, Industry, And Corporations

| Asset Ledger | Blueprint And Recipe Library |
| --- | --- |
| ![Asset ledger](static/ss/assets.png) | ![Blueprint and recipe library](static/ss/industry.png) |

| Corporation Sync | ESI Sync And Character Contacts |
| --- | --- |
| ![Corporation sync and wallet divisions](static/ss/corps.png) | ![ESI sync and character contacts](static/ss/esi.png) |

| Character Skills |
| --- |
| ![Character skills](static/ss/skills.png) |

### Navigation And Hauling Intel

| Navigation Hub | Route Checker |
| --- | --- |
| ![Navigation hub](static/ss/navigation.png) | ![Route checker](static/ss/routecheck.png) |

| Industrial System Threat | PvP Intel Report |
| --- | --- |
| ![Industrial system threat](static/ss/indythreat.png) | ![PvP intel report](static/ss/pvpintel.png) |

| Local Threat Analysis | Jump Freighter Plotter |
| --- | --- |
| ![Local threat analysis](static/ss/localthreat.png) | ![Jump Freighter plotter](static/ss/jfplotter.png) |

| Operational Jump Freighter Map |
| --- |
| ![Operational Jump Freighter map](static/ss/jfpmap.png) |

### Account, Settings, And Audit

| Profile And Messages | Audit Log |
| --- | --- |
| ![Profile and private messages](static/ss/profile.png) | ![Audit log](static/ss/audit.png) |

| Settings And SDE Import | Permissions And Privacy |
| --- | --- |
| ![Settings and SDE import](static/ss/settings1.png) | ![Permissions and privacy settings](static/ss/settings2.png) |

| Additional Settings |
| --- |
| ![Additional settings](static/ss/settings3.png) |

| EVE Developer Application |
| --- |
| ![EVE developer application setup](static/ss/developer.png) |

## Stack

- **Frontend:** React, TypeScript, Vite, lucide-react.
- **Backend:** FastAPI, SQLAlchemy, Alembic.
- **Database:** PostgreSQL.
- **Worker/cache:** Redis-backed worker placeholder for longer-running sync work.
- **Runtime:** Docker Compose.
- **External data:** EVE ESI/SSO and EVE Static Data Export.
- **Mobile:** Minimal Android WebView shell for sideload testing.

## Run Locally

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Docker Compose support enabled.
- Git for cloning the repository.
- On Windows, WSL2 is recommended for Docker Desktop Linux containers.
- An EVE developer application if you want ESI/SSO sync locally.
- Optional: Android Studio or Android SDK command-line tools if you want to build `EQM.apk`.


### Scripted Setup

For a quick evaluator install from a fresh clone, use the installer script for your platform:

```powershell
.\install-eqm.bat
```

```bash
chmod +x install-eqm.sh rebuild-eqm.sh update-eqm.sh
./install-eqm.sh
```

The installer checks for Docker Compose, creates `.env` from `.env.example` when needed, generates local auth/encryption secrets, creates the `sde/` folder, builds the containers, and starts EQM at http://localhost:5173. If prerequisites are missing, the Windows installer can offer to install Git, WSL2, and Docker Desktop with `winget`/`wsl`; the Linux installer can offer to install Git/curl with the detected package manager and Docker Engine with Compose using Docker's official installer. These prerequisite installs are prompted and may require administrator or `sudo` approval, a restart, or opening a new terminal before rerunning EQM setup. The installer does not create your EVE developer application or download the SDE for you; follow the EVE SSO and SDE sections below after the containers start.

For day-to-day local rebuilds without pulling new code:

```powershell
.\rebuild-eqm.bat
```

```bash
./rebuild-eqm.sh
```

To update from the current GitHub branch and rebuild containers:

```powershell
.\update-eqm.bat
```

```bash
./update-eqm.sh
```

The update scripts use a fast-forward-only pull so they stop instead of trampling local edits.

### First Run

From PowerShell in the repository root:

```powershell
copy .env.example .env
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health
- OpenAPI docs: http://localhost:8000/docs
- Schema metadata: http://localhost:8000/api/metadata/schema

On first launch, create the administrator account from the bootstrap screen. After that, use the admin account to create invites, configure permissions, import SDE data, and link EVE characters through SSO.

If the frontend loads but data panels are empty or offline, check the containers:

```powershell
docker compose ps
docker compose logs backend
```

To reset all local container data during early testing, stop the stack and remove volumes:

```powershell
docker compose down -v
```

That deletes the local PostgreSQL and Redis volumes, so only use it when you intentionally want a fresh database.

## EVE SSO Configuration

EQM can run for a first look without EVE SSO, but character login and live ESI sync need an EVE Developer application. CCP's EVE SSO uses OAuth 2.0: players sign in through EVE, explicitly approve scopes, and EQM receives scoped access and refresh tokens for the selected character. The EVE SSO docs describe the same registration, callback URL, client ID/secret, scope, and refresh-token flow: https://developers.eveonline.com/docs/services/sso/

![EVE developer application setup](static/ss/developer.png)

### Create An EVE Developer Account And Application

1. Go to https://developers.eveonline.com/ and sign in with an EVE Online account.
2. Open **Applications** / **My Applications** and create a new application.
3. Use a recognizable name, such as `EVE Quartermaster Local`, `EVE Quartermaster Test`, or your corporation/alliance name.
4. Use a private description, such as `Private EVE Online asset, blueprint, industry, and quartermaster tracking tool.`
5. Choose the web application / authentication option that allows EVE SSO plus ESI API scopes. The portal wording can change, but the application must support OAuth authorization-code login and scoped ESI access.
6. Add the callback URL for your EQM backend.

For local testing on the same machine, use exactly:

```text
http://localhost:8000/api/esi/auth/callback
```

For a hosted test instance, use the public HTTPS backend callback:

```text
https://your-domain.example/api/esi/auth/callback
```

The callback in the EVE developer portal and `EVE_SSO_CALLBACK_URL` in `.env` must match exactly. If they do not, EVE login can fail during the callback/token exchange even when the EVE login page itself appears to work.

### Client ID, Secret, And Local `.env`

After saving the EVE application, copy the application **Client ID** and **Secret** from the developer portal. The Client ID is okay to identify the application; the Secret must stay private and must not be committed.

Local EVE SSO settings live in `.env`, which is intentionally ignored by source control. If you used `install-eqm.bat` or `install-eqm.sh`, `.env` is created from `.env.example` for you.

Local development:

```env
EVE_SSO_CLIENT_ID=paste_client_id_here
EVE_SSO_CLIENT_SECRET=paste_client_secret_here
EVE_SSO_CALLBACK_URL=http://localhost:8000/api/esi/auth/callback
FRONTEND_URL=http://localhost:5173
```

Hosted testing:

```env
EVE_SSO_CLIENT_ID=paste_client_id_here
EVE_SSO_CLIENT_SECRET=paste_client_secret_here
EVE_SSO_CALLBACK_URL=https://your-domain.example/api/esi/auth/callback
FRONTEND_URL=https://your-domain.example
```

After changing `.env`, restart or rebuild EQM:

```powershell
.\rebuild-eqm.bat
```

```bash
./rebuild-eqm.sh
```

### Scope Guidance

For a full EQM evaluation, enable every ESI scope that EQM requests from the EVE developer page. Login may work with fewer scopes, but individual features can later show missing-scope warnings or fail when syncing assets, blueprints, skills, fittings, wallets, corporation data, structures, markets, contacts, or navigation support data.

EQM uses scope groups internally:

- **Core authorization** covers the normal character/corporation quartermaster workflow: assets, corporation assets, blueprints, corporation roles, structures, wallets, industry jobs, contracts, skills, and fittings.
- **Contact sync** adds `esi-characters.read_contacts.v1` and `esi-characters.write_contacts.v1` so standing/contact propagation can read and apply contacts.
- **Mail sync** adds EVE mail read/send/organize scopes for the profile mail tools.
- **Full evaluation** uses the broader scope list below so one developer application can cover current features and near-term modules without repeatedly editing the CCP developer entry.

Current full-evaluation scope list:

```text
publicData
esi-location.read_location.v1
esi-location.read_ship_type.v1
esi-mail.organize_mail.v1
esi-mail.read_mail.v1
esi-mail.send_mail.v1
esi-skills.read_skills.v1
esi-skills.read_skillqueue.v1
esi-wallet.read_character_wallet.v1
esi-wallet.read_corporation_wallet.v1
esi-search.search_structures.v1
esi-clones.read_clones.v1
esi-characters.read_contacts.v1
esi-universe.read_structures.v1
esi-killmails.read_killmails.v1
esi-corporations.read_corporation_membership.v1
esi-assets.read_assets.v1
esi-planets.manage_planets.v1
esi-ui.open_window.v1
esi-ui.write_waypoint.v1
esi-characters.write_contacts.v1
esi-fittings.read_fittings.v1
esi-fittings.write_fittings.v1
esi-markets.structure_markets.v1
esi-corporations.read_structures.v1
esi-characters.read_loyalty.v1
esi-characters.read_chat_channels.v1
esi-characters.read_medals.v1
esi-characters.read_standings.v1
esi-characters.read_agents_research.v1
esi-industry.read_character_jobs.v1
esi-markets.read_character_orders.v1
esi-characters.read_blueprints.v1
esi-characters.read_corporation_roles.v1
esi-location.read_online.v1
esi-contracts.read_character_contracts.v1
esi-clones.read_implants.v1
esi-characters.read_fatigue.v1
esi-killmails.read_corporation_killmails.v1
esi-corporations.track_members.v1
esi-wallet.read_corporation_wallets.v1
esi-characters.read_notifications.v1
esi-corporations.read_divisions.v1
esi-corporations.read_contacts.v1
esi-assets.read_corporation_assets.v1
esi-corporations.read_titles.v1
esi-corporations.read_blueprints.v1
esi-contracts.read_corporation_contracts.v1
esi-corporations.read_standings.v1
esi-corporations.read_starbases.v1
esi-industry.read_corporation_jobs.v1
esi-markets.read_corporation_orders.v1
esi-corporations.read_container_logs.v1
esi-industry.read_character_mining.v1
esi-industry.read_corporation_mining.v1
esi-planets.read_customs_offices.v1
esi-corporations.read_facilities.v1
esi-corporations.read_medals.v1
esi-characters.read_titles.v1
esi-alliances.read_contacts.v1
esi-characters.read_fw_stats.v1
esi-corporations.read_fw_stats.v1
esi-corporations.read_projects.v1
esi-corporations.read_freelance_jobs.v1
esi-characters.read_freelance_jobs.v1
esi-structures.read_corporation.v1
esi-structures.read_character.v1
```

Only grant scopes you are comfortable granting. When scopes are added or changed later, each linked character needs to run EVE SSO again before the new permissions are available to sync workers.

## SDE Import

EQM uses the EVE Static Data Export for type names, groups, market/category metadata, blueprints, industry activities, dogma, skills, systems, stargates, stations, and navigation maps. The official EVE Static Data docs list the current download locations and formats: https://developers.eveonline.com/docs/services/static-data/

Use the **YAML** SDE for EQM. CCP also offers JSON Lines, but EQM's importer is built around YAML files and YAML zip layouts.

### Download The Latest YAML SDE

Windows PowerShell from the repository root:

```powershell
New-Item -ItemType Directory -Force -Path .\sde
Invoke-WebRequest -Uri "https://developers.eveonline.com/static-data/eve-online-static-data-latest-yaml.zip" -OutFile ".\sde\eve-online-static-data-latest-yaml.zip"
```

Linux/macOS shell from the repository root:

```bash
mkdir -p sde
curl -L "https://developers.eveonline.com/static-data/eve-online-static-data-latest-yaml.zip" -o "sde/eve-online-static-data-latest-yaml.zip"
```

You may import directly from the zip by using this SDE path in EQM:

```text
/sde/eve-online-static-data-latest-yaml.zip
```

### Extracted Layout Option

If you prefer extracting it first, extract the YAML zip into `./sde` so the files are visible to the Docker bind mount.

Windows PowerShell:

```powershell
Expand-Archive -Path ".\sde\eve-online-static-data-latest-yaml.zip" -DestinationPath ".\sde" -Force
```

Linux/macOS shell:

```bash
unzip -o sde/eve-online-static-data-latest-yaml.zip -d sde
```

Then use this SDE path in EQM:

```text
/sde
```

Accepted extracted layouts include modern SDE root files:

- `categories.yaml`
- `groups.yaml`
- `types.yaml`
- `blueprints.yaml`

Older FSD layouts are also accepted:

- `fsd/categoryIDs.yaml`
- `fsd/groupIDs.yaml`
- `fsd/typeIDs.yaml`
- `fsd/blueprints.yaml`

If you keep the SDE somewhere else, set `SDE_HOST_PATH` in `.env` to that host folder. The container path remains `/sde` unless you also change `SDE_SOURCE_PATH`.

### Import The SDE In EQM

1. Start EQM and sign in as an admin.
2. Open **Settings -> SDE Import**.
3. Use `/sde/eve-online-static-data-latest-yaml.zip` if importing the zip, or `/sde` if importing an extracted folder.
4. Click **Import SDE**.
5. Leave Settings open if you want to watch progress. The progress message updates while EQM keeps working.
6. When the import completes, refresh the page or use **Refresh** in the SDE panel to confirm category, type, system, stargate, recipe, and dogma counts.

Navigation, route maps, recipes, blueprint activity, fitting simulation, station guidance, skill grouping, market item matching, and blueprint/category filters all get better as SDE coverage improves. Re-import after major EVE updates or when a new YAML SDE is published.

## Using ESI/SSO Sync

1. Confirm `.env` has `EVE_SSO_CLIENT_ID`, `EVE_SSO_CLIENT_SECRET`, `EVE_SSO_CALLBACK_URL`, and `FRONTEND_URL` set correctly.
2. Sign in to EQM with your local/admin account.
3. Open **ESI Sync**.
4. Use the main EVE SSO authorization link to connect a character. EVE will ask which character to authorize and which scopes to grant.
5. After the callback returns to EQM, the linked character appears on the ESI Sync page and on character-aware pages.
6. If a page shows missing scopes, return to **ESI Sync** and re-authorize that character after adding the missing scope to the EVE developer application.
7. Use **Authorize contact sync** only for characters that should read/write EVE contacts for standing propagation.
8. Use **Sync assets**, **Sync skills**, **Sync fittings**, and **Sync contracts** from character-aware pages when you want fresh data. The Skills page also has **Sync all skills** for every eligible character; characters marked as opted out are skipped.
9. Use **Corporations** for corporation asset, blueprint, and wallet syncs. Corporation sync requires a linked CEO/director-style character with the relevant corporation scopes.
10. If an ESI token cannot be decrypted after moving environments or changing `TOKEN_ENCRYPTION_KEY`, re-link the affected character through EVE SSO.

Privacy controls live under **Settings -> Character Privacy**. A character can be marked private from shared Quartermaster sync, and that preference is respected by sync-all workflows.

## Using EQM Sections

- **Overview:** quick health, totals, recent assets, and a lightweight blueprint preview. Use this as the command-center landing page, not as the full industry workspace.
- **Navigation:** route checker, operational maps, industrial system threat, PvP intel, local threat analysis, Uedama scout status, and the Jump Capable Ship Plotter.
- **Characters:** assign EVE characters to EQM accounts, review character dossiers, inspect assets/skills/queues, control visibility, and use character hover cards for quick context.
- **Character Skills:** expand/collapse skill groups, refresh displayed skills, sync one character, or queue **Sync all skills** for every eligible non-opted-out character.
- **Fittings:** sync saved fittings, import EFT-style fits, inspect readiness and dogma-derived resources, assign grouped ammo/scripts, price missing/full fits, and jump to assets or market.
- **Alliance Roster:** review corporations and pilots grouped for diplomacy, recruiting, or operational awareness.
- **Market:** paste item lists, compare trade hubs, inspect order depth signals, and jump from market rows into visible assets or fittings.
- **Assets:** filter inventory by owner kind, item, owner, location, flag, category, and subtype; export CSV; copy Janice-friendly lists; open item context and market/fitting handoffs.
- **Industry:** use the full Blueprint Library, BPO/BPC filters, SDE-backed category/subtype filters, Missing BPO pane, blueprint output context, recipes, and material input views.
- **Corporations:** refresh corporation links, sync corporation assets/blueprints/wallet divisions through eligible tokens, and inspect sync stale/error messages.
- **Contracts:** sync current character and eligible corporation contracts, then sort/filter active contract data.
- **Analytics:** capture and inspect snapshots, metric widgets, baseline-aware deltas, and exports.
- **Profile:** manage account details, timezone, private messages, and EVE mail features when mail scopes are present.
- **Settings:** configure character privacy, import SDE data, enable/disable major sections, and manage role/section permissions.
- **ESI Sync:** link/re-link EVE characters, inspect server status, review missing scopes, authorize contact sync, unlink tokens, and import public ESI entities by ID.
- **User Administration:** invite users, manage local accounts, and assign roles.
- **Audit Log:** review sync peeks, system events, admin activity, and operational history.

## Android APK

The repository includes a small Android wrapper in `android-eqm/`. It builds a sideloadable WebView APK named `EQM.apk`.

From PowerShell in the repository root:

```powershell
.\build-eqm-apk.bat
```

Override the default app URL for a test build:

```powershell
$env:EQM_URL = "http://192.168.0.20:5173/"
.\build-eqm-apk.bat
```

If Gradle dependencies need to be downloaded:

```powershell
$env:EQM_ONLINE = "1"
.\build-eqm-apk.bat
```

The current wrapper is intended for sideload testing, not Play Store distribution.

## Testing Checklist

After `docker compose up --build`, confirm:

1. The frontend loads and shows API status `ok`.
2. First admin bootstrap or normal login works.
3. EVE SSO can link a character and returns to the frontend.
4. Asset sync populates readable item/location/owner data.
5. Asset filters, CSV export, and Janice copy respect the current filter.
6. Corporation sync pulls eligible corporation assets, blueprints, member metadata, and wallet divisions where scopes allow.
7. Skill sync completes, skills group under real categories, and category SP totals display.
8. SDE import completes and recipes are browsable.
9. Analytics snapshots show totals immediately, but first-observation baselines do not inflate gain widgets.
10. Navigation route planning works from SDE data, and gatecheck details open for route systems.
11. Jump Freighter plotting calculates fuel, station cards, cyno guidance, and industrial kills per jump.
12. Local Threat accepts a large paste, shows queue progress, and renders top threats as the background job runs.
13. Notifications, private messages, audit log, and permissions behave according to the signed-in role.

## Roadmap

- Hardening pass for public testers, including clearer empty states and friendlier setup diagnostics.
- More complete industry planning: owned vs missing materials, procurement options, build readiness, and market pricing.
- Fittings browser for corporation and opt-in personal fittings.
- Expanded analytics platform: custom widget dashboards, report builder, CSV/JSON exports, and longer retention controls.
- More SDE coverage for market groups, dogma attributes, icons, station/system geography, and richer type metadata.
- More durable background job storage for long threat scans, ESI syncs, and scheduled snapshot capture.
- Signed/release APK path after sideload testing stabilizes.
- Deeper navigation overlays for assets, contracts, structures, cyno ranges, and route-specific operational planning.

## License

EVE Quartermaster is licensed under the **GNU Affero General Public License v3.0 or later**. See `LICENSE` for details.

This project is not affiliated with or endorsed by CCP Games. EVE Online and related names are trademarks of CCP hf. EVE ESI data belongs to its respective owners and is accessed through authorized user tokens.

## AI Collaboration Notice

This project is collaboratively created with generative AI. Human project direction, review, testing, deployment choices, EVE domain decisions, and final stewardship remain with the project maintainers.
