# Fighter tubes in the fitting simulator

Unreleased development addition to 2.4.3. Matching backend, frontend and Rust
core must be rebuilt together; no migration, new dependency or ESI scope.

Open **Fittings**, choose a carrier, supercarrier or Caiman, then select a pilot.
The **Fighter tubes** panel reads the hull's tube count and light/support/heavy
squadron limits from the imported SDE. Other fighter-capable hulls, including
the Komodo, use the same attributes rather than a ship-name allowlist.

Create an editable draft to load a tube. Choose existing hangar reserves to
move up to one full squadron into that tube, or **Add new stock** to add a full
squadron directly. Squadron size comes from the fighter type, including the
larger superiority squadrons; an undersized reserve stack loads a partial
squadron. **Recall** leaves the squadron loaded with zero DPS. **Deploy** makes
it contribute again. **Unload to hangar** returns the surviving fighters to
reserve stock. Changing the fighter count changes the fit's inventory too.
Loaded and reserve fighters both count toward the fighter hangar volume.

Tube positions and loaded/deployed state persist in EQM. A tube holds one
squadron of one type. Unsupported classes, oversize squadrons, occupied tubes
and excessive deployed class counts are refused. Malformed or legacy invalid
assignments produce a warning and contribute no damage. Standup fighters are
not supported on ships. Fighters cannot overheat.

## Damage estimates

Fighter damage appears separately from drone damage and contributes to total
DPS, volley, damage-type totals and weapon estimates alongside fitted weapons.
Only deployed squadrons contribute. Each ability's per-fighter SDE damage and
cycle are multiplied by the surviving squadron size, matching trained fighter
and racial specialization skills, applicable hull skill/role bonuses, and
online module modifiers. Drone Damage Amplifiers and Fighter Support Units
use the appropriate stacking penalties. Drone Interfacing is not a fighter
damage bonus. Ordinary drone calculations are unchanged.

Primary damage is selected by default. **Include missile salvo burst** adds
limited-ammunition missile salvos; this is a burst rate while ammunition is
available, not a long-term average including return/rearm time. Superiority
fighters' Micro Missile Swarm is an unlimited primary weapon and is always
included when deployed. Support fighter electronic warfare adds no weapon DPS.
Suicide/kamikaze damage is not included.

**Damage target** selects capital, subcapital, fighter/drone or structure
classification. The model applies the SDE's anti-fighter and anti-capital
missile class reductions, including superiority fighters' reduced damage to
ships. It assumes full signature/velocity/range application before shield,
armor or structure resists; it does not predict applied DPS against a moving
individual target. Travel, target switching, lost fighters during an attack,
ability downtime and pilot execution are not simulated.

The fighter layer runs once after the selected Python/Rust base-stats engine.
Fighter inventory is excluded from both engines' ordinary drone path, so a
Rust result cannot discard fighter damage or count it a second time. The UI
identifies this combination as Rust base stats plus the Python fighter model.

## Export and compatibility

EFT text and **Send to EVE** flatten loaded squadrons and reserve stock into
the fighter bay, preserving total carried quantities. EVE saved fittings do
not carry EQM's deployment choices. Imported fittings therefore start with
reserve fighters; load their tubes explicitly in a draft. Existing fittings
and ESI originals are not automatically rewritten into deployed squadrons.

Reimport SDE dogma and effects if tube attributes or hull/module bonuses are
missing. Missing hull-effect metadata is shown as an incomplete-estimate
warning. The regression catalog was checked against CCP HTTP SDE build
**3739102**, released **November 24, 2026**. Tube counts, sizes and bonus
values in the simulator come from each installation's imported SDE.

Validation uses a current CCP SDE subset and synthetic pilots/loadouts,
isolated SQLite API tests, a newly compiled Windows Rust core, and headless
Microsoft Edge workflows against the real fitting endpoints. PostgreSQL
concurrent-edit behavior and live in-game numerical comparisons were not
exercised. [Actual UI captures](screenshots.md#fighter-tubes).
