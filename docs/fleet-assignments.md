# Fleet Assignments

Fleet & Community → **Fleet Assignments** provides an Officer-and-above planning
board and an authenticated personal assignment view for ordinary members.
This first version covers planning and publication; engagement results, reships,
acknowledgements, survival, and director analytics are future work.

## Planning workflow

1. Create an operation, optionally choosing a saved composition preset.
2. Choose a fitting from an available doctrine or source character. Shared fits
   and fits owned by the planner are eligible. Adding a fitting intentionally
   distributes a copy to assigned members; broad staff inspection access alone
   does not permit distributing someone else's private fitting.
3. Add a role and target count. Targets are guides, not hard capacity limits.
   The operation saves the fit's complete item snapshot and EFT text immediately.
   Editing, deleting, or syncing the original fit never rewrites this copy.
4. Paste character names, one per line, or a tab-separated EVE fleet roster.
   A Name/Character/Character Name/Pilot header identifies its column; without a
   header the first column is used. Empty lines and duplicate names are skipped.
   Local characters resolve without network access; unknown names use the public
   ESI universe ID lookup. Corporation/alliance matches are ignored.
5. Unresolved names remain visible but cannot receive assignments. Correct the
   name and paste again; an existing unresolved row can be resolved by retrying
   the same name. Remove mistaken rows explicitly. Imports append; they never
   replace or erase the existing roster. Limits: 500 pilots, 100 fitting roles.
6. Drag a fitting's header/grip onto a pilot. If that pilot is selected, the fit
   applies to all selected pilots; otherwise only that pilot changes. Pointer
   capture supports mouse/touch. Search, Select visible, and the fitting picker
   plus **Assign selected** provide click/keyboard alternatives. Clear assignments
   preserves the roster. Remove a fitting role after clearing its assignments.
7. Save the composition as a preset when useful. A preset includes fitting
   snapshots, role labels, target counts, and briefing, never pilot names or
   assignments. New operations receive independent copies and new role keys.
8. Publish assignments and copy the member link. The briefing is member-facing.
   Drafts and archived operations are absent from member views. Unpublish to
   withdraw access, or archive and later restore to draft. Changes to published
   assignments are immediately visible on the member's next refresh.

The library can refresh the planner's authorized characters through the existing
ESI fitting-sync workflow (`esi-fittings.read_fittings.v1`). No EVE credentials
or tokens are included in assignment snapshots or member links.

## Personal view and permissions

- `#fleet-assignments/my` lists only the current account's published assignments.
- `#fleet-assignments/my/<operation-id>` narrows the same view to one fleet.
- URLs are navigation, not bearer credentials. EQM login is always required.
- The backend requires current `EveCharacter.owner_user_id` plus a matching,
  non-revoked `EsiToken` owned by that same account. Name similarity, a character
  selected in the UI, a supplied account ID, and staff role never widen this view.
- Revoking a link or transferring a character out of the account removes access
  on the next request. A new owner needs their own active SSO link. EQM tracks
  local authorization state; external CCP revocations take effect once detected
  and recorded by the normal token lifecycle.
- Member responses contain their assignment snapshots and the published brief,
  not the full roster, composition, other assignments, or staff operation state.
  Responses use `Cache-Control: private, no-store`.
- The `fleet_assignments` section can be disabled/restricted through existing
  section controls. Applicants cannot access it. Officer-and-above roles can plan;
  being allowed to view the section does not grant planning access.

Every mutation is audited. Assignment changes retain previous/new fitting
snapshots and pilot IDs so future reporting can reconstruct changes. Operations
use an atomic revision comparison; stale edits return 409 and the interface
reloads the saved board. Data changes and audit records commit together.

## Alliance Auth portability

No Alliance Auth installation or deployed integration is included in this change.
The boundary is explicit:

- `app/domain/fleet_assignments.py` contains framework-independent roster parsing,
  target validation, and personal visibility rules. `Principal` takes a stable
  subject and a verified set of EVE character IDs; staff status cannot bypass
  personal visibility.
- `app/services/fleet_assignments.py` adapts EQM identities, SQLAlchemy, fitting
  export, public ESI lookup, and audit storage.
- `app/api/fleet_assignments.py` supplies the FastAPI HTTP contract.
- React's `FleetAssignmentsPage` accepts an injected `ApiClient`. It does not read
  EQM tokens, account objects, roles, or database models directly. An AA host can
  mount it and provide a session/CSRF-aware client against equivalent endpoints.
- Snapshots carry schema version `eqm.fleet-assignments.v1`, EVE hull/item IDs,
  item quantities/flags, role metadata, and EFT text. Source fitting/doctrine IDs
  are provenance in the source installation; they must not be treated as valid
  database references on another installation. Operation/pilot row IDs are local;
  `character_id` in the API is the canonical EVE ID, never a local character PK.
- An AA adapter should derive identity from its verified ownership model, require
  an explicit app planning permission mapped to FRONT's approved groups, and
  persist snapshots/presets with Django models. Do not infer EQM Host or developer
  privilege from an AA group label, and do not share ESI refresh tokens/databases.
- A native AA implementation needs its own CSRF handling, migrations, audit
  adapter, and the same authorization contract tests. Planner access and future
  Director analytics should be separate AA permissions.

## HTTP contract

All paths are beneath `/api/fleet-assignments`; all require authenticated section
access. Everything below except `meta` and `my` additionally requires a planner.

| Endpoint | Purpose |
|---|---|
| `GET /meta` | Caller capability and contract version |
| `GET /sources` | Distributable fitting/doctrine summaries and own sync sources |
| `GET /my`, `GET /my/{id}` | Strictly owner-filtered published assignments |
| `GET/POST /operations` | Recent operations (up to 200) / create draft |
| `GET/PATCH /operations/{id}` | Full planner board / name, briefing, status |
| `POST /operations/{id}/roster` | Append/resolve pasted names; import report |
| `POST /operations/{id}/slots` | Snapshot a source fitting and optional doctrine |
| `PATCH/DELETE /operations/{id}/slots/{key}` | Role/target update or remove unused fit |
| `POST /operations/{id}/assign` | Atomically assign/clear selected pilot row IDs |
| `DELETE /operations/{id}/pilots/{pilot-id}` | Remove a pilot from this fleet |
| `POST /operations/{id}/preset` | Save a composition-only preset |
| `GET /presets`, `DELETE /presets/{id}` | List/remove presets |

Operation mutations submit the last received `revision` (DELETE uses a query
parameter). Create-operation accepts `name`, optional `briefing`, and optional
`preset_id`. Assign accepts `revision`, `pilot_ids`, and nullable `slot_key`;
null clears assignments. Slot creation accepts a local `fitting_id`, optional
local `doctrine_id`, `role`, and `target_count`. Arbitrary fitting snapshots and
extra payload fields are rejected.

## Deployment and verification

Apply migration **0088_fleet_assignments** after 0087, then rebuild backend and
frontend together. There is no version bump, additional runtime dependency, or
new ESI scope. No remote deployment is implied by this local implementation.

Tests cover the HTTP workflow, member/staff isolation, active token ownership,
revocation/transfer, private fitting distribution, roster lookup failures,
deduplication, invalid cross-fleet targets, concurrent revisions, snapshots,
presets, section permissions, audit history, and migration round-trip/single head.
Browser QA uses disposable synthetic fleets and separate member accounts.
