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
