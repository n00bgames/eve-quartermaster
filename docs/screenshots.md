# EQM screenshot gallery

**Latest:** [v2.0 development previews](#v20-development-previews), captured October 28, 2026.

HyperNet and PLEX previews added **October 3, 2026**, from source commit `4ec0931cda1f800afb1d83560e19862809148ccd`. Atlas previews were added September 19 from `f6131a1be18e808c886f75c380c6ebf646323bfb`; the earlier gallery reconciliation was September 11 against the v1.0 candidate `f894f27ad7fb2ef4956e5bef2e97d3865fe8cfd2`. [README](../README.md) · [v1.0.5 release notes](releases/v1.0.5.md) · [Install](../README.md#install)

## How to read this gallery

The v1.0 images are fresh browser captures of the actual current React components in a local preview, using synthetic pilots, stock and market data. They are component demonstrations, not authenticated production-server screenshots or live EVE state. The preview header is labeled; the clocks are the actual header-clock component. The calculator images are cropped to that component. Native Rust executed the supply/chain calculations; the planner used the disposable API preview and native allocation worker.

All **63 existing images** remain linked below. They are historical: some are demo illustrations or reconstructed/sanitized panels, and none is certified as an exact v1.0 screenshot. This audit reconciles module names and visible UX coverage; it does not certify runtime or PYFA parity. No old pixels were repainted to suggest a new version.

## v2.0 development previews

Captured **October 28, 2026** from the current **unreleased 2.0.0 working tree**. These are actual browser captures with synthetic accounts/pilots, not production EVE state. The Local Scan image includes real organization logos as visual references; its memberships are fictional. Crops retain the rendered UI without repainting.

### Earlier privacy implementation (Industry captures superseded below)

Current unreleased captures from the privacy/Industry Report implementation. All data and SSO completion are synthetic; report account identity is never used for attribution.

Profile main-character selection; only currently owned, actively linked characters are offered.

![Profile main-character selection; only currently owned, actively linked characters are offered.](../static/ss/v2.0/profile-main-character.jpg)

Post-link main-character checkbox on a simulated SSO return for an owned synthetic character.

![Post-link main-character checkbox on a simulated SSO return for an owned synthetic character.](../static/ss/v2.0/linked-character-main-checkbox.jpg)

Anonymous private Local Scan generation: signed-in export, no public-copy button, no account attribution.

![Anonymous private Local Scan generation: signed-in export, no public-copy button, no account attribution.](../static/ss/v2.0/scan-private-anonymous.jpg)

Existing D-Scan report now attributed to the selected main and ordered from Titan down through capital and subcapital threat classes.

![Existing D-Scan report now attributed to the selected main and ordered from Titan down through capital and subcapital threat classes.](../static/ss/v2.0/dscan-threat-order.jpg)

Industry Report private default, opt-in public link, dynamic database mode, anonymous attribution and retention controls.

![Industry Report private default, opt-in public link, dynamic database mode, anonymous attribution and retention controls.](../static/ss/v2.0/industry-report-options.jpg)

Actual public Industry Report with overall mineral/PI totals, owner stock detail, blueprints, jobs and PI infrastructure.

![Actual public Industry Report with overall mineral/PI totals, owner stock detail, blueprints, jobs and PI infrastructure.](../static/ss/v2.0/industry-report-dynamic.jpg)

Battle Report anonymous/private generation and expiration controls.

![Battle Report anonymous/private generation and expiration controls.](../static/ss/v2.0/battle-report-privacy.jpg)

Rendered Industry PDF: current main-character attribution, overall totals first, then itemized stock, blueprints, industry jobs and PI.

![Rendered Industry PDF: current main-character attribution, overall totals first, then itemized stock, blueprints, industry jobs and PI.](../static/ss/v2.0/industry-report-pdf.png)

Rendered anonymous private Battle PDF: small EQM logo, safe attribution, pilot totals, participants and timeline.

![Rendered anonymous private Battle PDF: small EQM logo, safe attribution, pilot totals, participants and timeline.](../static/ss/v2.0/battle-report-private-pdf.png)

### System totals, pilot portraits and PDF summaries

The selected system and whole-snapshot pilot/ship total lead both report pages. Local Scan includes unresolved pasted names in its total and labels the resolved/unresolved split. D-Scan totals include clearly identified manual additions. Filtering leaves these header totals unchanged.

Expanded corporation lists show small linked portraits; each opens that pilot's zKillboard in a new tab. The same drilldown appears in D-Scan's linked local list. Portraits come from EVE Image Server; memberships/names below are synthetic.

![Local Scan summary and linked portraits](../static/ss/v2.0/local-scan-summary-portraits.jpg)

![D-Scan system and total ship count](../static/ss/v2.0/dscan-system-total.jpg)

Both PDF exports repeat the system and total in the EQM banner on every page; generation attribution and timestamps remain visible. These are cropped banners from actual rendered exports.

![Local Scan PDF summary banner](../static/ss/v2.0/local-scan-pdf-header.png)

![D-Scan PDF summary banner](../static/ss/v2.0/dscan-pdf-header.png)

### Expanded scan reports

Scan workspaces and public report lists now expand vertically with their content, using the page scrollbar. The full-page demo below contains13 ship types,30 observed ships plus5 manual recons,and18 linked pilots. Opened object tables also expand; wide tables retain horizontal scrolling. Earlier D-Scan captures remain below as historical development states.

![Expanded D-Scan report using page scrolling](../static/ss/v2.0/dscan-expanded.png)

### D-Scan

Full public report with actual ship/deployable icons, frequency-ranked types/classes, separate observed/manual totals, base hull mass and linked-local organization highlights. Synthetic fixture:32 observed objects,30 observed ships,3 manual recons and18 linked pilots. The full-page image preserves the actual scrollable report; only11 ship types are present. The detail capture shows manual recon and linked-local controls. Both are unreleased development captures.

![D-scan public report](../static/ss/v2.0/dscan-public.png)

![Manual recon and linked-local editor](../static/ss/v2.0/dscan-editor.png)

### Live organization highlights

Account highlight changes immediately recolor the signed-in Local Scan and linked D-Scan pilot lists, including names and totals. This synthetic scan was generated before the preferences were added. The notice explains how to publish the new markings in a fresh public/PDF snapshot.

![Live red organization and pilot highlights](../static/ss/v2.0/local-scan-live-highlights.jpg)

### Local Scan

Public report with alliance/corporation groups, logos, counts, red organization highlights, creator/date, optional system, destination controls, public-link copy and PDF export.

![Local Scan with synthetic pilot memberships](../static/ss/v2.0/local-scan.png)

### Complete inventory snapshot

Load all accessible asset records with overall row/unit/type totals, local filtering and sorting, refresh controls and paged rendering. This cropped component shows 270 synthetic stacks, 1,074 units and three ship types.

![Complete inventory snapshot totals](../static/ss/v2.0/assets-all-records.png)

### Multiple account roles

Role-editor detail with **Intel Analyst** and **Quartermaster** selected for a synthetic account. Permissions are aggregated across assigned roles.

![Multiple role choices with Intel Analyst and Quartermaster selected](../static/ss/v2.0/multiple-roles.png)

### Complete SDE counters

Stored totals and current/last-import counters, including nested Dogma, blueprint and PI counts. The disposable fixture contains two systems and no SDE import; zero totals and last-run dashes are intentional.

![SDE stored and last-import totals overview](../static/ss/v2.0/sde-totals-overview.png)

![SDE Dogma, blueprint and PI detail totals](../static/ss/v2.0/sde-totals-details.png)

[Capture provenance and checksums](../static/ss/v2.0/capture-receipt.json) · [v2.0 release draft](releases/v2.0.md) · [Feature behavior and rollout](local-scan.md)

## v1.0.5 HyperNet and PLEX

Ten fresh browser captures of the current React components in a disposable local preview, covering changes since the published `v1.0.4` tag. Pilot and financial activity, PLEX quotes, and market history are **sample data**. HyperNet results, node history, and PLEX FIFO totals were computed by the current backend functions using an in-memory database. The Vindicator example reuses author-provided sale proceeds with explicitly illustrative acquisition and core costs; its loss is not the author's actual result. No live account records were changed.

The grid and participant images are author-supplied in-game screenshots processed through the current crop/import controls. OCR ran locally, recovered three participant rows, and the missing seller row was added during manual review. The reviewed import is not a claim of perfect recognition. No screenshots were generated or repainted.

### HyperNet overview

Sample offers show organic progress separately from seeded nodes, financial exposure, and combined lifetime results including a market disposition.

![HyperNet overview with sample activity](../static/ss/v1.0.5/hypernet-overview.png)

### Offer corrections

Correct the seller character, location, node total, prices, costs, expiry, and notes on an active or draft offer.

![HyperNet offer correction form](../static/ss/v1.0.5/hypernet-edit.png)

### Screenshot participant import

Upload or paste, crop the participant list, scan in the browser, and review names and counts before applying them. The screenshot shows the reviewed result with the missing seller row manually restored.

![Participant screenshot import and review](../static/ss/v1.0.5/hypernet-participant-import.png)

### Grid screenshot and node positions

The app retains an original-resolution lossless crop for matching node codes to numbered positions. This preview shows eight seeded positions and a sample winner selected while the offer is still active; saving a position alone does not complete the offer.

![Saved grid reference and numbered node tracker](../static/ss/v1.0.5/hypernet-node-reference.png)

### Node position history

Twelve synthetic completed draws demonstrate layout-specific winning positions and six observed seeded wins against six expected. The heatmap describes the sample and does not predict later draws.

![Node position history from synthetic completed offers](../static/ss/v1.0.5/hypernet-node-history.png)

### Market disposition after expiration

Gross proceeds, individual fees, net proceeds, acquisition and HyperCore costs produce one lifecycle result. The original offer stays expired.

![Expired Vindicator with a recorded market sale and illustrative costs](../static/ss/v1.0.5/hypernet-market-sale.png)

### Updated bid board preview

A fresh capture of the existing buyer workflow with illustrative wins, a pending bid, and a refunded bid. Refund handling was introduced in v1.0.4; it is shown for context, not as a new v1.0.5 feature.

![HyperNet bid history with sample outcomes](../static/ss/v1.0.5/hypernet-bids.png)

### PLEX prices and holdings

Illustrative global bid/ask quotes, holdings, FIFO costs, a sale scenario with 3% combined fees, and thirty days of sample market history. The amounts are fixture data, not current ESI quotes.

![PLEX overview and future-sale scenario with sample prices](../static/ss/v1.0.5/plex-overview.png)

### PLEX transaction ledger

Six sample purchases, sales, and consumption entries leave 950 PLEX and 313,350,000 ISK in realized trading profit, calculated by the current backend FIFO service.

![PLEX transaction ledger with six sample entries](../static/ss/v1.0.5/plex-ledger.png)

### PLEX transaction entry

Record a completed transaction's quantity, actual ISK price, fees, and notes. Opening holdings can retain unknown acquisition costs.

![PLEX transaction form with an illustrative purchase](../static/ss/v1.0.5/plex-record-transaction.png)

[Capture provenance and image hashes](../static/ss/v1.0.5/capture-receipt.json) · [Illustrated release notes](releases/v1.0.5.md) · [PLEX guide](plex-tracker.md) · [Node tracking guide](hypernet-node-positions.md) · [Market disposition guide](hypernet-market-disposition.md)

## v1.0.3 Navigation Atlas

Actual Star Map and Missions/LP components captured in a local browser preview. Geography, stations and agents use the installed public SDE; map activity uses public ESI snapshots. The linked pilot, LP balance and reward offers are **synthetic verification data**, not anyone's production account. These previews do not demonstrate a live private-character LP authorization. No image was repainted or generated.

### Star Map and route handoff

System search and focus, activity, NPC station and agent details, and a Jita-to-Perimeter route handed to the existing route planner. The first map uses a flat X/Z projection.

[Open full resolution](../static/ss/v1.0.3/star-map.png)

![New Eden Star Map — public SDE and local component preview](../static/ss/v1.0.3/star-map.png)

### Missions and LP rewards

Level-4 security agents, jump distances, mission references, corporation stations, reward costs and LP coverage. The preview explicitly identifies its synthetic pilot.

[Open full resolution](../static/ss/v1.0.3/missions-lp.png)

![Missions and LP — real public agent directory, synthetic pilot and rewards](../static/ss/v1.0.3/missions-lp.png)

[Mobile Star Map](../static/ss/v1.0.3/mobile-map.png) · [Mobile Missions & LP](../static/ss/v1.0.3/mobile-missions.png) · [Capture provenance and image hashes](../static/ss/v1.0.3/capture-receipt.json)

## v1.0 highlights

### Corporate stock, sync, scopes and surpluses

My Characters Only, a selected corporate hangar, the corporation sync action, separate stock columns and green surpluses. Demo factory configuration is illustrative.

[Open full resolution](../static/ss/v1.0/pi-supply.png)

![Corporate stock, sync, scopes and surpluses — current component with synthetic demo data](../static/ss/v1.0/pi-supply.png)

### P2 to P4 production

The current calculator with individual I imports, bulk stock import, intermediate factory counts, overlapping completion, bottlenecks and leftovers. Demo inventory produces 240 Recursive Computing Modules.

[Open full resolution](../static/ss/v1.0/pi-production.png)

![P2 to P4 production — current component with synthetic demo data](../static/ss/v1.0/pi-production.png)

### Operation planner

A completed weekly-quota scenario with costs, pilot/planet allocation, facility capacity and build/shopping export. Market prices and pilots are synthetic; this is not a profit forecast.

[Open full resolution](../static/ss/v1.0/pi-planner.png)

![Operation planner — current component with synthetic demo data](../static/ss/v1.0/pi-planner.png)

### Recipes and inventory

Dependency graph, available stock, complete batches and missing-material calculations.

[Open full resolution](../static/ss/v1.0/pi-recipes.png)

![Recipes and inventory — current component with synthetic demo data](../static/ss/v1.0/pi-recipes.png)

### Native template workbench

Actual generated JSON and pin/link preview. In-game placement, routing, capacity and import remain subject to validation.

[Open full resolution](../static/ss/v1.0/pi-template.png)

![Native template workbench — current component with synthetic demo data](../static/ss/v1.0/pi-template.png)

### Skills and queues

Current Export All CSV/JSON controls and an expanded demo skill profile and training queue. Header uses the current EVE/local clock component.

[Open full resolution](../static/ss/v1.0/skills-exports.png)

![Skills and queues — current component with synthetic demo data](../static/ss/v1.0/skills-exports.png)

### Fitting development notice

Current module entry screen, deliberately shown without a simulated fit. Informational only, still in development, not PYFA-complete.

[Open full resolution](../static/ss/v1.0/fittings-status.png)

![Fitting development notice — current component with synthetic demo data](../static/ss/v1.0/fittings-status.png)

[Production Calculator on mobile](../static/ss/v1.0/pi-production-mobile.png) · [Capture provenance](../static/ss/v1.0/capture-receipt.json)

## Suite gallery

The table covers every current sidebar module, plus navigation subtools and the external SSO setup reference. Current navigation is defined in [main.tsx](../frontend/src/main.tsx); the [README feature guide](../README.md#using-eqm-sections) describes behavior. **Battle Reports has no dedicated gallery image yet**; this gap is explicit rather than filled with an unrelated legacy screen.

| Current module / workflow | Earlier images | Reconciliation with current UX |
| --- | --- | --- |
| Overview | [overview.png](../static/ss/overview.png) · [eqm-overview.png](../static/ss/eqm-overview.png) | Current overview adds the EVE/local clocks and newer navigation entries. Earlier summary cards are historical. |
| Navigation | [navigation.png](../static/ss/navigation.png) · [eqm-navigation.png](../static/ss/eqm-navigation.png) · [routecheck.png](../static/ss/routecheck.png) · [eqm-route-hourly-intel.png](../static/ss/eqm-route-hourly-intel.png) · [pvpintel.png](../static/ss/pvpintel.png) · [eqm-pvp-hourly-intel.png](../static/ss/eqm-pvp-hourly-intel.png) · [indythreat.png](../static/ss/indythreat.png) · [localthreat.png](../static/ss/localthreat.png) · [jfplotter.png](../static/ss/jfplotter.png) · [jfpmap.png](../static/ss/jfpmap.png) | Route/gatecheck, hourly traffic, PvP/industrial/local intel and jump-ship maps remain under Navigation. Old jump-plotter screenshots do not show every current replot/docking control. |
| Characters | [eqm-characters.png](../static/ss/eqm-characters.png) | Character dossiers exist; this old demo-card layout does not establish current dossier or standings coverage. |
| Skills | [skills.png](../static/ss/skills.png) · [eqm-skills.png](../static/ss/eqm-skills.png) | Superseded by the v1.0 Skills capture; old images omit full CSV/JSON queue exports and current skill-plan controls. |
| Fittings - WIP | [eqm-fittings.png](../static/ss/eqm-fittings.png) | Historical demo only. Superseded for status/notice by the v1.0 fitting capture. Never use the old readiness/stats graphic as validation of simulator accuracy. |
| Jump Clones | [eqm-jump-clones.png](../static/ss/eqm-jump-clones.png) | Legacy sanitized detail crop; current module also manages clone and implant-set context. |
| Roster | [eqm-roster.png](../static/ss/eqm-roster.png) | Corporation-grouped roster remains available; old demo navigation and cards are not a current full-page capture. |
| ESI Sync | [esi.png](../static/ss/esi.png) · [eqm-esi-sync.png](../static/ss/eqm-esi-sync.png) · [eqm-contact-sync-exact-match.png](../static/ss/eqm-contact-sync-exact-match.png) · [eqm-v019-contact-sync-exact-match.png](../static/ss/eqm-v019-contact-sync-exact-match.png) | Sync and contact propagation remain available; scope requirements and authorization must follow current UI/docs, not an old checkbox list. |
| Market | [eqm-market.png](../static/ss/eqm-market.png) | Historical appraisal example; current prices and available order data must be fetched. |
| Corporate Exchange | [eqm-corporate-exchange.jpg](../static/ss/eqm-corporate-exchange.jpg) · [eqm-corporate-exchange-editor.jpg](../static/ss/eqm-corporate-exchange-editor.jpg) · [eqm-corporate-exchange-detail.jpg](../static/ss/eqm-corporate-exchange-detail.jpg) | Listings, editor and detail examples remain feature references. Inventory and market values are dated. |
| HyperNet Tracker | [eqm-hypernet-tracker.jpg](../static/ss/eqm-hypernet-tracker.jpg) · [eqm-hypernet-offer-detail.jpg](../static/ss/eqm-hypernet-offer-detail.jpg) | Manual-first tracking and offer details remain available. These are not live ESI HyperNet records. |
| Bounty Analytics | [eqm-bounty-analytics.png](../static/ss/eqm-bounty-analytics.png) · [eqm-v019-bounty-analytics.png](../static/ss/eqm-v019-bounty-analytics.png) | Private bounty analytics remains available; this overview is not an authorization or data-freshness test. |
| Notes & Lists | [eqm-notes-lists.png](../static/ss/eqm-notes-lists.png) | Legacy reconstructed demo; current Notes & Lists is the feature location. |
| Manufacturing | [eqm-manufacturing.png](../static/ss/eqm-manufacturing.png) | Legacy reconstructed production-ledger example; follow current input and valuation controls. |
| Research Projects | [eqm-research-projects.png](../static/ss/eqm-research-projects.png) | Legacy reconstructed job/history example; actual job state comes from retained ESI records. |
| Mining Ledger & settlements | [eqm-mining-ledger.png](../static/ss/eqm-mining-ledger.png) · [eqm-mining-analytics.png](../static/ss/eqm-mining-analytics.png) · [eqm-mining-settlement.png](../static/ss/eqm-mining-settlement.png) | Mining history, residue analytics and settlements remain in the mining workflow. Settlement crop shows only the opening steps. |
| Planetary Industry | [eqm-planetary-industry.png](../static/ss/eqm-planetary-industry.png) | Superseded by v1.0 PI captures. Missing in this old picture: planner, corporate supply selection/sync, green surpluses, scoped pilots, individual imports and chain timing. |
| Corporations | [corps.png](../static/ss/corps.png) · [eqm-corporations.png](../static/ss/eqm-corporations.png) | Corporation metadata, divisions and eligible sync characters remain available. Old images cannot demonstrate the new PI corporation-role boundary. |
| Ownership | [eqm-ownership.png](../static/ss/eqm-ownership.png) | Ownership and locations remain available; old demo cards are historical. |
| Assets | [assets.png](../static/ss/assets.png) · [eqm-assets.png](../static/ss/eqm-assets.png) | Asset ledger remains available; historical quantities/locations and layout are not current inventory evidence. |
| Industry | [industry.png](../static/ss/industry.png) · [eqm-industry.png](../static/ss/eqm-industry.png) | Blueprints and SDE recipe views remain available. Historical blueprint/category cards are references. |
| Contracts | [eqm-contracts.png](../static/ss/eqm-contracts.png) | Contracts remain available; old example values/statuses are not live contracts. |
| Analytics | [analytics.png](../static/ss/analytics.png) · [eqm-analytics.png](../static/ss/eqm-analytics.png) | Historical analytics exists with expanded domains, retention and coverage controls; these early charts are not the full current analytics UX. |
| Doctrines | [eqm-doctrine-management.png](../static/ss/eqm-doctrine-management.png) | Legacy reconstructed example; current doctrines support readiness plans and historical fit snapshots. |
| SRP Requests | [eqm-srp-operations.png](../static/ss/eqm-srp-operations.png) · [eqm-srp-analytics.png](../static/ss/eqm-srp-analytics.png) | Legacy reconstructed operations/analytics examples; current review history, valuation and permissions require current UI. |
| Killboard | [eqm-killboard.png](../static/ss/eqm-killboard.png) · [eqm-v019-killboard.png](../static/ss/eqm-v019-killboard.png) | Killboard remains available. Battle Reports is now a separate Fleet Operations module, not pictured here. |
| Battle Reports | [Feature guide](../README.md#using-eqm-sections) | Available in the current app, but no dedicated screenshot exists in this gallery. Do not mistake the old Killboard image for Battle Reports. See the README feature guide. |
| Calendar & Events | [eqm-calendar-events.png](../static/ss/eqm-calendar-events.png) | Events remain available; dated month/RSVP example does not show every current fleet/attendance workflow. |
| Recruiting | [eqm-recruiting.png](../static/ss/eqm-recruiting.png) | Legacy reconstructed configuration example; current public recruiting and staff review workflows extend beyond this screen. |
| Profile | [profile.png](../static/ss/profile.png) · [eqm-profile.png](../static/ss/eqm-profile.png) | Profile, private messages and authorized user administration remain available. User management is not a separate current sidebar module. |
| Settings | [settings1.png](../static/ss/settings1.png) · [settings2.png](../static/ss/settings2.png) · [settings3.png](../static/ss/settings3.png) · [eqm-settings.png](../static/ss/eqm-settings.png) | Current settings include SDE/configuration/privacy/permissions; old settings and scope choices are historical. |
| Audit | [audit.png](../static/ss/audit.png) · [eqm-audit.png](../static/ss/eqm-audit.png) | Audit remains available. Old demo events/layout are historical. |
| CCP developer setup | [developer.png](../static/ss/developer.png) | External CCP configuration screenshot, not an EQM module. Use the current README SSO guide; scopes/callbacks vary by deployment. |

## Historical image index

Every pre-v1.0 image is listed once here. **Historical reference** means capture provenance/current layout was not revalidated. **Legacy demo** identifies visibly synthetic/demo material. **Reconstructed/sanitized** identifies panels covered by the existing screenshot preparation scripts, not a fresh capture. Shared file hashes are labeled; duplicate files remain for link compatibility.

| File | Current home | Status / replacement |
| --- | --- | --- |
| [analytics.png](../static/ss/analytics.png) | Analytics | Historical reference; older UX |
| [assets.png](../static/ss/assets.png) | Assets | Historical reference; older UX |
| [audit.png](../static/ss/audit.png) | Audit | Historical reference; older UX |
| [corps.png](../static/ss/corps.png) | Corporations | Historical reference; older UX |
| [developer.png](../static/ss/developer.png) | CCP developer setup | Historical reference; older UX |
| [eqm-analytics.png](../static/ss/eqm-analytics.png) | Analytics | Legacy demo reference; older UX |
| [eqm-assets.png](../static/ss/eqm-assets.png) | Assets | Legacy demo reference; older UX |
| [eqm-audit.png](../static/ss/eqm-audit.png) | Audit | Legacy demo reference; older UX |
| [eqm-bounty-analytics.png](../static/ss/eqm-bounty-analytics.png) | Bounty Analytics | Legacy demo reference; older UX |
| [eqm-calendar-events.png](../static/ss/eqm-calendar-events.png) | Calendar & Events | Legacy demo reference; older UX |
| [eqm-characters.png](../static/ss/eqm-characters.png) | Characters | Legacy demo reference; older UX |
| [eqm-contact-sync-exact-match.png](../static/ss/eqm-contact-sync-exact-match.png) | ESI Sync | Legacy demo reference; older UX |
| [eqm-contracts.png](../static/ss/eqm-contracts.png) | Contracts | Legacy demo reference; older UX |
| [eqm-corporate-exchange-detail.jpg](../static/ss/eqm-corporate-exchange-detail.jpg) | Corporate Exchange | Legacy demo reference; older UX |
| [eqm-corporate-exchange-editor.jpg](../static/ss/eqm-corporate-exchange-editor.jpg) | Corporate Exchange | Legacy demo reference; older UX |
| [eqm-corporate-exchange.jpg](../static/ss/eqm-corporate-exchange.jpg) | Corporate Exchange | Legacy demo reference; older UX |
| [eqm-corporations.png](../static/ss/eqm-corporations.png) | Corporations | Legacy demo reference; older UX |
| [eqm-doctrine-management.png](../static/ss/eqm-doctrine-management.png) | Doctrines | Reconstructed/sanitized historical panel |
| [eqm-esi-sync.png](../static/ss/eqm-esi-sync.png) | ESI Sync | Legacy demo reference; older UX |
| [eqm-fittings.png](../static/ss/eqm-fittings.png) | Fittings - WIP | Legacy demo reference; older UX; [current notice](#fitting-development-notice) |
| [eqm-hypernet-offer-detail.jpg](../static/ss/eqm-hypernet-offer-detail.jpg) | HyperNet Tracker | Legacy demo reference; older UX |
| [eqm-hypernet-tracker.jpg](../static/ss/eqm-hypernet-tracker.jpg) | HyperNet Tracker | Legacy demo reference; older UX |
| [eqm-industry.png](../static/ss/eqm-industry.png) | Industry | Legacy demo reference; older UX |
| [eqm-jump-clones.png](../static/ss/eqm-jump-clones.png) | Jump Clones | Reconstructed/sanitized historical panel |
| [eqm-killboard.png](../static/ss/eqm-killboard.png) | Killboard | Legacy demo reference; older UX |
| [eqm-manufacturing.png](../static/ss/eqm-manufacturing.png) | Manufacturing | Reconstructed/sanitized historical panel |
| [eqm-market.png](../static/ss/eqm-market.png) | Market | Legacy demo reference; older UX |
| [eqm-mining-analytics.png](../static/ss/eqm-mining-analytics.png) | Mining Ledger & settlements | Legacy demo reference; older UX |
| [eqm-mining-ledger.png](../static/ss/eqm-mining-ledger.png) | Mining Ledger & settlements | Legacy demo reference; older UX |
| [eqm-mining-settlement.png](../static/ss/eqm-mining-settlement.png) | Mining Ledger & settlements | Reconstructed/sanitized historical panel |
| [eqm-navigation.png](../static/ss/eqm-navigation.png) | Navigation | Legacy demo reference; older UX |
| [eqm-notes-lists.png](../static/ss/eqm-notes-lists.png) | Notes & Lists | Reconstructed/sanitized historical panel |
| [eqm-overview.png](../static/ss/eqm-overview.png) | Overview | Legacy demo reference; older UX |
| [eqm-ownership.png](../static/ss/eqm-ownership.png) | Ownership | Legacy demo reference; older UX |
| [eqm-planetary-industry.png](../static/ss/eqm-planetary-industry.png) | Planetary Industry | Legacy demo reference; older UX; [current replacements](#v10-highlights) |
| [eqm-profile.png](../static/ss/eqm-profile.png) | Profile | Legacy demo reference; older UX |
| [eqm-pvp-hourly-intel.png](../static/ss/eqm-pvp-hourly-intel.png) | Navigation | Legacy demo reference; older UX |
| [eqm-recruiting.png](../static/ss/eqm-recruiting.png) | Recruiting | Reconstructed/sanitized historical panel |
| [eqm-research-projects.png](../static/ss/eqm-research-projects.png) | Research Projects | Reconstructed/sanitized historical panel |
| [eqm-roster.png](../static/ss/eqm-roster.png) | Roster | Legacy demo reference; older UX |
| [eqm-route-hourly-intel.png](../static/ss/eqm-route-hourly-intel.png) | Navigation | Legacy demo reference; older UX |
| [eqm-settings.png](../static/ss/eqm-settings.png) | Settings | Legacy demo reference; older UX |
| [eqm-skills.png](../static/ss/eqm-skills.png) | Skills | Legacy demo reference; older UX; [current replacement](#skills-and-queues) |
| [eqm-srp-analytics.png](../static/ss/eqm-srp-analytics.png) | SRP Requests | Reconstructed/sanitized historical panel |
| [eqm-srp-operations.png](../static/ss/eqm-srp-operations.png) | SRP Requests | Reconstructed/sanitized historical panel |
| [eqm-v019-bounty-analytics.png](../static/ss/eqm-v019-bounty-analytics.png) | Bounty Analytics | Legacy demo reference; older UX; identical to `eqm-bounty-analytics.png` |
| [eqm-v019-contact-sync-exact-match.png](../static/ss/eqm-v019-contact-sync-exact-match.png) | ESI Sync | Legacy demo reference; older UX; identical to `eqm-contact-sync-exact-match.png` |
| [eqm-v019-killboard.png](../static/ss/eqm-v019-killboard.png) | Killboard | Legacy demo reference; older UX; identical to `eqm-killboard.png` |
| [esi.png](../static/ss/esi.png) | ESI Sync | Historical reference; older UX |
| [industry.png](../static/ss/industry.png) | Industry | Historical reference; older UX |
| [indythreat.png](../static/ss/indythreat.png) | Navigation | Historical reference; older UX |
| [jfplotter.png](../static/ss/jfplotter.png) | Navigation | Historical reference; older UX |
| [jfpmap.png](../static/ss/jfpmap.png) | Navigation | Historical reference; older UX |
| [localthreat.png](../static/ss/localthreat.png) | Navigation | Historical reference; older UX |
| [navigation.png](../static/ss/navigation.png) | Navigation | Historical reference; older UX |
| [overview.png](../static/ss/overview.png) | Overview | Historical reference; older UX |
| [profile.png](../static/ss/profile.png) | Profile | Historical reference; older UX |
| [pvpintel.png](../static/ss/pvpintel.png) | Navigation | Historical reference; older UX |
| [routecheck.png](../static/ss/routecheck.png) | Navigation | Historical reference; older UX |
| [settings1.png](../static/ss/settings1.png) | Settings | Historical reference; older UX |
| [settings2.png](../static/ss/settings2.png) | Settings | Historical reference; older UX |
| [settings3.png](../static/ss/settings3.png) | Settings | Historical reference; older UX |
| [skills.png](../static/ss/skills.png) | Skills | Historical reference; older UX; [current replacement](#skills-and-queues) |

### Audit notes

- All 63 legacy images were inventoried and visually reviewed in contact sheets; all 8 new images were opened or checked at their rendered dimensions. Old images were preserved unchanged.
- Fresh desktop previews use 1560 px width; the mobile calculator uses a 390 px viewport. No horizontal page overflow or uncaught page errors occurred in the capture workflow.
- The old `eqm-*` demo shell omits current navigation and clocks. Existing reconstructed Doctrine/SRP images are produced by [the tracked sanitizer](../dev/sanitize_release_screenshots.py). Other known reconstructed crops came from the historical README screenshot preparation workflow; they are labeled rather than represented as production captures.
- Current fitting status is explicitly informational and unfinished. Screenshot coverage is not a claim of simulator accuracy or full feature parity.

### Industry/Inventory separation — current development captures

Actual narrow-window UI and real API PDFs with synthetic data only. Public Industry output replaces owner identities; private Inventory retains owner detail. These supersede the earlier general-stock Industry captures.

Station storage opt-in controls; public anonymity is mandatory.

![Station storage opt-in controls; public anonymity is mandatory.](../static/ss/v2.0/industry-selected-storage.jpg)

Anonymous Industry output preview: materials and approved stock; no character/corporation identities.

![Anonymous Industry output preview: materials and approved stock; no character/corporation identities.](../static/ss/v2.0/industry-anonymous-stock.jpg)

Creator-only Inventory Report including named owners and personal/fitted items.

![Creator-only Inventory Report including named owners and personal/fitted items.](../static/ss/v2.0/inventory-private-detail.jpg)

Rendered anonymous Industry PDF with approved stock and industrial activity.

![Rendered anonymous Industry PDF with approved stock and industrial activity.](../static/ss/v2.0/industry-anonymous-pdf.png)

Rendered private Inventory PDF with named owner/placement detail.

![Rendered private Inventory PDF with named owner/placement detail.](../static/ss/v2.0/inventory-private-pdf.png)

### Battle management and detailed PDFs — unreleased 2.0

Actual local UI with synthetic accounts and six saved battles. The management capture shows the filters and first rows; remaining rows/actions are reached by normal page scrolling. Date-range review selects three records and was cancelled after capture. No live reports were deleted. Default viewport: 1280×720; no mobile breakpoint validation claimed.

![Battle Report management](../static/ss/v2.0/battle-report-management.jpg)
![Date-range deletion review](../static/ss/v2.0/battle-report-deletion-review.jpg)
![PDF team totals and hull composition](../static/ss/v2.0/battle-report-pdf-summary.png)
![PDF pilots and complete timeline](../static/ss/v2.0/battle-report-pdf-details.png)

### Industry jobs first and structure names — unreleased 2.0

Current synthetic public report, superseding the earlier order and masked-structure examples. Actual browser full-page capture and a rendered one-page PDF; creator and owner fields remain anonymous.

![Jobs, blueprints, totals, ownership and PI in order](../static/ss/v2.0/industry-jobs-first.jpg)
![Matching PDF order and resolved facility names](../static/ss/v2.0/industry-jobs-first-pdf.png)
