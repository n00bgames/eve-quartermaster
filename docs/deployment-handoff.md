# EQM deployment handoff

Updated: 2026-09-11. Connection and checkout verified with read-only SSH commands.

## Remote access

On the configured Windows workstation, use `ssh eqm-server`. The existing SSH alias selects the dedicated deployment identity. Keep private keys, passwords, environment files, and private connection details out of Git. Full workstation connection details are in the local `D:\Codex\EVE\CHAT_HANDOFF.md`.

The verified remote Git checkout and active Compose working directory are **`/home/ubuntu/eqm/eve-quartermaster`**. Its parent `/home/ubuntu/eqm` is not a Git repository. The checkout uses `main`. Both production and development are now remote according to the user; a separate development checkout/service stack has not been identified, so do not assume an environment target from the alias alone.

The verified EQM services are `backend`, `frontend`, `postgres`, `redis`, and `worker`. Other applications share the host; scope operations to this checkout and Compose project.

## Update workflow

After the user requests deployment to the intended environment, connect and inspect the checkout:

```sh
ssh eqm-server
cd /home/ubuntu/eqm/eve-quartermaster
git status --short
git log -1 --oneline
```

Preserve any remote changes. For a clean checkout, use:

```sh
sh ./update-eqm.sh
docker compose ps
docker compose logs --tail=100 backend
curl --fail http://localhost:8000/api/health
```

The update script runs `git pull --ff-only` and `docker compose up --build -d`. The backend Dockerfile compiles `eqm-core` in its Rust build stage and installs it in the runtime image; no separate host Rust installation or binary copy is needed. Backend startup waits for PostgreSQL and runs `alembic upgrade head`. Updating frontend only would leave the new native PI commands unavailable.

Verify the application version, select a visible corporate station/Upwell hangar after corporation asset sync, compare inventory, and exercise the Production Calculator and green surplus rows. See [PI verification](pi-supply-and-production.md).

## Current release preparation

- Pushed implementation commit: `cb79eca70f2fa9fa5663f77407d596b7bdebba7f` (PI supply monitoring, Rust calculator, 1.0 preparation).
- Planned regular release: **v1.0 — The Bigger Slice of PI Release!** No beta/prerelease designation.
- Fitting Simulator is for informational purposes only, still in development, and not PYFA-complete.
- Remote checkout was clean at `003f4c5` when inspected on September 11. The new PI changes have not been deployed during this handoff update; recheck current state next time.
- GitHub publication/tagging remains separate from testing the pushed code on the remote server.

## HyperNet item bid history (1.0.6 development)

Rebuild backend and frontend together for the new `/api/hypernet/bid-history` endpoint and **Item bid history** window. No database migration or additional ESI scope is required. From a bid card/table or seller offer detail, open the window and select one character or All My Characters. Summary totals cover all owner-visible records for the exact item type; history pages contain up to 50 records. Pending and refunded/cancelled bids stay separate from settled spending, net result, win rate, and ROI. Winning results use recorded item valuations and do not imply cash realized from a later market sale.

Verify a known item with won/lost/pending/refunded bids, switch character scope, and page through history. Board search/status/outcome filters must not narrow item-history totals.

## HyperNet running outcome tallies (1.0.6 development)

Rebuild backend and frontend together; no migration or new scopes. The summary now includes `seller_outcomes`: quantities retained/lost and offer counts from completed draws classified by seller/external winner, plus the count of completed offers missing a known winner. Buying uses existing won/lost bid-record counts. Selling, Bidding, and Combined show separate tallies scoped to the selected character or All My Characters. These use full history independently of board search/status filters. Seller expired/cancelled/unresolved offers are excluded, including expired items later sold on the market; item loss is not a financial-loss classification. Verify a seller-won and outside-won offer (including stacked item quantities), a corrected winner, buyer won/lost/pending/refunded records, and both character and aggregate scopes.

## Future context windows

Read this document and the local `CHAT_HANDOFF.md` before deployment work. Check current Git and container state instead of treating dated snapshots as live status. The authoritative Windows publish repository remains `D:\Codex\EVE\_publish\eve-quartermaster-20260628-092452`; `D:\Codex\EVE` is a legacy tree, not an active Git repository or the running EQM server.

## HyperNet market dispositions (1.0.5 development)

Migration `0084_hypernet_market_sale` follows `0083_plex_tracker` and adds a nullable market-sale record to existing offers. Rebuild backend and frontend together. After an offer is recorded as expired, use **Record market sale**, verify gross/fees/net/lifecycle values, and confirm the expired card and seller lifetime totals reflect the lifecycle result once. Sale corrections and removal must persist after reload. No new ESI scope or SDE import is required. See [accounting and usage](hypernet-market-disposition.md). Remote deployment has not been performed by this change.

## PLEX Tracker (1.0.5 development)

Rebuild backend and frontend together and apply migration `0083_plex_tracker` through normal backend startup. Open **Finance & Trade → PLEX Tracker**, verify the global ESI bid/ask and history timestamps, then record a purchase and confirm it persists after reload. An unknown-basis opening holding must not produce a fictional profit. Public market requests require no new ESI scopes; user ledgers remain private under section permission `plex`. See [usage and accounting](plex-tracker.md). No remote deployment is implied by this note.


## Navigation distance widget

The System Distances & Warp Time addition requires migration `0080_system_distances` and backend/frontend rebuilds. Existing installations can select a system and use **Refresh ESI objects** to fill celestial positions; a full SDE reimport also populates planets, moons and belts. Verify the bottom Navigation widget, the acceleration/deceleration exclusion warning, and private structure access with the intended user. See [coverage and setup](system-distances.md).

## HyperNet node position tracking (1.0.5 development)

Rebuild backend and frontend together. Migration `0082_hypernet_node_positions` adds a nullable JSON map to `hypernet_offers`; normal backend startup applies it with `alembic upgrade head`. Existing offers start untracked and retain their financial results. No SDE fetch/import is needed for this feature.

After deployment, open an offer, mark seeded positions and a winner, save, and reload to verify persistence. Completed offers also allow map corrections. Reconcile an offer separately, then check **Node position history** on the seller board with the appropriate character selected. See [usage and sample definitions](hypernet-node-positions.md). This note does not assert that a remote deployment has occurred.

## HyperNet temporary grid references (October 3, 2026)

Rebuild backend and frontend together. Migration `0085_hypernet_grid_reference` follows `0084_hypernet_market_sale` and adds nullable metadata and PNG byte columns to offers. Backend requirements add Pillow 12.3.0. Existing offers need no image or backfill. The frontend Nginx API location now allows 10 MB request bodies; any outer reverse proxy must also allow 10 MB image uploads. Images are privately stored in the database, fetched on demand, and deleted transactionally once the offer is completed and its winning position is saved. No external OCR, image service, or upload directory is required. See [node tracking](hypernet-node-positions.md).

## Fleet Assignments (1.0.7 development)

Apply **0088_fleet_assignments** after 0087 and rebuild backend/frontend together.
No additional runtime dependencies or ESI scopes. The new **Fleet Assignments**
section defaults to ordinary member/view-only access; only Officer-and-above
roles can plan. Test create → add fitting → paste roster → multi-select/drag →
publish, then open the personal URL as two different member accounts. Each must
receive only assignments for its own currently linked characters. Confirm drafts,
archives, unresolved names, revoked links, and unrelated operation IDs do not
expose a roster. Save/load a preset and verify the new fleet has no pilots.
See [Fleet Assignments](fleet-assignments.md) for the access contract and future
Alliance Auth adapter boundary. Engagement outcomes/analytics are not part of
this first increment. This change has been implemented and tested locally;
remote installation and FRONT's AA integration remain separate steps.

## Intel Reports (1.0.7 development)

Apply migration `0089_intel_reports` after `0088_fleet_assignments` and rebuild backend/frontend together. The backend lifespan starts a database-leased public collector with resumable cursors and bounded retries. No new required secrets/scopes. Open Fleet & Community → Intel Reports as an authorized officer/director/admin/host; member recruiters also need section permission. Check an outsider character/corp/alliance without enrolling it, a page-limited collection, date-filtered systems/associates/evidence, profile history, and authorized versus denied private ESI. Private enrichment must not appear in the shared report response. Public ESI/zKill outages and partial coverage must stay visible. See [usage, retention, limits, and Alliance Auth boundary](intel-reports.md). This change has not been deployed.

## Quartermaster role

Rebuild backend and frontend together; no migration or new ESI scopes. Assign Quartermaster in User Administration and open Inventory & Industry → Quartermaster. Verify blueprint counts and nested locations, personal/corporate active jobs, and PI details across linked owners. Verify scoped Sync All progress and denied edit/general-sync requests and revoked/opted-out/unauthorized record exclusion. Corporate access probes use existing tokens and fail closed per feed. See [role access and validation](quartermaster-role.md). This change has not been deployed.

## Asset query and database connection recovery (2.0 development)

Prepared only; live deployment unchanged. See [pool settings, housekeeping scope, full-inventory snapshots and verification](database-connections.md). Backend/frontend/Compose must deploy together to enable the new response totals and Load all records UI. API pool defaults to 10 retained +20 overflow; worker 3+7; calculate combined process capacity before increasing replicas. Watchdog starts with API lifespan, scans tagged API connections every 60 seconds, and has a dry-run CLI. No database migration is introduced by this fix. The accumulated 2.0 migrations still apply when deploying that working tree.

## D-Scan (2.0 development)

Prepared in the working tree; not deployed by implementation. Rebuild backend/frontend together and apply **0092_dscan_reports** after 0091. Existing Local Scan rows default to report_kind=local; new d-scans use the same lifecycle table with kind=dscan. Lists, public reads and deletion are kind constrained. Verify SDE ship/group/category/mass coverage, the D-Scan Intel link for Intel Analyst, an anonymous public report/PDF, Local Scan isolation, scoped bulk deletion and selected-character destinations. D-scan analysis adds no private ESI scope. [Formats, limits and rollout](dscan.md).

## Unreleased report privacy / Industry Report rollout

Apply migration **0093_report_privacy** after 0092 and deploy the matching backend/frontend together. It adds user main identity and report privacy/dynamic/Battle expiry fields, and redacts legacy account labels. Named old reports resolve to current mains (Anonymous until selected); existing public visibility stays unchanged. Downgrade deletes private and Industry records before removing access-control fields, preventing older code from publishing them. See [full behavior and checks](report-privacy.md). No live deployment was performed for this implementation.

## Industry / Inventory split (unreleased)

Deploy matching backend/frontend after migration 0093; this split needs no additional migration. New private report kind `inventory` and section permission `inventory_reports` still require Assets access. Public Industry JSON/CSV/PDF always anonymize ownership and exclude unapproved general stock; pre-policy snapshots omit legacy stock and require regeneration. Dynamic selections are fixed owner/station/can or hangar choices and disable when unavailable. No ESI scope/collection changes. No deployment performed.

## Battle Report management (2.0 development)

Apply migration **0094_battle_report_corporation** after 0093 with the matching backend/frontend. Historic snapshots retain null corporation attribution; never infer it from battle participants. Verify own/private isolation, a director's attributed public reports, date-range review and a detailed PDF. [Scope, migration and tests](battle-report-management.md). This source update was prepared locally; it does not indicate a deployment.
