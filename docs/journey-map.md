# My Journey — private capsuleer flight log

**Unreleased 2.0.1 development feature.** Open **Navigation → My Journey** to record and replay selected characters' observed movements on an interactive New Eden map. Migrations **0103_journey_history** and **0104_journey_ship_history**, plus matching API/frontend, are required. No live deployment or real EVE consent was performed for these captures.

![Private journey map with visit and context markers](../static/ss/v2.0.1/journey-map.jpg)

## Start, pause and erase

Choose your linked character. If prompted, **Enable read-only location access** opens EVE SSO for that exact character, requesting `esi-location.read_location.v1` and `esi-location.read_online.v1`, while preserving already granted scopes that remain permitted. Existing revoked grants can be replaced with fresh minimal consent. Authorizing alone does not start tracking: click **Start tracking** or select the character under **Choose characters to track**. Each character opts in separately; use the character selector to view their separate journey.

Sampling defaults to a **15-second target**, selectable as 15/30/60/120/300 seconds. Collection continues when the browser is closed while the EQM API server is running. **Pause tracking** stops collection and preserves history. **Erase this character’s journey history** opens an explicit review/confirmation, erases only that character’s journey visits, and pauses tracking. Assets, killmails and other reports remain intact. Tracking is disabled by default for every account; migration does not enroll any character or recover earlier travel.

![Explicit per-character opt-in and sampling controls](../static/ss/v2.0.1/journey-controls.jpg)

## Optional ship types and hull icons

For the selected character, **Enable read-only ship access** requests `esi-location.read_ship_type.v1` alongside the existing location/online consent. This is read-only and is validated against that exact linked character. Consent alone never enables collection. Select **Record ship types** to opt that character into hull sampling; existing trackers and new characters default to location-only. Turning ship recording off preserves earlier hull history but stops new hull collection. Pause stops both kinds of collection. You can still pause or opt out if ship authorization is lost.

The sampler reads the character's current `ship_type_id` through ESI and stores timestamped hull segments within a visit. It discards the custom ship name and individual `ship_item_id`. Changing hull inside one system adds a timeline/replay step without adding a system visit. Traveling to another system still creates a normal visit. Current/replay hull badges and timeline entries include small CCP hull icons, names and existing type-level in-game links. Missing artwork falls back to a bordered placeholder; missing imported type metadata retains the sampled ID as `Type <ID>`.

Older visits and location-only intervals show **Unknown hull**; EQM never reconstructs those ships from assets, killmails or a later hull observation. A newly enabled hull starts at its first actual sample. Timeline gaps do not imply the previously recorded hull was flown continuously. API ship/location/online responses are independently cached and are not an atomic game-state transaction, so quick boarding changes or jumps may be missed or appear delayed. A failed/malformed ship response does not record a guessed hull; the sampler backs off and breaks continuity, using the existing authorization-stop behavior for terminal failures.

Hull history has the same account-only access, ownership rechecks, pause/erasure, transfer boundaries and no public sharing as system history. Utility-role consent does not enable regular asset/skill collection. Erasing a character's journey removes its hull segments as well. Ship sharing/redaction/export controls remain shelved future work.

![Independent private ship recording control](../static/ss/v2.0.1/journey-ships-controls.jpg)

![Timestamped hull changes and icons in the journey timeline](../static/ss/v2.0.1/journey-ships-timeline.jpg)

## Visits, totals and replay

The first online location sample starts an observed visit. Further samples in the same system update its last-confirmed time and sample count. A system change starts another visit; returning to a system increases its total. The panel shows all-time visits/unique systems, visits overlapping the selected UTC dates, per-system counts, first/last sightings, and the chronological visit log. **Observed span** means the interval between recorded samples, not time online or exact time spent in system.

An offline response, pause, failed sample or long gap breaks continuity. Resuming creates a new observed visit, even in the same system; this does not prove that the character physically left and returned. The displayed visit totals count these recorded observation segments. First/last times in the log retain the original sample bounds for visits overlapping the chosen dates.

**Replay journey** reveals observations in order at 0.5/1/2/4 steps per second. Play/pause, timeline scrubbing and **Latest / live view** control the display. This is an in-browser animated replay, not an exported video. Replay steps include visits and recorded hull changes. Replaying two hulls in the same visit moves the hull badge without increasing visit totals; speed is steps per second rather than actual flight speed. The map supports pan, zoom, fit and keyboard-selectable systems, and fits its projection to desktop/mobile dimensions. Search the visited-system list for keyboard access and systems without coordinates.

The map uses imported SDE X/Z positions. Lines join observed system changes; they do not claim a verified stargate route or travel method. Dashed links mark collection gaps. Unobserved intermediate systems are never filled in using a guessed shortest route. Characters can pass through systems between polls, so this is a sampled log rather than a complete jump counter. Online status and locations may lag because ESI caches them; worker load, downtime and rate limits can also delay samples.

The response includes at most the first **2,000 visits** in the selected window, with a visible truncation warning. Narrow the dates for a complete replay. All-time system totals remain complete. Timeline pages show 50 entries; the replay uses the loaded visits and hull segments. At most 5,000 hull segments are returned within loaded visits, with an explicit warning when truncated; narrow the date window for a complete replay. Unavailable hull rows stay unknown. History is retained until the account erases it; ordinary app restarts preserve it.

## Journey analytics

On Analytics, the pane supplies its own linked-pilot and UTC date controls and requires both Analytics and Navigation access. On Journey it uses the map pilot and date controls. Both placements retain account privacy independently of broader Analytics corporation scope. [Shared pane behavior](analytics-panes.md).

**Unreleased 2.4.0 follow-up.** Journey analytics is available on the main **Analytics** page and above the Journey replay. Its pane is **collapsed by default** in both locations; expand the heading to read existing stored data. Its default scope is **All my pilots → All stored history**, independently of the selected map pilot and replay dates. Choose **Selected journey pilot** for one character, or **Selected journey dates (UTC)** to use the date inputs above. No new migration, ESI consent, enrollment or external collection is added; matching API/frontend rollout is required.

| Ranking | What it counts |
| --- | --- |
| Systems most visited | Stored visits overlapping the selected dates, including resumed observations after gaps. |
| Ship types most flown | Hulls ranked by the number of visits containing an actual hull observation; optionally rank by summed confirmed observation span. |
| Recorded hulls with most kills | Recorded hull types with imported kills in the same pilot/date scope, ranked and graphed by descending kill count. The visit/span selector does not change this ranking. Kill hull comes from the selected pilot's attacker entry. |
| Systems with most kills | Distinct imported killmails involving selected pilots as attackers, grouped by kill location. |
| Ship types most lost | Distinct imported losses, grouped by the victim's destroyed hull, ranked and graphed by descending loss count. Unknown hulls remain explicit. |
| Pilots with most jumps | Account-owned pilots ranked by observed consecutive system changes without a recorded gap; selecting a name opens that pilot's journey and analytics. |

**Combat counts determine position and bars.** The kills card uses imported kills and the losses card uses imported losses, independently of the travel visit/span selector. SQL applies kill sorting before the top-N cutoff; equal kill counts use hull name/ID, not visit counts. Travel visits and confirmed span remain supporting context on the kills card. The existing recorded-hull eligibility and selected pilot/date/privacy scope are unchanged.

![Corrected Journey combat ranks on Analytics with span selected — synthetic v2.4.0 preview](../static/ss/v2.4.0/journey-combat-counts-analytics.png)

Summary cards show observed visits, unique systems, observed jumps, summed confirmed hull span, imported kills and imported losses. All aggregate queries run against the full selected scope in SQL: the replay's 2,000-visit and 5,000-hull limits do not trim these totals. Rankings default to the top 10 groups, with top 25/50 options. The caption shows the total groups and any top-N limit; limiting displayed groups does not limit aggregate totals. Equal values have deterministic secondary ordering.

### Interpretation and coverage

- **Observed jumps** are destination observations whose preceding visit was in another system and whose continuity flag has no gap. The preceding visit may be before the requested start. Initial observations, pauses/resumes and repeated same-system observations do not add jumps. Fast intermediate stops can be missed, and the counter does not distinguish stargates, wormholes or jump drives.
- **Most flown** means recorded hull use. Visit counts are distinct per hull and visit, so a visit with multiple hulls contributes once to each observed hull but once to total visits. **Confirmed observation span** sums each hull segment's first-to-last confirmed samples, clipped to the requested dates. It excludes between-segment gaps, can include docked time, and is not exact flight/online time. Single samples have a zero-second span. Visits without any hull record are counted explicitly; partially missing history is never reconstructed.
- **Combat is a separate source.** It uses already-imported killmails for the chosen pilots/dates, including combat outside recorded travel. It can predate Journey tracking. A recorded hull and a combat hull sharing a type does not prove the combat occurred during a particular recorded visit. Victim hulls never backfill flight history. Missing/conflicting attacker hull IDs remain unknown and cannot qualify a guessed hull for the recorded-hulls-with-kills ranking.
- **Shared kills** count once per group, even if duplicate attacker entries exist. A kill shared by two selected pilots can appear under both pilots and under each participating hull type. The account summary and kill-system totals count distinct killmails. A mail can be a kill for one selected pilot and a loss for another. Imported coverage may be incomplete; zero imported combat is not proof that no combat occurred.

Analytics is private to the signed-in account. Only currently owned linked characters and that account's trackers contribute; other staff cannot request another account's character. Existing Navigation permission/global disabling applies. Combat columns and rankings additionally require current access to Killboard, Battle Reports or Intel Reports; unavailable combat reads **Unavailable**, and no killmail query is made. Travel rankings remain usable without current ESI authorization. Pausing tracking preserves past rankings; clearing a character's journey refreshes its travel/hull statistics without deleting imported combat.

Visible analytics checks stored data every 60 seconds and supports manual refresh. Hiding analytics or closing Journey stops its polling. Pilot/date/sort/row changes cancel previous requests and start a separate result view. Refresh failures retain previous results with a warning and their last checked time. Analytics does not collect new data, modify EVE, or share history publicly.

The private/no-store `GET /journey/analytics` endpoint accepts optional local `character_id`, `period=all|range`, UTC `from_at`/exclusive `to_at`, `ship_order=visits|span`, and `limit` from 1–50. Date ranges use the existing Journey validation; all-history scope has no replay/date-page cutoff. Migration 0103/0104 and normal matching app builds remain prerequisites for existing Journey storage.

![Historical pre-correction journey rankings with synthetic travel and combat](../static/ss/v2.3.0/journey-analytics-desktop.png)

## Map controls

My Journey includes Atlas-style controls:

- **Scroll the mouse wheel/trackpad** over the map to zoom around the pointer, or use **+ / −**. The readout shows the current zoom (50%–8,000%).
- **Drag** the background, a route line, or a star to pan. A click/tap selects a system; dragging does not select it. Releasing outside the map or cancelling a touch gesture ends the drag.
- On touch devices, **drag with one finger** or **pinch with two fingers**. Scroll the page outside the map to move the page.
- **Zoom-and-Follow** is a toggle: center the current replay or latest recorded position at a minimum of 8× zoom, then keep it centered during playback, scrubbing and stored-history refreshes. A closer existing zoom is retained. Selecting a system for context does not change the follow target.
- **Center** recenters the current replay/latest recorded position once, preserving zoom and turning following off.
- Manual pan, wheel/pinch/toolbar/keyboard zoom, arrow-key pan, **Fit journey**, or **Focus selected** turns following off. Clicking Zoom-and-Follow again stops following without moving the camera.
- Position controls require coordinates for the current system. If they become unavailable while following, the camera holds its view and reports that following is paused; it resumes when coordinates return. Follow can still be turned off while paused.
- **Fit journey** restores the full projected view. **Focus selected** centers the selected system at 8× zoom.
- Focus the map with the keyboard: **arrow keys** pan, **+ / −** zoom, and **Home / 0** fit. Visited stars retain **Enter / Space** selection and the searchable visited-system list remains available.

Markers and labels stay at a consistent screen size as the route scales. Replay/scrubbing and context selection preserve your chosen zoom/pan in free view. Following keeps the current position centered, including when the map resizes or its projection changes. Resizing in free view fits the map; switching character/date range starts in fitted free view. Wheel gestures over the map are consumed by the map, not the page.

![Desktop zoom and pan controls — synthetic journey](../static/ss/v2.1/journey-map-controls-desktop.png)

![Touch-sized toolbar and journey — synthetic layout](../static/ss/v2.1/journey-map-controls-mobile.png)

Verification: nine journey math/replay/hull tests and eight actual-browser checks cover anchored wheel zoom, bounded zoom, panning, star selection, focus, keyboard input, replay retention, outside release, touch pinch/pan and cancellation recovery. Desktop/mobile captures use the actual JourneyPanel with synthetic local HTTP responses and illustrative coordinates; no production API or real character data was used. [Capture provenance and checksums](../static/ss/v2.1/capture-receipt.json).

### Zoom-and-Follow and Center — unreleased 2.3 follow-up

![Following the latest recorded position with Center beside the active toggle](../static/ss/v2.3.0/journey-follow-desktop.png)

[Mobile controls](../static/ss/v2.3.0/journey-follow-mobile.png) · [Capture provenance and checksums](../static/ss/v2.3.0/capture-receipt.json).

Validation: 26 journey tests, the complete TypeScript/Vite production build, and seven actual-browser scenarios pass. Browser checks cover replay, scrubbing, background history refresh/projection changes, selection, Center at existing zoom, follow cancellation, resize, missing coordinates, date resets, empty history and real mobile touch gestures. Actual JourneyPanel/JourneyMap with synthetic loopback responses and illustrative coordinates; no live character/API activity. Frontend-only change.

## Combat and asset context

Select a star or a system in the visited list. Map markers and the detail panel use **existing EQM data for that character only**:

- Imported killmails involving the selected pilot as attacker or victim, in the selected UTC range. Duplicate attacker rows do not duplicate kills. This requires Killboard, Battle Reports or Intel Reports permission. Context covers the selected date range and does not assert a kill occurred during a particular sampled visit.
- Current stored character assets in that system, with quantities, item links, locations and sync times. This requires Assets permission. Nested assets inherit resolved station/structure locations through their own-character hierarchy; unresolved locations are omitted. Corporate stock and other characters’ inventories are not added to this view.

The asset layer remains a **current inventory snapshot during replay**, not historical holdings. Refresh stored data after a normal asset/killboard sync to update context. Location-only journey tracking does not collect ship types; optional hull recording requires separate opt-in. Neither mode starts asset, skill or killmail collection and does not change regular sync opt-outs. Utility-only accounts remain outside ordinary private collection. Detail lists show up to 100 records per layer; map counts aggregate all matching stored records.

![Visited-system selection with imported combat and stock](../static/ss/v2.0.1/journey-system-context.jpg)

## Privacy and operations

Navigation permission is required. All history/settings/context routes enforce the current account's ownership of the linked character, with **no staff override**. Journeys are account-private and have no public share link. A character transfer does not expose the old account’s history to the new account. Unlinking, revocation, lost scopes, disabled Navigation or account deletion stops new writes. History stays in this private module, separate from Local Scan/Intel observations. Account/character deletion cascades owned journey records where applicable.

The server stores system IDs, UTC first/last observations and sample counts, plus private tracking state. With explicit hull opt-in it also stores ship type IDs and timestamped segment/sample counts within the visit; custom ship names and individual ship IDs are discarded. Station IDs, structure IDs and exact in-system positions from the location response are discarded. Short-lived access tokens and online cache entries remain in bounded process memory. Refresh-token rotation is persisted only after checking the original credential still matches. The sampler refresh requests only location/online scopes, adding ship-type read access when the character has explicitly opted in. A scope-mode change invalidates the transient bearer cache so a location-only bearer is never reused for ship collection.

The API lifecycle runs a bounded background sampler. Atomic database leases coordinate concurrent API processes and recover after interruption; paused/erased trackers invalidate in-flight leases. Ownership, enabled state and scopes are rechecked after network waits. Database sessions close before OAuth/ESI awaits. Cached online status avoids redundant calls; location scheduling follows remaining `Cache-Control` lifetime (legacy `Expires` fallback), requested interval and the existing shared ESI transport's rate/error controls. Failures back off, and terminal authorization failures stop collection until explicit reauthorization/restart. Errors do not log credentials or positions.

Apply `0103_journey_history` after 0102, followed by `0104_journey_ship_history`, with matching API/frontend. It creates `journey_trackers` and `journey_visits`, owner/character uniqueness, due-work and character/system/time indexes; no historical data is backfilled. The 0103 downgrade removes journey history only. Migration 0104 adds `track_ship` (false by default), a current-segment pointer and `journey_ship_segments` with a cascading visit foreign key and visit/time index. It does not enroll or backfill existing histories. Downgrading 0104 drops hull history/settings while retaining system visits. Source-based timing guidance follows [CCP’s cache-header guidance](https://developers.eveonline.com/blog/smarter-caching-when-events-drive-invalidation).

## Verification and screenshots

Backend tests cover opt-in/default privacy, utility scopes and real-auth Quartermaster mutation limits, staff isolation, repeated samples and revisits, gap/clock behavior, pause/erase, leases, credential races, in-flight revocation/transfer/permission changes, cache headers, offline detection, failure backoff, connection release during network waits, current-own-character context, nested assets, distinct killmail counts, explicit UTC context timestamps, date limits and migration upgrade/downgrade. Replay tests cover ordering, revisits, gaps, missing coordinates and projection. Run `npm --prefix frontend run test:journey` and the production build.

Browser captures use the actual built UI/APIs against an isolated synthetic database. Public CCP system coordinates are used for a fabricated route; pilots, holdings and combat are demo data. The preview does not perform real OAuth, collect a live character's location, or issue a game action. Playback advances through the route, scrubbing works, character switching clears the previous view, star selection loads context, opt-in/pause persist, and mobile layout has no document overflow. No JavaScript console errors were observed.

![Mobile journey map](../static/ss/v2.0.1/journey-mobile.jpg)

Ship follow-up verification adds 18 backend tests: explicit minimal ship consent without other collection, location-only defaults even with a broad grant, within-system switches and unchanged totals, cache/scoped bearer separation, post-network revocation/opt-out checks, malformed responses, no retained custom name/item ID, pause after revoked scopes, erasure/ownership/limits and migration upgrade/downgrade. The original regression run passed 136 backend tests plus 7 subtests; the final 18-test hull suite includes three additional network/OAuth checks (139 unique backend tests overall). Five frontend replay/projection tests and the final production build pass.

The actual browser preview verified per-character consent isolation, setting persistence, Deimos-to-Gila replay steps within Jita without inflating the ten-visit total, hull icons in desktop/mobile timelines and no document overflow or console errors. Fixtures contain synthetic hull history, not real flight logs. The sampler was not run against a real EVE grant. The official [ESI OpenAPI schema](https://esi.evetech.net/meta/openapi.json) was checked for the ship endpoint and required read scope; the old `/latest/swagger.json` URL no longer resolved during this check.

![Hull at the current replay step](../static/ss/v2.0.1/journey-ships-replay.jpg)

![Mobile hull timeline with contained table scrolling](../static/ss/v2.0.1/journey-ships-mobile.jpg)

[All captures and checksums](../static/ss/v2.0.1/capture-receipt.json)

## GIF and MP4 exports

Open **Export your journey** for the selected character and UTC dates. Choose the first and last loaded visit, then GIF or MP4. Create the file, review the preview and use **Download**. Clips are generated on your device; private flight history is not uploaded to a media service. A later date/character change or leaving the panel cancels active encoding and releases preview data. Automatic history refresh does not change a clip already being generated.

Both formats are **1920 × 1080**. MP4 is silent H.264 at 30 fps; GIF is a looping 10 fps animation with a limited color palette. Current desktop Chrome/Edge with OffscreenCanvas workers and H.264 WebCodecs encoding is recommended. An unavailable MP4 encoder gives an explicit GIF/browser fallback. The Android wrapper currently has no download handler for these generated files; use a desktop browser to save them. No APK change is included.

The film opens with one second at **100%**, spends one second zooming toward the first system, then advances at **one second per recorded visit**, including revisits. The camera pans between systems at a readable close-up scale. Hull changes remain inside that second; missing hull observations remain **Unknown hull**. It zooms back out over 1.5 seconds and holds the whole selected journey at 100% for one second. EQM branding stays in the upper left; the export date, visit times and combat times are UTC. First/last observations spanning the selected dates are clipped to those dates. This is a map of loaded journey systems, not a full universe atlas.

At visits with imported kills or losses, the camera pauses for **three additional seconds per page of six records**. Cards list total kills/losses for that visit, each destroyed hull and its UTC date/time. A record is attached once by pilot, system and time, so revisits get separate results. A continuous visit extends up to the next observation (exclusive); before an offline/pause/data gap it stops at the last confirmed sample (inclusive). Unmatched imports are counted and excluded rather than assigned to a guessed visit. Killmail victim hulls never backfill the pilot's recorded ship history. Existing imports can be incomplete; an empty card does not prove no combat took place. Without combat-section access, a clearly marked travel-only clip remains available.

Example: four visits plus three engagement pages produce **17.5 seconds** (4 seconds travel + 9 seconds combat + 4.5 seconds opening/closing). Each page adds time rather than speeding up travel.

Limits are **500 visits, ten minutes including pauses, and 128 MiB per file**. Select smaller clips for GIF, which can be much larger than MP4. History/hull truncation is warned; narrow the dates for complete data. Missing coordinates retain the visit and display a notice while the camera holds its previous mapped position. Gaps remain dashed; straight lines do not assert a verified gate route. For a single clip, the dedicated combat request still has a 5,000-record limit and asks for narrower dates if exceeded. Segmented exports page through additional combat/hull records automatically.

The new private/no-store `GET /journey/characters/{character_id}/export-combat` endpoint reuses Navigation, current account ownership and Killboard/Battle Reports/Intel Reports checks. It returns only existing imported killmails involving the selected pilot in visited systems and the requested UTC range. It does not initiate zKillboard/ESI collection, expose other characters' private inventories, or need a migration or new consent scope. Rollout requires matching API and frontend. The regular system detail still has its 100-record cap.

Encoders are pinned to gifenc 1.0.3 (MIT) and mediabunny 1.65.2 (MPL-2.0), loaded in a worker when exporting. [Encoder attribution and corresponding-source links](../static/licenses/journey-exports.txt), [gifenc license](../static/licenses/gifenc.txt), [mediabunny license](../static/licenses/mediabunny.txt).

![Actual export UI with a synthetic engagement preview](../static/ss/v2.1/journey-export-desktop.png)

![Frame from a generated 1080p MP4 showing imported kills and losses](../static/ss/v2.1/journey-export-engagement.png)

Verification: 17 frontend journey tests; 46 backend journey/ship/export tests; TypeScript and full production build; nine real-browser export cases using the production-bundled worker. Generated H.264 MP4 (525 frames at 30 fps) and GIF (175 frames at 10 fps) are both 1920×1080 and 17.5 seconds. Opening, engagement and closing frames were extracted from the actual generated media and visually checked. Synthetic fixtures only; this is not a live-character or Android download test. [Capture provenance](../static/ss/v2.1/capture-receipt.json).

Version note: the map/export captures and generated-media verification above were recorded against 2.1.0 development source before the 2.2.1 bump. Their original labels, paths and checksum receipts are preserved.

## Segmented and entire journey exports

Choose **Journey export scope** above the export panel:

| Scope | Included history |
| --- | --- |
| Single clip · selected visits | The first/last visit numbers from the loaded replay, up to 500 visits. |
| Segment selected dates · every visit | Every recorded visit in the current character/UTC date range, including pages beyond the map’s loaded 2,000 visits. |
| Entire recorded journey · all dates | All recorded dates for the selected character, independent of the map’s date controls and replay cap. |

The segmented modes traverse the timeline once in order. Each clip contains at most **500 visit contexts, ten minutes including the opening/closing shots, and 128 MiB**. A clip stops before the next visit or engagement page would exceed the limit; the following part begins with that next event. A long engagement can continue in the following clip at its next page, without adding another travel/visit event. The video marks the visit as **continued**, retains its original journey visit number and page number, and adds the part number to the title. The map still opens at 100%, zooms/follows the current part, then returns to 100% in each file. All clips in a batch share the export date.

At one visit per second, 500 visits without combat take **504.5 seconds**, including the 4.5-second opening/closing overhead. An engagement-heavy test stopped at **599.5 seconds** after page 198, then resumed on **page 199** in part 2. Each six-record engagement page still lasts three seconds. Continuation pages do not repeat the visit’s one-second travel event. A file that reaches the byte limit is retried as smaller consecutive groups of timeline events; a single event that cannot fit stops with an explicit MP4/format suggestion rather than being skipped.

Use **Export clips to folder** in a supported desktop browser to choose a destination and save all numbered parts automatically. The directory picker opens directly from the click before history loading/encoding; files are written using the browser’s [File System Access API](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access). The app retains one encoded clip/preview at a time. A timestamped batch name prevents different export runs sharing filenames. A JSON index is updated after each confirmed saved clip and at completion, cancellation or failure. It lists filenames, part numbers, visit ranges, timeline-event boundaries, duration/bytes, snapshot date and partial/completed status. Unavailable combat and unassigned imports are explicit in the index and movie.

**Export clips for download** works without folder access: save the current numbered clip, then select **Continue after saving** to release that preview and create the next one. This avoids relying on browser permission for repeated automatic downloads. The existing single-clip mode remains available. Keep the page open; changing character, dates or scope cancels the active batch. Cancellation finishes an already-started atomic file write, preserves saved files and records any unconfirmed pending clip. Partial indexes are downloadable when clips have been saved. Reload recovery from an index is not implemented; the index documents where a stopped batch reached. Android WebView downloads remain unsupported.

The new read-only/private/no-store `GET /journey/characters/{character_id}/export-history` endpoint freezes the selected scope at an export boundary and streams visit pages of 500, with a next-visit lookahead to match combat across page boundaries. Hulls and imported pilot-involved combat use separate 5,000-row attachment pages so they are not silently truncated. Signed cursors bind the account, character, tracker revision, date/snapshot bounds and position; every request rechecks current ownership and combat permissions. New visits beyond the starting watermark and post-snapshot killmail imports are excluded. Changed/erased history, changed access, inconsistent counts or expired cursors stop with saved clips preserved. Paging snapshots expire after 48 hours. Media is encoded on the device; no server rendering, new ESI collection, dependency, migration or consent scope is added. Matching backend/frontend builds are required.

![Entire-journey export: 501 synthetic visits saved in two clips](../static/ss/v2.2.1/journey-segments-complete.png)

![Continuation frame: part 2 resumes on page 199 of the same recorded visit](../static/ss/v2.2.1/journey-segments-continuation.png)

Verification: **25 frontend journey tests**, **51 backend journey/export tests** (50 broad cases plus the added permission/snapshot case, with the final five pagination cases rerun), production TypeScript/Vite build, and seven actual production-worker browser cases plus final download/cancellation/mobile refinements. The real 500-visit H.264 MP4 is 1920×1080, 30 fps, 15,135 frames, **504.5 seconds**, 78,723,306 bytes. The continuation MP4 is 11.5 seconds/345 frames. A real GIF limit test reduced only the test worker’s threshold to 6 MiB; all 15 visits and their engagement pages were automatically split into valid files, and the sampled GIF is 1920×1080 at 10 fps. The production limit remains 128 MiB.

Browser folder tests used real origin-private directory/file handles in an isolated Edge profile instead of automating the native user-folder picker. Individual downloads were saved and probed; no actual user folder, account, live SSO or EVE activity was used. Captures show actual JourneyPanel/export components with synthetic history and coordinates. [Capture provenance and checksums](../static/ss/v2.2.1/capture-receipt.json).
