# Market sales after HyperNet expiration

An item can now remain attached to its expired offer when it is subsequently sold on the market. This records the money across acquisition, the failed listing, and liquidation while retaining the original HyperNet outcome.

## Recording the sale

1. Reconcile the offer as **Expired**, using the actual HyperCore cost and the correct recorded acquisition cost.
2. Open the expired offer and select **Record market sale** under **Item disposition**.
3. Enter the completed sale time, gross proceeds, sales tax, broker fee, any other sale fees, and an optional note. All amounts are **total ISK for the entire recorded quantity**, not percentages or per-unit prices. Partial dispositions are not supported.
4. Save. The offer remains **Expired**, and the item becomes **Sold on market**. The card and table show the lifecycle result.

**Edit market sale** corrects the same disposition instead of creating another sale. **Remove sale**, followed by confirmation, clears an incorrectly recorded disposition and returns the item to retained. It does not undo an in-game transaction. Costs can still be corrected through **Edit ended offer**, and the lifecycle result recalculates from them.

The sale must occur on or after the recorded expiration and cannot be in the future. If an expiration was recorded at the wrong time, correct it first. Subsequent expiration corrections cannot move it past the sale.

## Accounting

`Net sale proceeds = gross proceeds − sales tax − broker fee − other sale fees`

`Lifecycle result = net sale proceeds − recorded acquisition cost − actual HyperCore cost`

Expired seeded nodes are treated as refunded, so their purchase cost is not subtracted again. No HyperNet completion payout or completion fee is applied to the market sale. Actual recorded HyperCore cost is used when present, otherwise required cores × recorded unit cost is used.

For example, the supplied Vindicator sale has **856,600,000 ISK** gross proceeds and **64,245,000 ISK** sales tax, leaving **792,355,000 ISK** net. Its lifecycle profit requires subtracting the item's recorded acquisition and HyperCore costs; those costs are not inferred from the screenshot.

The original HyperNet `final_profit` remains available separately as **HyperNet result before disposition**. A market-disposed offer contributes its calculated lifecycle result **instead of** its old expired-offer result to seller lifetime and combined lifetime totals. It is never counted as both results. Offer completion/expiration counts and node research retain the original expired classification.

A manual HyperNet profit override does not change the calculated lifecycle result. Correct the acquisition/core/sale amounts to change that result. Any estimated acquisition basis remains an estimate; a market sale does not establish an unknown historical purchase price. This disposition covers the recorded acquisition and this offer's costs; it does not automatically link separate re-listings or other asset ledgers.

## Implementation and deployment

Migration **0084_hypernet_market_sale**, following `0083_plex_tracker`, adds a nullable `market_sale` JSON field to `hypernet_offers`. Existing offers are unchanged. Backend and frontend must be rebuilt together.

Owner-scoped `PUT` and `DELETE /hypernet/offers/{id}/market-sale` record corrections in the audit log. Amounts are validated decimal values stored as strings in JSON; lifecycle calculations use server-side Decimal arithmetic and the existing ISK rounding rules. Read APIs return the sale with its computed net proceeds and lifecycle result. Sale editing requires the existing HyperNet section permission and offer ownership. No ESI scope or market-order access is required; this remains manual tracking.
