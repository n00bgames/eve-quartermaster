# Calendar and Events: First-Pass Design

Status: first-pass implementation complete  
Prepared: 2026-08-02  
Target baseline: EVE Quartermaster `0.1.16-beta`, migration `0058_exchange_public_auctions`

## Outcome

The first pass adds an authenticated Calendar and Events workspace for scheduling operations, RSVP tracking, multi-character registration, planned ships and fits, post-event attendance, lightweight analytics, and manager-only fleet-composition review. It also adds an Upcoming Events pane to Overview and a compact next-event badge in the application header.

This pass is internal to authenticated EQM users. It does not add public event URLs, recurring events, Discord API access, EVE fleet creation, external calendar synchronization, or reminder delivery. Those can be layered onto the normalized records below without replacing them.

## Repository findings and reuse

The design should reuse these existing contracts rather than create parallel systems:

- Character identity and ownership: `EveCharacter.owner_user_id`, active `EsiToken` records, and the active-character filtering pattern in `backend/app/api/characters.py` and `backend/app/api/mining_ledger.py`.
- Saved fittings: `CharacterFitting`, `can_view_fitting`, fitting serialization, and the existing relationship to `EveType` hulls. A registration may only choose a fitting belonging to its selected character, even if the user can view other shared fittings.
- Solar systems: `search_systems` and `serialize_system` from `backend/app/services/navigation.py`, including security, constellation, and region data.
- Stations and structures: `EveStation` plus resolved `Location` rows. Event locations need snapshot labels because private structures and deleted locations may later be unavailable.
- Hull search: `EveType` joined through `EveGroup` to the published `Ship` category. The Events API should expose its own permission-gated hull search so Events access does not depend on Fittings access.
- Permissions: `SECTION_DEFINITIONS`, `can_view_section`, `role_rank`, and custom roles mapped to built-in base roles.
- Time display: the user `timezone`, `preferredTimeZone`, and `formatDateTime` in `frontend/src/lib/time.ts`.
- EVE presentation: entity portraits/logos and security-status chips already used by Characters and Navigation.
- Auditing: `record_audit_event` for creation, status, lock, RSVP, and registration mutations.
- Overview integration: the existing Overview component can receive a small independent events payload without adding events to the large quartermaster bootstrap response.

There is no doctrine model today. The migration should therefore add a minimal doctrine anchor table, while the first UI continues to support manual names and external doctrine URLs. A dedicated doctrine-library editor is out of scope for this pass.

## First-pass user experience

### Navigation and routing

Add `calendar_events` to the Community navigation group, ahead of Recruiting. Use hash routes:

- `#events` — default Calendar and Upcoming Events workspace
- `#events/new` — event editor
- `#events/{id}` — event detail and registration
- `#events/{id}/composition` — manager composition view
- `#events/{id}/attendance` — post-event attendance ledger
- `#events/analytics` — authorized event analytics

The next-event badge and Overview cards navigate to `#events/{id}`. Hash parsing should be centralized rather than adding another one-off route listener.

### Workspace panes

The Events page contains:

1. **Calendar pane** — month view for the selected month, with formup time as the primary marker and start time as the fallback.
2. **Upcoming Events pane** — chronological cards grouped by day, with filters for event type, RSVP, and lifecycle state.
3. **Event detail pane** — scheduling, location, voice, doctrine, lead, links, instructions, and the current user's RSVP and registered characters.
4. **Event editor pane** — available to event creators and authorized managers.
5. **Registration pane** — user RSVP plus zero or more character registrations.
6. **Fleet composition pane** — attendee detail and requirement progress, gated separately from basic event visibility.
7. **Attendance pane** — post-event roll call for registered characters plus manually added linked characters, external EVE characters, and public guests.
8. **Analytics pane** — configurable-period event counts, RSVP totals, registrations, actual attendance, and registration-to-attendance comparisons.

### Overview and header

Overview receives the next three visible scheduled events. Each card shows event name/type, formup system, local formup time, EVE time, lead, doctrine label, RSVP total, and the current user's registered characters and ships.

The compact header badge shows only:

- event name;
- countdown to formup, or to start when formup is absent/past;
- formup system;
- doctrine name or event type; and
- the current user's RSVP.

Countdown priority:

1. Future `formup_at`: “Formup in …”
2. Future `start_at`: “Operation starts in …”
3. Started but not ended/completed: “In progress”

## Time rules

- Store all timestamps as timezone-aware UTC `DateTime(timezone=True)` values.
- Browser `datetime-local` input is converted with `new Date(value).toISOString()` before submission.
- Reject naive timestamps at the API boundary instead of silently assuming UTC.
- `formup_at` is optional, but `start_at` is required.
- When present, `formup_at <= start_at`.
- Exactly one of `end_at` or `estimated_duration_minutes` may be supplied. If neither is supplied, duration is unspecified.
- When present, `end_at > start_at`; duration must be between 1 minute and 30 days.
- API responses return ISO UTC values. The frontend renders both `formatDateTime(value, preferredTimeZone(user))` and a new `formatEveTime(value)` helper that always uses UTC and labels the result “EVE”.
- Add a human countdown helper that supports days, hours, and minutes; do not reuse `formatDurationMs`, whose `minutes:seconds` form is intended for short-running jobs.

## Controlled values

Store controlled values as indexed strings, matching current EQM model conventions. Validate them through shared constants and API schemas.

- Event type: `fleet`, `mining`, `logistics`, `mission`, `industry`, `training`, `social`, `other`
- Lifecycle: `draft`, `scheduled`, `in_progress`, `completed`, `cancelled`
- Registration state: `open`, `closed`, `locked`
- Doctrine mode: `required`, `recommended`, `none`, `assigned`, `freeform`
- Audience: `all_members`, `corporation`, `alliance`, `invite_only`
- Composition visibility: `participants`, `corporation`, `alliance`, `managers`
- RSVP: `going`, `maybe`, `declined`, `waitlisted`
- Character registration: `registered`, `waitlisted`
- Attendance outcome: `attended`, `no_show`, `excused`
- Attendance source: `registration`, `linked_character`, `external_character`, `public_guest`
- Confirmation: `confirmed`, `tentative`
- Ship source: `doctrine`, `saved_fitting`, `sde_hull`, `freeform`, `undecided`
- Location role: `formup`, `destination`, `route`
- Fleet role keys: `fleet_commander`, `logistics`, `command_bursts`, `tackle`, `scout`, `electronic_warfare`, `mainline_dps`, `capital`, `cyno`, `hauler`, `miner`, `booster`, `salvager`, `other`

Lifecycle and registration state remain separate. For example, a scheduled event may have registration open, closed, or composition locked without overloading one status column.

## Data model

Migration: `0059_calendar_events`, revising `0058_exchange_public_auctions`.

### `doctrines`

A minimal future-facing anchor, not a complete doctrine library.

- `id` primary key
- `name` varchar(255), required, indexed
- `description` text, nullable
- `external_url` varchar(1000), nullable
- `created_by_user_id` FK `users.id`, `SET NULL`, nullable, indexed
- `is_shared` boolean, required, default true
- `archived_at` timezone datetime, nullable, indexed
- `created_at`, `updated_at` timezone datetimes

### `events`

- `id` primary key
- `title` varchar(255), required, indexed
- `event_type` varchar(32), required, indexed
- `lifecycle_status` varchar(32), required, default `draft`, indexed
- `registration_status` varchar(32), required, default `open`, indexed
- `created_by_user_id` FK `users.id`, `SET NULL`, nullable, indexed
- `formup_at` timezone datetime, nullable, indexed
- `start_at` timezone datetime, required, indexed
- `end_at` timezone datetime, nullable, indexed
- `estimated_duration_minutes` integer, nullable
- `operational_area` varchar(500), nullable
- `route_notes` text, nullable
- `discord_voice_label` varchar(255), nullable
- `discord_voice_url` varchar(1000), nullable
- `discord_guild_id` varchar(64), nullable
- `discord_channel_id` varchar(64), nullable
- `lead_character_id` FK `eve_characters.id`, `SET NULL`, nullable, indexed
- `lead_name_snapshot` varchar(255), nullable
- `doctrine_mode` varchar(32), required, default `none`, indexed
- `doctrine_id` FK `doctrines.id`, `SET NULL`, nullable, indexed
- `doctrine_manual_name` varchar(255), nullable
- `doctrine_external_url` varchar(1000), nullable
- `doctrine_notes` text, nullable
- `related_url` varchar(1000), nullable
- `instructions` text, nullable
- `audience_kind` varchar(32), required, default `all_members`, indexed
- `audience_corporation_id` FK `eve_corporations.id`, `SET NULL`, nullable, indexed
- `audience_alliance_id` FK `eve_alliances.id`, `SET NULL`, nullable, indexed
- `composition_visibility` varchar(32), required, default `participants`
- `participant_limit` integer, nullable
- `limit_basis` varchar(16), required, default `characters` (`users` or `characters`)
- `locked_at` timezone datetime, nullable
- `locked_by_user_id` FK `users.id`, `SET NULL`, nullable
- `cancelled_at`, `completed_at`, `published_at` timezone datetimes, nullable
- `created_at`, `updated_at` timezone datetimes

Checks enforce positive limits and duration, valid time ordering, and the required corporation/alliance ID for those audience modes. Drafts are hard-deletable only while they have no responses; published events are cancelled rather than deleted.

### `event_locations`

- `id` primary key
- `event_id` FK `events.id`, `CASCADE`, required, indexed
- `location_role` varchar(24), required, indexed
- `sort_order` integer, required, default 0
- `system_id` FK `eve_systems.system_id`, `RESTRICT`, required, indexed
- `location_id` FK `locations.id`, `SET NULL`, nullable, indexed
- `eve_location_id` bigint, nullable, indexed
- `location_name_snapshot` varchar(500), nullable
- `notes` varchar(1000), nullable

Use partial unique indexes for one `formup` and one `destination` row per event. Route rows may repeat by order. Formup is required before moving an event from draft to scheduled.

### `event_role_requirements`

- `id` primary key
- `event_id` FK `events.id`, `CASCADE`, required, indexed
- `role_key` varchar(48), required, indexed
- `custom_label` varchar(120), nullable
- `requested_quantity` integer, required
- `notes` varchar(500), nullable
- `sort_order` integer, required, default 0

Unique `(event_id, role_key, custom_label)` and check `requested_quantity > 0`.

### `event_doctrine_requirements`

Each row is a requested composition bucket such as “Mainline DPS” or “Command Ships”.

- `id` primary key
- `event_id` FK `events.id`, `CASCADE`, required, indexed
- `role_requirement_id` FK `event_role_requirements.id`, `SET NULL`, nullable, indexed
- `label` varchar(255), required
- `requested_quantity` integer, required
- `notes` varchar(500), nullable
- `sort_order` integer, required, default 0

### `event_doctrine_requirement_options`

Accepted hulls/fits for one doctrine requirement, including alternates.

- `id` primary key
- `requirement_id` FK `event_doctrine_requirements.id`, `CASCADE`, required, indexed
- `ship_type_id` FK `eve_types.type_id`, `SET NULL`, nullable, indexed
- `fitting_id` FK `character_fittings.id`, `SET NULL`, nullable, indexed
- `manual_name_snapshot` varchar(255), nullable
- `is_primary` boolean, required, default false
- `sort_order` integer, required, default 0

At least one of ship, fitting, or manual name is required. If a fitting is selected, its hull is also stored as `ship_type_id` so the option remains useful if the fitting disappears.

### `event_user_responses`

- `id` primary key
- `event_id` FK `events.id`, `CASCADE`, required, indexed
- `user_id` FK `users.id`, `CASCADE`, required, indexed
- `status` varchar(24), required, indexed
- `notes` varchar(500), nullable
- `responded_at`, `updated_at` timezone datetimes

Unique `(event_id, user_id)`. This record exists independently of character registrations.

### `event_character_registrations`

- `id` primary key
- `event_id` FK `events.id`, `CASCADE`, required, indexed
- `user_id` FK `users.id`, `CASCADE`, required, indexed
- `character_id` FK `eve_characters.id`, `SET NULL`, nullable, indexed
- `character_eve_id_snapshot` bigint, required
- `character_name_snapshot` varchar(255), required
- `corporation_name_snapshot` varchar(255), nullable
- `alliance_name_snapshot` varchar(255), nullable
- `registration_status` varchar(24), required, default `registered`, indexed
- `confirmation_status` varchar(24), required, default `tentative`, indexed
- `planned_ship_source` varchar(24), required, default `undecided`
- `ship_type_id` FK `eve_types.type_id`, `SET NULL`, nullable, indexed
- `ship_name_snapshot` varchar(255), nullable
- `saved_fitting_id` FK `character_fittings.id`, `SET NULL`, nullable, indexed
- `fitting_name_snapshot` varchar(255), nullable
- `fitting_updated_at_snapshot` timezone datetime, nullable
- `doctrine_requirement_id` FK `event_doctrine_requirements.id`, `SET NULL`, nullable, indexed
- `doctrine_option_id` FK `event_doctrine_requirement_options.id`, `SET NULL`, nullable, indexed
- `role_key` varchar(48), nullable, indexed
- `custom_role` varchar(120), nullable
- `freeform_ship_description` varchar(255), nullable
- `notes` varchar(1000), nullable
- `created_at`, `updated_at` timezone datetimes

Use a unique index on `(event_id, user_id, character_id)` when `character_id IS NOT NULL`. Creation always requires a character; nullability exists only so historical registrations survive character deletion. Snapshot fields preserve what was selected if a character, hull, or fit later becomes unavailable.

### `event_attendance_entries`

Attendance is a post-event ledger and is intentionally separate from RSVP and registration records. The absence of a row means attendance has not yet been marked; it does not mean the participant was a no-show.

- `id` primary key
- `event_id` FK `events.id`, `CASCADE`, required, indexed
- `registration_id` FK `event_character_registrations.id`, `SET NULL`, nullable, indexed
- `attendee_source` varchar(32), required, indexed
- `attendance_status` varchar(24), required, default `attended`, indexed
- `linked_user_id` FK `users.id`, `SET NULL`, nullable, indexed
- `character_id` FK `eve_characters.id`, `SET NULL`, nullable, indexed
- `character_eve_id_snapshot` bigint, nullable, indexed
- `display_name_snapshot` varchar(255), required
- `corporation_name_snapshot` varchar(255), nullable
- `alliance_name_snapshot` varchar(255), nullable
- `checked_in_at` timezone datetime, nullable
- `notes` varchar(1000), nullable
- `recorded_by_user_id` FK `users.id`, `SET NULL`, nullable, indexed
- `created_at`, `updated_at` timezone datetimes

Use partial unique indexes for `(event_id, registration_id)` when registration is present and `(event_id, character_eve_id_snapshot)` when an EVE character ID is present. Application validation requires the registration to belong to the same event. A `registration` source requires `registration_id`; a `linked_character` source requires `character_id`; an `external_character` requires an EVE character ID and name; a `public_guest` requires only a display name. Manual public entries never create an EQM user, character, or SSO identity.

Registered characters may be marked `attended`, `no_show`, or `excused`. Manually added attendees begin as `attended`; mistaken entries are corrected or removed by an authorized recorder. Actual participation metrics count only `attended` entries, while the other outcomes keep the registration-versus-attendance denominator auditable.

## Authorization and privacy

Add `calendar_events` to `SECTION_DEFINITIONS`, visible by default to host, admin, director, officer, member, and view-only roles.

Mutation rules:

- Host/admin/director: create events and manage any event.
- Officer: create events and manage events they created.
- Member/view-only: view permitted events and manage only their own RSVP/registrations; view-only may RSVP because RSVP is participation rather than administrative editing.
- Event creator remains a manager even if their role later drops below officer, unless their account is retired.

Attendance is a distinct permission boundary. Host, admin, director, and officer base roles with Calendar and Events access may record attendance for any non-draft event they can view after it has ended. An event is eligible when its lifecycle is `completed`, its explicit `end_at` has passed, or `start_at + estimated_duration_minutes` has passed. An event without either end value must be transitioned to `completed` first. This includes officers who did not create the event. A demoted creator below officer may still edit the event under the creator rule but may not record attendance. Custom roles inherit this rule through their built-in base role.

Event-list visibility:

- `all_members`: any authenticated user with Calendar and Events access.
- `corporation`: user has an active linked character in the selected corporation.
- `alliance`: user has an active linked character in the selected alliance.
- `invite_only`: managers and users who already have an RSVP/registration. Explicit invitations are deferred; managers can seed an RSVP in a later increment.

Fleet-composition visibility:

- Managers always see full composition.
- Participants see their own response and registrations regardless of composition visibility.
- `participants`: users with a non-declined response or active character registration see the full list.
- `corporation`/`alliance`: require active-character affiliation to the event audience entity.
- `managers`: no other user sees attendee identities; summaries expose only aggregate counts.

Registration character validation must use a server-side join across `EveCharacter` and `EsiToken` requiring:

- `EveCharacter.owner_user_id == current_user.id`;
- `EsiToken.user_id == current_user.id`;
- `EsiToken.revoked_at IS NULL`; and
- no existing registration for the same event/user/character.

`sync_opt_out` does not block a voluntary registration by the owning user. It still prevents unrelated administrative sync, and composition privacy controls whether others see that voluntary registration.

A saved fitting must belong to the selected character. A supplied hull must be a published SDE type in the `Ship` category. IDs submitted without ownership/access are rejected even if the UI did not offer them.

Ordinary participants may mutate registrations only while lifecycle is `scheduled` or `draft` and registration state is `open`. `closed` blocks new registrations but permits managers to edit. `locked` blocks all ordinary registration and RSVP mutations. Completed and cancelled events are immutable except for manager notes/status corrections and authorized attendance reconciliation. Cancelled events retain existing attendance records for auditability but do not accept new attendance.

Attendance identities follow fleet-composition privacy. Authorized attendance recorders always see the full ledger; everyone else receives only the attendance aggregates allowed by the event's composition visibility. Freeform public-guest notes and identities are never exposed in aggregate-only responses.

No public event endpoint is part of this pass. Text is rendered as text, not raw HTML. External and Discord URLs accept only `https` or `http` schemes and open with `rel="noreferrer"`.

## API design

Create `backend/app/schemas/events.py` with Pydantic request/response models and literal-controlled fields. Create `backend/app/services/events.py` for visibility, mutation authorization, state transitions, composition aggregation, and serialization. Keep `backend/app/api/events.py` focused on HTTP concerns.

### Event discovery and management

- `GET /events?from=&to=&event_type=&lifecycle=&mine=&limit=` — visible event summaries for calendar/list panes.
- `GET /events/next` — next visible scheduled/in-progress event and current user's response, or `null`.
- `POST /events` — create draft; officer or higher.
- `GET /events/{event_id}` — full visible detail, own RSVP/registrations, permissions, requirements.
- `PATCH /events/{event_id}` — edit fields and replace nested locations/requirements transactionally; manager only.
- `POST /events/{event_id}/transition` — validated lifecycle/registration transition with `{lifecycle_status?, registration_status?, reason?}`.
- `DELETE /events/{event_id}` — draft without responses only; otherwise return 409 and require cancellation.

### Search and registration options

- `GET /events/search/systems?q=&limit=` — shared Navigation search service under Events permission.
- `GET /events/search/locations?system_id=` — resolved EQM locations plus SDE stations.
- `GET /events/search/ships?q=&limit=` — published SDE ship hulls only.
- `GET /events/{event_id}/registration-options?character_id=` — current user's active characters; when a character is selected, return that character's saved fits, doctrine options, roles, and current registration exclusions.
- `GET /events/doctrines?q=` — non-archived shared doctrine anchors; initially often empty.

### RSVP and character registration

- `PUT /events/{event_id}/rsvp` — idempotent upsert of user status and notes.
- `DELETE /events/{event_id}/rsvp` — remove response only when registration is open and no character registrations remain, otherwise require explicit character removal first.
- `POST /events/{event_id}/registrations` — create one character registration after ownership, lock, capacity, doctrine, hull, and fitting validation.
- `PATCH /events/{event_id}/registrations/{registration_id}` — owner or manager edit.
- `DELETE /events/{event_id}/registrations/{registration_id}` — owner or manager removal while permitted.
- `GET /events/{event_id}/composition` — detailed or aggregate-only response according to composition visibility.

Use HTTP 403 for access/ownership failures, 404 when an event is not visible, 409 for locks, duplicate registrations, capacity conflicts, invalid state transitions, or stale event edits, and 422 for field validation.

### Capacity and waitlist

`participant_limit` is paired with `limit_basis`:

- `users`: count non-declined user responses.
- `characters`: count character registrations whose `registration_status` is `registered`.

When the next accepted record would exceed capacity, store `waitlisted` rather than rejecting it. Automatic promotion when a slot opens is deferred; managers can promote a waitlisted response/registration explicitly in the first pass.

### Attendance and analytics

- `GET /events/{event_id}/attendance` — authorized roster containing every registration with derived `unmarked` state plus existing attendance entries.
- `PUT /events/{event_id}/attendance/registrations/{registration_id}` — idempotently mark a registered character `attended`, `no_show`, or `excused`.
- `POST /events/{event_id}/attendance` — add an attended linked character, external EVE character, or public guest who did not register through EQM SSO.
- `PATCH /events/{event_id}/attendance/{attendance_id}` — correct outcome, snapshots, check-in time, or notes.
- `DELETE /events/{event_id}/attendance/{attendance_id}` — remove a mistaken manual entry or reset a registered character to `unmarked`.
- `GET /events/analytics?from=&to=&bucket=&event_type=&include_cancelled=` — authorized aggregate series and totals. Declare this route before `/{event_id}` so `analytics` is not parsed as an event ID.

Attendance request/response schemas:

- `AttendanceRegistrationUpdate`: `{attendance_status, checked_in_at?, notes?}`.
- `AttendanceManualCreate`: a discriminated union keyed by `attendee_source`; linked-character entries require `character_id`, external-character entries require `character_eve_id` and `display_name`, and public-guest entries require `display_name`. All accept optional corporation/alliance snapshots, check-in time, and notes.
- `AttendanceEntryUpdate`: `{attendance_status?, display_name?, corporation_name?, alliance_name?, checked_in_at?, notes?}` with identity fields editable only for manual entries.
- `EventAttendanceRosterResponse`: event eligibility and permission flags, all registrations with their current registration state and nullable attendance entry, derived `unmarked` rows, and a separate `unregistered_attendees` collection.

The analytics response contains:

- event counts grouped by event type and time bucket;
- RSVP totals grouped by `going`, `maybe`, `declined`, and `waitlisted`;
- registered-character totals;
- marked outcomes grouped by `attended`, `no_show`, and `excused`;
- actual participants, split into registered and unregistered attendance;
- unmarked registrations; and
- registration attendance rate: attended registered characters divided by all non-waitlisted registrations, with numerator and denominator returned alongside the percentage.

`EventAnalyticsResponse` contains normalized UTC range/bucket metadata, a `totals` object, `by_event_type` rows, and chronological `series` buckets. Each bucket returns event count, RSVP status counts, registered characters, attended registered characters, attended unregistered participants, no-shows, excused, and unmarked registrations. Attendance rate returns `{numerator, denominator, percent}`; `percent` is `null` when the denominator is zero rather than reporting a misleading 0%.

Use event `start_at` as the reporting date. Support `day`, `week`, and `month` buckets and convenient 7-, 30-, 90-, and 365-day presets plus a custom UTC range. Default reports exclude drafts and cancelled events; `include_cancelled=true` adds cancelled events as a separate lifecycle dimension rather than blending them into completed activity.

Hosts, admins, and directors may aggregate all events they can view. Officers receive the same metrics across events they can view and for which their base role permits attendance recording. Members and view-only users do not receive cross-event analytics, preventing aggregate counts from revealing restricted activity.

No materialized analytics table is needed in the first pass. Aggregate directly from indexed `events.start_at`, RSVP, registration, and attendance rows. Add rollups only if measured production query time warrants them.

## Doctrine and composition behavior

- `required`: doctrine options appear first. A non-doctrine selection is accepted only as an explicit exception and is labeled `exception` in composition.
- `recommended`: doctrine options appear first, but other selections are allowed without blocking.
- `none`: all hull, fitting, freeform, and undecided paths are equal.
- `assigned`: ordinary users select character/availability; managers assign requirement, ship, fit, and role.
- `freeform`: freeform composition and requested roles are emphasized.

Doctrine compliance is calculated, not permanently stored:

- `compliant` — linked to an accepted requirement option, or hull/fit matches one.
- `exception` — required doctrine with a decided selection that does not match.
- `undecided` — no ship/fit/freeform selection.
- `not_applicable` — doctrine mode is `none` or `freeform` without requirements.

Composition response includes:

- totals by RSVP, attendance, confirmation, hull, and role;
- requirement progress (`registered`, `requested`, `remaining`);
- no-ship registrations;
- Going/Maybe users with no character registration;
- registration rows with portrait, character/corporation/alliance snapshots, ship, fit, role, confirmation, notes, and compliance when identity visibility is allowed.
- attendance outcome for registered characters and a separately labeled unregistered-attendee group once attendance has been recorded.

## Frontend structure

Add:

- `frontend/src/types/events.ts`
- `frontend/src/features/events/EventsPage.tsx`
- `frontend/src/features/events/EventCalendarPane.tsx`
- `frontend/src/features/events/UpcomingEventsPane.tsx`
- `frontend/src/features/events/EventDetailPanel.tsx`
- `frontend/src/features/events/EventEditor.tsx`
- `frontend/src/features/events/EventRegistrationPanel.tsx`
- `frontend/src/features/events/FleetCompositionPanel.tsx`
- `frontend/src/features/events/EventAttendancePanel.tsx`
- `frontend/src/features/events/EventAnalyticsPane.tsx`
- `frontend/src/features/events/NextEventBadge.tsx`
- `frontend/src/features/events/events.css`

Extract the system autocomplete currently embedded in Navigation into a reusable `frontend/src/components/SystemSearchField.tsx`; Navigation and Events should both consume it. Reuse the existing EVE entity icon, security helpers, fitting labels, and time helpers.

Main-shell changes:

- add Community navigation and title/subtitle entries for `calendar_events`;
- render `EventsPage` with `currentUser`, `preferredTimeZone(user)`, EVE entity components, and the shared API client;
- render `NextEventBadge` in the header;
- add `UpcomingEventsWidget` below Overview's status cards;
- centralize hash-to-tab synchronization for `events` and existing Exchange routes.

Keep all countdown timers client-side and refresh event data on a modest interval, such as 60 seconds. Do not poll the full application bootstrap payload.

## Transaction and validation rules

- Create/update event, locations, role requirements, doctrine requirements, and doctrine options in one database transaction.
- Compare `updated_at` from the edit form for optimistic concurrency; return 409 if another manager changed the event.
- Require a formup system and start time before scheduling.
- Require at least one requirement option for every doctrine requirement before scheduling a required-doctrine event.
- Require a manual/existing/external doctrine label for `required` or `recommended` mode.
- Preserve snapshot labels whenever foreign keys use `SET NULL`.
- Do not let participants alter manager-assigned registrations during `assigned` doctrine mode; they may update registration notes while registration remains open.
- Attendance mutations require an authorized recorder, a non-draft/non-cancelled event, and an event that is completed or whose effective end time has passed.
- Editing RSVP or registration never creates or changes attendance, and attendance reconciliation never rewrites RSVP or registration status.
- State changes, manager edits, RSVP changes, registrations, attendance reconciliation, locks, and cancellations create audit events.

## Test plan

Backend tests:

- migration upgrade/downgrade and foreign-key behavior;
- formup/start/end/duration validation;
- event visibility across all-members, corporation, alliance, invite-only, and hidden-event 404 behavior;
- manager matrix for creator, officer, director, member, and custom base roles;
- forged character ID rejection and active-token ownership checks;
- duplicate character registration prevention;
- fitting/character mismatch and non-ship type rejection;
- open, closed, locked, in-progress, completed, and cancelled mutation rules;
- user-level RSVP independence from character registrations;
- user- and character-based capacity/waitlist behavior;
- fitting deletion and character deletion snapshot fallbacks;
- doctrine compliance and role/hull requirement progress;
- composition identity privacy versus aggregate-only responses;
- attendance recorder role matrix, including an officer who did not create the event and a demoted creator;
- registered-character attendance outcomes, unmarked derivation, and duplicate prevention;
- manual linked-character, external-character, and public-guest attendance without creating SSO identities;
- strict separation between RSVP, registration, and attendance mutations;
- analytics date ranges, bucket boundaries, type counts, RSVP totals, registration totals, actual attendance, unmarked counts, and attendance-rate denominators;
- cancelled/draft analytics exclusion and cross-event analytics privacy;
- next-event formup/start priority.

Frontend/unit tests:

- local and EVE-time rendering around daylight-saving boundaries;
- formup/start countdown priority;
- hash route parsing;
- doctrine-adaptive ship selector behavior;
- composition grouping and missing-role calculations;
- locked/completed/cancelled control states;
- attendance roll-call states and analytics empty/loading/error displays.

Browser checks:

- create an event with local time and verify the UTC/EVE rendering;
- register two owned characters with different ships/fits;
- confirm another user's character cannot be submitted manually;
- verify locked registration controls disappear/disable;
- verify manager and ordinary-user composition privacy;
- mark registered attendance, add an unregistered public attendee, and verify registration and RSVP remain unchanged;
- compare the event's registration count to actual attendance in the Analytics pane;
- verify next-event badge and Overview navigation at desktop and narrow widths.

## Implementation order

1. **Schema and authorization foundation** — migration, models, constants, Pydantic schemas, visibility helpers, state machine, and backend tests.
2. **Event CRUD and discovery** — list, next, detail, editor, system/location/hull search, Calendar pane, Upcoming pane, and hash routing.
3. **RSVP and multi-character registration** — active owned characters, fitting/hull/freeform selection, limits, waitlist, snapshots, and registration tests.
4. **Doctrine requirements and composition** — role/hull/fit requirements, accepted alternates, compliance, progress, and manager privacy.
5. **Attendance and lightweight analytics** — post-event roll call, unregistered attendees, aggregate series, attendance comparison, privacy, and audit coverage.
6. **Overview and header integration** — next-event badge, Upcoming Events widget, audit entries, responsive QA, and release documentation.

Each phase should be mirrored to the publish tree and leave both development and publish builds/tests green before the next phase begins.

## Deliberate first-pass exclusions

- recurring event rules and exception dates;
- public or unauthenticated event pages;
- event invitation records and outbound notifications;
- Discord server/channel discovery or bot integration;
- EVE fleet creation, fleet invites, or calendar ESI writes;
- iCalendar/Google/Outlook synchronization;
- immutable full fitting snapshots;
- automatic waitlist promotion;
- a complete doctrine-library management UI;
- drag-and-drop calendar rescheduling.

These are exclusions from the first implementation slice, not schema dead ends. Discord IDs, doctrine relationships, fitting snapshots, event audience fields, and normalized requirement records are included now specifically to avoid redesign when those features arrive.
