# Changelog

All notable changes to EVE Quartermaster are tracked here.

This project is moving quickly during beta. Version sections are written as user-facing release notes first, with implementation detail included where it helps operators understand deployment or testing impact.

## [0.1.10-beta] - 2026-07-16

### Added

- Added a persistent per-character Mining Ledger with paged ESI history sync, detailed residue-aware CSV/TSV imports, SDE ore/system metadata, and captured market estimates.
- Added named mining operations grouped by solar system, selected participants, and configurable time windows, including miner/booster roles and optional ship/crystal notes.
- Added mining analytics for recovered and gross extraction, residue loss, net value, ore composition, yield history, system output, highest-value miners, highest-volume miners, and residue-measured efficiency rankings.
- Added a confirmation-protected, character-scoped Mining Ledger reset for correcting imports attributed to the wrong character.
- Added per-corporation analytics exclusion controls; hidden corporations are excluded automatically, while visible NPC or affiliation corporations can be excluded independently.
- Added Analytics-page corporation scope controls so affiliation-only and historical corporations can be included or excluded without appearing as managed corporations.
- Added submitting-user attribution to Manufacturing ledger cards.
- Added a Start Job action for Manufacturing drafts that begins the job timer from the current local timestamp.
- Added a Research Projects page backed by character industry queues for ME, TE, copying, and invention work, with research-only background sync, retained project history, and researcher/activity analytics.
- Added corporation-owned research projects with Director/Factory Manager role checks, installer attribution, and corporation ownership in project rows.

### Fixed

- Fixed Sync All mining jobs failing before persistence because the ESI worker did not import the mining-ledger upsert service.

- Fixed character contract syncs for player-owned structure locations whose trillion-range EVE IDs do not fit the station table's integer key.
- Preserved original contract-sync failures after database errors and displayed every failed Sync All task instead of only the first.
- Stored shared EVE contracts independently per character or corporation so syncing one owner no longer reassigns another owner's contract rows.
- Removed hidden and analytics-excluded corporations from existing analytics summaries, trends, duplicate-blueprint results, exports, and future snapshots.
- Fixed Jump Clone implant dogma cards painting beneath neighboring clone content and enforced an opaque tooltip surface.

### Changed

- Replaced Research Project cards with a sortable table and prechecked corporation roles before queuing corporation research syncs.
- Marked the Fittings navigation entry as a bright-red WIP warning while fitting calculations remain under development.
- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.10-beta.

## [0.1.9-beta] - 2026-07-15

### Added

- Added Manufacturing analytics widgets for realized output quantity, actual and current input costs, savings, kept/sold disposition, sales revenue, and realized profit.
- Added a README feature-preview warning for the Fittings module while dogma, skill, implant, cargo, and module-derived simulation values remain under active rebuild.
- Added Manufacturing final-product market lookup with highlighted best buy and lowest sell opportunities across major trade hubs.
- Added Manufacturing output tracking for pending, sold, and kept products, including sale price, outcome notes, and sale-margin summary.
- Added Manufacturing line-item price-paid tracking so operators can compare current market value against actual spend and see savings from on-hand materials.
- Added Manufacturing ledger support for ME/TE research, copying, invention, and reaction job tracking with decryptor/datacore/reaction material inputs.

### Changed

- Recolored the "EVE is Excel in a flight suit." tagline with the muted red interface accent on sign-in, invitation, and in-app views.
- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.9-beta.

## [0.1.8-beta] - 2026-07-13

### Added

- Added dogma-backed fitting Cargo cards that display current/maximum volume for cargo hold, drone bay, fighter hangar, fuel bay, fleet/ship maintenance bays, infrastructure bay, and specialized holds when the SDE exposes those capacities.
- Added item volume serialization for fitting cargo, drones, fighters, and bay contents so draft fits can estimate carried m3 before simulation.
- Stored EVE type cargo capacity from SDE and ESI metadata so ship cargo holds appear correctly in fitting simulation.
- Made pasted EFT fitting imports refresh public type metadata and return ship cargo capacity immediately to the draft workshop.
- Added a freighter base cargo-capacity fallback so draft fits show known cargo holds even before refreshed SDE/ESI capacity metadata is available.

### Changed

- Consolidated fitting cargo, drones, and fighters into one bay-aware draft workflow with utilization meters and over-limit highlighting.
- Made fitting cargo-hold capacity skill/module-aware in simulation, including racial freighter skill bonuses and fitted cargo-capacity modifiers.
- Corrected Fenrir fallback cargo capacity and kept over-slot fitted modules from contributing simulation effects.
- Corrected cargo-expander math by treating SDE cargoCapacityMultiplier as a direct, unpenalized multiplier and cargoCapacityBonus as a percent bonus.
- Applied imported passive structure HP and max-velocity multipliers so Expanded Cargohold penalties affect fitting tank and movement stats.
- Restored fitting stat estimates for online modules so imported fittings apply module effects without requiring every item to be toggled active.
- Added a red fitting simulator development warning badge because dogma coverage is still incomplete and values may be inaccurate.
- Clamped fitted-slot quantities to one module per slot so draft quantity cannot create false slot overages.
- Improved EFT import slot inference so obvious low-slot modules are not placed in mids just because of sparse section spacing.
- Normalized fitting add/update requests so low-slot modules are not saved into mid slots unless deliberately carried as cargo.
- Hid empty zero-capacity bays from fitting Cargo cards while keeping over-limit checks for bays with contents.
- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.8-beta.

## [0.1.7-beta] - 2026-07-13

### Added

- Added Windows and Linux/macOS SDE fetch scripts that download the latest Tranquility SDE into the mounted `sde/` folder with optional extraction.
- Added a persistent red-alert Threat Analyzer header action that jumps from any page to the Local Threat panel.
- Added a Characters-page Sync all eligible action that queues assets, skills, fittings, and contracts for every permitted non-opted-out character with matching ESI scopes and shows queue-badge progress.
- Added corporation hiding and tightened character/corporation lists so metadata-only CEOs and affiliation-only corporations do not appear as managed EQM entries.
- Added pagination and extra spacing to the Assets ledger so large filtered result sets render in manageable pages.
- Reduced browser memory pressure on large asset ledgers by loading a small asset sample at startup and fetching Assets-page rows from a server-backed paged endpoint.
- Expanded the README with detailed EVE developer application, ESI/SSO scope, SDE YAML download/import, and EQM section usage instructions.

### Changed

- Updated installer next-step guidance to use the new SDE fetch scripts.
- Updated installer next-step guidance to point operators at EVE developer credentials, YAML SDE setup, and README setup details.
- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.7-beta.

## [0.1.6-beta] - 2026-07-10

### Added

- Added wardec indicators to route, capital jump, and character killmail displays so hostile intel can distinguish war-target losses from ordinary ganks.
- Started frontend segmentation by moving the app version, killmail data shapes, and wardec badge into purpose-built modules.
- Split market appraisal data shapes, pricing helpers, and reusable market widgets out of the large frontend entry module.
- Split navigation route, jump plotter, and threat/intel widgets out of the large frontend entry module.
- Split fitting shared types, simulation helpers, and fit-context widgets out of the large frontend entry module.
- Split fitting sync, import, and saved-fitting list panels out of the large frontend entry module.
- Moved the remaining Fittings page container out of the large frontend entry module.
- Split the Analytics Platform page and analytics data shapes out of the large frontend entry module.
- Split the Alliance Roster page and roster data shapes out of the large frontend entry module.
- Split the Character Skills page and skill sync data shapes out of the large frontend entry module.
- Split the Characters page, persistent character hover card, and character dossier data shapes out of the large frontend entry module.
- Split the Profile page and profile/mail/message data shapes out of the large frontend entry module.
- Split the Settings page, section switch controls, SDE import panel, and permission data shapes out of the large frontend entry module.
- Split the ESI Sync page and ESI contact-sync data shapes out of the large frontend entry module.
- Split the profile user administration pane out of the large frontend entry module.
- Split the Contracts page and contract data shapes out of the large frontend entry module.
- Split the Corporations page and corporation sync data shapes out of the large frontend entry module.
- Extracted the shared frontend API client and inventory classification/types helpers out of the large frontend entry module.
- Added SDE-backed category and subtype filters for Assets and Blueprint Library views, including ship hull classes, ammunition/charge groups, rig groups, and capital-construction blueprint chain filtering.
- Added a Missing BPOs pane at the bottom of the Blueprint Library, grouped by product category from the SDE manufacturing catalog.
- Added fitting ammo/script groups so multiple launchers, turrets, or scripted modules can share charge assignment from one group control.
- Added reusable pilot security-status badges for character cards, local threat pilots, route killmail rows, and jump-planner killmail rows.
- Added a Skills-page sync-all action that queues backend skill refreshes for every eligible character, skips opted-out characters, and shows progress with the queue badge.
- Added prompted prerequisite bootstrapping to the Windows and Linux installer scripts for Git, WSL2, Docker Desktop, Docker Engine, and Docker Compose support.

### Fixed

- Made character hover cards persist until closed with the new X button or Escape so zKill links and card actions remain reachable.
- Widened the character picker pane so persistent character hover cards show their close button without horizontal scrolling.
- Raised Skills-page character hover cards above neighboring skill profile rows so persistent character summaries stay readable while open.
- Restored character dossier blueprint-product fallback logic so character pages no longer 500 when loading visible characters.
- Converted undecryptable ESI refresh tokens into a clear reauthorization-needed sync error instead of a 500 during asset sync.
- Backfilled blueprint product classification from SDE industry activities so blueprint category/subtype filters populate correctly, including Drones/Fighters.
- Kept final capital, freighter, and jump freighter hull BPOs out of the Capital construction blueprint filter while retaining supporting chain inputs/components.
- Split RAM and reaction formulas into their own blueprint filter categories and kept them out of capital-construction-only blueprint views.
- Excluded invention-produced Tech II blueprint copies from the Missing BPOs catalog so copy-only blueprints are not listed as missing originals.
- Applied strategic cruiser subsystem slot/resource dogma before fitting simulation readiness checks so T3C CPU, powergrid, slot capacities, probe launcher CPU, covert cloak CPU, and medium weapon required-skill fitting reductions are not evaluated from bare hull/module values only.
- Stored ESI character security status during public character imports and SSO sync so pilot identity surfaces can display current security information when available.

### Changed

- Renamed Capital Jump Plotter to Jump Capable Ship Plotter and added Black Ops battleships to the jump-capable ship list.
- Reorganized the sidebar navigation into overview/navigation, character functions, inventory and industry tools, and account/admin groups.
- Tuned the frontend typography hierarchy to reduce over-bold repeated labels, table values, filter chips, badges, and utility buttons so dense operational pages are easier to scan.
- Replaced the Overview Blueprint Library panel with a lightweight blueprint preview so dashboard loads do not initialize the full blueprint tooling or Missing BPO pane.
- Bumped the visible app and package version to 0.1.6-beta.

## [0.1.5-beta] - 2026-07-08

### Added

- Added a Prefer Safer Route option to Route Checker so gate routes can favor highsec travel even when the route becomes longer.
- Added Route Checker avoid-list controls matching the Capital Jump Plotter flow, including per-system avoid buttons and a clearable avoid list.

### Changed

- Route Checker and Gatechecker now pass safer-route and avoid-system preferences through the same backend route planner, keeping navigation behavior consistent across route tools.
## [0.1.4-beta] - 2026-07-06

### Changed

- Bumped the visible app, README, Android wrapper, backend API, and ESI client user-agent versions for the latest beta polish pass.
## [0.1.3-beta] - 2026-07-05

### Added

- Added cross-section context links: fittings now show owned hull/modules/cargo/drones and can price missing or full fits; market appraisal lines show owned quantities with asset/fitting jumps; assets can jump to pricing or fittings; recipes and blueprints show owned outputs/material coverage with market handoffs.
- Added the Market Appraisal module for Janice-style pasted item lists with flexible quantity parsing, multi-hub buy/sell/split comparisons, Dudreda support, and unmatched-item warnings.
- Added market usability signals: best instant-sale highlighting, cheapest acquisition highlighting, best split estimate highlighting, order-depth health badges, and top buy-here/sell-there margin hints.
- Added Contracts support for syncing current character contracts and eligible corporation contracts, with status filtering and sortable contract headers.
- Added fitting clipboard import so EFT-style fits can be pasted into EQM as editable draft fittings.
- Added fitting editor improvements: drag/drop part picker, module removal, charge/script assignment for valid fitted modules, cleaner cargo/drone/fighter rows, cargo hold display, and EVE-style copy/export behavior.
- Added deeper fitting simulation surfaces for readiness, resources, offense, tank, capacitor, movement, module state cycling, hot/overheated module states, charge-aware weapon estimates, and fitting-derived skill plan copy text.
- Added Capital Jump Plotter refinements: capital ship selection, NPC-station-only routing text, green-station filtering, industrial/all-kill selection, station/cyno guidance display, route avoid-list controls, and per-waypoint observed activity intel from cached hourly ESI jump observations.

### Changed

- Renamed the character standing sync area to Character Contacts Sync to match the actual writable ESI mechanic.
- Kept market appraisal freight-cost estimates out of the first implementation because player hauling, Red Frog Freight, PushX, and private logistics pricing need a more explicit model.
- Improved public-facing README documentation and screenshot ordering for tester onboarding.

### Fixed

- Market appraisal opportunity cards now only show profitable station-to-station trades; no-profit appraisals show a neutral no-current-profit badge instead of a negative trade suggestion.
- Corporation sync flows now continue past corporations where the linked character lacks the required corporation roles instead of stopping the whole batch.
- Improved station display plumbing for jump planning so NPC station names can be shown separately from station type/cyno-risk guidance when SDE data is available.

## [0.1.2-beta] - 2026-07-05

### Baseline

- First tracked beta baseline for the public-testing README badge and in-app version badge.
- Included account login, EVE SSO linking, asset and corporation syncs, blueprint/SDE import, analytics foundations, navigation tooling, local threat scanning, permissions, audit visibility, messaging, Android wrapper support, and initial fitting tools.
