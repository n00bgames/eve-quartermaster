<p align="center">
  <img src="static/eqm-logo.png" alt="EVE Quartermaster" width="900">
</p>

<p align="center">
  <a href="https://github.com/n00bgames/eve-quartermaster"><img alt="Project" src="https://img.shields.io/badge/project-eve--quartermaster-e8b84d?style=for-the-badge"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.11--beta-4fb3c7?style=for-the-badge">
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

> **Fittings feature preview:** The Fittings module is currently under active development and should be treated as a preview. Dogma, implant, skill, cargo, and module-derived values are known to be incomplete or inaccurate while the simulator is being rebuilt.

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
- Character asset sync, corporation asset sync, corporation blueprint sync, corporation wallet division sync, and skill sync.
- Asset ledger with sortable columns, fast dropdown filters, partial search, click-to-filter cells, CSV export, and Janice-friendly copy output.
- Blueprint and recipe views powered by SDE import, with BPO/BPC filters, ME/TE badges, owner filters, sortable blueprint lists, and recipe detail modals.
- Corporation page with enrolled corporations, CEO/member metadata where available, sync status, wallet divisions, and eligible sync characters.
- Roster page for corporation-grouped character display.
- Contact/standing propagation tools using writable ESI character contacts.
- Notifications, private messages, and admin audit log for sync transparency.
- Historical analytics foundation with scope-aware, hourly-coalesced snapshot runs, metric metadata/versioning, baseline-aware deltas, exports, composable widgets, and host-controlled legacy-history compaction.
- ESI-backed Research Projects queue for material/time efficiency, copying, and invention work, with retained researcher history and Analytics attribution.
- Planetary Industry workspace with queued per-character ESI sync, colony layouts, extractor program projections, routed factory warnings, storage totals, character/system/planet filters, and historical P0-P4 production analytics with per-commodity pilot rankings.
- Configurable Recruiting workspace with a public corporation page, applicant accounts, limited-scope EVE verification, recruiter review queues, interviews, audited decisions, and capability-based staff access.
- Calendar and Events workspace with month and upcoming views, local/EVE time presentation, RSVPs, multi-character fleet registration, doctrine and role planning, manager-only composition, post-event attendance, walk-in recording, and participation analytics.
- Manual-first HyperNet Tracker with offer economics, seller-seeded node risk, organic progress history, participant observations, and completed/expired reconciliation.
- Persistent Mining Ledger with per-character ESI history, detailed residue-aware imports, named mining operations, production/value graphs, and honest residue-measured efficiency rankings.
- Mining Op Settlement workflow with saved-operation or date-range sourcing, actual refined-output entry, hub price snapshots, operation reserves, expenses, support-role compensation, weighted shares, reconciled ISK payouts, editable drafts, and immutable finalized history.
- Navigation suite with SDE-backed route planning, gatecheck summaries, operational starmap rendering, and security-status color coding.
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

A quick tour of the current beta surface, ordered roughly the way a new Quartermaster operator would encounter the tool. Screenshots are captured from a disposable documentation database and use fictitious demo identities, corporations, locations, and operations.

### Command Center

| Overview | Navigation |
| --- | --- |
| ![Quartermaster overview](static/ss/eqm-overview.png) | ![Navigation and threat tools](static/ss/eqm-navigation.png) |

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
8. Use **Sync assets**, **Sync skills**, **Sync fittings**, and **Sync contracts** from character-aware pages when you want fresh data. The Skills page also has **Sync all skills** for every eligible character; characters marked as opted out are skipped.
9. Use **Corporations** for corporation asset, blueprint, and wallet syncs. Corporation sync requires a linked CEO/director-style character with the relevant corporation scopes.
10. If an ESI token cannot be decrypted after moving environments or changing `TOKEN_ENCRYPTION_KEY`, re-link the affected character through EVE SSO.

Privacy controls live under **Settings -> Character Privacy**. A character can be marked private from shared Quartermaster sync, and that preference is respected by sync-all workflows.

## Using EQM Sections

- **Overview:** quick health, totals, recent assets, and a lightweight blueprint preview. Use this as the command-center landing page, not as the full industry workspace.
- **Navigation:** route checker, operational maps, industrial system threat, PvP intel, local threat analysis, Uedama scout status, and the Jump Capable Ship Plotter. The plotter can auto-route through ordered systems where the pilot already has cynos, filling valid station-backed jumps between each required waypoint; every leg also exposes reachable alternate systems on the map and identifies candidates with no station or only red-risk stations. Select an alternate and use **Replot via…** to rebuild the complete route through it while retaining the initial ship, skill, safety, avoidance, intel, and feasible required-cyno constraints. If a required cyno cannot be retained, the new plot remains visible with an explicit warning naming the omitted system.
- **Characters:** assign EVE characters to EQM accounts, review character dossiers, inspect assets/skills/queues, control visibility, and use character hover cards for quick context.
- **Character Skills:** expand/collapse skill groups, refresh displayed skills, sync one character, or queue **Sync all skills** for every eligible non-opted-out character.
- **Fittings:** sync saved fittings, import EFT-style fits, inspect readiness and dogma-derived resources, assign grouped ammo/scripts, price missing/full fits, and jump to assets or market.
- **Alliance Roster:** review corporations and pilots grouped for diplomacy, recruiting, or operational awareness.
- **Recruiting:** hosts and recruitment administrators complete Initial Setup by resolving the corporation from ESI; EQM automatically records its current CEO and associated alliance, while an audited manual CEO override remains available for edge cases. Customize public copy, timezone, activity window, application questions, tags, interview prompts, privacy and retention values, then assign Recruiter or Recruitment Administrator capabilities without changing a user's normal role. Applicants register from the public Recruiting link, save drafts, link characters through the restricted recruitment SSO scope group, choose a main character, acknowledge interviews, communicate with recruiters, submit, or withdraw. Recruiters review the searchable queue, assign applications, add private notes and ratings, schedule interviews, and record applicant-visible status changes; final decisions remain administrator-only.
- **Calendar & Events:** plan operations from the Community section; publish scheduled events with formup systems, local and EVE times, voice/doctrine details, participant limits, fleet roles, and requested hulls. Members can RSVP Going or Maybe for each linked character independently, add several pilots from one EQM account, and optionally record a separate overall account response. Authorized managers can inspect aggregate or identity-visible fleet composition, close or lock registration, reconcile actual attendance after the event, add linked-character or public walk-ins, and compare registrations with real participation in configurable analytics.
- **Market:** paste item lists, compare trade hubs, inspect order depth signals, and jump from market rows into visible assets or fittings.
- **Corporate Exchange:** create and manage fixed-price or auction packages, publish account-free listing links, refresh five-hub appraisals, record external bids, and review seller activity. On a public listing, **Open prefilled EVE Mail** asks the buyer to authorize the character currently online, then opens an addressed purchase-request draft in that character's EVE client for review and sending.
- **HyperNet Tracker:** plan and manually record seller-side HyperNet offers from Finance and Trade. EQM calculates node price, the 5% completion fee, HyperCore cost, payout, net proceeds, profit, return, break-even and target offer values; seller-seeded nodes remain separate from organic sales and receive independent win-probability, retained-item, expected-result, maximum-loss, and tied-capital treatment. Add cumulative progress and participant observations, then reconcile completed or expired offers so realized results remain distinct from forecasts. ESI supplies character, item, location, and market context only—EQM does not claim that ESI exposes HyperNet offers, sales, participants, winners, or outcomes.
- **Assets:** filter inventory by owner kind, item, owner, location, named corporation hangar division, category, and subtype; resolve authorized Upwell structure names; export CSV; copy Janice-friendly lists; open item context and market/fitting handoffs. EQM retains the raw ESI flag or location ID when ESI cannot disclose a private structure.
- **Industry:** use the full Blueprint Library, BPO/BPC filters, SDE-backed category/subtype filters, Missing BPO pane, blueprint output context, recipes, and material input views.
- **Research Projects:** sync eligible character industry queues, monitor active ME/TE, copying, and invention projects, inspect facilities and timers, and retain completed work for Analytics. Active, paused, and ready-for-delivery ME/TE and copying jobs also act as a shadow blueprint inventory in Analytics so temporarily installed blueprints are not reported as missing.
- **Planetary Industry:** sync eligible colonies, inspect layouts and stored commodities, translate factory schematic IDs into SDE-backed product names and input recipes, monitor extractor expiry and projected program output, identify factories without inbound routes, and filter by character, system, or planet type. Extractor projections use imported SDE Dogma when available and CCP's documented decay/noise defaults otherwise; reauthorize older linked characters if EQM reports the PI scope is missing. Each successful sync also records a durable P0-P4 production observation: the first establishes current projected throughput, and later observations accrue estimated production for Analytics, tier totals, commodity leaders, and pilot rankings. ESI may not advance colony inventories from passive production alone; if a colony snapshot remains stale, visit the planet in space and interact with or submit a colony change, wait approximately 10 minutes for ESI caching, then use **Sync all eligible** or the character PI sync button. The plain **Refresh** button only reloads EQM's last saved snapshot.
- **Mining Ledger:** queue personal mining-history syncs, import the detailed EVE ledger export for residue/value fields, filter by character/system/date/operation, create named operations with selected miners and boosters, and compare recovered volume, gross extraction, residue loss, estimated value, and measured efficiency. ESI rows remain stored after they age out of CCP's rolling response window.
- **Mining Op Settlement:** open the calculator beneath Ledger History, choose a saved operation or date range, and select whether miner shares follow estimated raw value, recovered volume, raw quantity, or equal starting shares. Enter the actual refined minerals and quantities because recorded output is authoritative; optional hub pricing snapshots each unit price, while manual changes are flagged as overrides. Operation reserves and expenses are deducted before fixed-percentage support payouts and weighted shares. Enter percentages as either `10` or `0.10` for 10%; the preview shows the normalized result and must reconcile before saving. Drafts remain editable, while finalized settlements are immutable snapshots of ledger rows, prices, calculations, and payouts.
- **Corporations:** refresh corporation links, sync corporation assets/blueprints/wallet divisions through eligible tokens, and inspect sync stale/error messages.
- **Contracts:** sync current character and eligible corporation contracts, then sort/filter active contract data.
- **Analytics:** capture and inspect snapshots, metric widgets, baseline-aware deltas, and exports. Automatic ESI observations are limited to the character or corporation that changed and identical scope/source observations are coalesced for one hour, preventing unrelated syncs from duplicating the full blueprint and skill library. While a report is being assembled, EQM shows an explicit **Analytics loading** notice and asks the operator not to refresh. Hosts can use **Inspect storage** to preview redundant legacy automatic snapshots, then optionally compact them while preserving every manual snapshot and the latest complete automatic snapshot for each UTC day. Compaction makes freed PostgreSQL space reusable immediately; returning it to the host filesystem still requires a separately planned `VACUUM FULL` maintenance window.
- **Profile:** manage account details, timezone, private messages, and EVE mail features when mail scopes are present.
- **Settings:** configure character privacy, import SDE data, enable/disable major sections, and manage role/section permissions.
- **ESI Sync:** link/re-link EVE characters, inspect server status, review missing scopes, authorize contact sync, unlink tokens, and import public ESI entities by ID.
- **User Administration:** invite users, manage local accounts, and assign roles.
- **Audit Log:** review sync peeks, system events, admin activity, and operational history.

## Mining Settlement Limitations

Mining settlements currently pay in ISK and use manually entered actual refined output. EQM does not yet calculate theoretical refining from character skills, implants, structure bonuses, rigs, taxes, sovereignty, or SDE dogma. Physical mineral allocation, largest-remainder unit splitting, revisions, voiding, and payout exports are planned follow-up work; finalized Phase 1 settlements deliberately remain unchanged when prices, SDE data, characters, or ledger history later change.

## HyperNet Tracker Data Limits

HyperNet offer activity is manual in this release. ESI does not provide EQM with offer creation, node sales, participants, winners, expirations, or outcomes, so users must enter progress snapshots and reconcile final results from the in-game offer. Character, item, location, and market context may still be resolved through existing EQM/ESI data. The internal provider abstraction is intended for a future sanctioned source without changing saved offer records.
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
12. HyperNet Tracker reproduces the eight-node Marshal calculation, keeps seeded nodes separate from organic sales, records 0/8 to 1/8 organic progress, and reconciles completed profit or expired HyperCore loss without claiming ESI HyperNet access.
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

## License

EVE Quartermaster is licensed under the **GNU Affero General Public License v3.0 or later**. See `LICENSE` for details.

This project is not affiliated with or endorsed by CCP Games. EVE Online and related names are trademarks of CCP hf. EVE ESI data belongs to its respective owners and is accessed through authorized user tokens.

## AI Collaboration Notice

This project is collaboratively created with generative AI. Human project direction, review, testing, deployment choices, EVE domain decisions, and final stewardship remain with the project maintainers.
