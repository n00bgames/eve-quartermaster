# Private HyperNet analytics

Open **HyperNet analytics privacy** in the HyperNet Tracker or Analytics Platform. Each character starts disabled. Enable characters individually, enable all current characters, or disable analytics for the account. Account controls change the current switches; a newly linked character still starts disabled. Opting out hides analytics without deleting manual offers or bids.

Analytics appear only when the selected range contains non-draft offers or bids for an enabled character. Characters with no records, empty buying/selling datasets, and trends without valued results are omitted. Existing operational tracker summaries and item bid history remain available independently of these switches.

[HyperNet pause controls](hypernet-pause.md) separately block new EQM bid and offer records for a character or account. Pausing keeps existing opted-in analytics available and does not change analytics consent.

## Access

The server keys preferences by both authenticated user and character and restricts every query to the user's own offers and bids. There is no request parameter for another user, corporation rollup, admin override, shared snapshot, or public leaderboard. Changing the Analytics Platform's pilot/corporation/alliance selector does not change private HyperNet scope. Both preferences and analytics use `Cache-Control: private, no-store`.

Historical records remain eligible after a character is unlinked. Enabling a historical character includes only transactions owned by the requesting account. Consent cannot be inherited by another account that subsequently links the character.

## Metrics

- **Buying:** resolved wins/losses and win rate, resolved node spending, losing stakes, won item valuations, recorded net result and ROI, pending exposure, refunded spending, and expected versus actual wins. Pending, expired, and cancelled bids are excluded from win rates and ROI. Missing financial results are flagged; ROI is unavailable until those results are valued.
- **Selling:** completed draws, item quantities retained/lost, unknown winners, gross completed offer value, self-bought node spending, recorded selling result, completion rate, and active/expired counts. Completion rate uses completed, expired, and cancelled offers; drafts/invalid offers are excluded. Market dispositions replace the old offer result, rather than adding it twice.
- **Breakdowns:** character summaries, exact item types with ship filtering (SDE category 6), and monthly recorded results for buying and selling separately.

Won and retained items are valuations, not wallet receipts. Recorded selling results use the existing reconciliation and market-disposition accounting, including the acquisition cost entered by the user. Separate buying and selling datasets avoid presenting an aggregate cash profit that could count a retained/won item again after a relisting. This feature does not change offer prices, acquisition costs, or market values.

## Reporting periods

The choices are 7, 30, 90 days, 1 year, and **All-Time**. Resolved activity uses completion/refund dates, with entry dates as a fallback; unresolved activity uses entry dates. A recorded market sale uses its sale date. All-Time reads all available database records, including older imported history, without a ten-year cap or ESI lookback restriction. It cannot reconstruct history that was never stored or was deleted.

The Analytics Platform's period selector applies to its standard summaries, financial/planetary widgets, metric CSV/JSON exports, and private HyperNet analytics. Its ordinary permissions and financial privacy rules still apply. Private HyperNet data is not inserted into shared platform metrics or exports.

## Deployment and verification

Apply Alembic migration `0086_hypernet_private_analytics`, then rebuild/restart the backend and frontend together. The new preference table has a database default of false and is not backfilled with consent. No remote deployment is performed merely by building locally.

Regression tests cover opt-out defaults, character/account settings, new characters, account isolation even for staff, authentication/section access, empty datasets, refunds, corrections, dispositions, migration defaults, and All-Time SQL queries over history older than ten years. Browser verification covers settings, ship filtering, hiding after opt-out and stale responses, mobile overflow, and shared All-Time requests.
