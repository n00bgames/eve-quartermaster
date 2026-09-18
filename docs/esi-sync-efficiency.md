# ESI sync efficiency

The ESI facade now shares an HTTPX connection pool across characters within one
process/event loop. Authorization is supplied on individual requests; shared
client headers are never mutated. Cookies are not sent. A facade's `close()`
does not close connections used by other characters; FastAPI lifespan closes
the pool. Standalone async callers should call `close_esi_transport()` before
closing their loop.

Default maximum outbound concurrency is eight (`ESI_MAX_CONNECTIONS`, 1–32).
PI fetches up to four independent planet layouts at once; skills and skill queue
are fetched together. Fetch failures cancel and join siblings while preserving
the original HTTP exception. Character datasets and all associated database
writes remain sequential: existing handlers can hold transactions across network
awaits and insert shared type/location records, so parallelizing entire handlers
would risk database conflicts. Full parallel character sync needs a separate
fetch/apply design and is not enabled by this change.

## Limits and caching

- Learn route groups and budgets from `X-Ratelimit-*` response headers. Private
  budgets use application/character claims, so refreshing a token does not reset
  local accounting. Claims are only accounting hints, not an authorization check.
- Reserve 5% of the reported token allowance (`ESI_RATE_LIMIT_CUSHION`, .01–.25),
  including in-flight two-token requests. Small buckets reserve as much as they
  can while permitting a single successful request. Unknown routes have bounded
  concurrency but cannot be pre-budgeted until ESI supplies their first headers.
- Public requests use a conservative shared local budget. Public character/corp
  subroutes may initially be classified as private; ESI 429 responses still gate
  their observed buckets. This is not a complete OpenAPI-derived route registry.
- Pause all local requests when the legacy error allowance reaches five or on
  HTTP 420. Respect reset headers and `Retry-After` (seconds or HTTP date).
- Retry GET/HEAD only, at most three attempts, for 420/429/502/503/504. Do not
  automatically replay mutations or transport failures with uncertain outcomes.
- When a known bucket reaches its reserve, recovery is conservative: wait one
  reported window from the latest budget observation, rather than guessing which
  earlier server requests are about to expire. `Retry-After` sets an additional
  lower bound. This can pause longer than the server's earliest available token.
- Cache successful GET bodies only for ESI's max-age minus Age, or Expires; obey
  no-store/no-cache. No fabricated cache TTLs. At most 128 entries, each at most
  512 KiB. Private cache keys include a hash of the exact bearer credential;
  token rotations or scope changes cannot inherit a private cached response.
  Only listed public universe metadata routes share cached data across pilots.

Limits, cache and connection pool are **process/event-loop local**, not Redis
coordinated. They do not provide a combined budget across API replicas, RQ
processes or other apps sharing the egress IP. Keep the existing single API-worker
topology; distributed budgeting is needed before raising replica count or
running overlapping bulk ESI jobs in multiple processes. Existing background
activity remains subject to ESI's server-enforced limits.

## Validation and rollout

Run `python -m pytest -q tests/test_esi_transport.py tests/test_sync_freshness.py`
from backend. Transport tests use mock HTTP responses; they do not load ESI or
claim a measured live speedup. Regression checks should also include ESI scopes,
PI analytics/projection and contact sync access.

Backend-only rebuild, no migration or frontend build required. Do not restart
while a full sync is active: current bulk-job state is in memory. Compare real
sync duration and failures using the same character/dataset set after rollout.
Pooling removes repeated connection setup; gains depend on cache warmth, request
latency and database work. Deployment is separate from this local implementation.

References: [ESI rate limits](https://developers.eveonline.com/docs/services/esi/rate-limiting/)
and [HTTPX async client reuse](https://www.python-httpx.org/async/).
