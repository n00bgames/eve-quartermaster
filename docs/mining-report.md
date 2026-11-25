# Mining Report exports

Unreleased EQM **2.4.1** frontend addition. Open **Mining Ledger**, choose a date period and optional **Character**, **System** and **Operation** filters, then select **Apply**. The **Mining Report** panel above the summary cards provides **Export Mining CSV** and **Export Mining JSON**.

From and To include both selected UTC ledger dates. Leave either blank for an open-ended period. Changing any filter disables export until that selection loads successfully; loading and failed refreshes also block stale downloads. A late response from an earlier selection cannot replace a newer report.

## Included analytics

- Selection totals: recovered and residue quantities; gross quantity; recovered, residue and gross volume in m³; estimated recovered, residue and gross value in ISK; measured efficiency; total gross volume covered by residue measurements.
- Every returned day, ore, character and system breakdown. Exports include the entire filtered analytics result, beyond the ledger's current page and the charts' last-31-day/top-ten display limits.
- Applied filter IDs/names, inclusive date semantics, matching ledger-row count, first/last recorded day, recorded-day count, application/schema versions, export time and time the report data was loaded from EQM.

JSON uses the versioned `eqm.mining-report.v1` schema with `totals`, `by_day`, `by_ore`, `by_character` and `by_system`. CSV is one UTF-8 file with a byte-order mark and a `section` column: a `totals` row followed by those four breakdown sections. Metadata repeats on each row. Numeric column names state units, stored precision is retained, and text is quoted and protected against spreadsheet formula interpretation. Filenames include the selected date period and UTC export timestamp.

Unmeasured efficiency remains **null in JSON** and **blank in CSV**; a measured zero stays zero. Per-group measured gross volume is unavailable from the existing API and stays blank in CSV; the selection total is included. Empty selections still export metadata and zero totals with empty breakdowns. Missing days are not filled with fabricated zero observations.

## Meaning and access

Values come from EQM's retained ledger and existing authorized analytics response. The report does not request fresh ESI data or current market prices. Stored ISK estimates are not realized profit. Efficiency covers imported residue measurements; absent residue can understate gross extraction. The loaded-from-EQM timestamp records the report fetch, not the last ESI sync.

Exports explicitly project analytics and selected-filter metadata. They omit raw ledger entries, operation notes, the full character roster, credentials and unrelated payload fields. Existing Mining Ledger permission, character visibility, opt-out, date and operation filtering remain server-enforced. No new endpoint, migration, consent scope, background collector or public share is added. Deploy the updated frontend to make these actions available on a running installation.

## Synthetic development previews

Actual MiningLedgerPage rendered in a local preview with fabricated pilots, operations and extraction data; no production account or user screenshot was used. Browser verification covers actual CSV/JSON downloads, date and combined filters, pagination independence, pending/failed/overlapping requests, empty ranges and 390px layout. The preview uses a synthetic API adapter, not a live server or full authenticated application.

![Mining Report exports and selected period — synthetic desktop preview](../static/ss/v2.4.1/mining-report-desktop.png)

![Mining Report actions — synthetic mobile preview](../static/ss/v2.4.1/mining-report-mobile.png)

Capture provenance: [receipt](../static/ss/v2.4.1/capture-receipt.json).

## Day drill-down (v2.4.4 follow-up)

Click a day in **Yield over time** to switch to **Hourly activity** and apply that UTC date to the summary cards, ore composition, pilot rankings, system extraction, ledger history and Mining Report. Keyboard users can focus a day and press Enter or Space. Character, System and Operation retain the filters already applied to the visible graph. **Back to date range** restores that previous range and its filters, starting on page one. Editing and applying another date range returns to the daily graph.

The hourly view shows all 24 UTC hours. **ESI only supplies daily totals**, so it cannot reconstruct actual historical hourly mining. Bars group stored imported ledger totals by their recorded timestamp hour; a stored row can summarize a whole day's extraction, so these bars are **record-time buckets, not measured mining rates**. ESI rows, missing timestamps and timestamps inconsistent with the row's UTC ledger date stay in **Hour not recorded**. Untimed volume still contributes to all day totals and rankings. Empty hours do not establish zero mining.

Single-day API responses add `analytics.hourly` with `day`, `timezone`, `basis`, `by_hour`, `untimed`, `timestamped_rows` and `untimed_rows`. JSON reports add an optional `hourly` object; CSV adds `by_hour` and `untimed` sections with provenance metadata. All analytics are calculated before ledger pagination. Exports remain blocked while selection changes are pending or a request fails; a failed selection retains the previous data under its previous label.

Requires matching API and frontend builds. No database migration, new scope, historical backfill or hourly collector. Saved operation and settlement management retain their existing behavior.

These actual UI captures use an isolated synthetic SQLite database and the real Mining Ledger API in Microsoft Edge. They were captured on version 2.4.4 plus the then-unreleased changes, without real pilot data, live ESI or the full authenticated application bootstrap. Verification covers click/back navigation, combined filters, keyboard selection, pagination, downloaded reports, request failure/retry, ESI-only days, empty ranges and mobile layout.

![Hourly Mining Ledger and day analytics — synthetic development preview](../static/ss/v2.4.4/mining-hourly-drilldown.png)

[Daily view](../static/ss/v2.4.4/mining-daily-drilldown.png) · [Mobile hourly view](../static/ss/v2.4.4/mining-hourly-mobile.png) · [Capture receipt](../static/ss/v2.4.4/capture-receipt.json).
