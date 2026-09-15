# PI supply and Production Calculator

Release classification: regular release (not a prerelease). Package and application version: `1.0.1`.

Planned release title: **v1.0 — The Bigger Slice of PI Release!**
Recorded September 11, 2026 for release later today at the user's request. This note does not publish a release or change an existing tag.

## User workflow

The Character selector defaults to **My Characters Only**. EQM directors and higher can choose **My Corp Pilots**, but corporation membership alone never grants this group access: one of the viewer's own linked characters must have an active token with `esi-characters.read_corporation_roles.v1`, nonempty corporate roles verified through ESI, and a matching current corporation affiliation. An unprivileged alt in another corporation does not expose that corporation's pilots. Verification results are cached for at most 60 seconds; revoked tokens, missing scope, and changed local affiliations invalidate access, and verification failures exclude unverified corporations. Admins and hosts additionally retain **All Characters**. Custom roles inherit their configured base role.

Server-side PI listings restrict character choices, colonies, and sync-token metadata to the permitted groups. The selected group or individual pilot filters displayed colony totals, supply calculations and exports. Directors cannot bypass their scope through an individual pilot's ID in the supply API. Other EQM sections retain their existing permissions.

In Planetary Industry → Colonies & supply, the supply report displays shortages followed by bright-green surpluses. Surplus is configured daily supply minus configured daily demand, floored at zero. Finished output with no configured consumer is included. Exactly balanced ingredients are covered, but are not surpluses. Configured output still assumes upstream ingredients remain available.

Select a corporate station/Upwell hangar above the report to monitor its cached stock. The selection is remembered per EQM user in this browser. Colony stock and hangar stock are shown separately; both count toward runway, but hangar stock does not change daily throughput or eliminate a production deficit. Expand Monitored PI inventory to see all recognized PI ingredients/products at that location, even without configured consumers.

Corporate assets use EQM's existing owner visibility rules and Assets section permission. Divisions are identified by corporation, resolved station/structure, and CorpSAG1–7. Nested containers resolve through visible asset ancestry, with cycle and cross-owner guards. Unresolved locations and ancestry are excluded. Empty divisions are offered at known corporate hangar locations; locations with no synced corporate hangar records cannot be discovered from an empty asset list. Division names fall back to CorpSAG flags until metadata is synced.

The **Sync this corporation’s assets** button beside the source selector uses an eligible token from the existing Corporations permissions workflow, refreshes the entire selected corporation (ESI has no location-only asset sync), then reloads the displayed hangar stock. It is disabled without an authorized asset token. Failed syncs are shown explicitly; ESI caching can delay in-game changes even after success. Calculator entries stay as entered until an import button is used again.

PI sync only refreshes colonies. Use the existing corporation asset sync to refresh hangar contents; the PI page rereads cached records every 30 seconds. Oldest item sync time and missing timestamps are displayed. Snapshots can lag in-game transfers, so stock may still require hauling or a newer ESI checkpoint.

## Production Calculator

Choose a PI recipe from the SDE catalog, enter ingredient quantities and a factory count, or copy the selected hangar stock. For a P4 product, the calculator defaults to P2 feedstock. Select Materials I feed to expand the recipe chain from P0, P1, P2, or P3 as appropriate, or choose Direct recipe ingredients for the original single-step calculation. Lower-tier inputs used directly remain listed even when feeding P2. Shared ingredients are deduplicated and allocated across the entire chain. Missing quantities mean zero. Inputs must be whole nonnegative units; factories must be 1–10,000.

Use selected hangar stock imports all listed ingredients. The small **I** button beside each quantity imports just that material and preserves other entries; its tooltip previews the quantity and hangar. Import buttons are disabled until a hangar is selected. Materials absent from the selected snapshot import as zero. Imports use cached corporation assets, so sync those assets first if stock has changed in-game.

For direct-input mode:

- Complete batches = minimum of floor(stock / per-cycle ingredient requirement).
- Total output = batches × recipe output per cycle.
- All-factory runtime = floor(batches / factories) × cycle time.
- Final production completion = ceil(batches / factories) × cycle time.
- A partial last round identifies how many factories can run one additional cycle.
- Leftovers subtract only complete batches; every tied limiting ingredient is marked.

Chain mode expands demand through whole upstream batches, aggregates shared ingredient demand before rounding that recipe, and searches for the maximum number of complete final-product batches supported by the feedstock. It produces only the intermediate batches needed for that final output; unused feedstock remains unprocessed. The stage table shows intermediate quantities made, consumed downstream, and left over. Ingredient limits identify shortages preventing the next final-product batch.

Each recipe has its own factory count. The primary finish estimate now simulates overlapping factory cycles: complete-cycle inputs are consumed at the start, outputs become available at completion, and ready downstream recipes start immediately. Factories are dedicated to each recipe, and delivery between stages is instantaneous. Shared inputs are consumed from one stockpile and simultaneous completions are delivered together before scheduling starts. Routing/storage constraints and live cycle alignment remain outside the model.

P0–P4 tier cards show work time with inputs available and summarize start/finish offsets. Separate tables for each produced tier list every product, work time, start, and finish. Work times overlap and must not be added together. The original sequential sum is retained only in a collapsed, explicitly labeled comparison. For the user's 212 Recursive Computing Module example with four factories on each of three P3 recipes and two P4 factories, each tier needs 4d 10h of work and the overall ideal finish is 4d 11h including the first P3 cycle; the sequential comparison is 8d 20h.

The Rust event loop is bounded at 20,000 grouped completion events. Larger stockpiles retain exact yield and tier work times but return no overlapping ETA, with an explicit UI explanation. Factory counts change timing, not yield. Existing intermediate inventory is not included in feed-tier mode; direct mode remains available for feeding those ingredients.

The calculator assumes ingredients can be distributed between factories. It does not simulate storage/routing limits, travel, ongoing replenishment beyond the entered stock, or partially completed jobs. Recipes and cycle quantities come from the server's SDE catalog, not client-submitted recipe definitions.

## Engine and deployment

The existing Rust `pi-shortage` evaluator now emits `eqm.planetary-shortage-report.v2`, with `hangar_inventory`, `total_inventory`, and `net_surplus_per_day` on every row and finished products included in scope. The browser's deterministic reference calculation retains report availability if the native engine is missing, with a visible notice. JSON exports identify the calculation engine and selected inventory source. The former v1 fixture is retained as historical evidence.

The `pi-production` eqm-core command performs direct complete-batch/runtime/leftover arithmetic. `pi-production-chain` expands the server-provided SDE recipe graph and allocates feedstock for multi-stage output. Backend routes enforce PI permissions, read the authorized asset snapshot and SDE recipe, and invoke the Rust binary with bounded time. Calculator engine failure is explicit (503), never a fabricated estimate. Existing `EQM_CORE_BINARY` and `EQM_CORE_TIMEOUT_SECONDS` settings apply. Deploy/rebuild backend including eqm-core and frontend together. No database migration is needed for these additions.

## Verification and production follow-up

Local verification covers TypeScript/Rust report parity, unchanged prior shortage quantities, net-zero versus positive surplus, final output without consumers, stock extending runway without changing throughput, nested containers/owner separation, missing ancestry/cycles, denied permissions, invalid calculator quantities, partial final rounds, zero production, missing Rust worker, report export, and desktop/mobile controls.

Production checks remain pending:

- Compare a real station and Upwell division against in-game PI stock, including nested containers and an empty division.
- Check a user without corporate asset visibility sees no corporate inventory; a previously saved inaccessible selection must show unavailable.
- Sync corporation assets and confirm monitoring updates; PI sync alone must not claim a new hangar snapshot.
- Confirm green excess supply and final products; a supply deficit must remain a deficit after selecting a large stockpile.
- Try a P4 recipe fed from P2, including shared P2 requirements and any direct P1 input; verify intermediate batches, final output, leftovers, and per-recipe runtimes. Also confirm direct-input mode still works.
- Confirm the deployed Rust binary supports pi-shortage, pi-production, and pi-production-chain commands.
