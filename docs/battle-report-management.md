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
