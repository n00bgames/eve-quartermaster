# Market sales after HyperNet expiration or winning the item back

An item can remain attached to its ended offer when it is subsequently sold on the market. This supports expired listings and completed offers where the seller won the item back. It records money across acquisition, the HyperNet listing, and liquidation while retaining the original draw outcome.

## Recording the sale

1. Reconcile the offer as **Expired**, or as **Completed** with **Seller won item back**. Record the acquisition and actual HyperCore costs; for completed offers, also record the actual payout and final seeded nodes.
2. Open the ended offer and select **Record market sale** or **Mark won-back item as sold** under **Item disposition**.
3. Enter the completed sale time, gross proceeds, sales tax, broker fee, any other sale fees, and an optional note. All amounts are **total ISK for the entire recorded quantity**, not percentages or per-unit prices. Partial dispositions are not supported.
4. Save. The offer keeps its **Expired** or **Completed** status, and the item becomes **Sold on market**. The card and table show the lifecycle result; seller summaries and opted-in private analytics use that result too.

**Edit market sale** corrects the same disposition instead of creating another sale. **Remove sale**, followed by confirmation, clears an incorrectly recorded disposition and returns the item to retained. It does not undo an in-game transaction. Costs can still be corrected through **Edit ended offer**, and the lifecycle result recalculates from them.

The sale must occur on or after the recorded offer outcome and cannot be in the future. Correct an incorrect reconciliation time first. Later corrections cannot move the outcome past the sale. To change a completed offer's winner to an external participant, remove its recorded market sale first; external-winner and unresolved offers cannot record a disposition.

## Accounting

`Net sale proceeds = gross proceeds − sales tax − broker fee − other sale fees`

For an expired listing:

`Lifecycle result = net sale proceeds − recorded acquisition cost − actual HyperCore cost`

Expired seeded nodes are treated as refunded, so their purchase cost is not subtracted again. No HyperNet completion payout or completion fee is applied to the market sale. Actual recorded HyperCore cost is used when present, otherwise required cores × recorded unit cost is used.

For a completed listing won back by the seller:

`Lifecycle result = HyperNet payout + net sale proceeds − seeded-node spend − recorded acquisition cost − actual HyperCore cost`

The actual recorded payout is used, including any completion fee already deducted. If no payout was recorded, it falls back to the offer's total price less the 5% completion fee. Seeded-node spend is calculated from the final seeded count and total offer price divided by total nodes. The sale replaces any retained-item market valuation; neither that valuation nor a manual final-profit override is added to the sale result. Acquisition and HyperCore costs are deducted once. Use the recorded acquisition basis, including 1 ISK if that is the user's assigned basis for a previously paid-for item.

For example, the supplied Vindicator sale has **856,600,000 ISK** gross proceeds and **64,245,000 ISK** sales tax, leaving **792,355,000 ISK** net. Its lifecycle profit requires subtracting the item's recorded acquisition and HyperCore costs; those costs are not inferred from the screenshot.

The original HyperNet `final_profit` remains available separately as **HyperNet result before disposition**. A market-disposed offer contributes its calculated lifecycle result **instead of** its old offer result to seller lifetime, completed-offer averages, combined lifetime totals, and private selling analytics. It is never counted as both results. Offer completion/expiration counts and node research retain the original classification; a seller-winning draw stays a seller-winning draw after liquidation.

A manual HyperNet profit override does not change the calculated lifecycle result. Correct the acquisition/core/sale amounts to change that result. Any estimated acquisition basis remains an estimate; a market sale does not establish an unknown historical purchase price. This disposition covers the recorded acquisition and this offer's costs; it does not automatically link separate re-listings or other asset ledgers.

## Implementation and deployment

Migration **0084_hypernet_market_sale**, following `0083_plex_tracker`, adds a nullable `market_sale` JSON field to `hypernet_offers`. Supporting seller-won completed offers reuses that field and requires no additional migration. Existing sale records are unchanged. Backend and frontend must be rebuilt together.

Owner-scoped `PUT` and `DELETE /hypernet/offers/{id}/market-sale` record corrections in the audit log. Sale changes and reconciliation corrections lock the offer row to prevent conflicting outcome changes. Amounts are validated decimal values stored as strings in JSON; lifecycle calculations use server-side Decimal arithmetic and the existing ISK rounding rules. Read APIs return the sale with its computed net proceeds, payout, seeded spending, and lifecycle result. Sale editing requires the existing HyperNet section permission and offer ownership. No ESI scope or market-order access is required; this remains manual tracking. HyperNet recording pauses leave this correction workflow available.
