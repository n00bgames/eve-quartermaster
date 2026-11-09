# Local Scan character notes

**Unreleased development feature for EQM 2.3.0.** Requires migration `0106_scan_character_notes` and matching backend/frontend rollout. No new ESI scopes or background collection are required.

## Tag a scan

Generate or open a saved Local Scan. Above the results, enter a **Character note**, choose its visibility, then select **Add note to all N pilots**.

The note is attached to every distinct, resolved EVE character ID in the stored scan. Display filters do not reduce the tagged set. Unresolved names are skipped and the confirmation says so. The server derives the IDs and names from the authorized stored report; the browser cannot supply a different target list. Missing Intel dossiers are created from those resolved identities without fetching ESI, enrolling characters, collecting killmails or claiming that the pilots share an operator.

Use a specific label such as `Suspected multiboxer · North Gate crew`, with uncertainty clearly recorded. This is a human annotation, not an automatic multiboxing finding.

Notes remain on the characters after the report expires or is deleted. Later authenticated scans display the current viewer-visible notes on those characters. A saved report's public snapshot and PDFs are not modified. Up to three recent note previews per pilot are shown; open the Intel dossier for full text and note management.

## Public and Private

The new note controls default to **Private Note**:

| Setting | Who can read/search it |
| --- | --- |
| Private Note | Its author, while they retain Intel Reports access |
| Public Note | Signed-in EQM users who meet the existing Intel Reports role/capability and section requirements |

“Public” means shared **inside EQM intel**, not published to the internet. Neither setting appears on public scan links or PDFs. Private notes are also hidden from other Hosts and Admins through the application APIs, including direct note IDs, edit/delete attempts, search matches/counts and current-scan overlays.

Note visibility is independent of scan visibility. Choosing Public on a private scan explicitly shares those character annotations with authorized intel users; it does not share the scan's bearer link or its entire snapshot. Access to the private scan itself remains author-only.

Local Scan access and Intel Reports access are both required for scan annotation/readback. Search and dossier management require Intel Reports access. Existing role/capability requirements, combined/custom roles, section revocation and read-only restrictions remain enforced. Existing Intel notes retain their previous shared visibility after migration.

## Search notes

**Search character notes** is available in Local Scans and Intel Reports. Type a text string to find all characters with a visible matching note, including notes previously written directly on dossiers.

- Matching is a literal, case-insensitive substring search using the database's case mappings. `%`, `_`, apostrophes and other punctuation are treated as note text, not SQL patterns.
- Results contain distinct characters with links to their Intel dossier and zKillboard, visible matching-note counts and up to three recent matching previews. Long previews are shortened to 300 characters; open the dossier for full text.
- Fifty characters are shown per page, with navigation through the complete result set. Large groups are not silently capped at the first page.
- **Link to this search** creates an authenticated `#intel-notes?q=…` link. Clicking a note on a scan or the dossier's **Find characters with matching note text** link opens the same search. A shortened scan preview searches the displayed substring.
- Search links do not grant access. A different viewer sees only their own private notes and the shared notes they are authorized to read. Search results re-evaluate visibility when requested.

## Edit or remove a tag

Open the character's Intel dossier and select **Notes**. Authors can edit/delete their own notes and change visibility. Only the author can change Public/Private visibility. Hosts/Admins can moderate shared Public notes; they cannot read another author's Private notes through this UI/API. Editing one character's note changes that character only, not every member of the original batch.

Edits and deletes check both the original body and original visibility. A stale request returns a conflict instead of overwriting a concurrent change. The author and original creation time stay unchanged. Audit entries record action/IDs/counts without copying note text.

## Persistence and retries

`intel_notes` gains `is_private` (existing rows default shared) and an optional scan batch reference. `intel_scan_note_batches` keeps an author/request UUID, source hash, original note/visibility and target count. Raw report bearer tokens are not copied into that ledger.

Bulk writes are one transaction with bounded batches for large scans. Retrying the same request does not duplicate notes; reusing its UUID for different content, visibility or source returns a conflict. A failed partial write rolls back the notes, any newly created dossiers and the retry ledger. The operation was tested with 9,999 pilots and a simulated mid-batch write failure.

Migration downgrade refuses to proceed while private notes remain, preventing rollback from turning private content into shared legacy notes. Export and explicitly remove such notes before an intentional downgrade.

## Verification

Validation uses isolated SQLite, mocked public ESI responses and fabricated accounts/characters. The broad 95-case Local Scan/Intel regression run passed; a final focused 22-case notes/editing run passed after adding rollback and author-controlled visibility regressions (97 unique cases overall). TypeScript and the complete production Vite bundle pass. Seven real-browser scenario groups cover bulk tagging under a filtered view, search/dossier links, two-account visibility including an Admin viewer, per-character privacy edits, deep links, future scans and a 390px mobile layout. No live account, production database or private gameplay data was used.
