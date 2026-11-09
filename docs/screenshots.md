# EQM screenshot gallery

**Latest:** [persistent scan colors](#persistent-scan-colors), captured October 31, 2026. Earlier: [v2.0 development previews](#v20-development-previews), captured October 28, 2026.

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

## Appearance, layouts and sortable reports

October 29, 2026, unreleased 2.0.0. Actual synthetic browser checks; [controls and validation](appearance.md).

Saved Deep space palette and navigation editor with group naming, module placement and move controls.

![Saved Deep space palette and navigation editor with group naming, module placement and move controls.](../static/ss/v2.0/appearance-navigation.jpg)

Daylight palette with custom colors and per-account layout controls.

![Daylight palette with custom colors and per-account layout controls.](../static/ss/v2.0/appearance-daylight.jpg)

Overview after dragging Blueprint Library ahead of Recent Assets; panel moves are saved automatically.

![Overview after dragging Blueprint Library ahead of Recent Assets; panel moves are saved automatically.](../static/ss/v2.0/appearance-panels.jpg)

Personal and admin site branding uploads with reset controls; bundled art used as synthetic upload fixtures.

![Personal and admin site branding uploads with reset controls; bundled art used as synthetic upload fixtures.](../static/ss/v2.0/appearance-branding.jpg)

Public login using the uploaded site banner and alternative bundled background; personal theme cleared on logout.

![Public login using the uploaded site banner and alternative bundled background; personal theme cleared on logout.](../static/ss/v2.0/appearance-login.jpg)

Existing public Industry Report sorted by quantity descending across the complete stock section.

![Existing public Industry Report sorted by quantity descending across the complete stock section.](../static/ss/v2.0/industry-sortable-columns.jpg)

## Quicklaunch shortcuts

October 29, 2026, unreleased 2.0.0. [Setup and validation](appearance.md#quicklaunch-validation). Actual UI with synthetic accounts.

Quicklaunch at the top of the sidebar, with Local Scan retained in Intel and its shortcut opening the same page.

![Quicklaunch at the top of the sidebar, with Local Scan retained in Intel and its shortcut opening the same page.](../static/ss/v2.0/quicklaunch-navigation.jpg)

Quicklaunch editor with the Add shortcut dropdown, original-link notice, individual move controls and Remove shortcut actions.

![Quicklaunch editor with the Add shortcut dropdown, original-link notice, individual move controls and Remove shortcut actions.](../static/ss/v2.0/quicklaunch-editor.jpg)

Quicklaunch shortcut dropdown at a 420px viewport; the navigation editor scrolls independently and the page has no horizontal overflow.

![Quicklaunch shortcut dropdown at a 420px viewport; the navigation editor scrolls independently and the page has no horizontal overflow.](../static/ss/v2.0/quicklaunch-mobile.jpg)

## Password recovery and full asset downloads

October 29, 2026, unreleased 2.0.0. [Setup and verification](password-recovery-and-exports.md). Synthetic data only.

Forgot-password request with a generic response that does not reveal whether an account exists.

![Forgot-password request with a generic response that does not reveal whether an account exists.](../static/ss/v2.0/password-recovery.jpg)

New-password and confirmation form; no real credentials entered and the preview token is invalid.

![New-password and confirmation form; no real credentials entered and the preview token is invalid.](../static/ss/v2.0/password-reset-form.jpg)

Administrator recovery controls, including immediate sign-out and required reset; no link or password shown.

![Administrator recovery controls, including immediate sign-out and required reset; no link or password shown.](../static/ss/v2.0/admin-password-recovery.jpg)

Complete filtered CSV and Janice downloads alongside a ledger still displaying 100 of 621 synthetic rows.

![Complete filtered CSV and Janice downloads alongside a ledger still displaying 100 of 621 synthetic rows.](../static/ss/v2.0/full-asset-downloads.jpg)

## SDE maintenance

October 29, 2026, unreleased 2.0.0. [Controls, worker requirements and verification](sde-maintenance.md). Synthetic data and mocked queue/CCP transport; these are not production download measurements.

SDE maintenance running with overlapping actions disabled; synthetic worker/HTTP progress fixture.

![SDE maintenance running with overlapping actions disabled; synthetic worker/HTTP progress fixture.](../static/ss/v2.0/sde-maintenance-progress.jpg)

Completed synthetic SDE archive with build, filename, size, checksum and a later-import selector.

![Completed synthetic SDE archive with build, filename, size, checksum and a later-import selector.](../static/ss/v2.0/sde-maintenance-complete.jpg)

## EVE SSO and Ship Reports

October 29, 2026, unreleased 2.0.0. [Permissions, rollout and limitations](sso-and-ship-reports.md). Actual UI with synthetic accounts; CCP exchanges were mocked in API tests and no live sign-in was performed. Login/invite captures show the relevant lower page at the default browser viewport.

![EVE SSO login alongside password sign-in, with a centered recovery link.](../static/ss/v2.0/eve-sso-login.jpg)

![Invitation with combined roles, identity-only EVE SSO acceptance and password alternative.](../static/ss/v2.0/eve-sso-invite.jpg)

![Private Ship Report heading with total hull count and creator attribution.](../static/ss/v2.0/ship-report-summary.jpg)

![Ship Report totals section with 28 synthetic hulls across three types, sortable quantities and CSV/PDF exports.](../static/ss/v2.0/ship-report-totals.jpg)

## Ship classes and Fleet Commander Analytics

Unreleased 2.0 development captures from an isolated SQLite preview of the actual built frontend. All accounts, stock and three dated observations are synthetic. The fixture contains 40 non-capsule hulls across seven types, including five capital hulls; the lower Officer view has 35 hulls/four types. Subcaps additionally removes seven shuttles, producing 28 hulls/three types. No production permissions or records were changed.

![Fleet Commander Ship Report class checkboxes and Subcaps preset](../static/ss/v2.0/ship-class-exclusions.jpg)

![Fleet Commander sees all hull sizes in ship inventory Analytics](../static/ss/v2.0/ship-analytics-fleet-commander.jpg)

![Officer sees subcapital totals and history only](../static/ss/v2.0/ship-analytics-subcapital.jpg)

Full normal viewport captures at scroll positions showing the relevant controls. Charts continue below the viewport. Per-file provenance/checksums are in the capture receipt. [Behavior and verification](ship-filters-and-analytics.md).

## Intel note management and Market item history

Actual built 2.0 development UI on localhost:8783, isolated SQLite accounts/dossiers and mocked public ESI market responses. No production account, note, permission or order was changed. The market dates/prices are synthetic demonstration data and must not be treated as live quotes.

![An analyst's edited note and inline deletion confirmation; another author's note remains read-only](../static/ss/v2.0/intel-note-management.jpg)

![Expanded Jita item with The Forge completed-trade history and separate current hub orders](../static/ss/v2.0/market-item-history.jpg)

Full normal viewport captures at the relevant scroll position, without resizing or pixel edits. API tests exercise permanent deletion; the browser capture shows confirmation/cancel without executing a permanent UI deletion. See the per-file capture receipt for hashes and provenance.

## Intel non-combat sightings

Actual built 2.0 development UI at localhost:8784, backed by isolated SQLite and synthetic Example Visitor/Example Entry/Example Pocket records. Ship labels use imported demo hull metadata. Name resolution/identity are mocked; no outside character was enrolled or live location reported. One explicit report run created a current-time Tristan sighting; a second created an earlier Caracal sighting with a separate later posting time. Both show 0/0 K/L. Reload preserved both records without adding more.

![System, ship and historical time controls beside the dossier entry](../static/ss/v2.0/intel-sighting-entry.jpg)

![Two source-labelled sightings and the daily 0/0 timeline](../static/ss/v2.0/intel-sighting-timeline.jpg)

Full normal viewport captures at relevant scroll positions. No resizing or pixel changes. Apply migration 0099 before matching API/frontend rollout; these screenshots do not claim a release or production deployment. Per-file provenance/checksums are in the capture receipt.

## Intel affiliations and unknown hull sightings

Actual built frontend with an isolated SQLite demo on localhost:8785. A UI report run recorded Example Visitor in Example Entry at an explicitly entered earlier UTC time, with ship blank. Reload retained exactly one Unknown Ship Type sighting, 0/0 K/L and a separate posting timestamp. Names/tags are synthetic; the corporation/alliance logos come from the public EVE Image Server solely as visual references. Organization metadata and pilot identity are mocked; no live account or game action.

![Corp/alliance logos, names and tags next to the pilot portrait](../static/ss/v2.0/intel-affiliation-header.jpg)

![Unknown ship icon, historical sighting and 0/0 timeline](../static/ss/v2.0/intel-unknown-ship-sighting.jpg)

Full normal viewport captures with no pixel edits or viewport resizing. These are unreleased feature demonstrations, not evidence of production deployment. Migration 0100 is required for nullable hull IDs.

## Saved Battle Report search

Actual 2.0 development UI with isolated SQLite on localhost:8786. Thirty synthetic saved snapshots include an older 46-versus-312 battle at the public system Hagilua, with fictional Example corporations/alliances/pilots and real EVE type labels. No real engagement is represented. Search found that older report from beyond the initial page using Hostile Side, Example Cyno alliance/corporation, capital class, Revelation, 251–350 combatants and Hagilua.

![Date selectors followed by all remembered-detail controls](../static/ss/v2.0/battle-search-controls.jpg)

![Matching battle time, system, pilot totals and selected-side hulls](../static/ss/v2.0/battle-search-results.jpg)

Full normal viewport captures at relevant scroll positions, without pixel changes or viewport resizing. The source was not deployed or released. The manager remains usable while live discovery is disabled in the preview; no real ESI, account, report deletion or game action occurred.

### In-game links and optional support — v2.0 development

Actual built UI with synthetic accounts and owned items; unsent draft calls are mocked. No real mail or ISK actions. [Behavior, permissions and limits](in-game-links.md).

![Optional Overview support card](../static/ss/v2.0/overview-support-card.jpg)

![Owned blueprint instance link and character picker](../static/ss/v2.0/blueprint-client-link.jpg)

## Persistent scan colors

October 31, 2026, **unreleased 2.0.1 follow-up**. Actual browser captures backed by synthetic accounts, pilots and memberships. Public EVE logos/portraits are visual references, not claims about actual membership. [Feature and rollout](scan-colors.md) · [Receipt](../static/ss/v2.0.1/capture-receipt.json).

![Alliance and corporation colors with an expanded pilot list](../static/ss/v2.0.1/local-scan-colors.jpg)

![Color picker opened directly from scan results](../static/ss/v2.0.1/local-scan-color-picker.jpg)

![Mobile organization color picker](../static/ss/v2.0.1/local-scan-colors-mobile.jpg)

### Selected-character standings colors

October 31, 2026, same unreleased follow-up. The character, token grants and contacts are synthetic; contact fetch/refresh functions are mocked. The actual settings/API/color rendering run against an isolated database. No real SSO consent or private ESI query was performed.

![Persisted own-character standings source and manual overrides](../static/ss/v2.0.1/local-scan-standings-source.jpg)

![Contact-derived light blue alongside manual corporation/alliance colors](../static/ss/v2.0.1/local-scan-standings.jpg)

[Mobile standings source](../static/ss/v2.0.1/local-scan-standings-mobile.jpg) · [Receipt](../static/ss/v2.0.1/capture-receipt.json)


## Local Scan to Intel history

October 31, 2026, **unreleased 2.0.1 follow-up**. Actual built React UI and real scan/report APIs, isolated SQLite and synthetic resolved pilots. A Jita scan precedes dossier creation; a second scan is generated in Amarr through the browser. The timeline shows both with UTC generation times, Unknown Ship Type and 0/0 combat counts. No live account, ESI or database changes.

![System selection explains retained Intel sightings](../static/ss/v2.0.1/local-scan-intel-generation.jpg)

![Both Local Scan observations in the Intel timeline](../static/ss/v2.0.1/local-scan-intel-timeline.jpg)

![Mobile Local Scan sighting cards](../static/ss/v2.0.1/local-scan-intel-mobile.jpg)

[Behavior and rollout](intel-reports.md#local-scans-feed-the-sighting-timeline) · [Receipt](../static/ss/v2.0.1/capture-receipt.json)


## My Journey — private character movement history

October 31, 2026 client-date development session; **unreleased 2.0.1 follow-up**. Actual production UI and APIs with isolated synthetic accounts and visits. System coordinates/names are public CCP data, the route and holdings/combat are fabricated. No real OAuth or character location reads. [Workflow and migration](journey-map.md) · [Receipt](../static/ss/v2.0.1/capture-receipt.json).

![Selected-character opt-in, private scope and sampling controls](../static/ss/v2.0.1/journey-controls.jpg)

![Observed route, revisits, gap and current context markers](../static/ss/v2.0.1/journey-map.jpg)

![Character-owned stock and imported combat for a visited system](../static/ss/v2.0.1/journey-system-context.jpg)

![Viewport-fitted mobile map and gap legend](../static/ss/v2.0.1/journey-mobile.jpg)


## Matchups — PvP Knowledgebase foundation

November 1, 2026 development captures; unreleased 2.0.1 follow-up. Actual production React UI and APIs with isolated SQLite, synthetic accounts/counts and public CCP hull/dogma fixtures. No live private data, game action or deployment. [Coverage and limits](matchups.md) · [Receipt](../static/ss/v2.0.1/capture-receipt.json).

![Base hull resistance map, explicit unknown fit and D-Scan counts](../static/ss/v2.0.1/matchups-hull.jpg)

![Selected blaster scenario and conditional fleet counter tools](../static/ss/v2.0.1/matchups-counters.jpg)

![Weapon-family framework with linked mounted-weapon references and atlas limitation](../static/ss/v2.0.1/matchups-weapons.jpg)

![Responsive mobile hull and resistance reference](../static/ss/v2.0.1/matchups-mobile.jpg)


## My Journey — optional private hull history

November 1, 2026 unreleased 2.0.1 follow-up. Real production UI and journey APIs with isolated SQLite and synthetic hull observations. Current replay changes Deimos to Gila inside Jita while the all-time system visit total stays ten. Per-character ship consent/recording controls, legacy unknown hulls and desktop/mobile icons verified; no live private ESI, game action or deployment. [Guide/migration 0104](journey-map.md#optional-ship-types-and-hull-icons) · [Receipt](../static/ss/v2.0.1/capture-receipt.json).

![Explicit optional hull recording beside character controls](../static/ss/v2.0.1/journey-ships-controls.jpg)

![Hull and icon at the selected replay step, unchanged visit totals](../static/ss/v2.0.1/journey-ships-replay.jpg)

![Timestamped hull changes and small icons in the timeline](../static/ss/v2.0.1/journey-ships-timeline.jpg)

![Mobile timeline; table scroll stays inside its container](../static/ss/v2.0.1/journey-ships-mobile.jpg)


## Design exploration — Command Desk (not integrated or released)

November 1, 2026. Three clickable HTML studies; fictional data, original SVG art and no account connection. [Design notes and local preview](design/command-desk/README.md). Separate from released feature screenshots. Phase-01 images remain in the capture receipt as history; these are the refined second-pass compositions.

![Refined Overview: shorter introduction and open totals.](../static/ss/design-studies/command-desk/overview-refined.jpg)

![Intel: fictional identity, affiliation emblems and source-labelled sightings.](../static/ss/design-studies/command-desk/intel-dossier.jpg)

![Intel: editable sample field notes.](../static/ss/design-studies/command-desk/intel-field-notes.jpg)

![Industry: jobs, blueprints, totals, anonymous ownership and PI in Station daylight.](../static/ss/design-studies/command-desk/industry-manifest.jpg)

![Overview phone layout with theme and compact controls.](../static/ss/design-studies/command-desk/overview-refined-mobile.jpg)

![Intel phone layout.](../static/ss/design-studies/command-desk/intel-dossier-mobile.jpg)

![Industry phone layout with contained table scrolling.](../static/ss/design-studies/command-desk/industry-manifest-mobile.jpg)

[Provenance and checksums](../static/ss/design-studies/command-desk/capture-receipt.json).


## Unreleased Command Desk integration — actual application

November 1, 2026. Production UI and real account/inventory APIs with isolated synthetic data. Distinct from the standalone studies above. [Scope and verification](command-desk.md).

![Implemented opt-in Overview with synthetic SQLite holdings and real EQM APIs.](../static/ss/v2.0.1/command-desk-overview.jpg)

![Appearance header and persistent interface selector; exact crop from actual UI.](../static/ss/v2.0.1/command-desk-selector.jpg)

![Classic fallback retains the same account palette and data.](../static/ss/v2.0.1/eqm-classic-overview.jpg)

![Implemented mobile navigation and full-page Overview, synthetic holdings.](../static/ss/v2.0.1/command-desk-mobile.jpg)


## Organization membership trends — unreleased 2.0.1

Captured November 2, 2026 from the actual production React build and Intel APIs against an isolated synthetic SQLite database. Fictional corporation/alliance histories demonstrate growth, losses, incomplete census coverage, monitoring controls and observed corporation movements. A local synthetic census adapter handles preview refreshes; no real ESI authorization, private data or production account changes. Desktop captures crop to complete rendered panels; mobile retains normal scrolling context.

![Corporation member-count growth and comparison baselines](../static/ss/v2.0.1/membership-corporation.jpg)

![Alliance member losses and incomplete coverage](../static/ss/v2.0.1/membership-alliance.jpg)

![Observed corporation arrivals and departures](../static/ss/v2.0.1/membership-corporation-movements.jpg)

![Mobile organization strength](../static/ss/v2.0.1/membership-mobile.jpg)

[Behavior, privacy and rollout](intel-reports.md#corporation-and-alliance-membership-trends) · [Capture receipt](../static/ss/v2.0.1/capture-receipt.json). Migration 0105; no deployment or release publication is implied.

## Alliance corporation census and expanded profiles — unreleased 2.0.1

November 2, 2026. Actual production UI and real API routes with isolated fictional alliance/corporation data and synthetic public ESI/zKill adapters. Public EVE Image Server artwork supplies visual references. These captures do not represent live intelligence or deployed code.

![Searchable alliance member corporations, logos, CEOs and counts](../static/ss/v2.0.1/alliance-corporations.jpg)

![Expanded public corporation metadata and latest zKill summary](../static/ss/v2.0.1/alliance-corporation-expanded.jpg)

![Mobile alliance dossier and corporation census](../static/ss/v2.0.1/alliance-corporations-mobile.jpg)

[Feature guide](intel-reports.md#alliance-member-corporations) · [Source provenance and checksums](../static/ss/v2.0.1/capture-receipt.json). Desktop crops retain the complete relevant list/detail; mobile is a full-page scrolling capture.

## Market-run Receipts — unreleased 2.0.1

November 2, 2026. Actual React/receipt/navigation/auth APIs and isolated synthetic purchase records, a tiny fictional gate graph, manual fuel/costs and public EVE mineral artwork. No operational purchase data or real seller names were used. PDF rendering is the actual export, not a mockup.

![Complete public receipt with reconciliation, grouped purchases, fuel and route](../static/ss/v2.0.1/receipt-public.jpg)

![Exclusion credit, hauling fee and actual fuel entry](../static/ss/v2.0.1/receipt-cost-controls.jpg)

![Full mobile receipt with horizontal tables contained within the page](../static/ss/v2.0.1/receipt-mobile.jpg)

![First page of the branded PDF export](../static/ss/v2.0.1/receipt-pdf-page1.png)

[Two-page PDF example](examples/receipt-demo.pdf) · [Controls, privacy and rollout](receipts.md) · [Capture receipt](../static/ss/v2.0.1/capture-receipt.json). Source/build/provenance recorded; not a deployment or published release.

### Receipts: rounded unit-price follow-up (unreleased)

Actual public receipt with fictional purchases, showing pasted/effective prices and exact partial exclusion totals. No operational transaction data.

![Rounded clipboard price recovery](../static/ss/v2.0.1/receipt-rounded-price.jpg)

Source, validation and SHA-256 recorded in the [capture receipt](../static/ss/v2.0.1/capture-receipt.json).


## Local Scan capacity — unreleased 2.0.1 follow-up

Actual built UI and isolated SQLite API with **4,999 fictional pilots** and mocked public ESI responses. All 4,999 resolve and remain present in the saved public report. Existing batching and lookup deadlines remain in place. The preview has no live account/game data; its missing local branding image is unrelated to scan capacity.

![Local Scan: all 4,999 synthetic pilots resolved](../static/ss/v2.0.1/local-scan-4999.png)


## Local Scan capacity — 9,999-pilot unreleased follow-up

Actual built UI with isolated SQLite and mocked public ESI resolves and saves **9,999 fictional pilots**. The API also reopens all pilots intact and rejects 10,000 unique names before making upstream requests. Local Scan and D-Scan linked lists accept 1,200,000 characters; ESI batches and deadlines remain unchanged. No live ESI load benchmark or deployed build is claimed. The preceding 4,999-pilot capture remains a historical verification.

![Local Scan: all 9,999 synthetic pilots resolved](../static/ss/v2.0.1/local-scan-9999.png)


## Full-battle discovery — unreleased 2.0.1 follow-up

Actual built interface and isolated API with fictional participants/public-API mocks. Two cached kills expand to eight, including independent groups; classifications and coverage survive private/public saving. Desktop collection controls, expanded saved result and mobile totals/coverage are shown. [Workflow and limits](battle-discovery.md).

![Battle discovery editor and completed collection](../static/ss/v2.0.1/battle-discovery-editor.png)

![Full system/window report with eight synthetic kills](../static/ss/v2.0.1/battle-discovery-report.png)

![Mobile saved report](../static/ss/v2.0.1/battle-discovery-mobile.png)

## My Journey map controls — unreleased v2.1 follow-up

Actual JourneyPanel/JourneyMap React UI with the existing EQM styles and synthetic loopback HTTP responses. Demo account, observations and coordinates are fabricated for interaction testing, not a live character journey or accurate SDE map. Desktop and 390px mobile captures retain the full toolbar, viewport and legend.

![Desktop: zoom readout, fit and selected-system focus](../static/ss/v2.1/journey-map-controls-desktop.png)

![Mobile: responsive controls, one-finger pan and two-finger pinch](../static/ss/v2.1/journey-map-controls-mobile.png)

Nine journey tests and eight actual-browser checks pass; browser console errors and mobile document overflow are absent. No backend contract, migration, new consent scope or production deployment. [Controls](journey-map.md#map-controls) · [Source hashes, capture method and checksums](../static/ss/v2.1/capture-receipt.json).

## My Journey exports — unreleased v2.1 follow-up

Actual JourneyPanel/JourneyExport React components with existing EQM styles, production-bundled media worker and isolated synthetic HTTP responses in headless Edge. Four fabricated visits, illustrative system coordinates, observed demo hulls, seven combat records on one stop, one loss on a revisit and one unassigned gap record. No live account, OAuth, ESI or killboard collection. Generated files and captures remain a source follow-up, not a production deployment.

![Desktop export controls, generated MP4 preview and download](../static/ss/v2.1/journey-export-desktop.png)

![1080p frame extracted from the actual generated MP4 — engagement page](../static/ss/v2.1/journey-export-engagement.png)

![390px mobile export controls — desktop saving recommended](../static/ss/v2.1/journey-export-mobile.png)

Both synthetic GIF and MP4 outputs were probed as 1920×1080, 17.5 seconds. Nine browser cases cover encoding/downloads, cancellation, date changes, invalid ranges, truncation, unavailable combat, missing MP4 encoder and mobile overflow. [Guide](journey-map.md#gif-and-mp4-exports) · [Receipt and SHA-256 checksums](../static/ss/v2.1/capture-receipt.json).

## Sync All reliability — unreleased 2.2.1 follow-up

Actual CharactersPage and shared API/polling client, rendered with existing EQM styles and synthetic loopback HTTP responses. A fabricated pilot and minimal supporting/dossier fixtures; no live account or actual EVE sync. Crops retain the full Characters heading, sync/refresh controls and error or completion notice. No screenshot painting or replacement UI.

![Readable gateway notice without nginx HTML](../static/ss/v2.2.1/sync-gateway-message.png)

![The same job completed after a temporary 504 status response](../static/ss/v2.2.1/sync-gateway-recovered.png)

![390px mobile gateway notice](../static/ss/v2.2.1/sync-gateway-mobile.png)

[Reliability behavior and PostgreSQL regression](sync-reliability.md) · [Capture provenance and checksums](../static/ss/v2.2.1/capture-receipt.json). Not a deployment or live sync capture.

## My Journey segmented exports — unreleased 2.2.1 follow-up

Actual JourneyPanel, scope selector and segmented export components with existing EQM styles, a production-bundled media worker and synthetic loopback API responses. Fabricated pilot, history, coordinates and combat; no real account, SSO, ESI collection or user folder. Folder tests use real browser origin-private file handles in an isolated Edge profile. The native directory picker itself was not automated. Individual download files were saved and checked with FFprobe.

![501 real encoded synthetic visits saved as two clips](../static/ss/v2.2.1/journey-segments-complete.png)

![Numbered download preview and explicit save-before-continuing controls](../static/ss/v2.2.1/journey-segments-download.png)

![Actual frame extracted from the continuation MP4: part 2, visit 1 continued, page 199](../static/ss/v2.2.1/journey-segments-continuation.png)

![390px mobile scope and format controls](../static/ss/v2.2.1/journey-segments-mobile.png)

[Behavior and verification](journey-map.md#segmented-and-entire-journey-exports) · [Receipt and checksums](../static/ss/v2.2.1/capture-receipt.json). Captures are development evidence, not a deployment or a live journey.

## Matchups ship catalog and public loss fits

November 6, 2026 captures from the production UI with an isolated SQLite import of CCP SDE build 3670638 and synthetic loss records. The sample module types reflect public loss equipment. [Workflow and assumptions](matchups.md#ship-catalog-and-example-fits) · [Capture receipt](../static/ss/v2.2.1/capture-receipt.json).

![Onyx and the alphabetized Heavy Interdiction Cruiser class](../static/ss/v2.2.1/matchups-ship-catalog.jpg)

![Rail Deimos estimate and counter suggestions](../static/ss/v2.2.1/matchups-loss-fit.jpg)

![Assault Frigate subclass on a 390-pixel viewport](../static/ss/v2.2.1/matchups-catalog-mobile.jpg)

## Application Update

Unreleased 2.2.1 captures from the actual Settings UI and bridge API using a fabricated host account, revision and installation states. [Host setup](application-updates.md) · [Capture receipt](../static/ss/v2.2.1/capture-receipt.json).

![The updater installs a synthetic revision above SDE Maintenance](../static/ss/v2.2.1/app-update-installing.jpg)

![Settings after the synthetic update completes and refreshes the tab](../static/ss/v2.2.1/app-update-complete.jpg)

## Journey Zoom-and-Follow and Center — unreleased 2.3 follow-up

November 8, 2026 client-date development captures. Actual JourneyPanel/JourneyMap and existing EQM styles with synthetic loopback history/context/settings responses. Demo Cartographer, route observations and illustrative coordinates are fabricated; no live tracking, SSO or private account data.

![Desktop: active follow toggle, Center and current-position status](../static/ss/v2.3.0/journey-follow-desktop.png)

![390px mobile: complete toolbar, centered position and legend](../static/ss/v2.3.0/journey-follow-mobile.png)

26 journey tests, full TypeScript/Vite build and seven browser scenarios pass, including timed replay, live refresh/projection changes, selection, one-time centering, zoom retention, resize, manual navigation, missing coordinates, empty data/date resets and real touch pan/pinch. No browser page errors or mobile document overflow. [Guide](journey-map.md#map-controls) · [Provenance and checksums](../static/ss/v2.3.0/capture-receipt.json). Frontend-only; unreleased development evidence.

## Application Update permission preflight — unreleased 2.3 follow-up

November 8, 2026 client-date development captures. Actual AppUpdatePanel and existing EQM styles render an actionable message generated by the real helper/preflight code with synthetic root-owned-path findings. No live request, private host data or production update is shown.

![Desktop permission failure with repair guidance](../static/ss/v2.3.0/app-update-permissions-desktop.png)

![390px mobile permission notice and retry control](../static/ss/v2.3.0/app-update-permissions-mobile.png)

[Behavior and repair](application-updates.md#checkout-permissions) · [Source and image provenance](../static/ss/v2.3.0/capture-receipt.json). Cross-platform tests cover fail-before-merge, ownership repair boundaries and a successful Linux retry using simulated Docker. The screenshots demonstrate the error presentation, not a full Docker deployment.


## Owned Structures — v2.3.0 development preview

November 8, 2026 client date. Actual StructuresPage, shared API client and existing EQM styles rendered in headless Edge with synthetic HTTP responses generated by the real FastAPI serializers and isolated SQLite fixtures. Fabricated corporation, structures, quantities and times; no live character, SSO, ESI or gameplay collection. Complete module captured at 1440px and 390px. Both source lists, timer/fuel semantics, filters, empty/partial/failure states, character switching and polling verified. Unreleased; requires matching backend/frontend rollout and authorization. [Guide](structures.md) · [Capture receipt](../static/ss/v2.3.0/capture-receipt.json).

![Owned Upwell structures and expanded POS fuel with synthetic data](../static/ss/v2.3.0/structures-desktop.png)

![Structures filters, cards and POS fuel at 390px](../static/ss/v2.3.0/structures-mobile.png)


## Local Scan character notes — v2.3.0 development preview

November 8, 2026 client date. Actual LocalScanPage/LocalScanResults, IntelReportsPage, dossier note editor, shared API client and EQM styles, served through local Vite/headless Edge against real FastAPI routes and a separate disposable SQLite database. Fabricated pilots, corporation/alliance, labels and fixed synthetic note timestamps. Two synthetic accounts (Officer author and Admin viewer); public ESI source mocked and external portraits blocked. No production credentials, real notes, live account collection or game actions. Captures retain the full relevant report or search panel; mobile viewport is 390px. Unreleased; requires migration 0106 and matching backend/frontend rollout. [Guide](local-scan-character-notes.md) · [Capture receipt](../static/ss/v2.3.0/capture-receipt.json).

![Scan-wide Public note applied to six synthetic resolved pilots](../static/ss/v2.3.0/local-scan-character-notes-desktop.png)

![Note text search with six linked matching characters](../static/ss/v2.3.0/character-note-search.png)

![Public and Private character annotations at 390px](../static/ss/v2.3.0/local-scan-character-notes-mobile.png)

## Manual POS tracking — v2.3.0 development preview

November 8, 2026 client date. Actual StructuresPage/manual POS components, shared API client and existing EQM styles rendered in headless Edge at 1440px and 390px, backed by the real FastAPI CRUD routes and an isolated SQLite database. Fabricated accounts, corporation, locations, quantities and UTC times; mocked ESI denied the POS list while Upwell remained available. No live character, SSO, ESI or gameplay data. Browser scenarios verified persistence without a character, owner isolation, optimistic conflicts, reinforced checkbox/stront consumption, exact UTC overrides, presets, search, filters, deletion and mobile layout. Unreleased; requires migration 0107 plus matching backend/frontend rollout. [Guide](structures.md#manual-pos-tracking) · [Capture receipt](../static/ss/v2.3.0/capture-receipt.json).

![Manual fuel and reinforced strontium records](../static/ss/v2.3.0/manual-pos-desktop.png)

![Manual POS cards at 390px](../static/ss/v2.3.0/manual-pos-mobile.png)

![Reinforced mode checkbox and strontium fields at 390px](../static/ss/v2.3.0/manual-pos-reinforced-form.png)

## Journey analytics — v2.3.0 development preview

November 9, 2026 client date. Actual JourneyPanel/JourneyAnalytics and shared API/styles rendered in headless Edge at 1440px and 390px, backed by real Journey APIs and an isolated synthetic SQLite database. Fabricated pilots, system names/coordinates, hulls, observations and killmails; no live SSO, ESI, user history or production data. Browser checks cover all six rankings, pilot/date/span controls, drill-down, other-Admin isolation, revoked combat access, failed refresh retention, top-N/full-total distinctions, history erasure and mobile layout. Unreleased; matching backend/frontend rollout required. No new migration or scope. [Guide](journey-map.md#journey-analytics) · [Capture receipt](../static/ss/v2.3.0/capture-receipt.json).

![Six journey ranking cards and scope controls](../static/ss/v2.3.0/journey-analytics-desktop.png)

![Journey analytics controls and all rankings at 390px](../static/ss/v2.3.0/journey-analytics-mobile.png)

## Default-collapsed analytics panes — v2.3.0 development preview

November 9, 2026 client date. Actual affected React views and shared API/styles in headless Edge at 1440px and 390px. Fabricated accounts/history in isolated SQLite; real local serializers for Journey/Analytics/Bounties/SRP/Events/HyperNet. Fixed local Killboard read fixtures prevent automatic synchronization. No production records, live SSO, external ESI or game operations. Seven browser scenario groups cover default collapse, expansion/keyboard/anchors, retained controls, both Journey placements, independent pilot/date scope, Navigation-denied hiding, private HyperNet controls and mobile overflow. Unreleased frontend follow-up; no migration/new scope. [Guide](analytics-panes.md) · [Receipt](../static/ss/v2.3.0/capture-receipt.json).

![Analytics platform collapsed](../static/ss/v2.3.0/analytics-platform-collapsed.png)

![Analytics platform journey](../static/ss/v2.3.0/analytics-platform-journey.png)

![Analytics platform mobile](../static/ss/v2.3.0/analytics-platform-mobile.png)

![Journey analytics collapsed](../static/ss/v2.3.0/journey-analytics-collapsed.png)

![Bounties analytics collapsed](../static/ss/v2.3.0/bounties-analytics-collapsed.png)

![Killboard analytics collapsed](../static/ss/v2.3.0/killboard-analytics-collapsed.png)

![Srp analytics collapsed](../static/ss/v2.3.0/srp-analytics-collapsed.png)

![Events analytics collapsed](../static/ss/v2.3.0/events-analytics-collapsed.png)

![Hypernet analytics collapsed](../static/ss/v2.3.0/hypernet-analytics-collapsed.png)

## Intel subject browser and report retention (2.3 development)

Captured November 9, 2026 from an unreleased working tree based on `2cfb184ff19465548f340925a64822184f97bd6f`. Actual React components and FastAPI routes use an isolated synthetic SQLite database, public-source fixtures and DEMO placeholder portraits/logos; no production intel, game records, SSO, private notes or accounts. Desktop 1480×1100 and mobile 390×844. Crops retain rendered controls without repainting. These features require migration 0108 and matching backend/frontend rollout; no deployment performed. [Guide](intel-reports.md#saved-subjects-local-scan-stubs-and-priority-targets).

![Alliance branches collapsed by default with priority targets first](../static/ss/v2.3.0/intel-subjects-collapsed.png)

![Expanded alliance, corporation and pilot hierarchy with a Priority Target checkbox](../static/ss/v2.3.0/intel-subjects-priority.png)

![Report deletion confirmation states that notes and shared records are preserved](../static/ss/v2.3.0/intel-report-delete.png)

![Collapsed Intel subject browser on mobile](../static/ss/v2.3.0/intel-subjects-mobile.png)

## Intel Reports — v2.4.0 development previews

November 9, 2026 client date. Actual IntelReportsWorkspace/builder/view/public components and existing EQM styles, with real FastAPI report/resolve/refresh/snapshot routes backed by isolated SQLite. Fabricated systems, public killmails, analysts, private/shared sightings and ESI-hour samples; mocked public-source adapters. Full EQM App entry point also tested anonymously. No production records, credentials, live ESI/zKill pulls or real private intelligence. Desktop 1480×1100, mobile 390×844; rendered component crops/full pages, no pixel repainting. All source/image hashes and validation are in [v2.4.0 capture receipt](../static/ss/v2.4.0/capture-receipt.json). Requires migration 0109 and matching rollout; no live deployment. [Guide](intel-report-builder.md).

![Target lookup, UTC controls, explicit collection and snapshot privacy controls](../static/ss/v2.4.0/intel-reports-builder.png)

![System killmail, jump, pod/ship/NPC and UTC-hour charts](../static/ss/v2.4.0/intel-reports-system-charts.png)

![Internal sightings kept separate from combat and public sharing](../static/ss/v2.4.0/intel-reports-sightings.png)

![Anonymous public snapshot with public combat data only](../static/ss/v2.4.0/intel-reports-public.png)

![Alliance report with active systems, common hulls and activity hours](../static/ss/v2.4.0/intel-reports-alliance.png)

![System report at 390px with expanded charts and contained scrolling tables](../static/ss/v2.4.0/intel-reports-mobile.png)

## Journey combat-count rankings — v2.4.0 correction

Captured November 9, 2026 from a working tree based on `18fc326eecfc198c54835e98dcdcb1cf71b5b64c`. Actual shared JourneyAnalytics in Analytics' JourneyAnalyticsSection and JourneyPanel, backed by real Journey API routes and synthetic SQLite. Fabricated pilot/hulls/visits/killmails deliberately give one hull more visits and another more kills/losses; both combat bars retain the 3:1 count ratio after selecting confirmed span. Four browser groups cover both placements, scope/date controls, independent travel sorting and 390px no overflow; no page errors. Three rendered component captures; no repainting or live accounts, ESI or killboard collection. [Definitions](journey-map.md#journey-analytics) · [Additive capture receipt](../static/ss/v2.4.0/capture-receipt.json). No version bump or migration; matching backend/frontend rollout required.

![Analytics placement: combat cards show counts while travel uses confirmed span](../static/ss/v2.4.0/journey-combat-counts-analytics.png)

![Journey placement: kill/loss counts determine order and bar length](../static/ss/v2.4.0/journey-combat-counts-journey.png)

![Corrected count rankings at 390px](../static/ss/v2.4.0/journey-combat-counts-mobile.png)

## Structure calendar timers and role reminders — v2.4.0

Captured November 9, 2026 from the unreleased 2.4.0 working tree: actual Structures/settings/banner/Calendar components and shared styles, real FastAPI routes with isolated SQLite and synthetic Demo towers/users. The private browser harness explicitly triggers the real delivery service. No production account, ESI/SSO or private gameplay data was used; images are rendered component crops with no repainting. The desktop viewport was 1440×1100; mobile was 390×844. UI checks cover opt-in, custom lead times/roles, fuel/stront events, deduplicated inbox delivery, calendar links, failed-save retry, persistent dismissal, disabling, overflow and reduced motion. [Guide](structures.md#calendar-timers-and-role-reminders) · [Receipt](../static/ss/v2.4.0/capture-receipt.json)

| View | Synthetic development capture |
| --- | --- |
| Settings | ![Calendar checkbox, recipient roles and custom minutes](../static/ss/v2.4.0/structure-timer-settings.png) |
| Banner | ![Fuel and reinforcement timer reminders](../static/ss/v2.4.0/structure-timer-banner.png) |
| Calendar | ![Managed reinforcement deadline](../static/ss/v2.4.0/structure-timer-calendar.png) |
| Mobile | ![Mobile timer controls](../static/ss/v2.4.0/structure-timer-mobile.png) |

## Intel Reports ten-page pulls — v2.4.0

Captured November 9, 2026 from the unreleased working tree on c3d2dcb. Actual React Intel Reports controls and real API routes use a synthetic, isolated SQLite preview and a paced-source replacement returning 30 distinct Demo killmails across ten pages. No live zKill/ESI/SSO, production users or private gameplay data. Browser checks verified the full pull, cached repeat, persistent coverage and 390px overflow. Component crops are unaltered. [Guide](intel-report-builder.md#pull-recent-zkill-evidence) · [Receipt](../static/ss/v2.4.0/capture-receipt.json)

![Desktop ten-page pull coverage](../static/ss/v2.4.0/intel-reports-ten-pages.png)

![Mobile ten-page pull coverage](../static/ss/v2.4.0/intel-reports-ten-pages-mobile.png)
