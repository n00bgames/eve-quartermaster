<p align="center">
  <img src="static/eqm-logo.png" alt="EVE Quartermaster" width="900">
</p>

<p align="center">
  <a href="https://github.com/n00bgames/eve-quartermaster"><img alt="Project" src="https://img.shields.io/badge/project-eve--quartermaster-e8b84d?style=for-the-badge"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.22--beta-4fb3c7?style=for-the-badge">
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

> **Fittings feature preview:** The Fittings module is still under active development. Core cold-fit resources, offense, defense, capacitor, targeting, movement, trained skills, loaded charges/scripts, and common command-burst calculations are now checked against Pyfa 2.68.0 and selected EVE-client reference fits. Complete effect-graph, subsystem, implant, booster, fleet-effect, heat, and edge-case coverage is not yet claimed.

See [CHANGELOG.md](CHANGELOG.md) for version-by-version release notes.

## Install Time

**Typical first-time setup:**

- About 5 minutes if Docker is already installed.
- About 15-25 minutes from a clean Windows machine, excluding any required restart.
- One helper script checks the environment and can install supported prerequisites.
- The only account-side manual requirement is creating a CCP Developer application for ESI/SSO.

## Current Capabilities

- Account login, first-admin bootstrap, role management, one-time invite links, and per-section permissions.
- EVE SSO linking for characters, with linked-character ownership, unlinking, scope checks, and privacy controls.
- Character asset, wallet, skill, fittings, contracts, and standings sync, plus corporation asset, blueprint, and wallet-division sync. Character dossiers show both unmodified base standings and effective standings calculated from active Diplomacy, Connections, or Criminal Connections levels; Social is identified separately as affecting future gains rather than the current value.
- Asset ledger with sortable columns, fast dropdown filters, partial search, click-to-filter cells, CSV export, and Janice-friendly copy output.
- Blueprint and recipe views powered by SDE import, with BPO/BPC filters, ME/TE badges, owner filters, sortable blueprint lists, and recipe detail modals.
- Corporation page with enrolled corporations, CEO/member metadata where available, sync status, wallet divisions, and eligible sync characters.
- Roster page for corporation-grouped character display.
- Contact/standing propagation tools using writable ESI character contacts.
- Notifications, private messages, and admin audit log for sync transparency.
- Historical analytics foundation with scope-aware, hourly-coalesced snapshot runs, selectable full or change-only retention, metric metadata/versioning, organic-versus-coverage change composition, baseline-aware deltas, honest range coverage, exports, composable widgets, and host-controlled legacy-history compaction.
- ESI-backed Research Projects queue for manufacturing, material/time efficiency, copying, and invention work, with retained installer history and Analytics attribution.
- Planetary Industry workspace with queued per-character ESI sync, colony layouts, extractor program projections, routed factory warnings, storage totals, character/system/planet filters, and historical P0-P4 production analytics with per-commodity pilot rankings.
- Configurable Recruiting workspace with a public corporation page, applicant accounts, limited-scope EVE verification, recruiter review queues, interviews, audited decisions, and capability-based staff access.
- Calendar and Events workspace with month and upcoming views, local/EVE time presentation, RSVPs, multi-character fleet registration, doctrine and role planning, manager-only composition, post-event attendance, walk-in recording, and participation analytics.
- Doctrine Management with operator-configurable priority fields, canonical fittings, optional readiness plans, historical fit snapshots, and safe archival.
- Skill Plans integrated into Character Skills, including editable SDE-dogma-derived minimum requirements, recursive prerequisites, per-item provenance, deduplication, ordering, and character progress.
- Ship Replacement Program instances with generated intake links, EQM character ownership checks, doctrine or general fittings, exact timezone-aware loss recording, immutable historical snapshots, append-only review history, precise valuation/reimbursement fields, and permission-filtered analytics and CSV exports.
- Killboard discovery through zKillboard with canonical ESI killmail storage, resumable incremental sync, direct source links, and historical kill/loss, ISK, hull, geography, participation, opponent, streak, and wingmate analytics.
- Dynamic Battle Reports for a selected tracked pilot, with browsable retained engagement history, deterministic grouping, illustrated pilot/corporation/alliance/ship identity, team summaries, timeline, damage, SDE-resolved hull classes, clickable pilot zKill links, and revocable public snapshot links.
- Manual-first HyperNet Tracker with seller-offer economics, buyer-side node purchases, won/lost reconciliation, probability-versus-results analytics, seller-seeded node risk, organic progress history, and combined lifetime performance.
- Persistent Mining Ledger with per-character ESI history, detailed residue-aware imports, named mining operations, production/value graphs, and honest residue-measured efficiency rankings.
- Private Bounty Analytics with retained NPC payout ticks, net/gross/corporate-tax reconciliation, pilot leaderboards, time grouping, historical corporation context, evidence drilldowns, and CSV export.
- Mining Op Settlement workflow with saved-operation or date-range sourcing, actual refined-output entry, hub price snapshots, operation reserves, expenses, support-role compensation, weighted shares, reconciled ISK payouts, editable drafts, and immutable finalized history.
- Navigation suite with SDE-backed route planning, gatecheck summaries, operational starmap rendering, security-status color coding, and last-hour jump, ship-kill, and pod-kill traffic on every route system.
- Hauling intelligence widgets for industrial kill heat, PvP system intel, smartbomb indicators, and Local Threat analysis with background queue progress for large systems.
- Jump Capable Ship Plotter with automatic routing through ordered, required cyno waypoints, JDC/JFC fuel math, mapped alternate jump points, explicit station-risk warnings, nearby operational map context, and kill/activity intel per jump.
- Sideloadable Android WebView wrapper build script that outputs `EQM.apk`.

## Requirements

- [x] 64-bit Windows 11 with WSL2, or a current 64-bit Linux distribution
- [x] Docker Desktop, or Docker Engine with Docker Compose v2
- [x] 4 CPU cores recommended for builds, SDE imports, and background sync work
- [x] 8 GB of RAM available to Docker; 16 GB total system RAM recommended
- [x] 20 GB of free disk space for images, SDE files, PostgreSQL data, and growth
- [x] Git and reliable internet access for installation, ESI, image metadata, and SDE updates
- [x] CCP Developer application for ESI/SSO (one-time account setup)

## Screenshots

A quick tour of the current beta surface, ordered roughly the way a new Quartermaster operator would encounter the tool. Private identities and operational data are excluded or replaced with clearly fictitious demo data; public EVE system names and traffic telemetry may come from the live service.

### Command Center

| Overview | Navigation |
| --- | --- |
| ![Quartermaster overview](static/ss/eqm-overview.png) | ![Navigation and threat tools](static/ss/eqm-navigation.png) |

| Route Traffic Intel | PvP Traffic Intel |
| --- | --- |
| ![Route systems with last-hour jumps, ship kills, and pod kills](static/ss/eqm-route-hourly-intel.png) | ![PvP report with last-hour traffic telemetry](static/ss/eqm-pvp-hourly-intel.png) |

| Analytics Platform | Audit Log |
| --- | --- |
| ![Analytics platform](static/ss/eqm-analytics.png) | ![Audit log](static/ss/eqm-audit.png) |

### Character Functions

| Characters | Skills |
| --- | --- |
| ![Characters](static/ss/eqm-characters.png) | ![Character skills](static/ss/eqm-skills.png) |

| Fittings | Alliance Roster |
| --- | --- |
| ![Fittings](static/ss/eqm-fittings.png) | ![Alliance roster](static/ss/eqm-roster.png) |

| ESI Sync | Jump Clones |
| --- | --- |
| ![ESI sync](static/ss/eqm-esi-sync.png) | ![Jump clones and implant loadouts](static/ss/eqm-jump-clones.png) |

### Finance And Trade

| Bounty Analytics |
| --- |
| ![Private bounty income and authoritative corporation-tax analytics](static/ss/eqm-v019-bounty-analytics.png) |

### Inventory And Industry

| Corporate Exchange | Listing Detail & Appraisal | Owner Listing Editor |
| --- | --- | --- |
| ![Corporate Exchange listing board](static/ss/eqm-corporate-exchange.jpg) | ![Corporate Exchange listing detail and five-hub appraisal](static/ss/eqm-corporate-exchange-detail.jpg) | ![Corporate Exchange owner listing editor](static/ss/eqm-corporate-exchange-editor.jpg) |

**Built from user feedback:** The Corporate Exchange module was shaped directly by requests from EVE Quartermaster users, from shareable member listings through stock management, appraisals, auctions, and seller controls.
| HyperNet Tracker | Offer Detail & Economics |
| --- | --- |
| ![HyperNet Tracker dashboard with active offer summary](static/ss/eqm-hypernet-tracker.jpg) | ![HyperNet offer detail with financial and seeded-node risk calculations](static/ss/eqm-hypernet-offer-detail.jpg) |

| Manufacturing | Research Projects |
| --- | --- |
| ![Manufacturing ledger and build inputs](static/ss/eqm-manufacturing.png) | ![Research projects and job history](static/ss/eqm-research-projects.png) |

| Mining Ledger | Mining Yield Analytics |
| --- | --- |
| ![Mining Ledger controls and extraction totals](static/ss/eqm-mining-ledger.png) | ![Mining yield, residue, value, and efficiency analytics](static/ss/eqm-mining-analytics.png) |

| Mining Op Settlement | Notes & Lists |
| --- | --- |
| ![Mining operation settlement calculator](static/ss/eqm-mining-settlement.png) | ![Private notes and item lists](static/ss/eqm-notes-lists.png) |

| Market | Corporations |
| --- | --- |
| ![Market appraisal](static/ss/eqm-market.png) | ![Corporations](static/ss/eqm-corporations.png) |

| Ownership | Assets |
| --- | --- |
| ![Ownership](static/ss/eqm-ownership.png) | ![Asset ledger](static/ss/eqm-assets.png) |

| Industry | Contracts |
| --- | --- |
| ![Blueprints and industry](static/ss/eqm-industry.png) | ![Contracts](static/ss/eqm-contracts.png) |

| Planetary Industry |
| --- |
| ![Planetary Industry colony health and production](static/ss/eqm-planetary-industry.png) |

### Fleet Operations

| Doctrine Management | SRP Instances |
| --- | --- |
| ![Multi-fit doctrine management with linked skill plans](static/ss/eqm-doctrine-management.png) | ![Operation-linked SRP instances and shareable submission links](static/ss/eqm-srp-operations.png) |

| SRP Analytics | Killboard |
| --- | --- |
| ![SRP loss, reimbursement, and doctrine analytics](static/ss/eqm-srp-analytics.png) | ![Canonical ESI Killboard with zKillboard discovery and combat analytics](static/ss/eqm-v019-killboard.png) |

### Community

| Calendar & Events | Recruiting |
| --- | --- |
| ![Calendar and upcoming operations](static/ss/eqm-calendar-events.png) | ![Recruiting setup and administration](static/ss/eqm-recruiting.png) |

### Account And Settings

| Profile | Settings |
| --- | --- |
| ![Profile](static/ss/eqm-profile.png) | ![Settings](static/ss/eqm-settings.png) |

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
- **Mail sync** adds EVE mail read/send/organize scopes for the profile mail tools. Public Corporate Exchange listings use `esi-ui.open_window.v1` for a one-time buyer authorization that opens a prefilled, unsent draft in the selected character's running EVE client.
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

The repository includes helper scripts that download the latest Tranquility SDE zip into the local `sde/` folder mounted by Docker.

Windows from the repository root:

```powershell
.\sde-fetch.bat
```

Linux/macOS shell from the repository root:

```bash
chmod +x sde-fetch.sh
./sde-fetch.sh
```

You may import directly from the zip by using this SDE path in EQM:

```text
/sde/sde.zip
```

The scripts use CCP's official always-latest YAML SDE endpoint by default:

```text
https://developers.eveonline.com/static-data/eve-online-static-data-latest-yaml.zip
```

If CCP changes the endpoint or you want a test source, override it without editing the script:

```powershell
$env:SDE_URL="https://example.invalid/sde.zip"
.\sde-fetch.bat
```

```bash
SDE_URL="https://example.invalid/sde.zip" ./sde-fetch.sh
```

### Extracted Layout Option

If you prefer extracting it first, ask the helper script to extract the SDE into `./sde` after download.

Windows:

```powershell
.\sde-fetch.bat extract
```

Linux/macOS shell:

```bash
./sde-fetch.sh extract
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
3. Use `/sde/sde.zip` if importing the zip, or `/sde` if importing an extracted folder.
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
6. If a page shows missing scopes, return to **ESI Sync** and re-authorize that character after adding the missing scope to the EVE developer application. Existing linked characters must also reauthorize when a newly added feature, such as Planetary Industry, needs a scope their stored token predates.
7. Use **Authorize contact sync** only for characters that should read/write EVE contacts for standing propagation.
8. Use the individual sync controls from character-aware pages when you only need one dataset refreshed. **Sync all eligible** is the one-stop character refresh: for every accessible, non-opted-out character it queues every scope-authorized collector registered in the Sync & Freshness Center—assets, skills and queue, fittings, wallet history, contracts, industry jobs, mining history, planetary colonies, standings, jump clones, and active implants—plus eligible corporation industry projects. If multiple active authorizations exist for one character, EQM uses the newest token eligible for each dataset. Wallet hard opt-outs skip wallet collection while allowing the character's other eligible datasets to sync.
9. Use **Corporations** for corporation asset, blueprint, and wallet syncs. Corporation sync requires a linked CEO/director-style character with the relevant corporation scopes.
10. If an ESI token cannot be decrypted after moving environments or changing `TOKEN_ENCRYPTION_KEY`, re-link the affected character through EVE SSO.

Privacy controls live under **Settings -> Character Privacy**. A character can be marked private from shared Quartermaster sync, and that preference is respected by sync-all workflows.

### Character Wallet Analytics And Privacy

Character wallet history is enabled by default for the pilot's private dashboard, but participation in corporation wealth analytics is **disabled by default**. Existing characters are explicitly migrated to not participating; no previous setting is treated as consent. If the linked token includes `esi-wallet.read_character_wallet.v1` and the character has not opted out of all shared EQM sync, **Sync wallet** and **Sync all eligible** collect the current balance, the available ESI wallet-journal window, and the available market-transaction window. EQM retains later observations so daily, weekly, monthly, yearly, and longer-term trends can accrue after ESI's rolling response window moves on. Historical balance points begin with the first EQM wallet snapshot; EQM cannot reconstruct balance history from before collection began.

Individual wallet balances and general wallet history are visible only to the EQM account that owns the character. Directors do not receive another pilot's raw balance or personal wallet timeline, and EQM does not provide a richest-pilot leaderboard. Bounty Analytics is the narrow exception: effective Host and Admin roles may compare retained NPC bounty ticks for all enrolled pilots whose wallet-history collection and synchronization remain enabled; this does not expose balances or unrelated journal and transaction activity.

Wallet privacy has three effective modes:

- **Private collection — the default when no selection has been made:** wallet sync and personal Financial Analytics are enabled for the owning account. The character is excluded from all corporation wallet totals, medians, averages, distributions, growth metrics, and trend series. Staff cannot enable corporation participation for the pilot.
- **Include my wallet in corporation Financial Analytics — explicit opt-in:** wallet collection remains private to the owner, while the character is permitted to contribute to corporation-level calculations. Only the character's owning account can grant or withdraw this consent. Aggregates do not label individual balances, but a small participation pool can make a contributor's value easier to infer; the UI warns the pilot before and after opting in.
- **Hard opt out of wallet history collection and display:** EQM immediately deletes the character's stored wallet snapshots, wallet-journal events, wallet metrics, current balance, and wallet-sync timestamp. Future wallet collection is blocked, including administrator-triggered and Sync All attempts, and the character is excluded from every wallet report and aggregate. Other eligible character data may continue syncing. Staff cannot override this setting. Re-enabling collection starts a new private history from the next successful wallet sync; deleted history is not restored and corporation participation remains off until separately opted in.

Corporation Financial Analytics never grants access to individual member wallet pages. Every synced corporation-owned wallet division automatically contributes to corporation wealth; separately, only character wallets whose owners explicitly opted in can contribute. Corporation views default to a trend-only series rebased to zero, with raw combined wealth, corporation-wallet totals, opted-in pilot totals, median pilot wealth, and average pilot wealth hidden. A director may explicitly enable those totals for authorized officers, but that corporation-level setting cannot enroll characters. With no pilot opt-ins, the dashboard still reports synced corporation-owned wallet divisions while adding no pilot wallet balances.

The Financial Analytics dashboard records current wallet, net and percentage change, average daily growth, largest gain and loss, income, spending, spending velocity, wallet history, and notable wallet-journal events. Market journal entries are correlated with ESI transaction details where available so purchases and sales can include the item, direction, quantity, and unit price. Journal pages are deduplicated by ESI reference ID and atomically upserted, so overlapping pages, repeated syncs, or an already-stored reference refresh the local row instead of failing wallet collection. ESI only returns a rolling journal/transaction window, so EQM's locally retained history becomes more complete over time.

### Analytics privacy and scope

Analytics authorization and analytics identification are separate controls. Hosts and Admins may select **My Pilots**, **All Pilots**, or an available corporation/alliance. Directors may select **My Pilots** plus only corporations and alliances represented by their own linked pilots. A wider role never overrides a privacy choice.

An ordinary character sync opt-out may leave previously collected, non-destructive observations useful to population analytics, but EQM does not disclose that pilot's name in Analytics. Such observations may contribute only to the global **All Pilots** aggregate, only when at least three opted-out pilots form the anonymous cohort, and never to corporation/alliance drilldowns or pilot leaderboards. This minimum-cohort and single-scope rule prevents a viewer from recovering one opted-out pilot's value through simple subtraction between global, corporation, and alliance totals. If the cohort is smaller than three, its observations are suppressed rather than reported.

A HARD STOP privacy action is different: data covered by a destructive opt-out is excluded from the affected analytics for every role, including Host. For example, erasing/turning off wallet-history collection removes that character's wallet history and prevents those erased wallet values from contributing to Financial Analytics. Corporation-owned wallet divisions and explicitly opted-in character-wallet reporting retain their separate Financial Analytics rules described above. Privacy filtering is enforced by the API; hiding a name in the browser is not considered sufficient protection.

## Using EQM Sections

- **Overview:** quick health, totals, recent assets, and a lightweight blueprint preview. Use this as the command-center landing page, not as the full industry workspace.
- **Navigation:** route checker, operational maps, industrial system threat, PvP intel, local threat analysis, Uedama scout status, and the Jump Capable Ship Plotter. Route rows and PvP summaries display the latest hourly jumps, ship kills, and pod kills alongside longer-window kill intelligence. The plotter can auto-route through ordered systems where the pilot already has cynos, filling valid station-backed jumps between each required waypoint; every leg also exposes reachable alternate systems on the map and identifies candidates with no station or only red-risk stations. Select an alternate and use **Replot via…** to rebuild the complete route through it while retaining the initial ship, skill, safety, avoidance, intel, and feasible required-cyno constraints. If a required cyno cannot be retained, the new plot remains visible with an explicit warning naming the omitted system.
- **Characters:** assign EVE characters to EQM accounts, review character dossiers, inspect assets/skills/queues, control visibility, and use character hover cards for quick context. NPC standing rows display the ESI base value beside the skill-modified effective value and name the active Diplomacy, Connections, or Criminal Connections level used; Social changes future standing gains and is therefore not added to the current value.
- **Character Skills:** expand/collapse skill groups, refresh displayed skills, sync one character, or queue **Sync all skills** for every eligible non-opted-out character.
- **Skill Plans:** switch to the Skill Plans tab to create a manual plan or generate minimum requirements from a doctrine or fitting. Generation reads the imported EVE SDE; if requirement data is missing, EQM warns and never fabricates a skill. Generated plans remain fully editable and are only regenerated when explicitly requested. Saved plans can be copied or downloaded as an ordered, level-by-level EVE clipboard list for the client’s **Import Skills from Clipboard** action; EQM warns when an expanded plan exceeds EVE’s 150-level personal-plan limit.
- **Fittings:** sync saved fittings, import EFT-style fits, inspect readiness and dogma-derived resources, assign grouped ammo/scripts, price missing/full fits, jump to assets or market, and use **Send to EVE** to save a visible EQM fit into one of your own linked characters' in-client fitting libraries. Sending requires that character to grant `esi-fittings.write_fittings.v1`; staff permissions never allow one account to send through another account's character token.
- **Doctrines:** authorized officers can configure priority fields, create a doctrine around an existing canonical fit, import a custom EFT fit inline without losing form progress, link an optional Skill Plan, and archive records without invalidating Calendar or SRP history. Legacy Calendar doctrines continue to work until upgraded with the new required management fields.
- **SRP instances and requests:** authorized officers create an SRP instance for an operation and copy its generated submission link. Signed-in members may use that link to submit one or more losses; the instance and any configured doctrine are inherited and locked. Staff can close or reopen intake without deleting history. Standalone requests remain available for backward compatibility and unusual losses.
- **SRP loss records:** each request keeps UTC loss time plus the user-entered timezone, pilot corporation/alliance snapshots, operation and configurable loss-reason snapshots, immutable fit composition, ship type/class, optional system/region/security context, encrypted killmail hash, separate submission/killmail/verified valuations, requested/approved/paid reimbursement, and duplicate/invalid/test/cancelled disposition controls.
- **SRP Analytics:** the Analytics tab computes filtered server-side loss counts, exact ISK totals, calendar-day and active-loss-day averages, reimbursement liability, time series, doctrine/ship/operation/status breakdowns, top losses, data-quality indicators, drilldowns, and detailed or aggregate CSV exports. Members see only their own SRP analytics; officers see the SRP scope already granted by their role. Reporting uses EVE time/UTC by default.
- **Killboard:** open **EQM Violence Ledger** under Fleet & Community to inspect combined-account, character, corporation, or authorized all-entity views over 7, 30, or 90 days. EQM uses zKillboard only to discover killmail IDs/hashes and obtain explicitly labeled estimates/classifications; it fetches and retains the canonical victim, attacker, item, system, and time record from ESI. Public character, corporation, alliance, and faction IDs are translated in batches through ESI and stored in a separate refreshable name cache; deleted or inaccessible entities retain an honest ID fallback. Synchronization is incremental, deduplicated by killmail ID, cached locally, and resumable from a durable target/feed/page cursor. The configured refresh period is checked when the module is visited; **Sync now** remains available. zKillboard discovery is best-effort and must never be interpreted as a complete record of all activity.
- **Battle Reports:** choose one of your tracked pilots—or, for authorized officers, another visible tracked pilot—to reconstruct connected engagements from EQM's retained Killboard records. A dated selector and **Older battle**/**Newer battle** controls browse the selected pilot's retained history using stable seed killmail IDs, so rebuilding or sharing a historical report does not silently jump back to the latest fight. The configurable grouping gap joins the pilot's consecutive activity, then includes affiliation-connected killmails in the same systems and time window while excluding unrelated local losses. Involved, Summary, Timeline, Damage, and Composition views show deterministic teams, organizations, pilots, hulls, SDE-resolved ship classes (for example Battleship, Marauder, and Combat Battlecruiser), losses, damage, efficiency, and direct zKill evidence links. If the best-effort classifier gets a mixed fleet wrong, **Edit teams** provides three live drop zones: drag alliances or corporations between sides, refine an alliance move with a corporation choice, or override an individual non-anchor pilot. EQM rebuilds every dependent total, with pilot choices taking precedence; current-report edits reset when another battle is selected or history is rebuilt. A **Share report** action creates an immutable, unguessable public snapshot of the currently selected engagement—including its manual classifications—that works without an EQM login; creators can copy, audit view counts, and revoke each link without changing the underlying report. ESI remains canonical for killmail facts; zKill supplies discovery and explicitly labeled value estimates. Because public discovery can be incomplete and real battles can contain neutral or conflicting affiliations, EQM exposes its grouping rule and places unresolved participants on a visible **Third parties / ambiguous** side instead of pretending certainty.

### Doctrine, Skill Plan, and SRP data integrity

- Doctrine and Skill Plan removal is archival: linked Calendar events and historical records remain valid, and archived records can no longer be selected for new work.
- Doctrines reference the canonical Fittings record and also retain a small name/ship/time snapshot. A fitting used by an active shared doctrine cannot be made private; EQM has no destructive fitting-delete path.
- SRP records use stable foreign keys for navigation and immutable snapshots for historical truth. Renaming a character, doctrine, fitting, operation, corporation, alliance, ship class, loss reason, or system does not rewrite an older report. Referenced fits remain protected from destructive deletion and archived doctrine/operation records leave their SRP snapshots intact.
- SRP workflow and review mutations write append-only events for creation, submission, edits, review, approval/rejection, payment, reopening, overrides, and archival. The current status is queryable on the loss record but is backed by this audit stream.
- Monetary values use fixed-precision decimal ISK. Authoritative loss value precedence is: manual override, verified review value, verified killmail total, submission-time estimate, then unknown. Unknown is null—not zero—and is reported separately. Expected doctrine-fit value, destroyed/dropped killmail value, total estimate, requested, approved, and paid amounts remain separate.
- Operational analytics count distinct non-draft records and exclude duplicate, invalid, test, and cancelled dispositions by default. Duplicate reports point to their canonical request and remain auditable. Loss charts group by loss time; workflow reporting uses event time.
- Legacy Calendar doctrines remain readable without newly required management fields. Editing them through Doctrine Management upgrades them in place.
- **Alliance Roster:** review corporations and pilots grouped for diplomacy, recruiting, or operational awareness.
- **Recruiting:** hosts and recruitment administrators complete Initial Setup by resolving the corporation from ESI; EQM automatically records its current CEO and associated alliance, while an audited manual CEO override remains available for edge cases. Customize public copy, timezone, activity window, application questions, tags, interview prompts, privacy and retention values, then assign Recruiter or Recruitment Administrator capabilities without changing a user's normal role. Applicants register from the public Recruiting link, save drafts, link characters through the restricted recruitment SSO scope group, choose a main character, acknowledge interviews, communicate with recruiters, submit, or withdraw. Recruiters review the searchable queue, assign applications, add private notes and ratings, schedule interviews, and record applicant-visible status changes; final decisions remain administrator-only.
- **Calendar & Events:** plan operations from the Community section; publish scheduled events with formup systems, local and EVE times, voice/doctrine details, participant limits, fleet roles, and requested hulls. Members can RSVP Going or Maybe for each linked character independently, add several pilots from one EQM account, and optionally record a separate overall account response. Authorized managers can inspect aggregate or identity-visible fleet composition, close or lock registration, reconcile actual attendance after the event, add linked-character or public walk-ins, and compare registrations with real participation in configurable analytics.
- **Market:** paste item lists, compare trade hubs, inspect order depth signals, and jump from market rows into visible assets or fittings.
- **Corporate Exchange:** create and manage fixed-price or auction packages, publish account-free listing links, refresh five-hub appraisals, record external bids, and review seller activity. On a public listing, **Open prefilled EVE Mail** asks the buyer to authorize the character currently online, then opens an addressed purchase-request draft in that character's EVE client for review and sending.
- **HyperNet Tracker:** plan and manually record seller-side HyperNet offers and buyer-side node purchases from Finance and Trade. EQM calculates seller economics (node price, the 5% completion fee, HyperCore cost, payout, net proceeds, profit, return, break-even and target values) while keeping seller-seeded nodes separate from organic sales. Bid records capture the buyer, item, seller, location, total offer nodes, nodes purchased, node price and exposure; won/lost reconciliation calculates item-value-adjusted P/L, ROI, observed win rate, expected wins from purchased-node odds, luck versus expectation, and a combined seller-plus-buyer lifetime result. ESI supplies character, item, location, and market context only—EQM does not claim that ESI exposes HyperNet offers, purchases, participants, winners, or outcomes.
- **Assets:** filter inventory by owner kind, item, owner, location, named corporation hangar division, category, and subtype; resolve authorized Upwell structure names; export CSV; copy Janice-friendly lists; open item context and market/fitting handoffs. EQM retains the raw ESI flag or location ID when ESI cannot disclose a private structure.
- **Industry:** use the full Blueprint Library, BPO/BPC filters, SDE-backed category/subtype filters, Missing BPO pane, blueprint output context, recipes, and material input views. On desktop, hover any blueprint name for a concise shared card: owned instances show ME/TE, BPO/BPC and run state, owner, location, and active industry-job details; recipes and missing-blueprint definitions clearly state when no owned instance data applies.
- **Research Projects:** sync eligible character and corporation industry queues, monitor active manufacturing, ME/TE, copying, and invention projects, inspect facilities and timers, and retain completed work for Analytics. Active, paused, and ready-for-delivery ME/TE and copying jobs also act as a shadow blueprint inventory in Analytics so temporarily installed blueprints are not reported as missing.
- **Planetary Industry:** sync eligible colonies, inspect layouts and stored commodities, translate factory schematic IDs into SDE-backed product names and input recipes, monitor extractor expiry and projected program output, identify factories without inbound routes, and filter by character, system, or planet type. Extractor projections use imported SDE Dogma when available and CCP's documented decay/noise defaults otherwise; reauthorize older linked characters if EQM reports the PI scope is missing. Each successful sync also records a durable P0-P4 production observation: the first establishes current projected throughput, and later observations accrue estimated production for Analytics, tier totals, commodity leaders, and pilot rankings. ESI may not advance colony inventories from passive production alone; if a colony snapshot remains stale, visit the planet in space and interact with or submit a colony change, wait approximately 10 minutes for ESI caching, then use **Sync all eligible** or the character PI sync button. The plain **Refresh** button only reloads EQM's last saved snapshot.
- **Mining Ledger:** queue personal mining-history syncs, import the detailed EVE ledger export for residue/value fields, filter by character/system/date/operation, create named operations with selected miners and boosters, and compare recovered volume, gross extraction, residue loss, estimated value, and measured efficiency. ESI rows remain stored after they age out of CCP's rolling response window.
- **Bounty Analytics:** review NPC bounty income for wallet-visible characters connected to your own EQM account over 1, 7, 30, or 90 days or all retained history. A tick is one or more `bounty_prizes` journal rows for one pilot with the exact same authoritative ESI timestamp; EQM never invents a wider payout window. Repeated wallet imports remain duplicate-safe through the pilot/reference-ID uniqueness rule, while late-arriving rows with the same timestamp join the same deterministic tick. Pilot, historical-corporation, custom-date, and tax-evidence filters feed tick/hour/day charts, net-income and tax summaries, a traceable leaderboard, and a paged ledger whose ESI reference IDs can be expanded or exported as CSV. ESS transfers, mission rewards and bonuses, loot sales, and all non-`bounty_prizes` income are excluded.
- **Bounty tax and privacy:** ESI's original journal amount is preserved as net bounty. Corporate tax is the authoritative journal `tax` field, and gross is calculated as net plus that tax only when the field exists. Missing tax makes tax and gross **Unknown**—EQM does not apply a corporation's current rate to older payouts. Known-tax totals and evidence coverage remain visible, and every aggregate drills back to contributing tick/reference IDs. The corporation identity present at first import is retained so later corporation changes do not rewrite historical groupings; an authoritative historical tax receiver takes precedence where ESI supplies it. Bounty Analytics is account-private even for staff: it covers only the current user's eligible connected pilots, while corporation filters group those pilots' preserved history rather than exposing other members' wallets. Hard wallet-history opt-out and general sync opt-out remain fully respected. ISK/hour is deliberately not calculated because wallet journals do not supply reliable ratting-session boundaries.
- **Mining Op Settlement:** open the calculator beneath Ledger History, choose a saved operation or date range, and select whether miner shares follow estimated raw value, recovered volume, raw quantity, or equal starting shares. Enter the actual refined minerals and quantities because recorded output is authoritative; optional hub pricing snapshots each unit price, while manual changes are flagged as overrides. Operation reserves and expenses are deducted before fixed-percentage support payouts and weighted shares. Enter percentages as either `10` or `0.10` for 10%; the preview shows the normalized result and must reconcile before saving. Drafts remain editable, while finalized settlements are immutable snapshots of ledger rows, prices, calculations, and payouts.
- **Corporations:** refresh corporation links, sync corporation assets/blueprints/wallet divisions through eligible tokens, and inspect sync stale/error messages.
- **Contracts:** sync current character and eligible corporation contracts, then sort/filter active contract data.
- **Analytics:** capture and inspect snapshots, metric widgets, baseline-aware deltas, Financial Analytics, and exports. The role-aware pilot-scope selector offers **My Pilots**, authorized corporation/alliance scopes, and—for Hosts and Admins—**All Pilots**; the selection also scopes Planetary Industry analytics. Directors are limited to affiliations represented by their own linked pilots. The category bar jumps directly to each analytics section. Anonymous-cohort and HARD STOP behavior is defined in **Analytics privacy and scope** above, while Financial Analytics continues to enforce its stricter owner-controlled balance rules. Bounty Analytics is account-scoped for ordinary users, while effective Host and Admin roles can compare every eligible enrolled pilot. Corporation wealth includes all synced corporation-owned wallet divisions plus only those character wallets whose owners explicitly opted in. Character wallets build durable daily history and item-enriched financial timelines under the owner-controlled privacy rules documented above; character participation defaults off for every existing and future character and never exposes a richest-pilot list. Four standings widgets rank the selected period's top 10 NPC corporation and faction gains and losses by net unmodified base-standing movement across selected pilots; first observations establish coverage rather than appearing as gains, and Social-skill modifiers are excluded so training does not masquerade as reputation movement. The metric registry explicitly defines each metric's entity rollup, time rollup, supported aggregations and transforms, value kind, dimensions, privacy scope, version, and chart compatibility; snapshot writers reject unregistered or incorrectly scoped metrics so future widgets can consume one shared contract. Wallet balance metrics also declare virtual daily and weekly deltas, percentage growth, and 30-day rolling averages; EQM calculates these on demand through the shared registry engine rather than storing redundant derived observations. Historical time-series charts use dynamic visible-data ranges, human-friendly ticks, adaptive daily-to-quarterly date labels, peak headroom, and hover crosshairs rather than forcing every series onto a zero-based scale. Automatic ESI observations are limited to the character or corporation that changed and identical scope/source observations are coalesced for one hour, preventing unrelated syncs from duplicating the full blueprint and skill library. Hosts may choose **Full History** or **Changes + Daily Checkpoints** on Analytics. Full History stores every collected observation for maximum forensic detail at the highest storage cost. Changes + Daily Checkpoints stores changed values plus periodic state snapshots, records removed blueprint series as zero, and retains historical reconstruction at much lower storage cost. Changes + Daily Checkpoints is the default for new installations; upgrades with existing analytics history remain on Full History until a host changes the setting. The choice affects future observations only and never deletes existing history. Charts include the latest observation before the selected window as a baseline, and the coverage placard reports the actual platform history available while clarifying that every metric series has its own timestamps—one snapshot run ID does not mean every collector ran. The Change Composition widget applies **Net change = Organic change + Coverage change** to skill points, corporation wallets, members, and blueprints. Organic change compares owners with a baseline; coverage change identifies values first observed inside the selected period, so onboarding does not appear as training or financial growth. Coverage currently means a first retained observation; more specific causes such as relinking, newly granted scope, privacy opt-in, or delayed first success require their own durable lifecycle events before EQM can label them reliably. While a report is being assembled, EQM shows an explicit **Analytics loading** notice and asks the operator not to refresh. Hosts can use **Inspect storage** to preview redundant legacy automatic snapshots, then optionally compact them while preserving every manual snapshot and the latest complete automatic snapshot for each UTC day. Compaction makes freed PostgreSQL space reusable immediately; returning it to the host filesystem still requires a separately planned `VACUUM FULL` maintenance window.
- **Profile:** manage account details, timezone, private messages, and EVE mail features when mail scopes are present.
- **Settings:** configure character privacy, import SDE data, enable/disable major sections, and manage role/section permissions.
- **ESI Sync:** use the permission-filtered Sync & Freshness Center to review each linked character's durable job status, dataset age, failed or missing syncs, missing scopes, and privacy-disabled collection; link/re-link characters, authorize contact sync, unlink tokens, inspect server status, and import public ESI entities by ID. Contact sync can safely add missing contacts, optionally update differing standings, or use the destructive **Exact Match** mode to preview and then remove destination-only contacts so selected characters match the source one-for-one. Exact Match requires an explicit preview and confirmation, applies creates/updates first, deletes last in ESI-safe batches, and reports per-character deletion counts and samples. Applying either contact-sync mode queues a durable background job: the request returns immediately, progress is shown per destination character, completed work is retained when another target fails, leaving the page does not stop the job, and queued/running contact work is resumed after a backend restart. **Character Data Sync is an ESI workflow** and its bulk coordinator appears as active even while it is between per-dataset jobs. Bulk Character Data, Character Skills, Mining, Research, and Planetary Industry progress is remembered in the browser for six hours: leaving a module stops that page's polling without stopping the server job, and returning resumes the same progress indicator. A backend restart clears those older in-memory bulk coordinators, so stale browser references are discarded safely.
- **User Administration:** invite users, manage local accounts, and assign roles.
- **Audit Log:** review sync peeks, system events, admin activity, and operational history.

## Mining Settlement Limitations

Mining settlements currently pay in ISK and use manually entered actual refined output. EQM does not yet calculate theoretical refining from character skills, implants, structure bonuses, rigs, taxes, sovereignty, or SDE dogma. Physical mineral allocation, largest-remainder unit splitting, revisions, voiding, and payout exports are planned follow-up work; finalized Phase 1 settlements deliberately remain unchanged when prices, SDE data, characters, or ledger history later change.

## HyperNet Tracker Data Limits

HyperNet offer and bid activity is manual in this release. ESI does not provide EQM with offer creation, node sales or purchases, participants, winners, expirations, or outcomes, so users must enter progress and bids and reconcile final results from the in-game offer. Character, item, location, and market context may still be resolved through existing EQM/ESI data. The internal provider abstraction is intended for a future sanctioned source without changing saved records.
## Android APK

The repository includes a small Android wrapper in `android-eqm/`. It builds a sideloadable WebView APK named `EQM.apk`.

On first launch, the app asks for the EQM server URL and stores it locally. Use the native settings button in the upper-right corner to change servers later without rebuilding or reinstalling the APK.

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

Run the isolated Python 3.12 backend suite without adding test packages to the production backend image:

```powershell
docker compose --profile test run --rm backend-tests python -m pytest -q tests
```

Run only the fitting regression fleet while refining fitting calculations:

```powershell
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_fitting_regression_fleet.py tests/test_fitting_reference_fleet.py tests/test_fitting_eft_import.py
```

### Planetary Industry Rust engine

The backend image includes the release build of `eqm-core`. `EQM_PI_ENGINE` controls colony projection execution:

- `python` uses the original Python simulator.
- `shadow` serves Python while running Rust and logging parity mismatches.
- `rust` serves Rust results and automatically falls back to Python on any binary error or timeout.

Docker Compose defaults to `rust`. Set `EQM_PI_ENGINE=python` in `.env` and rebuild the backend for an immediate rollback. The PI page displays the engine that served each projection.

```powershell
docker compose --profile test run --rm eqm-core-tests
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_planetary_simulation.py tests/test_planetary_simulation_engine.py
```

### Fitting Rust hybrid engine

Fitting simulation now runs as a hybrid while combat-stat parity is expanded. `EQM_FITTING_ENGINE` controls the completed Rust slices: CPU, powergrid, calibration, slot limits, subsystem fitting modifiers, the module set allowed to affect stats, capacitor recharge stability/depletion, and the shared stacking or unpenalized reductions used by weapon, repair, mobility, signature, and capacitor modifiers.

- `python` keeps all migrated fitting calculations in Python.
- `shadow` serves Python while comparing the Rust results.
- `rust` serves the Rust results and automatically falls back to Python on any binary error or timeout.

Docker Compose defaults to `rust`. Python still prepares the EVE effect graph and the modifier lists; Rust reduces the migrated modifiers and resolves the nonlinear capacitor curve. Final combat, tank, mobility, targeting, and cargo assembly remains Python. The Fittings page labels this boundary as `Rust resources/math + Python effect graph`. Set `EQM_FITTING_ENGINE=python` and rebuild the backend to roll all fitting Rust slices back independently of Planetary Industry.

```powershell
docker compose --profile test run --rm eqm-core-tests
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_fitting_math_parity.py tests/test_fitting_math_engine.py tests/test_fitting_resources_parity.py tests/test_fitting_resources_engine.py
```

### Analytics Rust engine

`EQM_ANALYTICS_ENGINE` controls the shared Analytics summary evaluator. FastAPI and SQLAlchemy retain authentication, privacy/scope enforcement, and database retrieval. Rust owns the deterministic summary calculations: overview cards, organic-versus-coverage change composition, growth and extraction rankings, standing movement, and daily corporation trend series.

- `python` uses the reference Python calculations.
- `shadow` serves Python while comparing the complete Rust result and logging field-level mismatches.
- `rust` serves Rust results and automatically falls back to Python on a binary error, invalid contract, or timeout.

Docker Compose defaults to `rust`. The `/api/analytics/summary` response includes `engine_requested`, `engine_used`, and fallback or shadow metadata so a live cutover can be verified directly. Set `EQM_ANALYTICS_ENGINE=python` in `.env` and rebuild the backend for an independent Analytics rollback.

### Jump route Rust engine

`EQM_JUMP_ROUTE_ENGINE` controls the jump-capable route search. Python retains SDE and structure reads, ship access rules, docking filters, operational intel, fuel calculations, and map assembly. Rust owns the spatial grid, range graph, avoidance filtering, and shortest-path search used to fill automatic and required-waypoint route segments.

- `python` uses the reference Python route search.
- `shadow` serves Python while comparing every segment with Rust and logging path or distance mismatches.
- `rust` serves Rust routes and automatically falls back to Python on a binary error, invalid contract, or timeout.

Docker Compose defaults to `rust`. Jump plotter responses include `route_engine` metadata with the requested engine, engine used, segment count, shadow result, and any fallback reason. Set `EQM_JUMP_ROUTE_ENGINE=python` in `.env` and rebuild the backend for an independent route-search rollback.

### Bounty Analytics Rust engine

`EQM_BOUNTY_ANALYTICS_ENGINE` controls deterministic bounty reductions. Python retains wallet-journal access control, ESI row retrieval, authoritative tick construction, tax-status filtering, and reporting-timezone bucket preparation. Rust owns summary totals, tax-coverage reconciliation, pilot leaderboards, and timeline aggregation.

- `python` uses the reference Python reductions.
- `shadow` serves Python while comparing the complete Rust result and logging field-level mismatches.
- `rust` serves Rust results and automatically falls back to Python on a binary error, invalid contract, or timeout.

Docker Compose defaults to `rust`. `/api/bounty-analytics` includes engine metadata and the Bounty Analytics page displays the engine that served the report. Set `EQM_BOUNTY_ANALYTICS_ENGINE=python` in `.env` and rebuild the backend for an independent rollback.

### Mining settlement Rust engine

`EQM_SETTLEMENT_MATH_ENGINE` controls the deterministic mining-settlement allocator. Python retains ledger access, contribution aggregation, validation, pricing, and persistence. Rust owns exact-cent fixed/share payouts, deterministic largest-remainder rounding, payout ratios, and whole-unit mineral distribution with reserve retention.

- `python` uses the reference allocator.
- `shadow` serves Python while requiring exact contract parity from Rust.
- `rust` serves Rust results and automatically falls back to Python on a binary error, invalid contract, or timeout.

Docker Compose defaults to `rust`. Settlement previews include engine metadata and display which evaluator served the calculation. Set `EQM_SETTLEMENT_MATH_ENGINE=python` in `.env` and rebuild the backend for an independent rollback.

### Killboard Analytics Rust engine

`EQM_KILLBOARD_ANALYTICS_ENGINE` controls the deterministic Violence Ledger reducer. Python retains permissions, canonical killmail queries, identity matching, SDE/name enrichment, and recent-kill serialization. Rust owns combat KPIs, exact-cent ISK totals, efficiency and damage ratios, hull/geography/opponent rankings, streaks, wingmate pairs, and daily timeline aggregation.

- `python` uses the reference reducer.
- `shadow` serves Python while requiring exact normalized-contract parity from Rust.
- `rust` serves Rust results and automatically falls back to Python on a binary error, invalid contract, or timeout.

Docker Compose defaults to `rust`. Killboard analytics responses include engine metadata and the Violence Ledger displays the serving engine. Set `EQM_KILLBOARD_ANALYTICS_ENGINE=python` in `.env` and rebuild the backend for an independent rollback.

```powershell
docker compose --profile test run --rm eqm-core-tests cargo test --locked --test analytics_summary_contract
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_analytics_summary_engine.py tests/test_analytics_series.py
docker compose --profile test run --rm eqm-core-tests cargo test --locked --test jump_route_contract
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_jump_route_engine.py tests/test_jump_freighter_alternates.py
docker compose --profile test run --rm eqm-core-tests cargo test --locked --test bounty_analytics_contract
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_bounty_analytics.py tests/test_bounty_analytics_engine.py
docker compose --profile test run --rm eqm-core-tests cargo test --locked --test killboard_analytics_contract
docker compose --profile test run --rm backend-tests python -m pytest -q tests/test_killboard_analytics.py tests/test_killboard_analytics_engine.py
```

The test image is built from the dedicated Docker `test` stage and includes the repository's backend tests. The normal backend and worker continue to use the final `runtime` stage without pytest.

Fitting reference evidence lives under `backend/tests/fixtures/fittings/evidence/`. Every external capture records its simulator/profile version, module and drone state, heat/implant/booster assumptions, and display-rounded expected values. The current fleet includes cold All-V and exported Steihl Lianul skill-profile captures from Pyfa 2.68.0 for a Rail Moa, Rapid Light Caracal, Active Armor Vexor, and command-burst Absolution, with the Absolution also cross-checked in the EVE fitting simulator. EQM uses the currently imported CCP SDE as authoritative when a versioned Pyfa capture contains older module attributes; such source-version differences are documented in the evidence instead of being hidden with hard-coded corrections.

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
11. Jump Capable Ship plotting automatically routes through optional required cyno waypoints, calculates fuel, shows station/cyno guidance and kill/activity intel, and maps selectable alternate systems with explicit `NO STATION` and `ONLY RED STATIONS` warnings. Replot through a selected alternate and confirm the original constraints remain; when a required cyno is infeasible, confirm the replacement route renders with a warning naming it.
12. HyperNet Tracker reproduces the eight-node Marshal calculation, keeps seeded nodes separate from organic sales, records buyer-side node exposure, reconciles won/lost bids and completed/expired offers, and reports odds-based and combined realized analytics without claiming ESI HyperNet access.
13. Local Threat accepts a large paste, shows queue progress, and renders top threats as the background job runs.
14. Notifications, private messages, audit log, and permissions behave according to the signed-in role.

## Roadmap

- Hardening pass for public testers, including clearer empty states and friendlier setup diagnostics.
- More complete industry planning: owned vs missing materials, procurement options, build readiness, and market pricing.
- Fittings browser for corporation and opt-in personal fittings.
- Expanded analytics platform: custom widget dashboards, report builder, CSV/JSON exports, and longer retention controls.
- More SDE coverage for market groups, dogma attributes, icons, station/system geography, and richer type metadata.
- More durable background job storage for long threat scans, ESI syncs, and scheduled snapshot capture.
- Signed/release APK path after sideload testing stabilizes.
- Deeper navigation overlays for assets, contracts, structures, cyno ranges, and route-specific operational planning.

## Research Acknowledgments

Some EQM feature direction was inspired by research into [EVE Buddy](https://github.com/ErikKalkoken/evebuddy), an MIT-licensed EVE companion application by Erik Kalkoken and its contributors. In particular, its consolidated multi-character views, cross-character discovery, contextual information windows, background updates, and notification model helped inform our thinking. EQM's resulting features—including the Sync & Freshness Center—are independently implemented around EQM's server architecture, permissions, privacy boundaries, and interface rather than copied from EVE Buddy.

See [3RD PARTY SOURCES.MD](3RD%20PARTY%20SOURCES.MD) for source provenance, licenses, validation references, and the project's rules for recording future third-party research or incorporation.

## License

EVE Quartermaster is licensed under the **GNU Affero General Public License v3.0 or later**. See `LICENSE` for details.

This project is not affiliated with or endorsed by CCP Games. EVE Online and related names are trademarks of CCP hf. EVE ESI data belongs to its respective owners and is accessed through authorized user tokens.

## AI Collaboration Notice

This project is collaboratively created with generative AI. Human project direction, review, testing, deployment choices, EVE domain decisions, and final stewardship remain with the project maintainers.
