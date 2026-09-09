# PI operation planner

The **Operation planner** tab in Planetary Industry compares proposed EVE Online production operations using authorized EQM characters, imported CCP schematics and public ESI market orders. The existing colony, supply, simulation and history views remain available under **Colonies & supply**.

## Using it

1. Synchronize the relevant characters' PI and skills. Existing colonies occupy their slots by default. Explicitly allow replacement of a colony to free its slot; proposals never change anything in EVE.
2. Choose profit, maximum output, a weekly quota, a combined set of product quotas, or a comparison of products. Choose a sourcing tier or let the search compare extraction and purchasing. Individual intermediate commodities can also be purchased.
3. Select eligible planets for each pilot. Add hypothetical planets, reuse existing ones, or scout real systems. Enter customs rates and average extraction yields for the chosen program. Scouting establishes resource availability by planet type, not resource density.
4. Set visits, program duration, hauling capacity, link length and costs. Unknown skills are not assumed to be level V. Planned skill overrides describe a future operation and are disclosed in the result.
5. Calculate. Review the weekly ledger, setup capital, shopping list, unfilled sales, per-colony allocations and capacity meters. Export the build/shopping CSV, an input scenario or the complete calculation snapshot.

Saved scenarios are private to the EQM user and use optimistic revisions to prevent overwriting another session's edits. Recent runs let the user reopen results or reconnect after navigating away. Only the newest 20 runs and up to 100 scenarios are retained per user. Imported JSON is validated server-side. Snapshot import restores the scenario; replay of an owned run uses its frozen prices and data.

The recipe workbench consumes a one-time inventory only once across shared ingredients, rounds complete production batches, shows surplus and shopping requirements, and draws the dependency graph. Its “buildable” products are alternatives using the same inventory, not additive commitments.

## Calculation and Rust boundary

`pi_planner.py` controls the bounded search, recipe expansion, economic ledger, market fills and independent result validation. `pi_allocation.rs` implements the repeatedly invoked colony allocator and facility/link CPU, power, extraction and storage arithmetic. One Rust process holds the immutable input for an entire search and receives small candidate messages; the backend does not launch a process per candidate.

The default `EQM_PI_PLANNER_ENGINE=rust` is separate from the existing colony simulator's `EQM_PI_ENGINE`. Supported values are:

| Mode | Behavior |
| --- | --- |
| `rust` | Native allocator; explicit Python fallback if startup, protocol or execution fails. |
| `shadow` | Calculate in both engines, compare structure and numeric tolerances, retain Python results. A mismatch is disclosed as fallback. |
| `python` | Reference allocator, useful for diagnosis and parity work. |

`EQM_CORE_BINARY` identifies the existing `eqm-core` executable. `EQM_CORE_TIMEOUT_SECONDS` bounds worker startup and individual responses. The Docker backend already builds and packages that binary; this change adds its worker command without adding runtime dependencies. The worker has no ESI, credentials or database access. Worker exit, malformed output and broken pipes trigger fallback; workers are terminated and reaped at the end of a search.

Contracts:

- `eqm.pi-planning-input.v1`: user-owned scenario settings.
- `eqm.pi-planning-result.v1`: validated candidates, ledger, search coverage, engine and provenance.
- `eqm.pi-planning-snapshot.v1`: scenario, frozen context, market and result.
- `eqm.pi-allocation-state.v1`: immutable Rust worker state. First newline-delimited input; reply is `{"ready":true}`. Subsequent lines contain expanded `nodes`, `raw` requirements and `time_limit_ms`; responses contain `colonies` and `notes`. EOF closes the worker. Input lines are limited to 8 MB.

The calculation search has a 1–30 second budget and returns best-found alternatives. It samples small quantities, geometric scales, a capacity boundary, user demand and visible bid-depth breakpoints. It retains the best alternative per product set/sourcing cut, then ranks at most 30. A product/sourcing preflight and explicit coverage counts identify searches that ran out of time. Profit mode includes the valid choice to build nothing. Individual candidate evaluation is deterministic for frozen inputs. A time-limited replay can examine a different number of candidates on a different machine or engine; replay does not promise an identical ranking after a timeout.

## Prices and accounting

- Public ESI regional order pages are fetched through EQM's `EsiClient`, filtered to the selected Jita, Amarr, Hek, Dodixie or Rens NPC station. All reported pages are read, with a 100-page ceiling. Changing page counts, duplicate orders and empty intermediate pages invalidate the book.
- Snapshots record station, region, fetch time and cache expiry. Repeated requests reuse unexpired books. Four concurrent fetches and a 120-second overall deadline bound market work.
- Immediate output revenue walks finite bids and honors minimum volumes. Unsold units earn zero revenue. Input purchases walk asks; insufficient depth makes the candidate infeasible. No price tail is extrapolated. Remote ranged bids are conservatively excluded.
- Patient sales use the lowest visible station ask as an estimate, disclose that no fill is established, and include the entered broker fee. Fill timing and relisting are not simulated.
- Customs apply to each proposed import/export leg, including intermediate goods moved between colonies. High-security NPC customs use the pilot's active Customs Code Expertise; POCO owner rates are separate user inputs.
- The ledger separates input costs, customs, sales tax, broker fees, freight and overhead. It reports operating net, amortized setup net, first-week cash, positive-margin payback, hauling trips and ISK per visit/active hour.
- Construction uses CCP facility base prices plus command-center upgrade charges and user-entered additional setup costs. These are planning estimates, not executable market quotes for command centers. No purchase is made by EQM.

## Boundaries of a proposal

Existing colonies remain outside the incremental profit ledger unless replaced. Observed stock is offered to the one-time recipe calculator, not treated as free recurring input. Configured current output is not a guarantee that factories remain supplied.

Each proposed colony produces one processed commodity. P1 extraction can share its colony with a single ECU, limited to ten heads. P4 production is restricted to Barren/Temperate planets. Pilots have distinct skill/slot limits and cannot be assigned the same actual planet twice. The greedy allocator is a constrained family of layouts, not a proof of global optimality. Combined-product mode plans the entered quotas together; it does not automatically optimize arbitrary product proportions.

Storage reserves a full visit interval's external inputs and outputs plus a four-hour raw buffer for extraction. Link estimates include CPU/power upgrades but use the entered length and average transport assumptions. Factory throughput is steady-state; startup material/ramp-up and exact per-route timing are not simulated. Maintenance settings describe the whole proposed operation, not separate schedules per pilot.

Extractor estimates are average units per head per hour for the selected program. Existing program observations reuse EQM's CCP-documented decay/noise projection. Changing program duration requires checking the yield again. Head interference, depletion, planetary scan density, POCO ownership and transfer cooldowns cannot be inferred from these ESI observations.

## Native templates

The workbench generates original layouts using the public EVE clipboard field schema, inspects imported JSON, validates pin/planet/product compatibility and route connectivity, and previews links/pins. It exports the last validated preview; unvalidated text edits are not silently copied.

Templates are **starting layouts requiring EVE preview**, not certified one-click builds. Command-center placement/upgrading is manual; extractor heads and routes need in-game review. Factory storage is divided between buffers and may require expedited transfers and redistribution. Aggregate storage feasibility does not prove every buffer or link can handle a particular cycle. Exact pin placement, overlap, burst link load, transfer timing and live-client import have not been validated against an actual colony. No community templates or SPI implementation code are bundled.

## API, persistence and rollout

Routes are under `/api/planetary-industry/planner`: context; scenario validation/CRUD; recipe calculation; job creation/list/poll/cancel/snapshot/replay; regions/systems/scouting; template generation/inspection. Existing `planetary_industry` permission and character visibility checks apply. Saved runs/scenarios recheck visibility when read, even if access was revoked after creation.

Alembic revision `0079_pi_planning` creates only `pi_planning_scenarios` and `pi_planning_jobs`. It does not rewrite observed colonies or existing user settings. The normal backend startup applies migrations; operators using another startup method must run `alembic upgrade head` before enabling the UI. Deploy backend and frontend together. No deployment or live database migration was performed during implementation.

Jobs persist progress, snapshots and results but are executed by the backend worker process. A process restart interrupts active work. Jobs without a heartbeat for five minutes are marked failed and can be rerun. Admission limits are two active jobs per user and eight observed active jobs globally; the global admission check is advisory across simultaneous different-user transactions. This is not a distributed job queue.

## Verification and reproduction

Production verification is tracked in the [PI planner regression checklist](pi-planner-regression.md). Local passes do not establish live-server or EVE-client template compatibility.

```sh
cargo build --manifest-path rust/eqm-core/Cargo.toml --locked --release
cargo test --manifest-path rust/eqm-core/Cargo.toml --locked
PYTHONPATH=backend EQM_CORE_BINARY="$PWD/rust/eqm-core/target/release/eqm-core" \
  python -m pytest backend/tests/test_pi_planner.py backend/tests/test_pi_planner_api.py \
  backend/tests/test_pi_planning_context.py backend/tests/test_pi_allocation_engine.py -q
cd frontend
node --test --experimental-strip-types tests/piPlannerState.test.ts tests/planetaryExport.test.ts tests/planetaryShortageReport.test.ts
node node_modules/typescript/lib/tsc.js --noEmit
node node_modules/vite/bin/vite.js build --configLoader native
```

Use `eqm-core.exe` on Windows and set environment variables with PowerShell. Native parity tests require the compiled binary and assert that Rust actually executed. They cover all 68 recipes at two scales, all 15 extracted P1 products at four scales, combined products, six skill levels, replacement, mixed customs rates, worker failure and independently calculated Water CPU/power. API tests cover owner isolation, revoked visibility, revision conflicts, cancellation, replay and migration round trips. A database-backed context test exercises the real SDE/colony/skill serializers.

Browser checks use a disposable SQLite API with synthetic prices and a dedicated Vite test entry point; no live login is used. In separate terminals, start `python backend/tests/pi_planner_preview.py` and `node node_modules/vite/bin/vite.js --config tests/pi-planner/vite.config.mjs --configLoader native` (the latter from `frontend`). Run `node tests/piPlanner.browser.test.mjs` from `frontend` with a locally installed Playwright package. `PLAYWRIGHT_MODULE`, `BROWSER_EXECUTABLE` and `PI_SCREENSHOT_DIR` can select existing runtime paths. A separate read-only live ESI check successfully retrieved Jita Water orders on 2026-09-09; it placed no orders.

## Data provenance

The runtime schematic catalog comes from EQM's imported CCP SDE. The bundled pin fallback and recipe test fixture were extracted from CCP SDE build **3478781**, released **2026-08-25 11:07:20 UTC**, inspected locally on 2026-09-09. Imported Dogma overrides fallback attributes. The source ledger records [Solving PI](https://github.com/LackingTallent/SolvingPI) as research only, the [CCP extraction guide](https://developers.eveonline.com/docs/guides/pi/) as calculation documentation, and the [EVE template thread](https://forums.eveonline.com/t/planetary-industry-templates/470630) as public clipboard-format evidence. See [the source ledger](../3RD%20PARTY%20SOURCES.MD) for attribution and terms.
