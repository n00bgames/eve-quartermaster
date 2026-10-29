# SDE maintenance from Settings

Unreleased EQM 2.0.0 feature. Available to administrators and hosts, including aggregate roles whose base grants administrator access.

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

Actual browser checks use synthetic accounts and a mocked worker/CCP transport: queue/busy controls, progress polling, persisted completion after reload, filename/checksum receipt, selecting a downloaded archive, and automatic-import checkbox. No live SDE import, full production download, real Redis worker integration or host update was performed. CCP's current metadata and archive HEAD response were checked read-only. [Screenshots](screenshots.md#sde-maintenance) use build 1234567 and a tiny test ZIP; the progress fixture deliberately pauses to make the running state visible.
