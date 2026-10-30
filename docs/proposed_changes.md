# Proposed Changes

Use this file for good ideas that should not interrupt the current frontend segmentation pass.

## Fitting Dogma Fidelity

Continue improving fitting simulation Dogma fidelity as real fittings expose gaps. Prioritize targeted, evidence-backed modifiers over broad rewrites until the full effect graph is ready.

## Password Reset

- [x] Implemented: expiring single-use recovery links, configurable SMTP, admin-generated links/forced resets, session invalidation and shared throttling. [Setup and validation](password-recovery-and-exports.md).

## Server-side Asset Exports

- [x] Implemented: full filtered CSV and aggregated Janice downloads, batched standard queries, existing visibility/permissions and filter parity, without loading all rows into the browser table. [Behavior and limits](password-recovery-and-exports.md#full-filtered-asset-downloads).

## Settings Maintenance Actions

- [x] Settings controls to download/validate the latest CCP SDE into `/sde/downloads`, optionally import it, and show durable worker progress. Existing manual/agents imports now use the same worker and overlap guard. Requires migration 0097 and a writable worker SDE mount. [Controls and rollout](sde-maintenance.md).
- [ ] Host-level update/rebuild controls through a narrowly scoped, explicitly installed helper service. [Helper design](sde-maintenance.md#host-updaterebuild-helper-design-not-enabled).

## Local Scan Analysis

- [x] Add a local-chat pilot-list scan and analysis tool, similar to [who.ltns.space](https://who.ltns.space/). Place its navigation link in the **Intel** group (the second named sidebar group).
- [ ] Treat the user-supplied WHO local-scan screenshot and [who.ltns.space](https://who.ltns.space/) as the formatting and local-scan information/feature-parity reference, rather than providing only a flat pilot list. Preserve EQM branding and user-selected themes.
- [x] Use a compact, centered report with a two-column group layout on wide screens and a readable stacked layout on narrow screens. Show a **Local scan** heading, total character count, and generation timestamp/relative scan age above the results.
- [x] Group characters by alliance, with bold alliance headings, small alliance logos, and right-aligned total-count badges. Nest corporation rows below each alliance with corporation logos, names, and their character counts. Include an explicit **No alliance** group for unaffiliated corporations; rank groups by their scan counts and retain access to full long names.
- [x] Provide a **Simple** search/paste entry accepting character names, local scans, d-scans, or fleet compositions, routing each supported input to the appropriate analysis while keeping the dedicated d-scan module available.
- [x] Provide an **Advanced** mode with addable/removable conditions on **Character name**, **Corporation name**, or **Alliance name**, using **contains**, **starts with**, **ends with**, or **equals** matching. These field/operator choices and Add Condition were verified on the reference site on October 28, 2026.
- [ ] Match the reference's local-scan information and useful result interactions, including access to the characters underlying the corporation/alliance summaries. Verify remaining result/detail interactions against the reference during implementation; do not treat this screenshot's visible subset as the entire parity checklist.
- [x] Display clear notices when affiliation enrichment is unavailable or limited for large scans, as shown in the reference, and keep available counts/results readable. Determine supported limits during implementation rather than inferring an exact threshold from the screenshot.
- [x] Apply the shared **Public Scan and Battle Reports** requirements to local-scan results, including public URLs, selectable retention, scoped report deletion, and PDF export. Preserve alliance/corporation hierarchy, logos, counts, and scan metadata in the public report and PDF.

Implementation: [Local Scan, roles, ESI privacy, and SDE totals](local-scan.md). Simple input supports pilot names/fleet rows and hands recognizable d-scans to the dedicated D-Scan module as an unpublished draft. Simple and Advanced result filtering are implemented. Full third-party feature parity beyond the supplied reference remains a validation item.

## Directional Scan Parser

- [x] Add a paste-in directional scan (d-scan) parser, similar to [dscan.info](https://dscan.info/), with readable ship/object summaries. Place its navigation link in the **Intel** group alongside the local parser, Intel Reports, and Local Threat Analyzer.

- [x] Use the supplied dscan.info screenshots as the d-scan layout/feature reference: input textarea and report columns for ships by exact type, ship classes, deployables, and overall counts, sorted by frequency.
- [x] Show item icons beside actual ship-type and deployable rows in results/reports.
- [x] Provide manual combat-recon additions for Huginn, Lachesis, Rook, and Curse, clearly distinguished from ships observed on d-scan; support adding/updating a linked local scan and show total ship mass.
- [x] Let users select an optional solar system through a search bar. Show the selected system, generating EQM account, exact generation date and relative age, with Copy Link and PDF controls.
- [x] Reuse Local Scan's saved per-user corporation/alliance highlight list, with quick add/remove and red matching organization-owned assets/totals. Attribute objects only when supported by supplied/verified ownership data; ship names alone cannot identify an owner.

Implementation: [D-Scan formats, counts, public reports and rollout](dscan.md). Red markings apply to linked-local organization/pilot counts; ordinary d-scan rows do not establish ownership. Updates save new immutable snapshots.

## Public Scan and Battle Reports

- [x] Public links for Local Scan, D-Scan and Battle Reports, with anonymous and creator-only private generation options.
- [x] Retention: **30m, 1h, 2h, 12h, 24h, 3days, 7days, 30days, permanent**; expired/deleted reports cannot be read or exported.
- [x] Internal creator/corporation attribution and server-enforced individual, date-range and all-in-scope deletion. Directors manage attributed corporation public reports; admins/hosts manage all public reports. Private snapshots remain creator-only.
- [x] Branded PDFs with generation version/date and main-character attribution or Anonymous, never account login. Battle PDFs include team totals, composition, pilot details and timeline.

Implementation: [Battle Report management and migration 0094](battle-report-management.md). Historic unattributed Battle snapshots remain creator/admin-managed; corporation ownership is not inferred retroactively.

## Personal Section Layouts

- [x] Add cross-section shortcut dropdowns to navigation groups for persistent Quicklaunch menus, preserving original links and allowing individual shortcut removal.

Implemented for multi-section workspaces; [controls, coverage and rollout](appearance.md).

- [x] Let each user rearrange section panels/widgets with drag and drop.
- [x] Save layouts per EQM user and section, and restore them across sessions without changing other users' layouts.

- [x] Include navigation-menu customization: users can drag and drop whole sections to change their order and choose where each section appears.
- [x] Let users rename their navigation sections and move/reorder modules between sections.
- [x] Persist section order, custom section names, module grouping/order, and panel layouts per account across sessions; customization must not grant access to modules the user lacks permission to view.
- [x] Keep the standard navigation layout, including Intel as the second named group, as the default for users without a saved custom layout.

## Shared Report Header

- [x] Industry Report uses the EQM banner, generation-time application version and current main-character attribution (Anonymous fallback); account names are never published.
- [x] Branded PDF and CSV metadata include attribution and generation/data timestamps. Explicitly anonymous reports remain anonymous.
- [x] Apply the same header scheme to Inventory Report with private main-character attribution.

## Industry Report

- [x] Sortable section headers; full dataset sorted before pagination, including existing public reports.

- [x] Industrial materials, BPOs/BPCs/reaction formulas, active industry jobs and PI reporting; personal general assets use the separate private Inventory Report.
- [x] Overall mineral/PI and stock totals by type, followed by owner/location itemization.
- [x] CSV and PDF exports.
- [x] Private by default; opt-in expiring public snapshots or dynamic current-stock links. Public creator/owner anonymity is mandatory.
- [x] Explicit NPC-station/Upwell can or hangar selection for finished stock; exclude fittings/onboard contents and unselected finished goods.
- [x] Dynamic scope/permission revalidation, fixed original scope and scoped individual/date/all deletion.

## Ship Reports

- [x] Creator-only ship snapshots with total hulls and counts for each hull type/class, then character/corporation and location detail.
- [x] Count packaged stack quantities and exclude modules, drones, blueprints and capsules; per-class exclusions and Subcaps preset are saved with each report.
- [x] Assignable Fleet Commander below Director with ship-only reports; lower roles cannot see capitals in ship Analytics totals, history, type lists or exports.
- [x] Ship quantity/type history from asset sync/manual snapshots; owner privacy, zero observations for removed types and distinct-type deduplication.
- [x] Sortable tables, CSV/PDF totals, retention, saved history and individual/date/all deletion; no public ship links.

Implementation: [Ship Reports and account SSO](sso-and-ship-reports.md). Source complete; deployment is separate.

## Inventory Report

- [x] Add an **Inventory Report** with inventory totals grouped by item type and category, including all ship types, module types, and other inventory categories.
- [x] Use the same itemization order as the Industry Report: overall totals first, followed below by itemized assets grouped by character and corporation.
- [x] Export the Inventory Report to **CSV** or **PDF**.
- [x] Inventory reports are creator-only with no public links/listings; named owner detail, retention and individual/date/all deletion.

## Themes and Personal Branding

- [x] Admin-controlled site banner and login background uploads with validated images and reset controls.

- [x] Add user-selectable color palettes/themes for the EQM interface.
- [x] Allow each user to choose or upload their own logo for their EQM interface.
- [x] Save theme and logo preferences per user and restore them across sessions without changing other users' branding.

## Implemented in the 2.0 development pass

- [x] Intel Analyst role; Navigation and Market defaults available to all roles.
- [x] Multiple account roles with aggregated permissions, custom-role support, multi-role account creation/invitations, and host-assignment safeguards.
- [x] Role/section scoped ESI consent and collection, including existing broad tokens and utility-account exclusion from private collection/Quartermaster oversight.
- [x] Local-scan optional system search and selected-character Set Destination, with explicit waypoint consent and per-character results.
- [x] Per-user persistent corporation/alliance red-highlight preferences, captured in public local reports and PDFs.
- [x] SDE stored/import totals for every import-stat field and nested celestial/Dogma/blueprint/PI counts.


## EVE account sign-in

- [x] Log in with a linked EVE character using identity-only SSO, with browser-bound single-use PKCE and character ownership verification.
- [x] Accept an administrator invite and link the first EVE character without choosing an EQM password; retain exactly the invited combined roles.

Implementation and rollout: [EVE SSO sign-in](sso-and-ship-reports.md). Requires migration 0098 and matching frontend/API; no live CCP sign-in or deployment performed during local verification.

## Intel notes and market history

- [x] Edit/delete own Intel Report notes; Admin/Host moderation, inline deletion confirmation, concurrency conflicts and audit metadata.
- [x] Permit the assigned/custom-base Intel Analyst role through the Intel Reports access gate while retaining private-enrichment boundaries.
- [x] Expand matched appraisal items into regional completed-trade history with per-unit average/low/high, volume, current hub orders and a hub selector; load on demand and respect ESI caching.

Implementation: [Intel notes](intel-reports.md#editing-and-deleting-analyst-notes) · [Market history](market-history.md). Source complete; deployment is separate.

## Non-combat Intel sightings

- [x] Searchable system and ship type beside name entry; record sightings during explicit character report runs without requiring killmail evidence.
- [x] Default server report-run time plus optional historical UTC entry; retain posting time and analyst separately.
- [x] Timeline details and daily sightings, with 0/0 ship/system/region entries; keep kills/losses, combat activity and associations unchanged.
- [x] Retry deduplication, canonical SDE validation, current Intel permissions, bounded detail list/full counts and migration 0099.

Implementation: [Non-combat sightings](intel-reports.md#non-combat-ship-sightings). Source complete; migration and deployment are separate.
