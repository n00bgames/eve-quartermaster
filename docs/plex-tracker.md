# PLEX Tracker

Open **Finance & Trade → PLEX Tracker** (`#plex`). This module combines a private, manually maintained PLEX inventory with public ESI market data. It plans purchases and future sales of ordinary PLEX; it does not place orders, synchronize wallet purchases, or create futures contracts.

## Prices

CCP's [global PLEX market announcement for developers](https://developers.eveonline.com/blog/global-plex-market-and-sde-updates) specifies region **19000001**. The module queries that region with PLEX type **44992**, using the existing paginated ESI client and transport. It never substitutes Jita prices or ESI's adjusted item valuation.

- Highest buy offer: the best displayed bid, potentially available when selling immediately.
- Lowest sell listing: the cheapest displayed ask, potentially available when buying immediately.
- Quantities at the best prices and the bid–ask spread provide context; prices exclude fees. Neither best price guarantees a fill for an entire holding, especially when order conditions or market depth limit execution.
- Daily traded averages, lows, highs and volume are available for up to 90 returned days, with 7/30/90-day views. They are separate from current bids and asks.

Public prices are fetched on page load and **Refresh**, cached in the database for five minutes; daily history is cached for an hour. Upstream ESI caching can also apply. Timestamps indicate EQM's successful fetch time. Failed refreshes preserve and label the last good snapshot; without a snapshot, quotes stay unavailable. Ledger operations do not depend on ESI availability. No additional character scopes or token are needed for public prices.

## Record inventory

All records belong to the signed-in EQM account, across its pilots. The section's permission is `plex`; administrative roles cannot use the ledger API to read another account's entries. Notes can identify a pilot, source, pack, bonus, or estimated valuation.

- **Purchase**: quantity, completed price per PLEX, and total acquisition fees in ISK.
- **Opening holdings / gift / pack**: inventory already owned or acquired outside an ISK market purchase. Leave ISK basis blank when unknown. Zero explicitly means zero cost. Include bonus PLEX in quantity if allocating a known total cost across a pack. An entered replacement valuation is a user estimate and should be identified in the notes.
- **Sale**: completed price per PLEX and total sale fees/taxes in ISK.
- **Spent / converted**: removes PLEX used for Omega, HyperCores, gifts, or other uses. There are no proceeds and consumed cost is not counted as a realized trading loss.

Fees are total amounts for a recorded transaction, not percentages. Entry times are local in the browser and stored with UTC offsets. Transactions must have already occurred. Edits and deletion recalculate the whole ledger; changes that would oversell inventory at any historical point are rejected. Same-time entries are ordered by their saved IDs, with new entries following existing ones. Mutations are serialized per account on PostgreSQL.

## Calculations

The ledger uses FIFO: oldest acquisition lots are consumed first, including acquisition fees allocated per PLEX. Sale profit is gross proceeds minus actual sale fees minus the FIFO basis of the sold PLEX. Decimal arithmetic is used on the server; output ISK values are rounded to cents.

Unknown cost is preserved. A sale touching an unknown-cost lot has unknown profit; the total realized profit is also unknown, with the sum of known-profit sales shown separately. Remaining holdings display unknown total basis while any unknown-cost PLEX remain. Opening holdings do not count as a new cash purchase in trade cash flow.

The planning calculator can model selling all tracked holdings or a hypothetical new purchase. Blank entry and exit prices use the displayed ask and bid respectively. Enter the combined selling fee/tax percentage; the default is explicitly zero, and no skills or fee schedule are inferred. Break-even is total basis divided by quantity and by `(1 − fee rate)`. Scenario results are estimates and are not saved as transactions. Unknown basis suppresses profit and break-even.

CSV export contains only the current account's recorded ledger, including computed FIFO basis and realized profit. Notes that could be interpreted as spreadsheet formulas are escaped.

## Deployment and validation

Rebuild backend and frontend together. Migration **0083_plex_tracker**, after **0082_hypernet_node_positions**, creates `plex_transactions` and `plex_market_cache`. No SDE reimport is needed.

Regression coverage in `backend/tests/test_plex_tracker.py` covers FIFO fees, partial sales, consumption, unknown and explicit zero basis, chronology, validation, mutation rollback, ownership, permissions, market sides, global region selection, caching/failure fallback, history ordering, and migration upgrade/downgrade. Browser checks exercise recording/editing/deletion, retained form inputs on rejection, scenario arithmetic, history selection, market errors, CSV UI, and mobile layout. Live remote deployment remains a separate operation.


## Wallet screenshot import (v2.4.3 update)

Open **Finance & Trade → PLEX Tracker → Import wallet screenshot**. Paste an image into the screenshot area with Ctrl+V or select a PNG, JPEG or WebP. Drag over the complete wallet **market transaction** rows, including UTC date/time, quantity, PLEX and unit price, then scan. English tables are supported; wallet journal entries, PLEX Vault transfers, fees-only rows, contracts and orders are not converted into market trades.

Recognition uses the existing self-hosted Tesseract worker in your browser. It needs no API key; the wallet image and raw OCR text are never sent to the backend. Only selected, reviewed trade fields are saved to your own EQM account. Limits: 10 MB, 16 megapixels per input; a four-megapixel recognition canvas; 90-second timeout; 200 trades per batch. Only visible dated PLEX rows can be detected. Repeat for additional screenshots, and compare the detected row count with the source. Tiny fonts, localized numbers, partial rows and OCR errors may need manual correction. Text input is also available under **Recognized text / paste wallet rows**; rebuilding replaces the review.

Confirm **Purchase** or **Sale** for every row. Colour alone never determines direction. The bulk direction selector applies to selected rows, and individual dropdowns handle mixed screenshots. Verify the UTC timestamp, whole PLEX quantity and **ISK per PLEX** (not the total transaction value). Review prices as full numbers without thousands separators. Date fields remain UTC even when the surrounding ledger displays local time. If a screenshot omits seconds they become `00`; equal timestamps retain review order, after previously saved equal-time entries. Correct timestamps where necessary instead of guessing missing chronology.

Fees default to **0 ISK**. The market transaction table does not supply all broker fees and taxes; enter their totals separately for accurate profit. Review the fields, then check the confirmation box and import. Changing a row clears confirmation. Selecting another image, changing its crop or scanning again clears the previous review.

Possible duplicates match UTC minute, direction, quantity and unit price against this account's existing ledger and the batch; fees and notes do not change that comparison. Recognized matches are deselected when direction is known. Other matches are flagged once direction is selected. Leave those rows unchecked, or explicitly choose **Possible duplicate: import anyway** for legitimate identical trades. This is a conservative warning, not a unique EVE transaction ID. The server checks again under the account mutation lock; a conflict saves none of the batch. After an uncertain network outcome, refresh the ledger before retrying; an explicit duplicate override can intentionally create another matching entry.

The import endpoint saves the whole batch atomically, oldest first, and validates chronological FIFO inventory. An oversell saves nothing and leaves the review available for correction. Add earlier purchases or opening holdings first when importing sales from an incomplete history. Deploy matching frontend and backend for this feature; no migration, additional dependency, ESI scope or API key is required.

Validation: five parser test groups, 30 backend PLEX tests, TypeScript, production Vite build and nine actual Edge workflow groups, including real self-hosted OCR on a synthetic mixed-colour wallet image and the actual API against isolated SQLite. This does not certify OCR on a real user's screenshot, PostgreSQL concurrency or live ESI. [Development UI captures](screenshots.md#plex-wallet-screenshot-import).
