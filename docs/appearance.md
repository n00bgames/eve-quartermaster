# Appearance and workspace customization

Available in the unreleased 2.0.0 build. Deploy the matching frontend/API and apply migration **0095_appearance** before use.

## Personal settings

Open **Appearance** in the page header or **Settings → Appearance & layout**. All signed-in roles can use these presentation controls, including utility-only Intel Analysts and Quartermasters. They do not grant module permissions, enable ESI collection, or expose administrative settings.

- Choose EQM dark, Deep space, Emerald, Amethyst or Daylight, or edit the six color controls. Preview before saving; Cancel preview restores your saved palette. Text contrast is validated on both the client and server. Semantic warning/threat colors remain distinct.
- **My banner** overrides the application banner for your account. It does not change another person's banner or the public login page.
- **Customize navigation** opens the sidebar editor. Drag section handles to reorder groups; edit their names; move modules between groups with handles or the group selector. Arrow buttons provide keyboard/touch alternatives. Add an empty section, or remove a section once its modules have been moved. Use each section’s **Add shortcut** dropdown to select any permitted navigation item, grouped by its standard section. This keeps its original link. For a Quicklaunch menu, add a section, name it Quicklaunch, add your frequently used links, and move the section to the top. Items already in that section are omitted from its dropdown. **Remove shortcut** removes only that copy and is available when another copy remains. Moving a link affects only that occurrence; dropping it into a section that already has it leaves one copy there. Press **Save navigation** to persist edits; Cancel discards the draft.
- **Arrange panels** enables handles on multi-section workspaces. Each move saves immediately. Overview (including the asset/blueprint pair), Navigation, Ownership, Industry, ESI Sync, Profile, Settings, Quartermaster, Local Scan, D-Scan, Industry/Inventory report workspaces, Battle Reports, Events, HyperNet and PLEX support section ordering. Forms, tables and single-panel modules keep their internal structure. Public report section ordering remains the standard report order.
- Reset colors, navigation or all panel positions independently. Each panel region also has a Reset section control.

Preferences are stored by account in the database and restored on later sessions/devices. Temporary edit mode and unsaved palette/navigation previews are not persisted. Missing/new modules retain default placements, and permission-hidden modules cannot be exposed through the editor. Temporarily absent panels retain their saved positions. Account switching clears personal appearance state. A stale save from another browser returns a conflict with a Reload preferences action, rather than silently overwriting it.

The default navigation retains Intel as the second named group. The fixed Appearance header button remains available even after menu customization.

## Site branding

Admins and hosts additionally see **Site banner** and **Login background** uploads in Settings. These images are intentionally public. The site banner is the default unless a signed-in account has its own banner. The login background is site-wide because visitors have not yet selected an account. Reset controls restore the bundled defaults. Uploads/resets create audit events.

Accepts PNG, JPEG and WebP up to **5 MB / 20 megapixels**. The API decodes, strips metadata, resizes within **2560 × 1440**, and re-encodes WebP. SVG/HTML, malformed images and excessive sizes are rejected. Images are stored in the database (included in normal PostgreSQL backups), not under a user-provided filesystem path. Only site branding has public image endpoints; personal banners are delivered through the authenticated own-account endpoint with no-store headers.

## Industry and Inventory table sorting

Click a column header to sort ascending; click again for descending. Arrows and `aria-sort` announce the direction. Numbers sort numerically, dates chronologically, names naturally, and missing values stay last. Every row is sorted **before** the 100-row display pagination, and choosing a sort returns to page one. Each table sorts independently. Existing saved/public Industry Reports use the new renderer automatically; no regeneration is required. Inventory Reports share the same table renderer.

Sorting changes the browser view. CSV/PDF exports retain their complete standard report ordering and do not inherit a temporary browser sort.

## Validation and rollout

API tests cover account isolation, actual Quartermaster authentication/write restrictions, image formats/limits/re-encoding, admin-only public branding, optimistic revision conflicts, resets, validation and the migration round trip. Frontend tests cover navigation normalization, section/module moves, hidden panels and full-data numeric/text/date sorting (2,501 rows). TypeScript and production builds pass. Actual synthetic browser checks cover mouse dragging, arrow moves, saved palette/navigation/panel reloads, a site-banner upload, login background, logout/account isolation and ascending/descending report quantities. Light/dark settings, upload controls, navigation editing and report rendering were visually inspected. At a narrow viewport the appearance controls fit the content width; legacy host permission tables can still require horizontal scrolling.

The preview uses disposable synthetic data; no production deployment or live settings were changed. [Screenshots](screenshots.md#appearance-layouts-and-sortable-reports) are unreleased development captures.

When extending the UI, preserve existing `data-layout-id` values and region IDs. Add a stable new ID for a new panel; never renumber existing panels. Keep permission checks around the original module elements. Preferences control presentation only.

## Quicklaunch validation

Cross-section shortcuts require the matching updated frontend and API, using the existing 0095 preferences table; no additional migration. Older saved navigation layouts remain valid. API validation accepts the same module in different sections, but rejects duplicates within one section and unknown modules. Hidden links remain saved and are never offered or rendered without their existing permissions.

36 appearance API tests and 11 frontend appearance/report tests pass, along with TypeScript and the production build. Synthetic browser checks cover adding links from Intel, Finance and Industry, moving Quicklaunch to the top, saving/reloading, retained original links, duplicate omission from the picker, removing one copy, moving one occurrence, pointer reordering, Cancel, opening Local Scan through its shortcut, and 420px controls without document overflow. No browser warnings/errors were observed. [Quicklaunch screenshots](screenshots.md#quicklaunch-shortcuts) use disposable synthetic accounts.
