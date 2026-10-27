# Intel Reports

Intel Reports is a restricted staff workspace for investigating EVE characters, corporations, and alliances without enrolling outside characters into EQM. Open **Fleet & Community → Intel Reports**. Paste one name or zKill entity URL per line, resolve the names, and choose the intended match if the same name identifies more than one entity. Saved dossiers and `#intel/{id}` links still require authentication and Intel Reports access.

## First version

- Public ESI identity, current character affiliation, character employment history, corporation alliance history, and public alliance member corporations.
- zKill discovery for kills and losses, with canonical public ESI killmails stored once in the existing killboard tables.
- Selectable UTC date ranges; observed PvP kills/losses, ships, systems, regions, UTC hours, and daily activity.
- Repeated co-attacker characters, corporations, and alliances, including shared kill counts, distinct days, estimated engagements, and sampled source links. Historical affiliation comes from each killmail.
- zKill character indicators: LOGI, BLOPS, CAPITAL, SUPER, TITAN, CYNO, AWOX, ALLIANCE AWOX, FACTION AWOX, GANKER, FC and BAIT when upstream fields support them. ROOKIE is separately identified as EQM applying zKill's presentation rule to its public counters and birthday.
- Subject-specific smartbomb evidence: confirmed kills, percentage of observed PvP kills, and weapon metadata coverage. A local **Frequent Smartbomber** indicator requires at least five confirmed kills and at least 20% of observed kills in the selected report window.
- Change-only public profile/badge observations, collection history, and restricted analyst notes.
- A separate, permission-checked Authorized ESI tab for available cached skills/SP, queue, saved fitting templates, and applicant verification. Authorized refresh reuses EQM's existing sync services.

The module presents evidence for a human review. Shared attacker appearances do not prove shared fleet membership, identity, intent, or a formal coalition. Recorded combat locations are not current locations or verified home systems. Missing evidence is unknown, not a safety finding.

## Collection and coverage

**Collect public history** starts a durable database job from the chosen start date through the current time. The report end date filters retained evidence independently. The default collection depth is ten pages per kills/losses feed, with an explicit range of 1–100 pages and up to 200 entries per zKill page. The queue permits one active job per subject and at most 100 active jobs overall.

Jobs checkpoint their feed/page, retain progress across page failures, and use database leases so another backend process can recover expired work. Cancelling prevents new writes after ownership is lost. Automatic retries respect upstream backoff and stop after three consecutive failures at a checkpoint; interrupted jobs can resume. A finished page-limited job is **partial**, and a new, deeper collection can extend its retained history. A completed fetch is not a claim that zKill contains every killmail.

The backend lifespan runs the collector. No external scheduler or new user automation is required. zKill requests have a descriptive user agent and gzip support and are spaced within each backend process. Page discovery references and compact zKill flags are cached for an hour; statistics for ten minutes, public character identity for an hour, and other identity for a day. Metadata fallbacks are cached for thirty days. Multiple backend processes share database leases and the page cache, but the outbound pacing gate is process-local; large deployments should use a shared upstream limiter.

Reports analyze the newest 10,000 retained killmails within the requested window, with a 250,000-attacker budget. Whole unfilled batches are excluded rather than analyzing incomplete participant lists. Caps and observed coverage are disclosed. Responses contain the top 50 associates per entity kind, top 100 ships/systems, the 200 newest evidence records, up to ten recent evidence links per ranking, the latest 20 collection attempts, and the latest 30 public change observations. Metadata lookup is bounded per collection: 150 types, 50 systems, and 900 names; unresolved IDs remain visible. Large corp/alliance reports may need deeper collection and subsequent metadata passes.

NPC-only killmails remain identifiable in evidence but do not contribute to the PvP summaries. Smartbomb detection uses the subject's own recorded attacker weapon, classified by SDE group 72; another attacker's weapon cannot tag the subject. An attacker row records one weapon and is not a full weapon-use history. Saved fitting templates do not prove what a pilot flew.

Badges retain zKill's own rolling windows and do not change with EQM's report dates. Ship-role appearances use 90 days; cyno and other character indicators use their documented yearly windows. CYNO means a fitted cyno was lost, not that it was lit. Badge semantics follow the [zKill FAQ](https://zkillboard.com/information/faq/) and its [public badge presentation source](https://github.com/zKillboard/zKillboard/blob/master/templates/components/info_top_image.pug). Transport behavior follows the [zKill API documentation](https://zkillboard.com/api/docs/). Unknown future indicator fields are not guessed.

## Authorization boundary

Intel Reports requires section permission `intel_reports` and Officer-or-higher role or Recruiter capability. Its default section roles are Admin, Director, and Officer; existing host behavior remains in force. A member recruiter also needs an explicit Intel Reports section grant. Applicants and anonymous/deleted users cannot enter the workspace. Analyst notes and dossier URLs are staff-only.

The public adapter never receives an EVE access token. Tracking an outsider creates an `IntelSubject`, not an `EveCharacter` enrollment. Killmail hash discovery enables the public ESI killmail read without the subject's SSO consent.

Private enrichment is evaluated for every request and never written into public subject data, observations, collection jobs, or public report responses. It requires a currently owned EQM character, an unrevoked token belonging to its current owner, sync enabled, and the relevant grants. Regular access follows existing character-detail and dataset section permissions; it does not give an officer access to another officer's private data. Recruiter access requires an eligible application and verified/stale linked-character verification; its scopes are intersected with recorded applicant consent. Withdrawn/declined applications do not provide recruiter access. Revocation, ownership changes, opt-out, and missing scopes block enrichment. Successful private reads/refreshes are audited without copying private payloads. Responses are `Cache-Control: private, no-store`.

This first increment exposes only skills/SP, queue, saved fitting metadata, and verification status where authorized. It does not yet include private wallets, transactions, assets, contracts, contacts, mail, or complete application answers. Applicant-only sync may provide total SP without a detailed cached skill list. An authorized but never collected dataset is labelled separately from a collected empty dataset. No additional ESI scope is silently requested.

## Storage and Alliance Auth portability

Migration `0089_intel_reports` follows `0088_fleet_assignments` and adds `intel_subjects`, `intel_observations`, `intel_collections`, `intel_source_cache`, and `intel_notes`. Canonical killmail JSON and participants reuse the existing shared killboard store, so overlapping character/corporation/alliance investigations do not duplicate full killmails. Page caches contain discovery IDs/hashes, timestamps, and small zKill flags. Public changes are fingerprinted and stored only when content changes. Associations are computed from retained facts on demand; no permanent all-pairs graph is built.

The framework-independent `backend/app/domain/intel.py` contains the entity parser, indicator rules, evidence calculations, `PublicIntelSource` protocol, and an immutable principal contract. Responses use `schema_version: eqm.intel.v1`. The React feature lives under `frontend/src/features/intel` and accepts an injected API client rather than EQM credentials or roles.

The current HTTP, persistence, worker, and permission adapters are EQM-specific. Porting to FRONT's Alliance Auth will require Django models/migrations, a Celery task adapter, Alliance Auth permission and verified character/token ownership mapping, and a private enrichment adapter that checks Alliance Auth's token grants. Reuse the domain calculations, source contract, response shape, and React view. The principal contract describes that boundary; it does not itself authorize current EQM requests. A working Alliance Auth plugin has not been implemented by this increment.

## Deployment and validation

Rebuild backend and frontend together and apply `0089_intel_reports` through normal backend startup. No new secrets or required ESI scopes. A populated SDE improves ship/weapon/geography metadata immediately; bounded public metadata lookups provide fallbacks.

Check an external character, corp, and alliance; ambiguous pasted names; date windows; limited collection coverage; interrupted retries/cancel; co-attacker evidence; and denied versus permitted private enrichment. The automated suite `backend/tests/test_intel_reports.py` uses synthetic sources and databases, not production records. Local browser verification also uses synthetic data. Live collection completeness depends on upstream availability, page depth, and zKill coverage.
