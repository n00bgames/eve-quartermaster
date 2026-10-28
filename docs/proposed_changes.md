# Proposed Changes

Use this file for good ideas that should not interrupt the current frontend segmentation pass.

## Fitting Dogma Fidelity

Continue improving fitting simulation Dogma fidelity as real fittings expose gaps. Prioritize targeted, evidence-backed modifiers over broad rewrites until the full effect graph is ready.

## Password Reset

Add an account password reset flow. Prefer a secure token-based reset path for users who cannot sign in, plus clear admin controls for forced resets.

## Server-side Asset Exports

Add full filtered CSV and Janice-list exports from the backend for the Assets ledger so large inventories can export complete filtered results without loading every row into browser memory.

## Settings Maintenance Actions

Add Settings-page maintenance buttons for safe backend-worker tasks such as fetching the latest SDE into `/sde` and optionally queueing SDE import. For host-level update/rebuild controls, prefer a small explicit host helper service over mounting the Docker socket into the app container.

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

Local Scan and D-Scan implement the lifecycle below. Battle-report enhancements remain pending, so the shared all-three checklist stays open.

- [ ] Generate public-facing share links for **local scan reports**, **d-scan reports**, and **battle reports**, viewable without signing in.
- [ ] When generating any of these reports, provide a retention dropdown with these choices, in this order: **30m, 1h, 2h, 12h, 24h, 3days, 7days, 30days, permanent**. Apply the chosen lifetime from report generation; permanent reports remain until explicitly deleted.
- [ ] Expire reports automatically at the selected retention deadline. Expired or deleted reports must no longer be available through their public links or server-side PDF exports.
- [ ] Record the generating EQM account and corporation attribution when the report is generated so ownership and corporation deletion scope can be enforced.
- [ ] Authenticated users may delete their own reports. Directors may also delete reports generated by their corporations. Admins and roles above admin may delete any report.
- [ ] Support deletion **case by case**, **for a report-generation date range**, or **en masse** across all reports within the acting user's permitted scope. Enforce the same ownership/corporation/admin scope on every deletion mode on the server.
- [ ] Export all three report types as **PDF**. Use small logos and the header attribution **Generated by EVE Quartermaster v{version} by {accountname}**, resolving the version and generating account from the report's generation metadata, rather than the public viewer or downloading account.

## Personal Section Layouts

- [ ] Let each user rearrange section panels/widgets with drag and drop.
- [ ] Save layouts per EQM user and section, and restore them across sessions without changing other users' layouts.

- [ ] Include navigation-menu customization: users can drag and drop whole sections to change their order and choose where each section appears.
- [ ] Let users rename their navigation sections and move/reorder modules between sections.
- [ ] Persist section order, custom section names, module grouping/order, and panel layouts per account across sessions; customization must not grant access to modules the user lacks permission to view.
- [ ] Keep the standard navigation layout, including Intel as the second named group, as the default for users without a saved custom layout.

## Shared Report Header

- [ ] At the top of both the Industry Report and Inventory Report, show the EQM banner and the attribution **Generated with EVE Quartermaster v{version} by {accountname}**.
- [ ] Resolve `{version}` from the application version at generation time and `{accountname}` from the generating EQM account, rather than a selected character or corporation.
- [ ] Include the banner and attribution in rendered/PDF reports; preserve the equivalent version/account attribution in the top metadata rows of CSV exports.

## Industry Report

- [ ] Add a unified **Industry Report** that brings assets, industry jobs, and planetary industry (PI) information together under one report workflow.
- [ ] Total all minerals and PI commodities on hand, with quantities by item type.
- [ ] After the overall totals, itemize the holdings by character and corporation so each owner's contribution is visible.
- [ ] Export the Industry Report to **CSV** or **PDF**.

## Inventory Report

- [ ] Add an **Inventory Report** with inventory totals grouped by item type and category, including all ship types, module types, and other inventory categories.
- [ ] Use the same itemization order as the Industry Report: overall totals first, followed below by itemized assets grouped by character and corporation.
- [ ] Export the Inventory Report to **CSV** or **PDF**.

## Themes and Personal Branding

- [ ] Add user-selectable color palettes/themes for the EQM interface.
- [ ] Allow each user to choose or upload their own logo for their EQM interface.
- [ ] Save theme and logo preferences per user and restore them across sessions without changing other users' branding.

## Implemented in the 2.0 development pass

- [x] Intel Analyst role; Navigation and Market defaults available to all roles.
- [x] Multiple account roles with aggregated permissions, custom-role support, multi-role account creation/invitations, and host-assignment safeguards.
- [x] Role/section scoped ESI consent and collection, including existing broad tokens and utility-account exclusion from private collection/Quartermaster oversight.
- [x] Local-scan optional system search and selected-character Set Destination, with explicit waypoint consent and per-character results.
- [x] Per-user persistent corporation/alliance red-highlight preferences, captured in public local reports and PDFs.
- [x] SDE stored/import totals for every import-stat field and nested celestial/Dogma/blueprint/PI counts.
