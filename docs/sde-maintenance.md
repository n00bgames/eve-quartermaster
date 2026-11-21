# SDE maintenance from Settings

Available in EQM; HTTP JSONL source added in 2.4.2. Available to administrators and hosts, including aggregate roles whose base grants administrator access.

## Controls

Under **Settings → SDE Maintenance**, press **Download latest SDE** to queue a download of CCP's latest published Tranquility YAML archive. By default this only downloads and validates the archive; imported database records remain unchanged. Select **Import automatically after a successful download** to import after validation. Otherwise use **Use downloaded archive for import** and **Queue SDE import** later. The existing path input and **Queue agents-only import** remain available for mounted folders or ZIPs.

The panel shows queued/running/completed/failed state, stage, bytes received, archive build, filename and SHA-256. The full server path is used internally for import and is available in the administrator-only path input. Progress is stored in the database and can be recovered after leaving Settings or reloading the API. All dataset/subfield totals remain available below the controls. Download-only jobs do not report import totals.

Only one SDE operation can be queued or running, including legacy `/sde/import` calls, across API processes and users. Duplicate submissions return 409. Existing imports now use the worker rather than an API background thread. Repeated delivery of one worker job cannot import twice.

## Deployment

1. Let any old API-thread SDE import finish before upgrading; it cannot participate in the new database lock.
2. Apply migration **0097_sde_maintenance** after 0096 before starting updated API/workers. Deploy matching frontend/API/worker code.
3. Run the existing Redis service and `rq worker --url redis://redis:6379/0 eve-quartermaster`. These jobs use that established queue.
4. Give the worker write access to the mounted SDE directory and sufficient free disk space. Compose now mounts `/sde` read/write in the worker and keeps it read-only in the API. Recreate the worker so the mount change takes effect.
5. Check `SDE_DOWNLOAD_PATH` (default `/sde/downloads`), `SDE_JOB_TIMEOUT_SECONDS` (default 7200, permitted 60–21600), and `SDE_DOWNLOAD_MAX_BYTES` (default 512 MiB). They are wired for both services in Compose. Custom download paths must exist on storage visible at the same path to API and worker. `SDE_SOURCE_PATH` remains the default for manual imports.

Read-only bind mounts, missing workers or Redis, storage permissions and exhausted disk space must be resolved by the operator. A queued job waits for the worker; it is not reported as complete merely because the API accepted it. A lost enqueue response returns 503 and retains the lock because Redis may already have accepted the job. Refresh status before retrying. Confirmed missing queued jobs older than ten minutes are marked failed on status polling or the next submission. Redis outages do not unlock potentially running jobs. RQ failure/stop callbacks and status reconciliation mark failed/terminated jobs and release the lock. If Redis loses all job records while an operation is running, an operator must verify the worker has stopped before manually recovering the database lock; a timeout by itself is not proof that an import stopped.

## Download behavior and limits

The source is fixed to [CCP's documented static-data service](https://developers.eveonline.com/docs/services/static-data/). EQM reads the `sde` build from `https://developers.eveonline.com/static-data/tranquility/latest.jsonl`, then constructs the version-specific YAML URL. Requests cannot supply a URL, shell command or download destination. HTTPS certificate checks remain enabled and redirects are not followed. Metadata is bounded to 1 MiB; streaming downloads enforce the configured size ceiling and HTTP timeouts, while RQ bounds total job duration.

The worker writes a private operation-specific `.partial` file, checks size and ZIP integrity, rejects unsafe/encrypted/duplicate entries and missing core datasets, and checks uncompressed-size limits. It never extracts archive paths into the filesystem. The validated archive is atomically renamed to a versioned, operation-specific filename. Existing archives are preserved. SHA-256 records the downloaded bytes for later comparison; it is not a signature or a separately supplied CCP checksum. The receipt includes the exact source URL and metadata release date in the API response.

Ordinary errors remove the current partial file. Force-killing a worker may leave its partial file; after confirming that job is stopped, the operator may remove that specific file. Archives/job history are retained rather than automatically deleted: monitor disk use and manually archive/remove obsolete downloads when no import is using them. Each request downloads a new archive, even if CCP's build has not changed. CCP may cache its latest metadata for five minutes.

Imports retain the existing importer's dataset/batch commits. **A failed import can leave partially updated static data.** Inspect the error/logs and rerun the import; this is not a whole-database rollback mechanism. Download validation ensures archive integrity and the presence of core datasets, not every future SDE schema change.

## Host update/rebuild helper: design, not enabled

Application/server upgrades are a separate privilege boundary and are not implemented as web-executable commands in this pass. The proposed next step is a host-installed helper with a fixed checkout and Compose project, no user-supplied paths/refspecs/commands, and a narrow authenticated Unix-socket API. The app would request a named operation (status, prepare update, apply prepared revision, rebuild approved services), and the helper would return an operation ID, exact revision, stages and bounded logs. Authorization must be host-only with password reauthentication; the helper must independently authenticate requests and deduplicate operations. Preparation should fetch/inspect a fast-forward-only revision and prepare a database backup; applying schema migrations or restarting services needs a concrete review of that prepared plan, a maintenance window, health checks and a documented recovery path. Containers should never receive the Docker socket or general shell execution. Operators would install/configure the helper explicitly; an absent helper should leave update controls unavailable without affecting SDE maintenance.

## Verification

Tests use small synthetic ZIP archives and mocked HTTP/queue delivery, executing the actual worker function and importer. They cover admin/host boundaries, forbidden URL/path/command inputs, global overlap, duplicate delivery, download-only/import modes, bad ZIP/missing dataset/traversal/oversize/HTTP failure, preservation of existing archives, cleanup, queue uncertainty, failed-worker reconciliation/callbacks, agents-only failure, migration round trip and existing stored/processed totals. TypeScript and production build pass.

The original YAML ZIP browser checks used synthetic accounts and a mocked worker/CCP transport: queue/busy controls, progress polling, persisted completion after reload, filename/checksum receipt, selecting a downloaded archive, and automatic-import checkbox. That original ZIP validation did not perform a live SDE import, full production download, real Redis worker integration or host update; the separate HTTP-source validation is documented below. CCP's current metadata and archive HEAD response were checked read-only. [Screenshots](screenshots.md#sde-maintenance) use build 1234567 and a tiny test ZIP; the progress fixture deliberately pauses to make the running state visible.

## CCP HTTP SDE source (v2.4.2)

Under **Settings → SDE Maintenance**, choose **CCP SDE API (JSONL)**, then **Fetch and import full HTTP SDE**. This always queues a full fetch plus import through the established Redis/RQ worker. The API accepts no URL, release, destination or partial-section override (`POST /api/sde/http-import`, empty JSON object). The same administrator/host grant and one-operation database lock apply to HTTP, ZIP download and manual import alike. Selecting a source never silently queues work. YAML ZIP remains the initial/default choice; switch back for existing mounted paths and agents-only imports.

The worker reads `https://sde.evetech.net/tranquility/latest/` once per job, follows the expected release redirect, pins the manifest release ID and uses its exact JSONL links. CCP redirects those links to content-addressed blobs; only the same HTTPS origin and the exact blob version named by that manifest are permitted. Redirects to other releases, hosts, schemes or arbitrary paths are rejected before requesting them. TLS verification stays on. `httpx` decodes gzip once; wire Content-Length is not confused with decoded size. Per-table SHA-256 receipts describe staged decoded bytes, not a CCP signature.

Only 20 tables currently consumed by the full importer are fetched, with at most two concurrent requests. Required tables are validated before database writes: explicit named ID keys, duplicate fields/IDs, positions and importer-required types, blueprint inputs/products, dogma attributes/effects and PI inputs/outputs. PI's named `types` array is adapted to the existing keyed input. Large map tables remain file-backed streams rather than all being loaded into memory. Optional stars/planets/moons/belts/NPC-character tables retain the existing absent-table semantics; absent optional tables are disclosed. Named celestial exceptions and cached star positions survive; new stars with no position remain unknown.

Settings displays **job source, pinned release, build, validated-table progress, final totals, failure stage and last successful HTTP import**. Release IDs are tracked separately from builds: two releases sharing a build are distinct. A later failed job never advances the last-success receipt, though its pinned release is still shown for diagnosis. That receipt is historical and does not imply a later partial failure left the database fully consistent.

### HTTP limits, storage and recovery

`SDE_HTTP_MAX_BYTES` defaults to **4GiB decoded across all tables**, configurable from 1024 bytes to 16 GiB. Each table is capped at 1 GiB, each JSONL record at 8 MiB, the manifest at 2 MiB, redirects at four requests, connect timeout at 15 seconds and read timeout at 60 seconds. The existing RQ `SDE_JOB_TIMEOUT_SECONDS` bounds the whole job. Give the worker sufficient space under `SDE_DOWNLOAD_PATH` for staging and permit outbound HTTPS to `sde.evetech.net`; the API needs no new network path or write privilege.

Staged HTTP files are operation-specific and removed after ordinary success/failure; persisted job receipts retain release, table counts, sizes and hashes. Force-killing the worker may leave its private temporary directory: confirm that job has stopped before removing that specific directory. Existing ZIP archives are untouched. A release that expires mid-fetch fails as one batch; retry a **new full HTTP job**, which reads a fresh manifest. Files from different releases are never combined.

**Imports retain batch commits.** A failure during database import can leave partial data, so inspect the stage/logs and rerun the full import. Validation before writes protects against failed downloads and malformed inputs, not every possible database/storage failure. Never mark a failed release current or assume ZIP/download success updates a remote host.

### Upgrade and verification

Deploy matching **2.4.2 API, worker and frontend** after current maintenance jobs finish. This change needs no additional migration; installations coming from before 2.4.1 still need `0111_local_universe`. Select the new HTTP source explicitly and wait for a successful **import**, then check stored planet/star/type/recipe totals, a PI Scout planet and Navigation distance data. The existing local runtime SDE reads, live ESI routes and `2026-07-22` ESI compatibility date are unchanged.

Regression tests exercise real shared import upserts with paired schema-derived YAML/JSONL fixtures from selected fields of the pinned public CCP release `20261120T165826Z`; they cover hierarchy, planet type/radius, stars/cached positions, gates, stations, dogma, blueprints, PI and rerun stability. These fixtures are not a claim of full independent ZIP-release parity. Mocked transport/queue tests cover redirect/gzip/size/schema failures, expiry, same-build releases, permissions, overlap, retry and retained success receipts. Synthetic browser checks cover the actual Settings component, durable status display and 390px containment. [Release notes](releases/v2.4.2.md) record the separate real Redis/RQ/PostgreSQL validation and its limits. Production host rollout remains a separate operator step.

Reference: [CCP's HTTP SDE announcement](https://developers.eveonline.com/blog/the-sde-over-http-static-data-dynamically).

Real isolated integration passed on **20261120T165826Z / build 3724492**: two full live CCP HTTP imports through Redis/RQ into disposable PostgreSQL 16, with identical processed/stored totals on rerun and clean staging. A deliberate live fetch-size failure before writes left the database unchanged and did not advance the imported release. Verified Rifter, Jita station, gate destination, unknown star coordinates, PI Scout's Tanoo I diameter (10,120 km) and a Navigation distance from imported positions, with ESI access blocked during runtime checks. Imported 68,407 planets and 8,089 stars; processed 53,941 types, 658,480 type-dogma attributes and 19,303 blueprint activities. This validates the HTTP release and repeatability; it is not a full independent ZIP-release parity claim or a production-host rollout.
