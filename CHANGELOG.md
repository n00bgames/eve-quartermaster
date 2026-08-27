# Changelog

All notable changes to EVE Quartermaster are tracked here.

This project is moving quickly during beta. Version sections are written as user-facing release notes first, with implementation detail included where it helps operators understand deployment or testing impact.

## [0.1.22-beta] - 2026-08-27

### Added

- Added last-hour ESI traffic intelligence to the Jump Capable Ship Plotter, Route Checker/Gatecheck, and PvP Intel Report. Route systems and jump alternates now display ship jumps, ship kills, and pod kills from a shared five-minute cache backed by hourly observations rather than scraping Dotlan.
- Added supercapital-aware docking targets to the Jump Capable Ship Plotter. Supercarriers and titans now route only through known Keepstar-class structures, exclude NPC stations from their destination details, and warn operators that structure eligibility does not guarantee docking or tether access. Character and corporation structure syncs retain ESI structure types so accessible allied and public Keepstars can participate after refresh.
- Added dynamic Battle Reports built from the existing Killboard cache. Select a permission-visible pilot to reconstruct their latest engagement using a configurable inactivity gap, deterministic affiliation connectivity, and explicit third-party/ambiguous handling; Involved, Summary, Timeline, Damage, and Composition views expose team efficiency, organizations, pilots, hulls, losses, damage, and direct zKill evidence links without duplicating canonical ESI killmail storage.
- Added revocable public Battle Report snapshot links. Shared reports use unguessable tokens, open without an EQM account, retain the exact generated report rather than silently changing with later syncs, and expose creator-side copy and view-count controls.
- Added canonical SDE ship classes to Battle Report Composition, including groups such as Battleship, Marauder, and Combat Battlecruiser, with an explicit unresolved fallback when SDE data is unavailable.
- Linked Battle Report pilot names directly to their zKillboard character pages in authenticated and public views.
- Added pilot portraits, corporation and alliance names/logos, and ship imagery throughout Battle Report participant, team, timeline, and composition views.
- Added retained Battle Report history browsing with stable engagement seed IDs, a dated system-aware selector, and Older/Newer controls. Public sharing now captures whichever historical engagement is selected instead of always reverting to the latest report.
- Added an **Edit teams** mode to Battle Reports. Drag alliance and corporation chips between the selected pilot's side, the opposing side, and third parties/ambiguous, or reclassify individual non-anchor pilots with a selector. Corporation choices can refine a broader alliance move, individual pilot choices take final precedence, EQM rebuilds all dependent analytics from canonical killmails, and public snapshots preserve every manual classification.

- Added a separate Battle Reports section permission and transparent coverage placards that distinguish canonical ESI facts from zKillboard discovery/value estimates and disclose the active grouping rule rather than presenting best-effort public history as complete.
- Added role-aware Analytics scopes for My Pilots, All Pilots, corporations, and alliances, with Director affiliation limits and convenient category jump links.
- Added privacy-preserving Analytics aggregation: ordinary opt-outs may contribute only as a global cohort of at least three without identifying drilldowns, while HARD STOP data remains excluded for every role. The README now documents these guarantees and the subtraction-attack protection explicitly.

### Fixed

- Fixed Battle Reports classifying the selected pilot and their alliance as third-party/ambiguous when a friendly pilot appeared among the attackers on an allied loss. Friendly-fire records and missing alliance IDs now use linked character/corporation/alliance identity without creating a false opposing-team edge, while the selected pilot's affiliation remains the report anchor.
- **Sync all eligible** on Characters now queues every scope-authorized character dataset registered in the Sync & Freshness Center, including the previously omitted Jump Clones and active implants collector. When a character has multiple active authorizations, EQM selects the newest eligible token per dataset instead of allowing one partial-scope token to hide another usable authorization. Bulk progress reports the current dataset by its user-facing name, while character and wallet privacy opt-outs remain hard exclusions.

### Changed

- Bumped the visible application, package, backend API, Android wrapper, export metadata, README badge, and outbound service user-agent versions to 0.1.22-beta for release.

## [0.1.19-beta] - 2026-08-20

### Added

- Added a permission-aware Character Skills finder with comma-separated multi-skill search, All/Any matching, minimum trained-level filtering, pilot result counts, and concise matched-skill badges.
- Added consistent record finders for research and manufacturing projects, contracts, HyperNet offers, and jump-clone implants/custom sets; existing Standings and Corporate Exchange search remain available.

- Added four baseline-aware Analytics widgets for the selected reporting range: top 10 NPC corporation standing gains, NPC corporation standing losses, faction standing gains, and faction standing losses. Rankings use four-decimal unmodified ESI base standings, sum net movement across pilots visible to the viewer, exclude first-observation coverage, and begin accruing through automatic standings snapshots.
- Added a permission-aware Analytics pilot-scope selector for **All visible pilots**, **My data**, or an accessible corporation. The selection filters pilot history, standings, skills, mining, research, planetary, blueprint, and eligible corporation widgets without weakening Financial Analytics privacy boundaries.

- Added a private, account-scoped Bounty Analytics module backed by retained character wallet journals, with authoritative NPC bounty classification, deterministic payout ticks, 1/7/30/90-day and all-history views, tick/hour/day charts, pilot and historical-corporation filters, summary metrics, traceable leaderboards, paged ledger evidence, and CSV export.
- Added corporate-tax analytics to bounty history. Each tick preserves ESI's original net wallet amount and first-import corporation identity; gross bounty, corporate tax, and effective rate are calculated only from authoritative tax fields, missing evidence remains Unknown, and tax cards, charts, leaderboards, filters, drilldowns, and exports expose reconciliation coverage without applying current corporation tax rates retroactively.

- Added an explicit **Exact Match** option to Character Contacts Sync. Its preview identifies destination-only contacts by name and character, then the confirmed apply operation creates missing contacts, updates changed standings/watch states, and deletes extras in ESI-safe batches so selected characters match the source one-for-one.
- Moved Character Contacts Sync apply operations into durable background jobs so long multi-character copies and Exact Match runs return immediately instead of timing out, report per-target progress in the Sync & Freshness Center, resume their status after navigation, preserve completed targets when another fails, and recover queued/running work after a backend restart.

- Added the EQM Killboard: polite incremental zKillboard discovery, authoritative ESI killmail retrieval, normalized victim/attacker/item storage, raw source payload retention, deduplication by killmail ID, durable resumable cursors, direct zKill links, and account/character/corporation combat analytics across configurable 7/30/90-day views.

- Added combat analytics for kills, losses, zKill-estimated ISK destroyed/lost and efficiency, solo/fleet participation, final blows, damage contribution, hull usage/destruction/loss, system/region/security activity, recurring opponents, streaks, inactivity, and characters frequently appearing together. Registered Killboard gauges also feed EQM's existing snapshot infrastructure.

- Added administrator-configurable Killboard enablement, refresh period, historical lookback, zKill request delay, and page ceiling, plus per-role section permissions and explicit discovery-coverage/source placards.

### Changed

- Killboard synchronization automatically refreshes when due and the module is visited, while preserving its server-side cursor and page progress across navigation. Failed source requests retain every previously imported canonical record and can be resumed safely.

### Fixed

- Fixed Jump Clone sync failures for clones located in Upwell structures by storing EVE location IDs as 64-bit integers; failed refreshes now explicitly confirm that previously synced clone data was preserved.

- Character summary hover cards now render through a viewport-level overlay, automatically flip above their trigger near the bottom edge, remain constrained to the visible window, and track scrolling or resizing instead of being clipped by card lists, tables, and other overflow panes.

- Character wallet journal synchronization now writes large histories in bounded, transaction-safe batches instead of exceeding PostgreSQL's 65,535-parameter statement limit. Aggregate Character Sync failures also suppress generated SQL and parameter dumps so the review placard remains concise and useful.

- Killboard opponents and other public combatants now resolve through ESI into a dedicated, refreshable entity-name cache instead of remaining as raw `Character 123456789` or corporation/alliance ID labels. Deleted or inaccessible entities continue to show an explicit ID fallback without breaking analytics.

- Replaced the Killboard's leftover personalized ledger heading with the generic **EQM Violence Ledger** label used by every installation.

## [0.1.18-beta] - 2026-08-06

### Added

- Added ESI manufacturing jobs to Research Projects, including character and corporation jobs, active/history views, activity filtering, a dedicated summary count, and Analytics attribution alongside ME/TE, copying, and invention.

- Added **Send to EVE** for saved and draft fittings. Users can choose one of their own linked characters, authorize `esi-fittings.write_fittings.v1` through EVE SSO when needed, and save the EQM fit directly into that character's EVE fitting library; write-token ownership remains account-private even for EQM staff.

- Added EVE-compatible Skill Plan export with one-click clipboard copy and UTF-8 text download. Target levels expand into ordered individual levels for EVE’s Import Skills from Clipboard action, with a warning for plans beyond the client’s 150-level personal-plan limit.

- Added multiple, optionally fitting-specific skill-plan links per doctrine; plan links now deep-link directly to the selected Skills > Skill Plans record, and two or more plans can be combined into a reviewed master plan with duplicate skills retained at the highest requested level.

- Added permission-filtered Assets and Blueprint Library exports in CSV and JSON. Users can export the current filter or every accessible record; exports include a versioned schema, UTC generation time, application version, stable EVE IDs, BPO/BPC research/job context, item taxonomy, volume fields, exact-ID-safe JSON strings, timestamped filenames, and explicit unknown pricing fields. Optional privacy controls can suppress owner/location names and IDs, substitute user-defined location aliases, or replace sensitive IDs with keyed hashes.

- Expanded Doctrine Management from one canonical fit per doctrine to an ordered multi-fit doctrine library. Officers can now create a named doctrine before attaching fits, add or remove several shared fits, select a primary compatibility fit, inspect each fit, and run live multi-hub market appraisal with per-fit and combined buy, split, and replacement totals. Existing doctrines migrate their canonical fit automatically.

- Added an integrated Doctrine Management module with searchable list/detail views, officer-managed create/edit/archive workflows, configurable validated priority fields and generated or manual priority codes, canonical Fittings links with historical snapshots, inline EFT fit creation, audit metadata, and optional Skill Plan links. Existing Calendar & Events doctrine records remain compatible and can be upgraded in place.

- Added editable Skill Plans inside the Character Skills module. Plans may be built manually or generated from a doctrine/fitting using imported EVE SDE dogma for hulls, modules, rigs, drones, fighters, charges, scripts, and recursively available prerequisites; repeated requirements are deduplicated at the highest minimum level, generation sources remain visible during review, and linked-character progress distinguishes complete, partial, and missing skills.

- Added Ship Replacement Requests with owner-scoped EQM character selection, doctrine or general fitting selection, labeled EVE-time/UTC loss date and time, stable historical name snapshots, search and filters, draft editing, and the extensible Submitted → Under Review → Approved/Rejected → Paid workflow. Officer review permissions and all data validation are enforced on the server.

- Expanded SRP into staff-created operation instances with generated submission links, open/closed intake, inherited operation/doctrine context, configurable loss reasons, location and organization snapshots, encrypted optional killmail hashes, immutable fitting composition, fixed-precision loss and reimbursement values, duplicate/invalid/test/cancelled controls, and append-only workflow/review events.

- Added a permission-filtered SRP Analytics workspace with UTC/custom-range reporting, loss and ISK trends, doctrine/fit/ship/class/pilot/operation/organization/location/status breakdowns, reimbursement gaps, data-quality indicators, aggregate drilldowns, and exact detailed or aggregate CSV exports. Missing valuations remain unknown rather than becoming zero.

- Added systemic resumable progress tracking for bulk character workflows. Character Data, Character Skills, Mining, Research, and both bulk and per-character Planetary Industry syncs now remember their server job, stop page-local polling when the module is left, and resume the same progress indicator when the user returns. Stale references are safely cleared after expiry or a backend restart.

- Added live bulk-workflow rows to the ESI Sync & Freshness Center. Character Data Sync, Character Skills, and Planetary Industry coordinators are now counted and refreshed while active, including overall progress and the current character/data type.

- Added a permission-filtered ESI Sync & Freshness Center that consolidates durable per-character dataset status, age, active and failed jobs, never-synced data, missing scopes, and owner-disabled collection. Full character sync opt-out and wallet-history opt-out are identified as intentional privacy states instead of false failures.

- Added a third-party research and provenance ledger plus a README acknowledgment for feature-direction research informed by the MIT-licensed EVE Buddy project. The record clearly separates independent implementation and validation evidence from incorporated source code or assets.

- Added a versioned fitting-reference fixture harness with required provenance, explicit tolerances, reusable metric-path assertions, and an initial formula-based Fenrir fixture. Independently verified Pyfa or EVE-client fixtures can now become measurable release gates without treating EQM's own output as its source of truth.

- Added a host-selectable Analytics storage policy: **Full History** preserves every eligible observation, while **Changes + Daily Checkpoints** stores metric values only when they change and limits high-volume skill, corporation, and blueprint detail to daily checkpoints. The lower-storage mode is the default for new installations; upgrades with existing history remain on Full History until a host changes it. Blueprint removals are retained as explicit zero-value changes, and switching modes never rewrites existing history.

- Added selected-range coverage metadata and an Analytics placard that reports the history actually available instead of implying a complete 7D/30D/90D/1Y window. Metric series are explicitly treated according to their own timestamps rather than as globally synchronized snapshot runs.

- Added a compact Change Composition widget for skill points, corporation wallets, members, and blueprints. Net change is separated into organic movement for already-observed owners and coverage change from first-time observations, preventing newly linked characters or corporations from masquerading as enormous growth.

- Added an enforced analytics metric registry. Every snapshot metric now declares entity and time aggregation, supported rollups and transforms, value kind, dimensions, privacy scope, version, and chart compatibility; unregistered or incorrectly scoped metrics are rejected before collection.

- Added registry-declared virtual metrics. Wallet balance observations now produce daily and weekly deltas, percentage growth, and 30-day rolling averages at query time without collectors storing redundant derived rows; financial KPIs consume the same shared derivation engine.

### Changed

- Rebuilt the fitting simulator's common cold-fit calculation path around imported SDE dogma and character skills. Turret/launcher/drone damage, hull bonuses, resistance compensation, extender and repair rigs, capacitor use, targeting, propulsion, signature radius, sensor compensation, resource reductions, and drone activation now follow the applicable skill and module state instead of broad name-based approximations. Loaded charge and script effects, T2 hull-skill routing, command bursts and their charges, plate mass, passive-coating compensation, and shared agility effects now use the same reusable Dogma path across ship classes.

- Added externally verified Pyfa 2.68.0 All-V and Steihl Lianul reference evidence for Rail Moa, Rapid Light Caracal, Active Armor Vexor, and command-burst Absolution fits, including explicit heat, implant, booster, fleet-effect, module-state, drone-state, rounding, and SDE-version provenance. The Absolution fixture is also cross-checked against the EVE fitting simulator for offense, tank, movement, targeting, and drone output.

- Added an isolated Python 3.12 backend test image and opt-in Compose test profile. The complete pytest suite and the focused fitting regression fleet now run through repeatable Docker commands without installing pytest in the production backend or worker images.

- Historical character, corporation, and financial trends now include the most recent observation before the selected range as their opening baseline, keeping deltas and unchanged series correct under change-only retention.

- Analytics gain rankings now remain explicitly organic: owners need a comparison baseline before their movement can appear as training, wallet, member, or blueprint growth.

- Duplicate-blueprint analytics now reads the current scoped blueprint inventory rather than depending on the latest retained full-detail checkpoint.

- Bumped the visible app, package, backend API, Android wrapper, README badge, and navigation-intel user-agent versions to 0.1.18-beta for the next development cycle.

- Improved historical chart rendering with dynamic non-zero Y-axis domains, 5–10% peak headroom, human-friendly tick intervals, date labels that adapt from daily through quarterly views, and pointer crosshairs with readable multi-series value cards.

- Character dossiers now display both base NPC standings and effective standings calculated from active Diplomacy, Connections, or Criminal Connections levels, including the applied skill and level; the interface clarifies that Social affects future gains rather than the current standing.

### Fixed

- Fixed the Skill Plan editor remounting its form after every keystroke, which caused name, description, search, per-skill notes, and plan-notes fields to lose focus after a single character.

- Fixed Blueprint Library exports leaving canonical locations blank for blueprints nested beneath containers and corporation offices. Export schema v2 now follows the permission-checked asset hierarchy to the containing station or Upwell structure, exposes immediate and root locations plus container ancestry and corporation flags, classifies resolved/parent-resolved/anonymized/inaccessible/unresolved records, reports location-resolution quality totals, and uses the same canonical root location in the Blueprint Library UI.

- Fixed Doctrine Management text fields losing focus after every typed character. The editor now stays mounted through form-state updates, so names, purposes, searches, notes, priority configuration, and inline EFT input accept uninterrupted typing.

- Fixed the Blueprint Library dropping originals while ESI temporarily removes an installed blueprint from the normal blueprint inventory response. Active ME, TE, and copying jobs now contribute a permission-filtered in-research library row, preserve the last observed ME/TE and location context, remain searchable, and do not appear as a false Missing BPO.

- Fixed Character Data Sync appearing as zero active jobs while its coordinator was still processing characters between durable ESI subjobs. Bulk job access is now scoped to the account that launched it so persisted browser references cannot expose another user's progress.

- Fixed EFT imports that misclassified Drone Damage Amplifiers, Drone Link Augmentors, and Omnidirectional Tracking Links as drones, which removed them from their actual fitting slots and corrupted resources, damage, range, and capacitor estimates.

- Fixed online-but-inactive fitted modules and inactive drone-bay entries contributing active effects, and corrected afterburner capacitor use to include both Afterburner and Fuel Conservation skill modifiers plus the trained activation cycle.

- Fixed shield booster repair amounts being mistaken for permanent shield capacity, made applicable hull rate-of-fire modifiers carry through to turret capacitor draw as well as weapon DPS, and stopped applying a stacking penalty to SDE-declared stackable capacitor rechargers.

- Fixed T2 ammunition such as Scorch and Conflagration being omitted from laser charge selectors. Fitting controls and simulation now use the SDE's allowed charge groups and charge sizes, so modules offer compatible standard, faction, and T2 charges without mixing weapon sizes.

- Fixed draft normalization moving Armor and Shield Command Bursts into low or mid slots because their bonus-family names resembled tank modules. Every command-burst family now remains in a high slot when cloning, importing, editing, or repairing a draft.

- Fixed SDE imports preferring stale nested `fsd` copies over newer root YAML files, and fixed duplicate pending placeholder groups during large current-SDE imports. Re-importing now refreshes current ship cargo, module attributes, Dogma, scripts, and ammunition metadata reliably.

- Character wallet journal sync now deduplicates repeated ESI reference IDs and uses an atomic database upsert, preventing an already-stored journal entry from failing the entire balance/history sync. Failure records also omit enormous bulk-parameter dumps.

## [0.1.17-beta] - 2026-08-03

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added historical character wallet collection on eligible syncs, including daily balance snapshots, growth and change KPIs, income/spending velocity, and locally cached wallet-journal events enriched with item-level market purchase and sale details.
- Added a dedicated Financial Analytics dashboard with personal wallet history, notable financial-event timelines, corporation-wide trends, wealth distribution, and privacy-preserving aggregate views without richest-pilot leaderboards.
- Added explicit, owner-only consent for corporation Financial Analytics. Wallet history defaults to the pilot's private dashboard and contributes to no corporation metric until that pilot opts in; staff cannot opt in on a pilot's behalf.
- Added owner-only hard wallet opt-out controls. Opting out purges stored wallet snapshots and journal events, clears the current balance, blocks future collection without staff override, and excludes the pilot from every financial aggregate.
- Added director-controlled corporation wallet-total visibility. Corporation wealth combines every synced corporation wallet division with explicitly opted-in pilot wallets and shows the sources separately; reporting defaults to rebased trends, and raw totals appear only when explicitly enabled for authorized officers.
- Added an opt-in Remember me sign-in using a 30-day HttpOnly, SameSite cookie, with cookie-aware API requests and explicit server-side cookie removal on sign-out.
- Added live Planetary Industry checkpoint simulation that advances extractor cycles, routed commodities, factory production, storage capacity, starvation, and blocked outputs from the last ESI observation to the current time.
- Added accessible Character Skills dogma popovers with lazy-loaded descriptions, rank, training attributes, prerequisites, per-level and current effective bonuses, affected categories, and EVE type/effect IDs.
- Added week-long local dogma caching plus authoritative SDE type-bonus lookup so repeated hover, focus, and touch access is immediate while hull-specific bonuses remain accurate.
- Added a compact Character Skills report-action menu on narrow cards so Expand and Sync Skills remain visible while Copy Report and Download Report stay available without crowding the layout.

### Changed

- Included character wallet balance and journal collection in Sync All when the ESI scope is present, while independently honoring the wallet hard opt-out so other character data can continue syncing.
- Extended all queued character-sync polling to a hard 30-minute maximum across Characters, Skills, Mining, Planetary Industry, and Research, with a shared timeout message instead of indefinite polling.
- Enforced character sync opt-out as a non-overridable financial privacy boundary on character sheets: other accounts, including staff, no longer receive contract ISK fields or kill-history ISK totals for an opted-out pilot.
- Distinguished projected PI inventories and factory health from their ESI-observed checkpoint values, with automatic 30-second local refreshes and stale-checkpoint warnings.
- Bumped the visible app, package, backend API, Android wrapper, README badge, and navigation-intel user-agent versions to 0.1.17-beta for the next development cycle.
- Reworked shared mobile and foldable layout behavior with container-aware skill cards, wrapping toolbars and action groups, compact navigation, responsive statistics, reduced small-screen spacing, and removal of nested Skills-page scrolling.

## [0.1.16-beta] - 2026-07-30

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added the manual-first HyperNet Tracker with offer planning, exact fee/core/profit calculations, seller-seeded node risk, progress snapshots, participant observations, reconciliation, and history. HyperNet offer data is never assumed to be available through ESI.
- Added the Calendar & Events workspace with scheduling, multi-character registration, fleet composition, independent attendance, and participation analytics.
- Added quick Going or Maybe RSVP controls for every linked character, allowing several pilots from one EQM account to join the same event.
- Added ordered required-cyno waypoint input to the Jump Capable Ship Plotter. EQM automatically fills valid jumps between origin, each system where the pilot already has a cyno, and the destination while retaining fuel, kill, and activity intelligence.
- Added selectable alternate jump systems to every plotted leg and rendered them on the operational map, with explicit `NO STATION` and `ONLY RED STATIONS` warnings.
- Added one-click replanning through a selected alternate jump point. EQM retains the original ship, skills, destination, station safety, avoids, intel filters, and feasible required cynos; any required cyno that cannot be retained is named in a visible route-warning placard.
- Added a persistent Analytics loading placard that warns long-running reports may take time and should not be interrupted by refreshing the page.
- Added host-visible legacy Analytics storage inspection and confirmation-gated compaction that preserves every manual snapshot plus the latest complete automatic snapshot for each UTC day.

### Changed

- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.16-beta for the next development cycle.
- Reworked corporation wallet and blueprint trends into daily closing series with a distinct color, line, and latest-value legend for each corporation.
- Made automatic Analytics snapshots scope-aware and coalesced identical character/corporation sync observations for one hour, eliminating full-library blueprint and skill duplication on unrelated ESI refreshes.
- Reduced Analytics summary query duplication, added history-query indexes, and loaded each selected character/corporation history set once per report.

### Fixed

- Stopped Analytics trend charts from interleaving every raw refresh into a repeating high/low bar pattern instead of displaying the selected historical range.
- Removed unlinked characters from the active Characters list as soon as their last ESI token is revoked, while retaining their stored historical data.

## [0.1.15-beta] - 2026-07-29

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Replaced the public Corporate Exchange seller-name clipboard action with one-time EVE SSO authorization that opens a polished, addressed purchase-request draft in the buyer's running EVE client for review and sending.

### Changed

- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.15-beta for the next development cycle.

## [0.1.14-beta] - 2026-07-28

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added live five-hub appraisal previews to the Corporate Exchange listing editor, with one-click buy or sell price selection for fixed-price listings and auction opening bids.
- Added auction listings to the Corporate Exchange with opening bids, optional hidden reserves, scheduled endings, complete-lot or partial-quantity bidding, and configurable public, highest-only, or seller-private bid displays.
- Added account-free public Exchange links so alliance members can inspect shared fixed-price listings or auctions and submit contact-backed bids without receiving an EQM account.
- Added seller bid review with accept or reject actions, automatic listing-stock reservation, transaction records, notifications, and audit history when a winning bid is accepted.

- Added the first Corporate Exchange marketplace slice with ESI-linked seller identities, fixed-price personal listings, permanent shareable URLs, package manifests, five-hub appraisal snapshots, atomic partial or complete-lot reservations, transaction records, buyer/seller notification records, and audited listing activity.
- Added an extensible marketplace schema for future bids, auctions, corporation-owned stock, counteroffers, storefronts, and moderated transaction workflows without presenting those unfinished paths as active features.
- Added appraisal-ready implant shopping-list exports for individual jump clones, all clones on a selected character, and custom implant sets, with duplicate implant quantities combined automatically.
- Added a Planetary Industry workspace with queued ESI sync, colony and layout storage, SDE Dogma-backed extractor program projections, routed factory warnings, storage totals, and character/system/planet filters.
- Added historical Planetary Industry production observations and Analytics widgets for P0 extraction through P4 manufacturing, including tier totals, current projected throughput, per-commodity leaders, and filterable pilot rankings.
- Added SDE-backed Planetary Industry schematic names, products, cycle outputs, and input recipes so factory rows describe what they manufacture instead of showing only schematic IDs.

### Fixed

- Protected committed Exchange claims and active auction bids from destructive stock, package-content, and auction-price edits while preserving each transaction's recorded price.
- Corrected Exchange totals and appraisal comparisons to follow the stock still available after partial sales.
- Unified draft and saved-listing appraisals through EQM's shared market calls and corrected multi-package listings to price the full offered quantity.
- Fixed Planetary Industry reauthorization so the core and PI-specific SSO flows request `esi-planets.manage_planets.v1`, persist the granted scope, and return directly to the PI workspace.
- Moved single-character Planetary Industry sync into a queued status job so colony imports no longer time out in the browser.
- Kept active, paused, and ready-for-delivery ME, TE, and copying jobs in blueprint analytics as a deduplicated shadow inventory keyed by ESI blueprint item ID.
- Resolved corporation asset flags to configured corporation hangar division names and expanded authorized Upwell structure-name refreshes, while retaining raw ESI identifiers when a private location cannot be disclosed.
- Fixed corporation offices in third-party Upwell structures by preserving external structure IDs that ESI reports as item locations, resolving them through authenticated structure lookup, and propagating the structure name through nested asset containers.

### Changed

- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.14-beta for the next development cycle.

## [0.1.13-beta] - 2026-07-27

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added per-character NPC standings sync and display for agents, NPC corporations, and factions, with resolved ESI names, source filters, search, sorting, relationship meters, sync freshness, and Sync All integration.

### Changed

- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.13-beta.

## [0.1.12-beta] - 2026-07-22

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a configurable public recruiting subheading and safe structured description sections using plain Markdown-style headings without rendering raw HTML.
- Added per-character categorized skill report exports with clipboard and plain-text download options for sharing trained levels, skill points, sync recency, and the current training queue.

### Fixed

- Protected committed Exchange claims and active auction bids from destructive stock, package-content, and auction-price edits while preserving each transaction's recorded price.
- Corrected Exchange totals and appraisal comparisons to follow the stock still available after partial sales.
- Filtered Research Projects corporation queues through EQM's approved corporation scope while preserving corporation-owned jobs whose ESI installer is an active SSO-linked character, including restricted linked-installer syncs for otherwise excluded corporations.
- Fixed Analytics corporation scope so only corporations with current successful corporation-level ESI access contribute to snapshots, growth widgets, metric exports, and corporation-owned blueprint reporting.
- Fixed applicant character linking so incomplete applications can be saved as drafts before EVE SSO opens in a forced separate tab, preventing in-progress answers from being lost.
- Removed duplicated decorative markers from configured recruiting lists while retaining the original stored content.

### Changed

- Polished the public Recruiting page with clearer hierarchy, natural-height responsive cards, expandable long lists that retain core expectations, a concise privacy summary with an accessible full notice, improved form readability, and a DST-aware Typical member activity window.
- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.12-beta.

## [0.1.11-beta] - 2026-07-20

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a configurable Recruiting module with public corporation/alliance branding, applicant accounts and drafts, limited-scope EVE character verification, main-character selection, recruiter review queues, interview coordination, applicant messaging, audited decisions, privacy/retention controls, and capability-based Recruiter and Recruitment Administrator access.
- Added Recruiting Initial Setup with ESI-resolved corporation, alliance, logos, and current CEO; manual CEO overrides are reserved for explicit audited edge cases.
- Added selectable ISK-share or mineral-share Mining Op settlements, with deterministic whole-unit mineral allocation, proportional reserve and expense retention, and immutable per-pilot mineral payout snapshots.
- Added one-click Discord-ready Mining Op reports for previews, drafts, and finalized settlements, including scope, refined output, deductions, payout mode, and itemized pilot shares.
- Added a Host account role above Admin for installation ownership and host-only database maintenance, including status inspection, portable `.eqmbackup` exports, transactional restores, and confirmation-protected database clearing that retains the signed-in host and schema.
- Added EVE Online Multibuy-ready clipboard exports for either asset-aware remaining needs or complete shopping lists using plain item-name and quantity rows.

### Fixed

- Protected committed Exchange claims and active auction bids from destructive stock, package-content, and auction-price edits while preserving each transaction's recorded price.
- Corrected Exchange totals and appraisal comparisons to follow the stock still available after partial sales.
- Fixed the signed-out Apply / Recruiting link so hash-route changes immediately open the public recruiting page without requiring a manual reload.
- Accepted CCP's current no-trailing-slash EVE SSO token issuer and returned recruitment-link failures to the applicant workspace instead of exposing a raw API error page.
- Saved the current recruitment application draft before opening EVE SSO in a separate window, then refreshed the original application when character linking completes.

- Hardened EVE SSO identity handling by validating access-token signatures, issuer, audience, expiry, signing key, and configured application client before trusting character claims.
- Added the required ESI compatibility-date header through the shared ESI client and all containerized sync paths.
- Fixed fitting simulations retaining stale or unchanged module values after an undefined multiplier helper crashed fresh calculations.
- Corrected freighter cargo and velocity calculations to derive racial skill type IDs, per-level hull bonuses, and fitted module multipliers from imported SDE Dogma data, including cargo expanders, reinforced bulkheads, and inertial stabilizers.
- Added SDE-backed ship mass and align-time calculations using hull agility, applicable piloting skills, fitted mobility modules, and selected implant or implant-set Dogma effects.
- Corrected capacitor capacity, recharge time, and peak recharge calculations to apply imported Capacitor Management and Capacitor Systems Operation skill bonuses.
- Updated the bundled SDE fetch helpers to use CCP's official always-latest YAML export and made the simulated pilot explicit in Character Readiness.
- Added the first fitting regression-fleet sentries covering Fenrir cargo, structure, signature, velocity, role-based fitting cost, valid slot state, and exact SDE-derived reference output.
- Added PostgreSQL client compatibility handling for restores and excluded internal migration metadata from backup data to prevent restore conflicts.
- Protected the final Host account from deletion or demotion and applied Host access consistently across existing administrative tools.

### Changed

- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.11-beta.
## [0.1.10-beta] - 2026-07-16

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added first-launch Android server setup and persistent in-app Server Settings so sideloaded clients can switch EQM installations without rebuilding the APK.

- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

- Added a persistent Next Research Queue beneath Research Projects with visibility-aware owned BPO/BPC search, research activity and run planning, source location snapshots, and editable source-hangar tracking.
- Added queue ordering, pending/completed views, completion and restoration controls, deletion, and retained completed entries for operational history.

- Added plain-text shopping-list clipboard exports for either asset-aware remaining needs or every row's full requested quantity, omitting pricing, categories, headers, and totals.
- Added a private Notes & Lists workspace for freeform notes and persistent resupply lists with tags, destination systems, station/structure targets, preferred market hubs, search, sorting, duplication, soft deletion, and undo.
- Added SDE-backed item-line parsing and manual resolution for list imports, including explicit duplicate merging, editable quantities, six fulfillment statuses, bulk updates, reordering, and completed-item cleanup.
- Added visibility-aware asset cross-reference summaries for requested, at-destination, elsewhere, and remaining quantities with owner filters, sync freshness, and expandable location details.
- Added selected-item market pricing across configured trade hubs using requested or remaining quantities without changing item status or initiating purchases.
- Added Notes & Lists persistence, migration, permissions, shared asset-visibility and item-parser services, and focused parser/validation/CRUD tests.

- Added a persistent Mining Op Settlement workflow beneath the Mining Ledger with saved-operation or date-range sourcing, contribution-based automatic miner shares, manual support pilots, and exact ISK payout reconciliation.
- Added authoritative actual-refined-output entry using SDE mineral choices, captured hub or manual unit prices, refiner metadata, operation reserves, repeatable expenses, fixed-percentage payouts, and weighted-share compensation.
- Added editable settlement drafts and immutable finalized snapshots that retain source ledger rows, prices, outputs, deductions, participant calculations, warnings, and payout results for future analytics.
- Added backend settlement calculation tests covering percentage normalization, gross value, reserves, deductions, fixed and weighted payouts, manual pilots, missing and overridden prices, validation failures, and deterministic cent rounding.

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

- Protected committed Exchange claims and active auction bids from destructive stock, package-content, and auction-price edits while preserving each transaction's recorded price.
- Corrected Exchange totals and appraisal comparisons to follow the stock still available after partial sales.
- Fixed a local development/publish environment mismatch that made every stored ESI refresh token appear to require reauthorization; the running backend now uses the database's original token-encryption key and configured EVE SSO client credentials.
- Fixed Character Contacts Sync preview and apply requests failing before ESI access after the token permission guard became database-aware, and display contact-sync failures with error styling instead of a green success notice.
- Fixed user deletion failing when invitation, audit, messaging, manufacturing, mining, or settlement history still referenced the account; deleted accounts are now anonymized, denied login, removed from active account lists, and retained only for historical attribution.
- Fixed Sync All mining jobs failing before persistence because the ESI worker did not import the mining-ledger upsert service.

- Fixed character contract syncs for player-owned structure locations whose trillion-range EVE IDs do not fit the station table's integer key.
- Preserved original contract-sync failures after database errors and displayed every failed Sync All task instead of only the first.
- Stored shared EVE contracts independently per character or corporation so syncing one owner no longer reassigns another owner's contract rows.
- Removed hidden and analytics-excluded corporations from existing analytics summaries, trends, duplicate-blueprint results, exports, and future snapshots.
- Fixed Jump Clone implant dogma cards painting beneath neighboring clone content and enforced an opaque tooltip surface.

### Changed

- Added a hover glow and enlarged opaque job preview to Research Projects rows, and increased the results pane height by approximately 25% for easier queue scanning.
- Replaced Research Project cards with a sortable table and prechecked corporation roles before queuing corporation research syncs.
- Marked the Fittings navigation entry as a bright-red WIP warning while fitting calculations remain under development.
- Bumped the visible app, package, backend API, Android wrapper, and ESI user-agent versions to 0.1.10-beta.

## [0.1.9-beta] - 2026-07-15

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

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

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

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

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

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

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

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

- Protected committed Exchange claims and active auction bids from destructive stock, package-content, and auction-price edits while preserving each transaction's recorded price.
- Corrected Exchange totals and appraisal comparisons to follow the stock still available after partial sales.
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

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

- Added a Prefer Safer Route option to Route Checker so gate routes can favor highsec travel even when the route becomes longer.
- Added Route Checker avoid-list controls matching the Capital Jump Plotter flow, including per-system avoid buttons and a clearable avoid list.

### Changed

- Route Checker and Gatechecker now pass safer-route and avoid-system preferences through the same backend route planner, keeping navigation behavior consistent across route tools.
## [0.1.4-beta] - 2026-07-06

### Changed

- Bumped the visible app, README, Android wrapper, backend API, and ESI client user-agent versions for the latest beta polish pass.
## [0.1.3-beta] - 2026-07-05

### Added

- Added concise desktop-only blueprint hover cards throughout Blueprint Library, overview—including blueprint rows in Recent Assets—item context, research queues/projects, recipes, missing-BPO references, and blueprint analytics. Owned instances show ME/TE, type, runs, owner, location, and current ESI industry-job details; definition-only references are identified without fabricating instance data.

- Added owner editing for Corporate Exchange listings, including restocking, available-stock adjustments, per-package fixed pricing, pre-bid auction pricing, visibility, expiration, handoff details, and unlocked package contents.
- Added viewer-triggered five-hub appraisals and an EVE Mail recipient-copy action to account-free public Exchange listing pages.
- Added a Host account role above Admin for installation ownership and host-only database maintenance; existing installations promote the oldest active administrator during migration.
- Added Settings controls to inspect and export portable database backups, transactionally restore matching EQM backups, and irreversibly clear all stored data while retaining the signed-in host account and schema.

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

- Protected committed Exchange claims and active auction bids from destructive stock, package-content, and auction-price edits while preserving each transaction's recorded price.
- Corrected Exchange totals and appraisal comparisons to follow the stock still available after partial sales.
- Market appraisal opportunity cards now only show profitable station-to-station trades; no-profit appraisals show a neutral no-current-profit badge instead of a negative trade suggestion.
- Corporation sync flows now continue past corporations where the linked character lacks the required corporation roles instead of stopping the whole batch.
- Improved station display plumbing for jump planning so NPC station names can be shown separately from station type/cyno-risk guidance when SDE data is available.

## [0.1.2-beta] - 2026-07-05

### Baseline

- First tracked beta baseline for the public-testing README badge and in-app version badge.
- Included account login, EVE SSO linking, asset and corporation syncs, blueprint/SDE import, analytics foundations, navigation tooling, local threat scanning, permissions, audit visibility, messaging, Android wrapper support, and initial fitting tools.
