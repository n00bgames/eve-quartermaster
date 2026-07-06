# Changelog

All notable changes to EVE Quartermaster are tracked here.

This project is moving quickly during beta. Version sections are written as user-facing release notes first, with implementation detail included where it helps operators understand deployment or testing impact.

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