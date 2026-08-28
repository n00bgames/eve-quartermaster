# EQM Core

`eqm-core` is EVE Quartermaster's experimental deterministic Rust calculation core. It is a parity harness first: production continues using the existing Python and TypeScript implementations until Rust produces the same versioned JSON for shared golden fixtures.

## Current scope

- `pi-shortage`: configured PI throughput, projected inventory, target-chain traversal, net deficits, processor equivalents, raw P0 expansion, and eligible planet types.
- Cross-language contract: `eqm.planetary-shortage-report.v1`.
- Shared fixtures: `frontend/tests/fixtures/planetary-shortage-*.v1.json`.

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

## Migration rule

Rust does not access PostgreSQL, ESI, authentication, or permissions. Application layers assemble a bounded JSON input, call the deterministic core, and retain their existing authorization and persistence responsibilities.

The next planned module is colony simulation. It should receive checkpoint time, projection time, pins, routes, schematics, capacities, and type volumes as JSON and match Python's `simulate_colony` output against shared fixtures before any production cutover.
