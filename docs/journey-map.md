# My Journey — private capsuleer flight log

**Unreleased 2.0.1 development feature.** Open **Navigation → My Journey** to record and replay selected characters' observed movements on an interactive New Eden map. Migration **0103_journey_history** and matching API/frontend are required. No live deployment or real EVE consent was performed for these captures.

![Private journey map with visit and context markers](../static/ss/v2.0.1/journey-map.jpg)

## Start, pause and erase

Choose your linked character. If prompted, **Enable read-only location access** opens EVE SSO for that exact character, requesting `esi-location.read_location.v1` and `esi-location.read_online.v1`, while preserving already granted scopes that remain permitted. Existing revoked grants can be replaced with fresh minimal consent. Authorizing alone does not start tracking: click **Start tracking** or select the character under **Choose characters to track**. Each character opts in separately; use the character selector to view their separate journey.

Sampling defaults to a **15-second target**, selectable as 15/30/60/120/300 seconds. Collection continues when the browser is closed while the EQM API server is running. **Pause tracking** stops collection and preserves history. **Erase this character’s journey history** opens an explicit review/confirmation, erases only that character’s journey visits, and pauses tracking. Assets, killmails and other reports remain intact. Tracking is disabled by default for every account; migration does not enroll any character or recover earlier travel.

![Explicit per-character opt-in and sampling controls](../static/ss/v2.0.1/journey-controls.jpg)

## Visits, totals and replay

The first online location sample starts an observed visit. Further samples in the same system update its last-confirmed time and sample count. A system change starts another visit; returning to a system increases its total. The panel shows all-time visits/unique systems, visits overlapping the selected UTC dates, per-system counts, first/last sightings, and the chronological visit log. **Observed span** means the interval between recorded samples, not time online or exact time spent in system.

An offline response, pause, failed sample or long gap breaks continuity. Resuming creates a new observed visit, even in the same system; this does not prove that the character physically left and returned. The displayed visit totals count these recorded observation segments. First/last times in the log retain the original sample bounds for visits overlapping the chosen dates.

**Replay journey** reveals observations in order at 0.5/1/2/4 visits per second. Play/pause, timeline scrubbing and **Latest / live view** control the display. This is an in-browser animated replay, not an exported video. Replay speed is visits per second rather than actual flight speed. The map supports pan, zoom, fit and keyboard-selectable systems, and fits its projection to desktop/mobile dimensions. Search the visited-system list for keyboard access and systems without coordinates.

The map uses imported SDE X/Z positions. Lines join observed system changes; they do not claim a verified stargate route or travel method. Dashed links mark collection gaps. Unobserved intermediate systems are never filled in using a guessed shortest route. Characters can pass through systems between polls, so this is a sampled log rather than a complete jump counter. Online status and locations may lag because ESI caches them; worker load, downtime and rate limits can also delay samples.

The response includes at most the first **2,000 visits** in the selected window, with a visible truncation warning. Narrow the dates for a complete replay. All-time system totals remain complete. Visit-log pages show 50 rows, while the replay uses the full loaded window. History is retained until the account erases it; ordinary app restarts preserve it.

## Combat and asset context

Select a star or a system in the visited list. Map markers and the detail panel use **existing EQM data for that character only**:

- Imported killmails involving the selected pilot as attacker or victim, in the selected UTC range. Duplicate attacker rows do not duplicate kills. This requires Killboard, Battle Reports or Intel Reports permission. Context covers the selected date range and does not assert a kill occurred during a particular sampled visit.
- Current stored character assets in that system, with quantities, item links, locations and sync times. This requires Assets permission. Nested assets inherit resolved station/structure locations through their own-character hierarchy; unresolved locations are omitted. Corporate stock and other characters’ inventories are not added to this view.

The asset layer remains a **current inventory snapshot during replay**, not historical holdings. Refresh stored data after a normal asset/killboard sync to update context. Journey tracking does not start asset, skill, ship-type or killmail collection and does not change regular sync opt-outs. Utility-only accounts remain outside ordinary private collection. Detail lists show up to 100 records per layer; map counts aggregate all matching stored records.

![Visited-system selection with imported combat and stock](../static/ss/v2.0.1/journey-system-context.jpg)

## Privacy and operations

Navigation permission is required. All history/settings/context routes enforce the current account's ownership of the linked character, with **no staff override**. Journeys are account-private and have no public share link. A character transfer does not expose the old account’s history to the new account. Unlinking, revocation, lost scopes, disabled Navigation or account deletion stops new writes. History stays in this private module, separate from Local Scan/Intel observations. Account/character deletion cascades owned journey records where applicable.

The server stores system IDs, UTC first/last observations and sample counts, plus private tracking state. Station IDs, structure IDs and exact in-system positions from the location response are discarded. Short-lived access tokens and online cache entries remain in bounded process memory. Refresh-token rotation is persisted only after checking the original credential still matches. Only the two journey scopes are requested for the sampler's access-token refresh.

The API lifecycle runs a bounded background sampler. Atomic database leases coordinate concurrent API processes and recover after interruption; paused/erased trackers invalidate in-flight leases. Ownership, enabled state and scopes are rechecked after network waits. Database sessions close before OAuth/ESI awaits. Cached online status avoids redundant calls; location scheduling follows remaining `Cache-Control` lifetime (legacy `Expires` fallback), requested interval and the existing shared ESI transport's rate/error controls. Failures back off, and terminal authorization failures stop collection until explicit reauthorization/restart. Errors do not log credentials or positions.

Apply `0103_journey_history` after 0102 with matching API/worker/frontend. It creates `journey_trackers` and `journey_visits`, owner/character uniqueness, due-work and character/system/time indexes; no historical data is backfilled. Downgrade removes journey history only. Source-based timing guidance follows [CCP’s cache-header guidance](https://developers.eveonline.com/blog/smarter-caching-when-events-drive-invalidation).

## Verification and screenshots

Backend tests cover opt-in/default privacy, utility scopes and real-auth Quartermaster mutation limits, staff isolation, repeated samples and revisits, gap/clock behavior, pause/erase, leases, credential races, in-flight revocation/transfer/permission changes, cache headers, offline detection, failure backoff, connection release during network waits, current-own-character context, nested assets, distinct killmail counts, explicit UTC context timestamps, date limits and migration upgrade/downgrade. Replay tests cover ordering, revisits, gaps, missing coordinates and projection. Run `npm --prefix frontend run test:journey` and the production build.

Browser captures use the actual built UI/APIs against an isolated synthetic database. Public CCP system coordinates are used for a fabricated route; pilots, holdings and combat are demo data. The preview does not perform real OAuth, collect a live character's location, or issue a game action. Playback advances through the route, scrubbing works, character switching clears the previous view, star selection loads context, opt-in/pause persist, and mobile layout has no document overflow. No JavaScript console errors were observed.

![Mobile journey map](../static/ss/v2.0.1/journey-mobile.jpg)

[All captures and checksums](../static/ss/v2.0.1/capture-receipt.json)
