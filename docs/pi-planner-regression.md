# PI planner production regression checklist

Recorded 2026-09-09 for the initial PI operation planner implementation. **Production verification is pending.** The user will verify on the production server. Keep these points for follow-up debugging; do not infer production success from the local checks.

## Local baseline

- Backend: 70 passed, one existing platform-specific test skipped on Windows.
- Rust: 41 passed, including existing core coverage. Native/Python allocation parity covers all 68 recipes at two scales, all 15 extracted P1 products at four scales, mixed operations and skill levels.
- Frontend: nine tests passed, TypeScript and production build passed. The build retains the existing large-chunk warning.
- Browser workflow passed twice consecutively with the Rust worker: save/update/delete scenario, calculation, CSV export, template preview/inspection, inventory recipe calculation, scouting, mobile layout and reopening a completed run after reload.
- Public ESI Jita Water order retrieval succeeded; the complete browser tests used synthetic prices and a disposable database.
- A browser harness defect caused intermittent failures with concurrent sessions sharing one SQLite connection. The harness now uses a disposable file database with separate connections. This was not a production authentication change.

## Deployment and existing PI behavior

- [ ] Backend and frontend are the same revision. Alembic reaches `0079_pi_planning`; the two new planning tables exist. Existing colony records and user settings remain intact.
- [ ] Open Planetary Industry through the normal authenticated app. Both **Colonies & supply** and **Operation planner** work, including switching back while a calculation is active.
- [ ] Existing colony summaries, supply/shortage views, simulation, analytics/history and PI exports still load and behave as before.
- [ ] Character synchronization still updates colonies, skills, inventory and extractor programs. Compare the planner's imported values with an actual known character.
- [ ] Verify mobile navigation, controls, tables and export downloads in the deployed app; no horizontal page overflow or console/API errors.

## Rust and real character context

- [ ] A completed run reports **Allocation engine: rust** under **Constraints, provenance & search limits**. `EQM_PI_PLANNER_ENGINE=rust` selects the new allocator; `EQM_PI_ENGINE` still controls the existing simulator independently.
- [ ] The packaged `eqm-core` supports `pi-allocation-worker`. A fallback is visibly disclosed, not mistaken for native execution. Investigate fallback logs before treating production Rust integration as verified.
- [ ] Active CCU/Interplanetary Consolidation/Customs Code Expertise levels match the pilot. Unknown skills are not level V; future skill overrides appear as planning assumptions.
- [ ] Existing colonies reserve slots by default. Explicit replacement frees the intended slot; a real planet cannot be assigned twice to the same pilot. Lowercase ESI planet types normalize correctly.
- [ ] Extractor estimates come from the observed program or entered averages. Inventory is a one-time recipe input, not free weekly supply.

## Calculations, prices and accounting

- [ ] Start with a small Water quota, then a purchased-input higher-tier product and a combined quota. Check whole factory batches, shared ingredients, surplus, shopping units and per-pilot assignments.
- [ ] Review CPU, power, heads, links, storage and slots against a known colony. P4 is limited to Barren/Temperate; longer visit intervals increase required buffers.
- [ ] Verify all five hub selectors use their stated station, with source and expiry timestamps. Spot-check a fresh price against current station orders rather than the universe average.
- [ ] Immediate sales use finite bid depth/minimum order volumes; unsold output earns zero. Missing input depth makes a plan infeasible. Patient-sale revenue is explicitly an estimate with uncertain fill.
- [ ] Reconcile one simple weekly ledger manually: purchases, each customs import/export leg, highsec NPC tax with pilot CCE, sales tax/broker fees, freight, overhead, setup, first-week cash and payback. Zero/negative margin does not produce misleading positive payback.
- [ ] Profit, maximum output, quota, combined quotas and product comparison return sensible best-found results. Check the explicit search coverage/time-limit notes; the search is not a global-optimum guarantee.

## Persistence and access

- [ ] Save, reopen, update and delete a scenario. Deleting its saved copy leaves the draft usable. Concurrent edits from two tabs report a revision conflict instead of silently overwriting.
- [ ] Start a job, reload/navigate away, and reopen it through recent runs. Cancel a long job and verify it leaves the active queue. Completed results retain their input snapshot even when the draft is subsequently edited.
- [ ] Export/import scenario JSON and a full snapshot; replay an owned run using its frozen data. A time-limited replay may examine a different number of candidates.
- [ ] Users cannot read another user's scenarios/runs. Removing PI permission or character visibility also removes access to previously saved records involving those characters.
- [ ] On a planned backend restart, interrupted jobs eventually become failed after the five-minute stale threshold and can be rerun. Persisted results survive restart; active work is not a durable distributed queue.

## Scouting, recipes and native templates

- [ ] Real region/system scouting returns correct planet types and diameters and adds selected planets without duplicates. Scores represent available resource types, not measured extraction density.
- [ ] Recipe graphs, raw material volumes, stock subtraction and CSV quantities agree with the selected recipe. Alternative buildable products do not imply the same stock can fund all alternatives simultaneously.
- [ ] Generate, inspect and export a native template. Changed text must be validated before export. Malformed JSON, incompatible pins/products and disconnected routes are rejected clearly.
- [ ] **Still unverified in the live EVE client:** clipboard import, actual placement/overlap, command-center setup, extractor heads, routes, per-buffer storage, burst link loads and transfer timing. Preview and adjust a layout in game before treating it as build-ready. Generated templates are original starting layouts, not certified one-click colonies.

## When reporting a regression

Record the deployed commit, affected screen/action, observed versus expected behavior, job ID and reported allocation engine. Retain the scenario/snapshot when useful, plus the HTTP status and relevant sanitized server log. Keep credentials, tokens and unrelated character data out of shared reports. Update the matching checkbox and note the result or follow-up fix here.

See [implementation contracts and limitations](pi-operation-planner.md) for the calculation model and reproduction commands.
