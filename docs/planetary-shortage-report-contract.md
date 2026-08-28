# Planetary shortage report contract

EQM's PI shortage evaluator is a pure, deterministic calculation over a Planetary Industry payload. The frontend, future API implementations, and the planned Rust comparison harness should emit the same `eqm.planetary-shortage-report.v1` document for the same payload, target, and generated timestamp.

## Calculation rules

- Treat every configured factory as planned full-cycle capacity, including factories that are idle, starved, or have never started.
- `configured_supply_per_day` is the sum of each producing factory's schematic output per cycle multiplied by `86400 / cycle_time`. Extractor supply uses its projected daily output.
- `configured_demand_per_day` is the equivalent daily input consumption of every configured consuming factory.
- `coverage = configured_supply_per_day / configured_demand_per_day`.
- `net_shortfall_per_day = max(0, demand - supply)`.
- `inventory_days_at_demand = projected_inventory / configured_demand_per_day`.
- `runway_days_at_net_shortfall = projected_inventory / net_shortfall_per_day`; it is `null` when configured throughput is balanced.
- `additional_processors_to_balance` is the ceiling of the net shortfall divided by one configured producer's daily output. It is `null` when the commodity has no factory schematic, such as an extractor-only raw material.
- `base_components` recursively expands the row's net shortfall through the complete SDE schematic catalog to raw P0 resources. Each entry includes the additional raw units per day and every eligible planet type.
- Targeted reports recursively include the selected configured product's recipe inputs and their factory-produced dependencies. Network reports include every commodity with configured demand.

## Severity thresholds

- `critical`: coverage below 50%.
- `short`: coverage from 50% through below 75%.
- `watch`: coverage from 75% through below 100%.
- `covered`: coverage at or above 100%.

## Cross-language fixtures

The canonical comparison pair lives in:

- `frontend/tests/fixtures/planetary-shortage-input.v1.json`
- `frontend/tests/fixtures/planetary-shortage-report.v1.json`

The TypeScript test consumes this pair today. A Rust implementation should deserialize the same input, accept target type `2870` and generated timestamp `2026-08-28T12:30:00Z`, serialize its report, and compare it structurally with the expected JSON. JSON object key order is not part of the contract; array order is deterministic by severity, coverage, commodity name, then type ID.

## Known limits

Projected inventory is network-wide and may be stranded on another character or planet. ESI does not reveal manual transfers or unsubmitted edits until it publishes a new checkpoint. Processor counts are throughput equivalents, not a CPU or powergrid layout solver. Planet-type availability comes from the EVE University resource distribution matrix and does not claim that every eligible planet has equal resource density.
