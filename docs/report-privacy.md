# Report identity, privacy and Industry Reports

This unreleased 2.0 development change requires **0093_report_privacy** after 0092. Deploy backend, frontend and migration together. No production migration/deployment was performed during implementation.

## Main character and retroactive attribution

Profile offers a main-character selector. An owned-character checkbox appears after SSO returns, and each owned character on ESI Sync also has a main checkbox. Choices require both current ownership and a live token owned by the same account; arbitrary/foreign IDs are rejected. This selects identity only and adds no ESI scopes or collection.

Named Local Scan, D-Scan, saved Battle and Industry reports resolve their creator to the account's **current main character** at read/export time. Thus old links/PDF downloads update after a main is selected or changed. Without a valid linked main, attribution is **Anonymous**, never an account/login name. Explicitly anonymous reports always remain anonymous. A revoked/transferred main stops supplying identity. The compatibility JSON field `account_name` now contains this safe display label; no account identifier is published.

The migration redacts historical scan `account_name` values to Anonymous while retaining named mode, so later main selection applies retroactively. It does not guess which character should be a user's main. Existing public reports retain their visibility; existing downloaded copies cannot be recalled.

## Anonymous and private reports

Local Scan, D-Scan and Battle Report generation provide independent Anonymous and Private options. Anonymous hides **creator attribution** and the report-attributed corporation ID, not scanned pilots, participants, stock owners or other report contents.

Private reports have no share URL. Their random record identifier is usable only through authenticated routes; the public JSON/PDF routes return 404 even when the creator is signed in. Only the creator can read/export their private record. Other accounts, directors and administrators cannot read its content. Local/D-Scan/Industry private reports are also excluded from other users' management listings/deletions. Battle private snapshots likewise cannot be revoked by another account. Public deletion/management retains the existing role scope.

Private PDF/CSV buttons fetch with the user's sign-in credentials; they do not create public download links. All public report responses use no-store/noindex/no-referrer headers. Public pages revalidate every minute. Access and expiry are rechecked after rendering exports. Expired scan/Industry/Battle records are removed by the existing periodic cleanup.

Scans retain their membership/object snapshot. Changing account highlights updates the private view; sharing different markings still requires a new snapshot. Attribution and D-Scan presentation order are the explicit retroactive exceptions.

## Industry Report

Inventory & Industry now includes Industry Report. The report defaults to private. Overall stock totals appear first, including mineral and PI quantities by type. Detail follows by character/corporation, item, location and source, then blueprints, active industry jobs, and PI infrastructure. Planetary pin contents contribute stock separately from character/corporation asset storage; these represent separate inventories. Stock metadata comes from the SDE; accessible pin contents also identify PI types when type grouping is missing.

The page, CSV and branded PDF use main-character/Anonymous attribution and generation/data timestamps. CSV includes all rows and guards spreadsheet formulas. The screen renders at most 100 rows per table page while exports contain all accessible report rows. Stock, blueprint, job and PI datasets remain permission scoped. Quartermaster report access does not grant general asset access or start private collection.

Check **Create a public link** deliberately to share included stock, locations, jobs, blueprints and PI with anyone holding the link. Select 30m, 1h, 2h, 12h, 24h, 3days, 7days, 30days or permanent. A public report can be a saved snapshot or a **dynamic** report. Dynamic links query current synchronized database stock on each read/export (and the public UI refreshes each minute). They do not start an ESI dataset sync. Existing corporate authorization checks may verify a feed before granting visibility.

Dynamic scope freezes the allowed owner/character/corporation dataset IDs at generation. New characters or owners do not silently expand the published data. Every load rechecks the original creator's current permissions and current valid feeds; losing any original grant disables the link. Deleted/retired creators also disable dynamic links. The report shows data-as-of, latest and oldest sync metadata; it cannot promise live in-game stock. Snapshot links preserve their saved data until expiry/deletion.

Saved Industry Reports support individual, UTC date-range or all-in-scope deletion. The newest 100 are listed, while date/all deletion covers every matching record. Public access and exports stop after deletion. Private reports remain creator-only. Industry Report has its own section permission, defaulting to members, officers, directors, admins, hosts, Quartermasters and view-only accounts, but every included dataset still requires its normal underlying access.

## Battle Reports

Saved battles now support anonymous/private options, retention, revocation and PDF export. Public and creator-only download routes enforce the same access/expiry as their JSON routes. Anonymous creator attribution does not hide the selected subject or participating pilots. Named attribution updates with the creator's main. Existing public shares retain their existing lifetime until revoked; new shares default to 24 hours. Battle PDFs include branding, generation metadata, pilot/killmail totals, participant damage and timeline. Additional team/composition export styling and corporation/date-range Battle management remain separate planned enhancements.

## D-Scan threat presentation

Ships and Ship Classes now order by a fixed hull-class priority: Titan, Supercarrier, Lancer Dreadnought, Dreadnought, Command Carrier, Carrier, Force Auxiliary, Marauder, Black Ops, faction battleships, battleships, then the configured smaller combat/logistics/industrial hull classes. Counts and names break ties within each class. Faction battleship labels include navy/fleet issues and a maintained named hull set; unknown/future groups fall back at the end. This is a display taxonomy, not an assessment of fittings, pilot skill or actual combat outcome.

Ordering is applied when reports are returned/rendered, so existing tokens and PDFs use it without regenerating scans. Original observations, totals, manual recon distinctions and mass remain unchanged. PDF ship tables split and repeat their headings instead of moving a large table off page one.

## Verification

116 targeted scan, privacy, Battle, account-role and Quartermaster tests pass, including migration/downgrade, private-route rejection, retroactive identity, dynamic changes/scope revocation, expired/deleted links, CSV/PI totals and first-page PDF content. One existing Rust-shadow integration test was excluded because it hard-codes `/usr/local/bin/eqm-core`, unavailable on this Windows checkout; an initial broad run exposed that environment failure. No Rust engine code changed.

TypeScript and production frontend compilation pass. Actual synthetic browser checks cover Profile/post-link main selection, old-report names/order, private/anonymous generation and download, Battle private saving, dynamic stock refresh and narrow-screen containment. PDFs were rendered and inspected with Poppler. Captures and provenance are in [the gallery](screenshots.md) and [receipt](../static/ss/v2.0/capture-receipt.json).
