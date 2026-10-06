# HyperNet node position tracking

Open an offer under **Offers created** and use **Node position tracker**. The grid is available on active and ended offers. Positions are numbered from 1, left-to-right and top-to-bottom. Node codes can be retained temporarily in a grid screenshot; they are not transcribed into the map.

1. Keep **Hide unavailable** off in EVE and choose the matching column count in EQM (four by default; two, eight, and sixteen are also available).
2. Choose **Mark seeded nodes**, then click your positions. Shift-click a second position to mark or clear a range. Gold cells are seeded.
3. Choose **Mark winning node** and click the winning position. Clicking it again clears the winner. A star and green outline identify the winner, including when it was seeded.
4. **Save node positions** persists the map. **Discard changes**, **Clear seeded positions**, and **Clear winner** support corrections. Clearing requires saving afterward.

The grid follows the offer's recorded capacity, up to 512 positions. Larger grids scroll without changing their column layout. Changing columns rearranges the same numbered positions; verify the map against the game before saving. Record comparable layouts in the same order. Without node codes, EQM cannot verify that the game's displayed ordering stayed the same between observations.

Maps do not change sold counts, seeded counts, offer status, reconciliation, or profit. Complete/reconcile the offer separately. Partial maps can be saved. A mismatch with the offer's seeded count or reconciled winner is shown beside the grid. Reducing an offer's capacity is blocked until recorded positions beyond the new capacity are cleared or corrected.

## Temporary grid screenshot

Before the offer ends, choose **Add grid screenshot** in the node tracker. Select one or multiple PNG, JPEG, or WebP files, or paste captures one at a time with Ctrl+V into the upload area. Drag across the grid (or adjust the crop percentages) for each capture. One saved image per offer can be replaced or removed.

For a grid that spans several screens:

1. Capture from top to bottom with **Hide unavailable** off. Keep the window size and column count unchanged; overlap one or two complete rows between captures.
2. Arrange the captures with the up/down buttons and crop away headings, toolbars, and surrounding UI. Cropped widths must match exactly. **Apply this crop to all captures** reuses the percentages when the same crop fits every capture.
3. Choose **Detect overlaps**. Matching compares native screenshot pixels locally in the browser. Flat gaps, repetitive backgrounds, and uncertain matches remain unresolved. You can enter the overlap in pixels for any join; this is the repeated height at the top of the next crop. Use `0` only if captures adjoin without repeating rows. Manual settings survive another detection pass; crop/order/removal changes clear alignments for review.
4. Choose **Preview combined grid** and check every dashed seam for duplicated or missing rows. Original-size preview supports scrolling. Seam guides are not embedded in the saved PNG. **Save combined grid** uploads only the composed grid after review. A single capture uses **Preview selected grid area** and **Save selected grid area**. Changing a crop, order, or overlap invalidates the preview; failed saves retain the draft for retry.

The grid is stored as lossless PNG without resizing or generating pixels. At each overlap, the earlier capture is retained and only new rows from the next capture are appended. **View at original size** provides scrolling when the image is wider than the screen. Each input is limited to 10 MB and 16 megapixels; up to 64 captures and 64 megapixels of source images can be loaded. The combined PNG is limited to 10 MB, 64 megapixels, and 32,767 pixels on either side. Oversized grids are rejected instead of silently degrading them; crop away more UI or capture with more columns. Existing blur or compression in the source cannot be recovered. Source screenshots remain local; only the reviewed PNG is sent to EQM.

After the draw, read the winning code from the image and select its corresponding position in the numbered grid. The reference is removed from the live record only once **both** the winning position is saved and the offer is **completed**, in either order. Unsaved winner selection does not delete it. Completing without a position keeps it available. Expired, cancelled, or invalid offers retain the reference until **Remove grid screenshot**; this removal asks for confirmation. Clearing a winner later does not recover a deleted image. Normal database backups retain their normal retention policy.

Screenshots are owner-only and loaded on demand through an authenticated endpoint with `Cache-Control: private, no-store`. Board responses contain only dimensions, byte count, and a version identifier. Image contents and source metadata are not included in audit logs.

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

Grid references additionally require migration `0085_hypernet_grid_reference`, following `0084_hypernet_market_sale`, and the Pillow backend dependency. Two nullable columns store metadata and deferred PNG bytes on the offer. `GET/PUT/DELETE /api/hypernet/offers/{id}/grid-reference` are owner- and permission-scoped. PUT accepts a raw PNG body and enforces a streaming 10 MB limit before decoding. The frontend proxy allows 10 MB API requests; any additional reverse proxy must permit that size too. Rebuild backend and frontend together. Deletion is transactional with completion/node edits; row locks serialize uploads and cleanup.

Multiple-capture stitching requires frontend and backend rebuilds together because the saved-grid pixel limit increased from 16 to 64 megapixels for tall 512-node grids. No additional migration or dependency is needed. `npm run test:hypernet` includes overlap detection, ambiguous matches, crop geometry, join bounds, and 512-node composition tests. Backend tests retain ownership/permission, metadata stripping, lifecycle cleanup, failed-upload preservation, and large-grid validation coverage.
