# Local static universe data

Patch base: `8e7ca71ce91315474b30899e621861d79a3ae80e` (main, checked 2026-11-20).
The ESI compatibility date remains `2026-07-22`. The existing YAML ZIP download,
validation, maintenance queue, and importer remain the supported update path.

## Retiring call inventory and replacement

| Consumer | Former static ESI routes | Local replacement |
| --- | --- | --- |
| PI Scout | systems, planets | EveSystem and EveSystemObject type/radius/name |
| PI colony naming | planets | EveSystemObject; missing rows retain `Planet <id>` |
| Fittings | types | Imported EveType; unknown IDs retain `Type <id>` |
| Sync type/skill metadata | types, groups, categories | Existing imported type/group/category relationships; missing IDs remain placeholders |
| Manual type/system/station import | types, systems, stations | Local rows; missing rows return 404 with reimport guidance; location creation retained |
| Intel metadata fallback | types, systems, constellations, regions | Local type and map relationships; missing rows raise the existing recoverable source error |
| Distance refresh | systems manifest, stargates, stations, planets, moons, asteroid_belts | Existing local object/gate/station catalog; SDE reimport updates static data |
| Gatecheck NPC station labels | stations | EveStation; missing rows retain generic location/structure labels |

Live `/universe/ids`, `/universe/names`, `/universe/structures`,
`/universe/system_jumps`, and `/universe/system_kills` are preserved. Other
character, corporation, killmail, market and UI routes are unchanged. Structure
position fetching, token ownership/scope checks, expiry and access-loss eviction
remain unchanged. Refreshing distances still resolves accessible structures.

## SDE fields and fixtures

Verified against CCP's official SDE build **3720952**, released
**2026-11-19T11:07:08Z**, downloaded from:
https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-3720952-jsonl.zip

The fixture `backend/tests/fixtures/universe-sde-3720952.json` contains original
first records from `_sde`, `mapStars`, `mapPlanets`, `mapMoons`, and
`mapAsteroidBelts`. Tests convert the numeric `_key` into YAML map keys and feed
the existing ZIP importer; the production importer still uses YAML, not JSONL.
The equivalence of those formats is documented by CCP:
https://developers.eveonline.com/docs/services/static-data/

`mapPlanets` supplies `typeID` and `radius` (metres), plus `position`. Migration
0111 adds nullable type/radius columns without fabricating a backfill. Reimport
fills them. Scout uses diameter = radius * 2 / 1000 km and marks incomplete
systems with score -1 and reimport guidance. Unsupported planet types are skipped.
Names honor localized exceptions and orbit names, using CCP's naming rules:
https://developers.eveonline.com/docs/guides/staticdata/

**Star position limitation:** `mapStars` supplies ID, system, type and radius,
but no position. New star rows therefore have null coordinates and cannot be
used for a distance estimate. Previously stored star coordinates and their
provenance survive reimport. The patch does not assume the star is at zero or
confuse galaxy system coordinates with local positions. This differs from the
old ESI refresh, which unconditionally manufactured a zero-position star.

## Applying and operating the patch (not performed here)

1. Start with the exact base above. Run `git apply --check eve-quartermaster-v2.4.1-prepared.patch`,
   then `git apply eve-quartermaster-v2.4.1-prepared.patch`.
2. Back up the database and let any active SDE import finish. Stop API/workers
   while updating schema; deploy matching API/worker/frontend builds using the
   normal operator procedure. No release, push, or deployment is part of this patch.
3. From the configured backend environment run `alembic upgrade head` before
   starting updated API/workers. This adds revision `0111_local_universe` after
   `0110_structure_timers`.
4. In Settings → SDE Maintenance, download a current CCP YAML ZIP and choose
   **Use downloaded archive for import**, then **Queue SDE import**, or enable
   automatic import on download. Use the full import, not agents-only. Existing
   mounted ZIP paths also work. Wait for completion; a download alone does not
   populate the new fields. Existing imports commit in batches; rerun after a
   failure rather than assuming an atomic rollback.
5. Confirm planet/star totals, scout a known system, sync a colony, import a
   known type/station, and refresh distances using a character authorized for
   structures. Static corrections require another SDE import; Refresh objects
   only rereads stored static data and refreshes live structures.

Rollback code only with the matching schema policy: stop services, use
`alembic downgrade 0110_structure_timers` if removing the new columns is desired,
and restore the previous application build. Downgrade discards imported
planet type/radius metadata. Old code will again depend on retired ESI routes.

## Validation

Run from `backend` with repository requirements plus pytest installed:

```sh
python -m pytest tests/test_local_universe.py tests/test_system_distances.py tests/test_sde_import_totals.py tests/test_sde_maintenance.py tests/test_pi_planner_api.py tests/test_planetary_industry_projection.py tests/test_fitting_eft_import.py tests/test_fitting_send_to_eve.py tests/test_intel_reports.py tests/test_intel_report_builder.py tests/test_intel_identity_extensions.py tests/test_esi_transport.py tests/test_esi_auth_scopes.py tests/test_killboard_entities.py -q
```

Final broader run: **144 passed, 7 subtests passed** (27.78 seconds). The final
focused run after the live-route and star/totals fixes passed **35 tests**:

```sh
python -m pytest tests/test_local_universe.py tests/test_system_distances.py tests/test_esi_transport.py tests/test_sde_import_totals.py -q
```

Frontend checks from `frontend`: `npx tsc --noEmit` passed;
`npm run test:navigation` passed **10 tests**. Dependencies were installed into
an external local venv and frontend node_modules; no dependency manifests were
changed. The workspace proxy also required local `socksio` installation.

Coverage includes official field fixtures through ZIP/reimport, missing metadata,
manual imports, PI radius conversion and naming, Intel fallback, Gatecheck,
migration upgrade/downgrade with retained rows, no retiring static GET calls in
runtime source, live universe routes and compatibility header, and private
structure scope/expiry/access-loss behavior. Tests use SQLite and mocked ESI.
No live PostgreSQL migration, full production SDE import, authenticated ESI
integration, browser check, or deployment was performed.

Packaging verification: `git diff --check` and `git apply --check` against a
clean detached checkout of the exact base passed. The final patch was also
applied there and checked with `git diff --check`.

## Versioned preparation follow-up

The superseding package prepares 2.4.1, Android source code 33, release notes and
a queue-worker schema guard. The guard reads this build's Alembic heads, waits
for backend migration completion, and exits without starting RQ on timeout or
mismatch. Backend remains the sole automatic migration runner. Existing custom
Compose overrides must retain the new worker command. Full SDE reimport remains
an explicit operator action after application readiness.

Additional verification: `python -m unittest discover -s scripts/tests -v` ran
11 tests successfully with one Windows-only skip. From backend,
`python -m pytest tests/test_worker_schema.py tests/test_app_update.py tests/test_local_universe.py tests/test_sde_maintenance.py tests/test_system_distances.py tests/test_esi_transport.py tests/test_intel_report_builder.py -q`
passed 86 tests. `npm run build` passed for version 2.4.1 (existing large-chunk
warning). Docker/PostgreSQL executables were unavailable, so no disposable
container-stack upgrade or production database migration was exercised. No APK
was built. No commit, push, tag, PR, GitHub release, or deployment was performed.


## Combined Windows checkout verification — November 20, 2026

The supplied preparation patch was reviewed and merged with the existing Mining Report exports and v2.4.1 source bump. The combined checkout passed 151 backend tests plus 7 subtests, 15 frontend tests, TypeScript and the production frontend build. The 11 host-updater cases produced 4 passes and 7 POSIX-only skips on Windows. `docker compose config --quiet` passed; Docker Desktop's engine was stopped, so full-stack/PostgreSQL upgrade verification remains unperformed.

Actual Navigation and PI Scout components were exercised with a synthetic API adapter: one-AU coordinate calculation, disabled unknown star positions, refresh timestamp wording, local Scout loading state, radius-to-diameter presentation, incomplete-data guidance and 390px page containment. Four check groups passed with no page errors. Backend import, authorization and migration behavior were tested separately with mocked ESI/disposable SQLite. [Desktop capture](../static/ss/v2.4.1/local-universe-desktop.png) · [Mobile capture](../static/ss/v2.4.1/local-universe-mobile.png) · [Additive provenance receipt](../static/ss/v2.4.1/capture-receipt.json). No production migration, full SDE reimport, live ESI authentication or deployment was performed.
