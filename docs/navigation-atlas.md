# New Eden Atlas: Star Map and Missions/LP

Navigation now starts with a **Star Map** and **Missions & LP** tab. Both share a route origin and can send a destination directly to the existing Route Checker. The checker retains its safer-route, highsec-only and avoidance settings, except an endpoint cannot remain on its avoid list. The resulting route is drawn on the atlas.

## Explore and plan

- Search for a system, click a star, filter by region, pan, zoom, or focus the selected system. The default view shows known space; disconnected regions are available explicitly. This first version uses the SDE X/Z projection, not a rotating 3D renderer.
- Color by security, hourly ship/pod/NPC kills, hourly jumps, NPC station counts, or agent counts. Select a system for stations, agents, route actions, and direct DOTLAN/zKillboard links.
- Find agents by name, corporation, system, level, division, highsec location, or distance from the route origin. Distances use the shortest permanent stargate path. A highsec agent does not imply a highsec journey or mission destination. Inaccessible/disconnected and unresolved locations stay unavailable.
- Open an agent on the map, plan a route to its system, or browse its corporation's rewards. Mission-name search opens EVE University; EVE-Survival's mission report index is also linked.
- Select one of your linked pilots to retrieve current ESI-cached LP balances, or browse public rewards without a pilot. Search rewards and required items; optionally show only offers covered by the selected LP balance. Each offer retains its quantity, LP cost, ISK cost, required items, and Analysis Kredits when applicable. LP coverage is not a claim that every redemption requirement is satisfied.
- Corporation stations are ordered by shortest gate distance when an origin is selected. Confirm the relevant LP store service in-game.

## Data and privacy

| Information | Source / behavior |
| --- | --- |
| System geography, security, permanent gates, NPC stations, type names | Installed YAML SDE |
| Agent directory | Modern `npcCharacters.yaml` agent records, or legacy `agents.yaml`; corporation names/factions from SDE |
| Last reported hour of kills/jumps | Public ESI `/universe/system_kills/` and `/universe/system_jumps/` |
| LP rewards | Public ESI `/loyalty/stores/{corporation_id}/offers/` |
| Character LP | Authorized ESI `/characters/{character_id}/loyalty/points/` |
| Additional system intelligence | External DOTLAN and zKillboard links; existing Route Checker intel remains available |

Public snapshots respect ESI expiration headers and use a bounded, process-local cache. If refresh fails, retained snapshots are explicitly marked stale. If no snapshot exists, activity is unknown rather than zero. Systems absent from a successful sparse ESI activity feed count as zero; wormhole activity remains unknown. Timestamps come from the feed's Last-Modified header and are not invented when it is missing. Hourly activity is not a live safety assessment.

LP reads require `esi-characters.read_loyalty.v1`, an active token owned by the signed-in account, and a character that has not opted out of collection. Admin privileges do not override ownership. Responses use `Cache-Control: private, no-store`; private LP never enters the shared public atlas cache. Existing ESI transport caching remains credential-isolated. Re-link older authorizations missing the loyalty scope.

No active mission journal, mission eligibility calculation, automatic LP redemption, or profitability estimate is included. The map lists NPC stations, not a complete player-structure directory. ESI/SDE are fetched directly; DOTLAN and zKillboard are linked rather than scraped. Special agents are identified separately; some in-space agent locations are unresolved in this initial importer.

If a pilot still shows **re-link for LP scope** after relinking on v1.0.3, update to the v1.0.4 scope fix first. The original Atlas release omitted loyalty from the normal/core SSO request even though it appeared in the full scope list. Ensure the CCP developer application enables `esi-characters.read_loyalty.v1`, reload EQM to obtain a fresh authorization link, then relink affected pilots through **ESI Sync**. Return to Missions & LP and click **Refresh** to reload the pilot scope status. Refreshing an existing token cannot grant a permission that was never authorized.

## Rust boundary

`eqm-core atlas-distances --input <payload.json>` computes unweighted directed breadth-first distances from an origin. Its payload is `{"origin":30000142,"edges":[[30000142,30000144]]}`; output uses schema `eqm.atlas-distances.v1` and a system-ID-to-distance map. Unreachable systems are omitted.

Python retains authorization, SDE/ESI reads, filtering, and response assembly. It invokes the configured `EQM_CORE_BINARY` when available and falls back to a deterministic Python BFS if the binary is absent or fails. This traversal supplies agent/station distances; the established route planner still owns safety preferences and route selection. Rebuild the Rust binary with the backend image to enable the new command.

## Activate on an installation

1. Build backend and frontend together and apply **0081_mission_atlas** through EQM's normal migration/startup process. The migration creates the public `eve_agents` table. It has no private LP storage.
2. Existing installations with systems and stations already imported can open **Settings → SDE Import → Import agents only**, using their installed YAML SDE path. A full SDE import also imports agents after stations. Missing agent files preserve an existing directory.
3. Refresh Navigation. Check system details, find an agent, and send its destination to Route Checker. Link a pilot with the LP scope for the private balance view.

No production migration, SDE import, deployment, or character authorization is performed merely by adding this source change.

## Verification

Run `python -m pytest tests/test_mission_atlas.py tests/test_system_distances.py -q` from `backend`, `npm run test:navigation` and `npm run build` from `frontend`, and `cargo test --locked` from `rust/eqm-core`.

Tests cover migration upgrade/downgrade, modern/legacy agent imports, security boundaries, shortest paths, disconnected locations, complete reward costs, stale/unavailable feeds, and private LP access including cross-account admin rejection, revocation, missing scope, and opt-out. Browser verification uses the installed public SDE with synthetic pilot/LP fixtures, checking map selection, agent filters, route handoff, reward search and LP filtering, plus desktop and 390-pixel mobile layouts. Live private-character LP is an operator check after authorization.
