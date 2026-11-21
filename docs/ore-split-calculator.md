# Ore Split Calculator

Unreleased source follow-up after v2.4.1. No application version bump or published release is included.

Open **Mining Ledger → Ore Split Calculator**, paste one ore name and quantity per line, then choose a percentage. The panel starts collapsed. This is independent of Mining Ledger's dates, character filters, stored analytics and Mining Report exports.

Use the **Split percentage (%)** number field or the linked slider from **0% to 100%**. Both accept increments of **0.01%**. Presets are **5%, 10%, 15%, 20%, 25% and 50%**; the initial percentage is **15%**.

Each result shows the original quantity, **Cut off**, and **Remaining**, in whole units. Fractions round to the nearest whole unit, with exact half units rounded up. Remaining is calculated by subtracting the rounded cut from the original, so every unit is accounted for. Each ore type is rounded independently.

## Pasting and copying

Paste EVE's tab-separated item list, optionally including a `Name` / `Quantity` header and additional columns after quantity, or paste a name followed by a space and a quantity. For example:

```text
Compressed Brimful Coesite	100000
Compressed Coesite	20000
Zeolites	501
```

Tabs are preferred. Whole nonnegative quantities may contain correctly grouped commas or spaces, including nonbreaking spaces. Trailing backslashes copied from chat messages are accepted. Decimal, negative and abbreviated quantities are rejected. Repeated names combine case-insensitively before rounding; **compressed and uncompressed names remain separate**. Input order and the first name spelling are retained.

Malformed rows are identified by line number. Results and copy buttons remain unavailable until the entire list and percentage are valid. Up to 100,000 characters / 2,000 ore rows are accepted, with at most 30 digits per quantity. Integer arithmetic preserves quantities above JavaScript's safe-number range.

**Copy cut amounts** and **Copy remaining amounts** produce plain tab-separated ore names and ungrouped whole quantities, without a header. If clipboard access is blocked, a selectable text box provides the same output. Editing the list or percentage clears earlier copy feedback. **Clear ore list** removes the pasted list; collapsing the panel preserves it while the page remains mounted.

## Scope and verification

Calculation runs entirely in the browser, even when the ledger fetch fails. Pasted names and quantities are not saved, uploaded, priced, reprocessed or matched to SDE IDs. Changing Mining Ledger's filters does not alter the pasted list. No new API route, ESI scope, database migration or permission is added; the existing Mining Ledger page access applies.

Verification: 11 focused ore-calculator tests and the existing 5 Mining Report tests pass. Six browser groups exercise the actual MiningLedgerPage component with a synthetic API adapter: keyboard expansion, paste results, all presets, typed and slider percentages, invalid/empty values, rounding, duplicate aggregation, cut/remainder copy actions through a clipboard adapter, denied-copy fallback, independent calculations during a ledger error, and 390px layout. No new API calls occur during calculator interaction. TypeScript and the production frontend build pass with the existing large-chunk advisory.

[Desktop preview](../static/ss/v2.4.1/ore-split-desktop.png) · [Mobile preview](../static/ss/v2.4.1/ore-split-mobile.png) · [Capture provenance](../static/ss/v2.4.1/capture-receipt.json). Captures show unreleased source with synthetic quantities; no production account or private gameplay screenshot is used.
