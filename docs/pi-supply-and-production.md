# PI supply and Production Calculator

Release classification: regular release (not a prerelease). Package and application version: `1.0.0`.

Planned release title: **v1.0.0 — A Bigger Slice of the PI Update!**
Recorded September 11, 2026 for release later today at the user's request. This note does not publish a release or change an existing tag.

## User workflow

In Planetary Industry → Colonies & supply, the supply report displays shortages followed by bright-green surpluses. Surplus is configured daily supply minus configured daily demand, floored at zero. Finished output with no configured consumer is included. Exactly balanced ingredients are covered, but are not surpluses. Configured output still assumes upstream ingredients remain available.

Select a corporate station/Upwell hangar above the report to monitor its cached stock. The selection is remembered per EQM user in this browser. Colony stock and hangar stock are shown separately; both count toward runway, but hangar stock does not change daily throughput or eliminate a production deficit. Expand Monitored PI inventory to see all recognized PI ingredients/products at that location, even without configured consumers.

Corporate assets use EQM's existing owner visibility rules and Assets section permission. Divisions are identified by corporation, resolved station/structure, and CorpSAG1–7. Nested containers resolve through visible asset ancestry, with cycle and cross-owner guards. Unresolved locations and ancestry are excluded. Empty divisions are offered at known corporate hangar locations; locations with no synced corporate hangar records cannot be discovered from an empty asset list. Division names fall back to CorpSAG flags until metadata is synced.

PI sync only refreshes colonies. Use the existing corporation asset sync to refresh hangar contents; the PI page rereads cached records every 30 seconds. Oldest item sync time and missing timestamps are displayed. Snapshots can lag in-game transfers, so stock may still require hauling or a newer ESI checkpoint.

## Production Calculator

Choose a PI recipe from the SDE catalog, enter ingredient quantities and a factory count, or copy the selected hangar stock. The calculation uses direct recipe ingredients, not a recursive chain. Missing quantities mean zero. Inputs must be whole nonnegative units; factories must be 1–10,000.

- Complete batches = minimum of floor(stock / per-cycle ingredient requirement).
- Total output = batches × recipe output per cycle.
- All-factory runtime = floor(batches / factories) × cycle time.
- Final production completion = ceil(batches / factories) × cycle time.
- A partial last round identifies how many factories can run one additional cycle.
- Leftovers subtract only complete batches; every tied limiting ingredient is marked.

The calculator assumes ingredients can be distributed between factories. It does not simulate storage/routing limits, travel, ongoing extraction, upstream production, or partially completed jobs. Recipes and cycle quantities come from the server's SDE catalog, not client-submitted recipe definitions.

## Engine and deployment

The existing Rust `pi-shortage` evaluator now emits `eqm.planetary-shortage-report.v2`, with `hangar_inventory`, `total_inventory`, and `net_surplus_per_day` on every row and finished products included in scope. The browser's deterministic reference calculation retains report availability if the native engine is missing, with a visible notice. JSON exports identify the calculation engine and selected inventory source. The former v1 fixture is retained as historical evidence.

The new `pi-production` eqm-core command performs complete-batch/runtime/leftover arithmetic. Backend routes enforce PI permissions, read the authorized asset snapshot and SDE recipe, and invoke the Rust binary with bounded time. Calculator engine failure is explicit (503), never a fabricated estimate. Existing `EQM_CORE_BINARY` and `EQM_CORE_TIMEOUT_SECONDS` settings apply. Deploy/rebuild backend including eqm-core and frontend together. No database migration is needed for these additions.

## Verification and production follow-up

Local verification covers TypeScript/Rust report parity, unchanged prior shortage quantities, net-zero versus positive surplus, final output without consumers, stock extending runway without changing throughput, nested containers/owner separation, missing ancestry/cycles, denied permissions, invalid calculator quantities, partial final rounds, zero production, missing Rust worker, report export, and desktop/mobile controls.

Production checks remain pending:

- Compare a real station and Upwell division against in-game PI stock, including nested containers and an empty division.
- Check a user without corporate asset visibility sees no corporate inventory; a previously saved inaccessible selection must show unavailable.
- Sync corporation assets and confirm monitoring updates; PI sync alone must not claim a new hangar snapshot.
- Confirm green excess supply and final products; a supply deficit must remain a deficit after selecting a large stockpile.
- Try a known recipe with unequal ingredients and multiple factories; verify the last partial round and leftovers.
- Confirm the deployed Rust binary supports both updated pi-shortage and new pi-production commands.
