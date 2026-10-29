# Report identity, privacy and Industry Reports

This unreleased 2.0 development change requires **0093_report_privacy** after 0092. Deploy backend, frontend and migration together. No production migration/deployment was performed during implementation.

## Main character and retroactive attribution

Profile offers a main-character selector. An owned-character checkbox appears after SSO returns, and each owned character on ESI Sync also has a main checkbox. Choices require both current ownership and a live token owned by the same account; arbitrary/foreign IDs are rejected. This selects identity only and adds no ESI scopes or collection.

Named Local Scan, D-Scan, saved Battle and private Industry/Inventory reports resolve their creator to the account's **current main character** at read/export time. Thus old links/PDF downloads update after a main is selected or changed. Without a valid linked main, attribution is **Anonymous**, never an account/login name. Explicitly anonymous reports always remain anonymous. A revoked/transferred main stops supplying identity. The compatibility JSON field `account_name` now contains this safe display label; no account identifier is published.

The migration redacts historical scan `account_name` values to Anonymous while retaining named mode, so later main selection applies retroactively. It does not guess which character should be a user's main. Existing public reports retain their visibility; existing downloaded copies cannot be recalled.

## Anonymous and private reports

Local Scan, D-Scan and Battle Report generation provide independent Anonymous and Private options. Anonymous hides **creator attribution** and the report-attributed corporation ID, not scanned pilots, participants, stock owners or other report contents.

Private reports have no share URL. Their random record identifier is usable only through authenticated routes; the public JSON/PDF routes return 404 even when the creator is signed in. Only the creator can read/export their private record. Other accounts, directors and administrators cannot read its content. Local/D-Scan/Industry private reports are also excluded from other users' management listings/deletions. Battle private snapshots likewise cannot be revoked by another account. Public deletion/management retains the existing role scope.

Private PDF/CSV buttons fetch with the user's sign-in credentials; they do not create public download links. All public report responses use no-store/noindex/no-referrer headers. Public pages revalidate every minute. Access and expiry are rechecked after rendering exports. Expired scan/Industry/Battle records are removed by the existing periodic cleanup.

Scans retain their membership/object snapshot. Changing account highlights updates the private view; sharing different markings still requires a new snapshot. Attribution and D-Scan presentation order are the explicit retroactive exceptions.

## Industry Report

**Current policy:** public Industry Reports always hide creator and owner identities, independently of the Anonymous option described for scans/Battles. They contain industry materials and explicitly approved finished stock. The earlier general-stock Industry behavior and captures are superseded.

Inventory & Industry now includes Industry Report. The report defaults to private. Overall stock totals appear first, including mineral and PI quantities by type; ordinary personal ships/modules are excluded. Detail follows by character/corporation, item, location and source, then blueprints, active industry jobs, and PI infrastructure. Planetary pin contents contribute stock separately from character/corporation asset storage; these represent separate inventories. Default asset stock uses an SDE classification allowlist: minerals, material/asteroid/PI categories, and recognized industrial groups such as fuel, gas, components and salvage. Unknown/general commodity groups are omitted unless storage is explicitly selected. PI pin contents form a separate industrial source.

Private pages/exports may use the main character and named owners. Public Industry pages, JSON, CSV and branded PDFs always use Anonymous attribution and Character Owned / Corporation Owned labels, with generation/data timestamps. Hangar/container identifiers, job/installer IDs and PI pin IDs are not published. NPC station, Upwell structure, facility and planet names and industry quantities remain visible. CSV includes all rows and guards spreadsheet formulas. The screen renders at most 100 rows per table page while exports contain all accessible report rows. Stock, blueprint, job and PI datasets remain permission scoped. Quartermaster report access does not grant general asset access or start private collection.

Check **Create a public link** deliberately to share the anonymous industrial view with anyone holding the link. Public creator anonymity is mandatory. An authenticated preview of a public report uses the same safe projection as its public link/exports; private reports retain names. Select 30m, 1h, 2h, 12h, 24h, 3days, 7days, 30days or permanent. A public report can be a saved snapshot or a **dynamic** report. Dynamic links query current synchronized database stock on each read/export (and the public UI refreshes each minute). They do not start an ESI dataset sync. Existing corporate authorization checks may verify a feed before granting visibility.

Dynamic scope freezes the allowed owner/character/corporation dataset IDs at generation. New characters or owners do not silently expand the published data. Every load rechecks the original creator's current permissions and current valid feeds; losing any original grant disables the link. Deleted/retired creators also disable dynamic links. The report shows data-as-of, latest and oldest sync metadata; it cannot promise live in-game stock. Snapshot links preserve their saved industrial data until expiry/deletion. Existing pre-policy snapshots have no proof of station placement/approval; their stock and derived totals are omitted on read/export with a regeneration notice. Blueprints, jobs and PI remain available with public identities removed. Existing downloaded copies cannot be recalled.

Saved Industry Reports support individual, UTC date-range or all-in-scope deletion. The newest 100 are listed, while date/all deletion covers every matching record. Public access and exports stop after deletion. Private reports remain creator-only. Industry Report has its own section permission, defaulting to members, officers, directors, admins, hosts, Quartermasters and view-only accounts, but every included dataset still requires its normal underlying access.

### Selecting station storage

The authenticated selector lists accessible NPC-station and Upwell hangars and supported station storage containers. Corporate divisions use synchronized hangar names when available; containers use type plus unique item ID because custom asset names are not currently synchronized. Search, quick check/uncheck, clear and refresh controls are available. No storage is checked initially; up to 100 choices are accepted.

Selecting a hangar includes only its direct finished goods; nested cans require their own explicit selection. Selecting a can likewise adds direct contents only. Container shells, ships' fitted items and all onboard contents (including carried cans) never appear in Industry Report. Materials/BPs in ships, unknown locations, unsupported flags, missing/cyclic/cross-owner ancestry fail closed. All ordinary material stock must resolve to station/structure storage through supported containers. Choices are saved internally with each report and dynamic links cannot silently follow a can to a different owner/station or inside a ship; unavailable choices disable the dynamic link. A selected hangar/can intentionally publishes future direct stock added there.

## Private Inventory Report

Inventory & Industry has a separate **Inventory Report**, with a dedicated `inventory_reports` section permission plus existing Assets visibility. It covers every accessible synchronized asset: ships, modules, ammo, drones, container shells/contents, fitted items and onboard cargo. Category/type totals appear first, followed by owner/location/placement/container detail. CSV/PDF exports include all rows. Character/corporation and selected main names are permitted here because the report is private.

Inventory generation accepts retention only; attempts to enable public sharing are rejected. There is no public read/export route, no share URL and no public report listing. Reads, exports, saved listings and individual/date/all deletion are creator-only, including against other directors/admins. Saved records never grant broader asset access, and current Inventory/Assets permission is checked on reads/exports. The existing expiry cleanup handles these records too. Full-page scrolling and bounded horizontal tables match the other reports.

No additional schema migration is needed for this split; it uses report kinds/JSON within migration 0093. Deploy the matching API/frontend together. No new ESI scopes or private collection are introduced.

## Battle Reports

Saved battles now support anonymous/private options, retention, revocation and PDF export. Public and creator-only download routes enforce the same access/expiry as their JSON routes. Anonymous creator attribution does not hide the selected subject or participating pilots. Named attribution updates with the creator's main. Existing public shares retain their existing lifetime until revoked; new shares default to 24 hours. Battle PDFs include branding, generation metadata, pilot/killmail totals, participant damage and timeline. Team/composition summaries, complete pilot/timeline tables and scoped corporation/date-range/bulk management are now implemented. Other users' private snapshots remain inaccessible to directors/admins. Apply migration 0094; historic shares remain unattributed. See [Battle management, access rules and verification](battle-report-management.md).

## D-Scan threat presentation

Ships and Ship Classes now order by a fixed hull-class priority: Titan, Supercarrier, Lancer Dreadnought, Dreadnought, Command Carrier, Carrier, Force Auxiliary, Marauder, Black Ops, faction battleships, battleships, then the configured smaller combat/logistics/industrial hull classes. Counts and names break ties within each class. Faction battleship labels include navy/fleet issues and a maintained named hull set; unknown/future groups fall back at the end. This is a display taxonomy, not an assessment of fittings, pilot skill or actual combat outcome.

Ordering is applied when reports are returned/rendered, so existing tokens and PDFs use it without regenerating scans. Original observations, totals, manual recon distinctions and mass remain unchanged. PDF ship tables split and repeat their headings instead of moving a large table off page one.

## Verification

131 targeted scan, privacy, Industry/Inventory, Battle, account-role and Quartermaster tests pass, including migration/downgrade, private-route rejection, retroactive identity, dynamic changes/scope revocation, expired/deleted links, CSV/PI totals and first-page PDF content. One existing Rust-shadow integration test was excluded because it hard-codes `/usr/local/bin/eqm-core`, unavailable on this Windows checkout; an initial broad run exposed that environment failure. No Rust engine code changed.

TypeScript and production frontend compilation pass. Earlier synthetic checks cover Profile/post-link main selection, old-report names/order and scans/Battle privacy. This split adds actual narrow-window browser generation/reopening, storage choices, anonymous public preview and full private inventory checks. The new captures use the actual 615px-wide app browser; desktop/mobile viewport overrides were unavailable in this session, so they are not claimed as tested. Public endpoint anonymity is verified through real ASGI JSON/CSV/PDF tests. A copied-link browser navigation was blocked as an invalid URL by browser policy; no alternate browser navigation was attempted. API exports were rendered and inspected directly. PDFs were rendered and inspected with Poppler. Captures and provenance are in [the gallery](screenshots.md) and [receipt](../static/ss/v2.0/capture-receipt.json).

## Corporation office storage correction

The Industry storage resolver now recognizes canonical corporation Office records (type 27, group 16) as station/Upwell hangar roots when ownership matches, the root has `OfficeFolder`, the child uses `CorpSAG1` through `CorpSAG7`, and the office is not nested inside another asset. Office shells themselves are not report stock or selectable cargo cans. Division identity survives nested container traversal, so explicitly selecting a division still includes direct finished goods only; cans require their own selection. Station `CorpDeliveries` stock is supported. Missing/cross-owner ancestry, ship cargo, invalid office metadata and unresolved locations remain excluded.

This corrects a filter regression that could omit thousands of synchronized blueprints despite the report scope including them. No schema/frontend change or new ESI scope is needed. Existing dynamic reports use the correction after backend deployment; immutable snapshots must be regenerated. Forty Industry/Inventory/privacy tests pass, including an existing dynamic link with 2,501 blueprint rows and CSV completeness, NPC and Upwell offices, direct-vs-nested storage choices and invalid/cross-owner/ship ancestry. Live diagnostics used read-only transactions; no production records were modified.

## Industry section order and structure names

Industry web reports and CSV/PDF exports now show active industry jobs, blueprints/reaction formulas, overall stock totals, stock by ownership, then planetary infrastructure. Inventory Reports retain totals first. This presentation order also applies when opening old saved reports.

At the user's request, public Industry Reports may display the actual station/Upwell and job-facility names, including any text chosen as part of a structure's name. Creator and owner fields remain Anonymous, Character Owned or Corporation Owned. Container names, storage identifiers and private owner fields are still excluded. This supersedes the earlier blanket masking of Upwell/facility names. Blueprint locations resolve to their verified station/Upwell storage root, including nested cans and corporation offices. Job facilities prefer resolved names in the current synchronized Location cache over stale job labels. Public reads do not trigger ESI requests; names unavailable to the authorized sync remain unresolved until a later sync can resolve them.

Existing dynamic links use these resolved names after deployment. Immutable snapshots retain their saved location labels and may need regeneration if the saved public location was already masked. Forty-two Industry/Inventory/privacy tests pass, including ordered CSV/PDF sections, named structures with anonymous owner fields, nested blueprint placement and facility-cache updates. TypeScript/build and synthetic browser/PDF visual checks pass. No migration or new ESI scopes required.
