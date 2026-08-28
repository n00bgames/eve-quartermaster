# EQM Core

`eqm-core` is EVE Quartermaster's experimental deterministic Rust calculation core. It is a parity harness first: production continues using the existing Python and TypeScript implementations until Rust produces the same versioned JSON for shared golden fixtures.

## Current scope

- `pi-shortage`: configured PI throughput, projected inventory, target-chain traversal, net deficits, processor equivalents, raw P0 expansion, and eligible planet types.
- `colony-simulation`: deterministic event scheduling, routed factory inputs and outputs, storage capacity, extractor decay/noise, blocked output, and truncation safeguards.
- `fitting-math`: dogma multiplier normalization, stacking penalties, capacitor recharge, stability, and finite depletion simulation.
- Cross-language contracts: `eqm.planetary-shortage-report.v1`, `eqm.planetary-colony-simulation-input.v1`, and `eqm.fitting-math-input.v1`.
- Shared fixtures: `frontend/tests/fixtures/planetary-shortage-*.v1.json` and `backend/tests/fixtures/planetary-colony-simulation-*.v1.json`.

## Docker test

From the repository root:

```sh
docker compose --profile test run --rm eqm-core-tests
```

The test compares Rust output structurally with the same golden report used by the TypeScript test suite.

## CLI

```sh
cargo run -- pi-shortage \
  --input ../../frontend/tests/fixtures/planetary-shortage-input.v1.json \
  --target-type-id 2870 \
  --generated-at 2026-08-28T12:30:00.000Z
```

If `--generated-at` is omitted, the CLI uses the input payload's `as_of` value to remain deterministic.

```sh
cargo run -- colony-simulation \
  --input ../../backend/tests/fixtures/planetary-colony-simulation-input.v1.json
```

```sh
cargo run -- fitting-math \
  --input ../../backend/tests/fixtures/fitting-math-input.v1.json
```

## Migration rule

Rust does not access PostgreSQL, ESI, authentication, or permissions. Application layers assemble a bounded JSON input, call the deterministic core, and retain their existing authorization and persistence responsibilities.

The next fitting slice is resource-envelope validation: ship CPU, powergrid, calibration, slot capacity, skill reductions, and subsystem fitting modifiers.
