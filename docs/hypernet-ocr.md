# HyperNet participant screenshots

Open an active offer, find **Add progress snapshot**, and choose **Import participants from screenshot**.

1. Open the importer and immediately press **Ctrl+V** (**⌘V** on Mac), or choose a PNG, JPEG or WebP file. You can also paste an image directly into the Participants field to open the importer; ordinary text still pastes normally. Files are limited to 10 MB and 16 megapixels.
2. Drag a rectangle around the participant list and the HyperNode counts beneath the names. Portraits and the participant heading can be included; exclude node tickets and unrelated panels. Percentage inputs provide keyboard-accessible crop controls; **Use full image** resets the selection.
3. Choose **Scan selected area**. The English OCR engine loads only when scanning starts. Images are processed locally in the browser, with all engine/language files supplied by EQM.
4. Review the extracted `name | nodes | optional seeded` lines. Correct character names and seller flags. OCR can confuse similar letters, particularly through EVE's transparent windows. Raw recognized text is available for inspection. Empty/unrecognized scans leave the original participant field untouched.
5. Choose **Use reviewed participants**. Existing names are matched case-insensitively and their cumulative counts are replaced, not added. Other participants remain in the field, so additional screenshots can extend a scrolled list.
6. Check **Nodes sold**, **Seeded nodes**, and **Unique participants**, then **Save snapshot**. Import does not infer whole-offer totals from a possibly incomplete screenshot or submit anything automatically.

OCR is a transcription aid, not an ESI import or verification of the in-game offer. Each screenshot covers only the visible names. Review duplicate/misspelled names before merging; a spelling difference can produce a second entry. Counts above the offer capacity block application.

Recognition converts EVE's light text to dark text and uses text positions to pair names with counts while excluding portrait fragments. An additional original-color pass handles tight text-only crops; the pass with more parsed participants is shown, preferring the positional pass on ties. Competing results are never merged automatically.

## Deployment and development

Rebuild the frontend. No backend dependency, database migration, API key or external OCR service is needed. `npm ci` installs pinned dependencies; `npm run build` and `npm run dev` prepare `/ocr/` assets automatically via `scripts/prepare-ocr.mjs`. Generated files in `static/ocr/` are excluded from Git and Docker build context; Docker generates them after copying source. OCR is lazy-loaded separately from the main application bundle. The first scan downloads the selected WebAssembly core and English recognition data from the EQM server, which may take longer on a slow connection.

Run parser/layout/merge tests with `npm run test:hypernet`. Real-browser validation extracted all four names and counts correctly from a user-provided participant-panel crop including portraits and the heading. A tighter crop from the earlier full screenshot still recognized `Maegwynn Swift` as `Maegwunn Swift`, demonstrating why review remains necessary. Private screenshots are not included in the repository.
