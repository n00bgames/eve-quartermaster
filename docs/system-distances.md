# System Distances & Warp Time

The bottom widget in **Navigation** compares objects within one solar system. Type two or more letters and pick a system, choose the **From** object, then select a destination from the table. Objects are ordered by gate, NPC station, Upwell structure, planet, moon, asteroid belt and star.

The list shows three-dimensional straight-line distances in AU from the selected starting object. Distances use system-relative XYZ positions in metres, divided by 149,597,870,700 metres per AU. Galaxy-map system positions are never used for in-system distances. The database stores coordinates rather than every possible pair, so distances are calculated as you change the origin.

Enter warp speed in AU/s and align time in seconds. The displayed reference is:

```text
reference seconds = distance AU / warp speed AU per second + align seconds
```

**Rough estimate: does not include acceleration and deceleration times and should only be used as an estimated reference time.** Docking, gate activation and server delays are excluded. No ship-specific warp curve is simulated. Zero distance displays zero travel time; missing positions or invalid inputs suppress the estimate.

## Object coverage

- Existing imported SDE gates and NPC stations are available immediately.
- A full SDE import now also reads `mapPlanets.yaml`, `mapMoons.yaml`, and `mapAsteroidBelts.yaml`. Older exports missing these files still import; ESI can fill the gap.
- **Refresh ESI objects** fetches the selected system's public manifest and object positions. Successful public checks are cached for 24 hours; partial checks for five minutes. Failed lookups retain existing valid coordinates.
- Known Upwell structures are resolved with the signed-in user's own active ESI tokens containing `esi-universe.read_structures.v1`. Even admin users cannot borrow other users' authorizations. Results are stored per token and visible only to its owner while the token remains active and the one-hour position cache is fresh.
- **Resolve an additional Upwell structure** accepts a structure ID. It must resolve through your characters and belong to the selected system. Refresh known structures or re-resolve its ID to renew expired positions. ESI permission/not-found responses remove that token's cached entry.
- ESI has no complete system-wide list of all player anchorables. This is a static-object and known-accessible-structure catalog, not an exhaustive anchored-object scanner. Structures may be missing or inaccessible. Cached visibility does not promise docking access. Anomalies, temporary wormholes, mobile deployables, and ship positions are not included.

## Deployment

Rebuild the backend and frontend and apply migration **0080_system_distances** through the normal EQM startup/update process. This creates public position records, static ESI refresh metadata, and token-scoped structure position records. No new SSO scope is introduced beyond the existing structure-read scope; a character without it must be relinked with that scope to resolve structures.

A full SDE reimport is optional for an existing installation: select a system and use **Refresh ESI objects** to populate it on demand. Reimport to populate the wider celestial catalog. No live server has to be crawled for every system.

## Verification

Focused tests cover SDE import and repeat import, missing/invalid coordinates, public ESI fallback and caching, partial failures, private-token isolation, revocation/expiry, cross-system rejection, and Navigation permissions. Frontend tests cover 3D AU distances, input validation, zero distance and the exact reference-time formula.

Local browser verification uses public Jita ESI coordinates, not authenticated production data. Desktop and 390-pixel mobile checks cover search, origin/destination changes, stale search responses, refresh selection, structure errors, input validation and the warning. Production deployment and live private-structure verification are separate operator checks.
