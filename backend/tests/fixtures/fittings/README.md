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

## All-V Pyfa fleet

`test_fitting_reference_fleet.py` imports the Rail Moa, Rapid Light Caracal, and Active Armor Vexor from `pyfa-all-v/fits.eft` into the simulator using a temporary SQLite catalog. The offline catalog pins the CCP SDE archive dated August 25, 2026 and records its SHA-256. It includes the fit types, charges, relevant All-V skills, and their Dogma attributes and effects. The expected values come from `evidence/pyfa-all-v-2026-08-11.json` (Pyfa 2.68.0). Each fit runs cold with the bay idle and then with the captured drone flight active. The Vexor's spare Hobgoblins remain in the bay. These cases use no implants, boosters, or fleet effects.

The tests exercise both the resources and stats engine paths. They assert that the requested engine ran, so fallback fails the case. The backend test image includes `eqm-core`. For a local run, point `EQM_CORE_BINARY` to a built `eqm-core` executable.

The assertions cover fitting resources, damage, volley, supported resistances, capacitor capacity and stability, movement, targeting, and bay capacity. The screenshots round some combined totals separately from their components, so volley has a one-point tolerance. Moa and Caracal powergrid use is checked within 0.5 MW to allow the small observed differences between the capture and the pinned SDE.

The following comparisons remain open. The Vexor's powergrid use reflects a changed repairer attribute in the SDE. Moa and Caracal shield EM resistances and Vexor armor resistances differ from the captures, as do the resulting Omni EHP figures. The capacitor readouts use different stability and depletion estimates. The capture's repair readouts are effective HP/s, while EQM shows raw HP/s. These values remain in the evidence for follow-up.
