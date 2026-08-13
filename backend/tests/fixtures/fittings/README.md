# Fitting reference fixtures

These fixtures compare EQM fitting calculations with explicitly documented reference values. They are intentionally separate from focused unit tests so a result cannot become "correct" merely because EQM produced it once.

Every JSON fixture must include:

- `schema_version`: currently `1`.
- `source.kind`: for example `pyfa`, `eve_client`, `published_formula`, or `existing_eqm_regression`.
- `source.externally_verified`: `true` only when the values were independently checked outside EQM.
- Ship, character skill, module, charge, implant, and heat inputs needed to reproduce the reference configuration.
- One or more expected metric paths with an explicit absolute or relative tolerance.

List selectors are supported in metric paths. For example, `cargo_bays[key=Cargo].capacity` selects the Cargo row before reading its capacity.

The initial Fenrir fixture proves the fixture loader and retains the already-established formula checks. It is marked as not externally verified and therefore does not, by itself, justify removing the Fittings preview warning. New release-gate fixtures should normally use Pyfa or EVE-client values and set `externally_verified` to `true`.

Useful reference values include CPU, powergrid, calibration, DPS, volley, layer HP, resistances, EHP, active repair, capacitor stability or depletion time, maximum velocity, align time, warp speed, signature radius, drone bandwidth, and cargo capacity. Record the Pyfa version or EVE build date and the exact skill/implant/heat state.
