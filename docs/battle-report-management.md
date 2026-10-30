# Battle Report management

Implemented in the unreleased 2.0.0 build. Saved Battle Reports are available even when the selected pilot has no cached battle. Filter by management scope, attributed corporation and generation dates; browse 25 records per page, reopen a saved snapshot, download its PDF or copy its public link.

| Actor | Reports within management scope |
| --- | --- |
| Authenticated user with Battle Reports access | Own public and private reports |
| Director | Own reports plus public reports attributed to a corporation of a currently linked character |
| Admin or host | Own reports plus all public reports |

Other users' private reports remain inaccessible, including to directors/admins. Role unions/custom roles use the existing permission engine, and Battle Reports section access is required. Corporation attribution is explicitly selected at creation from the creator's linked characters; the selected battle pilot or combatants do not establish ownership. Anonymous reports keep internal attribution for management but do not publish it. Private reports have no corporation attribution.

Deletion can target one report, checked reports on the current page, a complete generation-date range, or every active report in scope. Date/all operations cover all matching pages. The review shows the eligible count and freezes an upper generation timestamp so newer reports are excluded. The server checks current permissions and membership again on confirmation. Dates are entered in browser-local time, sent as UTC, with an inclusive start and exclusive end. Expired/revoked reports are excluded from the manager. Deletion permanently removes saved snapshots and immediately invalidates their links/PDF endpoints; canonical cached killmails and other report types remain untouched. Previously downloaded copies cannot be recalled.

The PDF includes an EQM logo, generation-time version, current main-character attribution (or Anonymous), generation timestamp, systems, pilot/killmail totals, team metrics, hull composition, pilot details and full timeline. Repeated headings support long tables. Composition counts observed pilots and killmail appearances, not a simultaneous fleet census. Unknown loss prices remain identified. Saved team classification is preserved. Authorization and expiry are rechecked after PDF rendering.

## Migration and rollout

Apply `0094_battle_report_corporation` after `0093_report_privacy` with the matching API/frontend. It adds a nullable external EVE corporation ID and index; it deliberately leaves historic reports unattributed rather than guessing their corporation from battle subjects or current membership. Those reports remain manageable by their creator and, if public, admins. Downgrade removes only the new attribution column/index, preserving saved payloads. No new ESI scopes, version bump or live deployment is part of this change.

## Verification

54 targeted Battle, privacy and role tests pass; one existing Linux-only Rust-shadow test is deselected on Windows. Tests cover spoofed corporation IDs, own/director/admin/host scope, private isolation, membership revocation, pagination, date boundaries, all/selected deletion, public-link/PDF invalidation, render-time access changes, long PDFs and migration upgrade/downgrade. TypeScript and the production build pass (existing bundle-size advisory). Actual local browser checks confirm own/all scope, a three-record date filter/review, six-record bulk review/cancellation and reopening a corporation report. Real deletions are verified through ASGI tests; browser review was cancelled. Two-page synthetic PDF output was rendered and inspected. No live services or real reports were changed.

## Find a battle by remembered details

Below the existing generation-date selectors, choose **My Side** (the saved report’s selected-pilot side, side 0) or **Hostile Side** (its opposing side, side 1). This does not recalculate sides from your current character or corporation. Third parties/ambiguous pilots remain side 2 and never silently become hostile.

Combine any of these optional details:

- Partial, case-insensitive **pilot name**, **combatant corporation** and **combatant alliance** names retained in the snapshot. The existing **Attributed corporation** selector describes report management/ownership; it is distinct from a corporation that fought in the battle.
- **Ship class / deployable / structure**, grouped by type, with broad **Any capital hull**, **Any deployable** and **Any structure** choices. Capitals use the shared SDE hull classification, including XL/XXL capital classes. Structures include Upwell, starbase, sovereignty and orbital classes represented in the SDE.
- A dependent **Specific hull / deployable / structure** selector populated from the selected imported class. Changing class clears the previous specific type. Import the SDE to populate these choices; no live market or character lookup is needed.
- **Involved pilots on selected side**: Any number, Solo, 2–4, 5–9, 10–25, 26–50, 51–100, 101–150, 151–250, 251–350, 351–500, 501–1,000, and 1,001+. Bounds are inclusive. These count distinct recorded character IDs on that side across the entire battle; reships/repeated appearances do not add pilots. They are not a simultaneous fleet census. Unobserved pilots cannot be inferred.
- Partial **System** name, such as Hagilua, retained in the report or its loss timeline. Killmails do not retain exact gate names, so the filter cannot establish a particular gate or prove a cyno/jump-in.

**Match all details (AND)** requires pilot/corporation/alliance/hull clues to describe the same recorded combatant or loss on the selected side. It prevents a corporation’s frigates from matching because an unrelated corporation on that side brought a dreadnought. **Match any detail (OR)** accepts any of those four clues on that side. Class plus specific type remain one hull/object constraint. System, pilot-count range, generation dates and access scope always narrow results with AND, in either detail mode.

Click **Search saved reports**, or press Enter in a detail input. Text fields are literal substring matches: `%` and `_` do not become SQL wildcards. **Clear battle details** resets the new controls; **Clear filters / refresh** also clears date and attributed-corporation filters. Draft changes display an unapplied notice and disable deletion controls until searched or cleared. Applying a search resets pagination, selection and any deletion preview. Background requests are cancelled/ignored when their filters become stale.

The database applies access, expiry, dates and detail conditions **before** counting/pagination. Search covers every accessible active saved report, not just the 25 currently displayed. Results show retained battle time (browser-local), systems, recorded My/Hostile pilot counts and up to eight selected-side composition hull names, with an extra-type count. Open the snapshot for the complete pilots/composition/timeline; search never alters it. Existing snapshots work immediately with the matching backend/frontend. Older per-pilot hull-name arrays can match via imported SDE names when structured hull rows are absent. Pilotless structure/deployable losses are searched through recorded victim side and owner in the timeline; objects absent from retained evidence cannot be found.

Date/all/selected deletion previews and confirmation apply the same search fields and current permissions, across all pages, along with the frozen generation cutoff. A one-result search cannot silently review deletion of every unrelated report in scope. Browser verification only reviewed/cancelled deletion; disposable API fixtures test actual deletion.

Implementation: `GET /battle-reports/reports` accepts `side`, `match`, `pilot_name`, `combat_corporation`, `alliance_name`, `class_key`, `type_id`, `combatants`, `system_name` in addition to its existing scope/date/pagination fields. `GET /battle-reports/report-search-options?class_key=...` supplies class-specific published SDE types and ranges. Delete inputs accept the same search fields. Search uses parameterized correlated JSON/JSONB EXISTS/count expressions against saved payloads; no new search table, backfill, ESI scope or additional migration is required. Existing private-report/management access remains unchanged.

Verification: 52 search/management/report tests passed; one existing Linux Rust-shadow executable test is deselected on Windows. Covered same-side/same-combatant AND/OR behavior, all size boundaries through 1,001+, repeated-pilot deduplication, pilotless objects, legacy snapshots, literal wildcards, cross-page matches, validation, private scope, exact deletion parity and PostgreSQL query compilation. Runtime API tests use isolated SQLite; PostgreSQL expressions are compile-checked, not run against production. TypeScript and Vite build passed. Actual synthetic browser located a 46-versus-312 capital battle among 30 saved reports, exercised dependent structure choices and AND/OR/side switching, and reviewed/cancelled a one-report deletion. No production reports or game actions were changed.
