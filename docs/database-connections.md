# Database connections and inventory loading

The asset timeout investigation found SQLAlchemy pool exhaustion at 5 retained + 10 overflow connections. The server's PostgreSQL ceiling was 100; later inspection found five healthy idle application connections, with no stuck transactions or blockers. Raising PostgreSQL max_connections was unnecessary for this configuration.

## Pool behavior

The API now retains up to 10 connections and opens up to 20 temporary overflow connections as demand rises (30 total per API process). Overflow connections close when returned. RQ uses a separate 3 + 7 pool tagged `eqm-worker`. Keep the sum across API processes, worker processes, watchdog connections, migrations and other clients below PostgreSQL's limit with headroom; these limits are per process, not deployment-wide. Recycle aged connections after 900 seconds and validate them on checkout. A 10-second pool wait returns HTTP 503 with Retry-After instead of an unexplained 500. PostgreSQL login timeout is five seconds.

Compose exposes the DB_* variables in `.env.example`. Direct development also reads the Settings fields from `.env`. Set DB_APPLICATION_NAME=eqm-worker for a standalone worker outside Compose. Recreate API and worker containers for pool environment changes.

## Periodic housekeeping

The API lifespan runs a watchdog every 60 seconds on a dedicated short-lived connection, so a full application pool cannot block it. An advisory lock prevents overlapping watchdog scans. Its scope is the current database and login, `eqm-api` tagged client backends only; it excludes itself, workers, untagged clients and migration sessions.

- Terminate abandoned idle-in-transaction sessions older than 300 seconds. PostgreSQL also enforces a 300-second idle-in-transaction timeout on new application connections.
- Cancel active SELECT statements older than 180 seconds, leaving their connection to roll back normally. Skip explicit advisory locks, pg_sleep and SELECT FOR UPDATE/SHARE. It never automatically terminates an active write, maintenance command, or ordinary healthy idle pool session. Age is a recovery threshold, not proof that a query is hung; configure it above expected legitimate read durations.
- Recheck database/login/application/state/age before each action. Log PID/action/outcome only. Failures retry next interval without leaking queries or connection credentials.

Inspect once without signaling any session:

```sh
docker compose exec backend python -m app.db.watchdog
```

Add `--apply` to act on eligible sessions. Set DB_WATCHDOG_ENABLED=false to disable periodic scans. DB_WATCHDOG_IDLE_SECONDS, DB_WATCHDOG_QUERY_SECONDS and DB_WATCHDOG_INTERVAL_SECONDS control the watchdog; DB_IDLE_TRANSACTION_TIMEOUT_SECONDS controls PostgreSQL's independent idle timeout. Connection recovery is only useful alongside fixing queries and releasing sessions promptly.

## Asset inventory

Normal item/owner searches filter in SQL, calculate matching row/quantity/type totals in the database, then load only one page. Owner visibility is resolved once for the query, including combined account roles. Category/subtype filters reuse the existing item classification rules. Computed container-location and named hangar sorting/filtering retain their existing Python semantics after SQL narrows candidates; these can still require loading the matching candidate inventory.

**Assets → Load all records** clears view filters and retrieves every record allowed by the existing visibility rules. It displays overall stack rows, units and distinct item types, keeps table rendering paged, and filters/sorts the loaded snapshot locally. The totals above the table follow active filters; the snapshot line retains overall totals. **Refresh all records** replaces the snapshot; **Use server paging** releases it and resumes fresh server queries. This is a snapshot, not a continuous sync. It does not expand permissions or pull additional ESI data.

Search input is debounced 250 ms and obsolete fetches are aborted. Browser cancellation does not guarantee cancellation of already executing server SQL; the SQL paging change bounds the usual search work. The deliberate full snapshot has a 120-second request budget, while ordinary requests retain their usual timeout.

## Verification and rollout

The exact screenshot search over 45,074 live asset records took 1.902 seconds with the old full-hydration path and 0.058 seconds with the new SQL path in sequential read-only checks, both returning zero matches. These were idle snapshots, not a concurrency load test. The watchdog dry run found zero eligible sessions. No live session was canceled or terminated and no database configuration or deployed application was changed during validation.

Backend/frontend and Compose changes are prepared in the unreleased 2.0 working tree. Deploy them together when requested; do not deploy this tree accidentally as a database-only hotfix. No schema migration is added by this fix, although the accumulated 2.0 changes have their own migrations.
