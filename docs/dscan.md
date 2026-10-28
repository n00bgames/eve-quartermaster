# Directional scans

**Intel → D-Scan** (`#d-scan`) analyzes copied scan results. Select all results in EVE, copy, then paste into EQM. Accepted English clipboard formats are tab-separated **Name / Type / Distance** or **Type ID / Name / Type / Distance**, with an optional header. Rows separated by two or more spaces are also accepted when unambiguous. A scan supports up to **5,000 object rows** and 500,000 input characters. Identical rows count as separate objects. Malformed rows are counted and listed by line/reason without publishing their raw rejected text.

Local Scan hands recognizable directional-scan input to D-Scan as an unpublished draft. Plain pilot names and fleet rows remain in Local Scan. Ambiguous three-column rows ending in `-` should be entered directly in D-Scan. Changing modules does not generate a public report automatically.

## Classification and totals

EQM resolves type IDs against the imported SDE, or exact case-insensitive type names when the clipboard has no IDs. A valid imported ID takes precedence over a disagreeing pasted name. An unknown supplied ID is never guessed from its name. Unknown or partially imported types remain explicit unresolved objects; missing data does not become a fabricated ship class or zero-mass total.

Results show frequency-ranked ship types with actual item icons, ship classes, deployables with icons, structures, drones/fighters, other objects and unresolved types. Summary counts distinguish observed objects, observed ships, manual ships and their combined ship count. The raw-object detail view renders the first 250 rows; the report snapshot and all totals retain every parsed object. Type lists expand to their full height and longer lists have local search. D-Scan and Local Scan workspaces use the page scrollbar; opened object tables also grow with their rows. Wide tables retain horizontal scrolling. Public reports use the same expanded layout.

**Huginn, Lachesis, Rook and Curse** can be added manually. These counts are labeled estimates, not d-scan detections, and are added to observed totals/classes/mass. Each manual count must be an integer from 0 to 1,000. Imported SDE entries are required for manual types.

Ship mass is the sum of **SDE base hull mass**, including manual ships, displayed in tonnes. Fitted modules, cargo, propulsion changes and other mass modifiers are not inferred. Missing mass or unresolved objects explicitly make the result a known/partial mass sum. Refresh/import the SDE to fill missing type metadata.

## Systems, local scans and red markings

Choose an optional system using search; reports preserve its name/ID, creator account, exact creation timestamp, relative age and application version. Set Destination reuses Navigation's selected-character interface and existing waypoint scope, with append by default. Only the viewer's own authorized character tokens are offered; public report access alone cannot send a destination.

An optional linked local list uses Local Scan's public ESI enrichment and shared, persistent corporation/alliance highlight preferences. Organization logos, group totals, pilot drilldowns, filters and red markings appear beneath the ship summary. The PDF includes organization totals and the complete linked pilot list. Ship names do **not** identify pilots or corporations, so EQM never assigns ownership or red ship totals from a name match. No private assets or character data are fetched by d-scan analysis.

Use the analysis controls to change manual recons or update the linked local list, then **Save a new report**. The new snapshot gets its own public URL, timestamp and selected retention; previous shared reports remain immutable. Opening a saved report restores its copied objects, recons, linked pilot names, system and retention into the editor. Generation and updates explicitly disclose that the resulting scan/local information will be public.

## Public lifecycle and access

D-Scan has its own `dscan` section permission. Defaults match Local Scan, including Intel Analyst. Account overrides, combined roles, global section settings and Quartermaster mutation restrictions continue to apply. Highlight preferences are shared between the two modules, even when an account has only one scan section enabled. D-Scan adds no private ESI scope.

Public URLs use random 256-bit tokens at `#d-scan/{token}`. JSON/PDF reads require no login, request no caching/indexing and enforce expiry immediately. Retention choices are **30m, 1h, 2h, 12h, 24h, 3days, 7days, 30days, permanent**, default 24h. The shared once-per-minute cleanup physically deletes expired snapshots. PDF access is rechecked after rendering to handle expiry/deletion during export.

Users manage their own reports; directors also manage reports attributed to their linked corporations; admins/hosts manage all. Corporation attribution is limited to the creator's own linked-character corporations. Individual, selected, UTC generation-date-range (start inclusive/end exclusive), and all-in-scope deletion are available with a review step. Every server query/deletion is constrained by actor scope **and report kind**, so Local Scan management cannot delete d-scans or vice versa.

PDFs use small EQM/type/organization logos, complete type/class totals, observed/manual columns, base mass, linked-local organization totals/pilots and **Generated by EVE Quartermaster v{generation version} by {generating account}**. Icon retrieval uses fixed EVE Image Server URLs with bounded time/bytes/concurrency; missing images leave complete text/counts. PDFs summarize object types rather than printing thousands of individual object-name rows.

## Rollout

Deploy backend/frontend together and apply **0092_dscan_reports** after 0091. It adds a `report_kind` discriminator to the existing public-snapshot table, marking every existing row as Local Scan. Upgrade preserves local reports. Downgrade removes d-scan snapshots before removing the discriminator, preserving local records. No version bump, release publication or production deployment is implied by implementation.

Signed-in linked local lists immediately apply the viewer’s current organization highlights. Existing public links and PDFs retain their generation-time markings; regenerate to share preference changes.

The report header leads with the saved system (or Not specified), **Total ships**, and the observed/manual split. The count is the whole report's observed ships plus manual additions; it excludes known deployables and other non-ship objects and is unaffected by list filters. Linked local headers also show the system and total pasted pilots, with compact portrait links in expanded corporation lists. The PDF repeats the system and total ship count on every page; observed/manual details remain directly below the first-page banner.
