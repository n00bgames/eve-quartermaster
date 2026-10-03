# HyperNet node position tracking

Open an offer under **Offers created** and use **Node position tracker**. The grid is available on active and ended offers. Positions are numbered from 1, left-to-right and top-to-bottom; in-game node codes are not stored.

1. Keep **Hide unavailable** off in EVE and choose the matching column count in EQM (four by default; two, eight, and sixteen are also available).
2. Choose **Mark seeded nodes**, then click your positions. Shift-click a second position to mark or clear a range. Gold cells are seeded.
3. Choose **Mark winning node** and click the winning position. Clicking it again clears the winner. A star and green outline identify the winner, including when it was seeded.
4. **Save node positions** persists the map. **Discard changes**, **Clear seeded positions**, and **Clear winner** support corrections. Clearing requires saving afterward.

The grid follows the offer's recorded capacity, up to 512 positions. Larger grids scroll without changing their column layout. Changing columns rearranges the same numbered positions; verify the map against the game before saving. Record comparable layouts in the same order. Without node codes, EQM cannot verify that the game's displayed ordering stayed the same between observations.

Maps do not change sold counts, seeded counts, offer status, reconciliation, or profit. Complete/reconcile the offer separately. Partial maps can be saved. A mismatch with the offer's seeded count or reconciled winner is shown beside the grid. Reducing an offer's capacity is blocked until recorded positions beyond the new capacity are cleared or corrected.

## History comparison

**Node position history**, beneath the seller offer list, uses all history belonging to the current user and selected character. Board status and text search do not restrict this sample. Offers with different capacities or column counts are separate groups.

- Winning-position counts include completed offers with a recorded winning position. Each such offer contributes one draw. Missing maps, missing winners, and non-completed records are reported separately.
- Seeded-position counts and seeded-win comparisons additionally require a full seed map whose count matches the offer and whose winner agrees with seller/external reconciliation. Partial and conflicting maps are excluded from this comparison but retain their winning-position observation.
- Expected seeded wins are the sum of `seeded nodes / total nodes` across eligible completed offers, assuming equally likely nodes. Expected wins at each position are `draws / total nodes` for that layout.
- Cell tooltips show winning counts, times seeded, and wins while seeded. The **Show** selector changes the heatmap between winning and seeded frequency.

These are descriptive counts, not evidence of a predictive advantage. Small samples, selectively recorded results, or inconsistent in-game ordering can create apparent patterns. Recording every completed result makes the comparison more useful.

## Storage and deployment

Migration `0082_hypernet_node_positions` adds `hypernet_offers.node_map` as nullable JSON. Existing records remain untracked. The owner-scoped `PUT /api/hypernet/offers/{id}/nodes` endpoint replaces the map and records before/after values in the audit log. Offer responses include the map; the summary includes position statistics. Unique integer positions must be within the offer capacity.

Rebuild backend and frontend together; backend startup applies the migration. Tests cover persistence, account and character isolation, ended-offer corrections, capacity guards, sample definitions, and migration upgrade/downgrade. Browser checks cover saving/reloading, error recovery, range selection, keyboard use, 512-node layouts, and mobile scrolling.
