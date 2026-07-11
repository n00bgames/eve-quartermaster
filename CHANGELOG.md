# Changelog

All notable changes to EVE Quartermaster are tracked here.

This project is moving quickly during beta. Version sections are written as user-facing release notes first, with implementation detail included where it helps operators understand deployment or testing impact.

## [0.1.6-beta] - 2026-07-10

### Added

- Added wardec indicators to route, capital jump, and character killmail displays so hostile intel can distinguish war-target losses from ordinary ganks.
- Started frontend segmentation by moving the app version, killmail data shapes, and wardec badge into purpose-built modules.
- Split market appraisal data shapes, pricing helpers, and reusable market widgets out of the large frontend entry module.
- Split navigation route, jump plotter, and threat/intel widgets out of the large frontend entry module.
- Split fitting shared types, simulation helpers, and fit-context widgets out of the large frontend entry module.
- Split fitting sync, import, and saved-fitting list panels out of the large frontend entry module.
- Moved the remaining Fittings page container out of the large frontend entry module.
- Added fitting ammo/script groups so multiple launchers, turrets, or scripted modules can share charge assignment from one group control.
- Added reusable pilot security-status badges for character cards, local threat pilots, route killmail rows, and jump-planner killmail rows.
- Added a Skills-page sync-all action that queues backend skill refreshes for every eligible character, skips opted-out characters, and shows progress with the queue badge.

### Fixed

- Applied strategic cruiser subsystem slot/resource dogma before fitting simulation readiness checks so T3C CPU, powergrid, slot capacities, probe launcher CPU, covert cloak CPU, and medium weapon required-skill fitting reductions are not evaluated from bare hull/module values only.
- Stored ESI character security status during public character imports and SSO sync so pilot identity surfaces can display current security information when available.

### Changed

- Renamed Capital Jump Plotter to Jump Capable Ship Plotter and added Black Ops battleships to the jump-capable ship list.
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