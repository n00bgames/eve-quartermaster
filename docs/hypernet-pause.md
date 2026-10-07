# HyperNet pause controls

Open **HyperNet pause controls** near the top of HyperNet Tracker. HyperNet recording starts enabled. Check a character's switch to pause new bid and offer records for that character, or check **Pause HyperNet for my EQM account** to pause every character. Uncheck the switch to resume at any time.

The account switch overrides individual character switches, including for characters linked later. It preserves individual choices: if Betty was paused before the account pause, Betty remains paused when the account resumes. Character switches are disabled while the account pause is active.

These controls affect EQM recording only. They do not prevent purchases inside EVE or request an in-game self-exclusion.

## What stays available

Existing offers and bids, history, financial summaries, corrections, and outcome reconciliation remain available while paused. Private analytics continue to follow their separate [opt-in preferences](hypernet-private-analytics.md); a pause neither enables analytics nor hides existing opted-in results.

New bids and offers, including offer drafts, are blocked. Paused characters cannot be selected in new-entry forms. Direct links and stale browser tabs also cannot submit new records because the server checks the saved pause state before creating either record type.

## Privacy and deployment

Pause preferences belong to the signed-in EQM user. Character controls are restricted to that user's currently linked characters, including for staff accounts. Preferences are keyed by both user and character, so another account linking a character does not inherit its previous owner's individual preference. Existing monthly settings are preserved.

Apply migration `0087_hypernet_pause` after `0086_hypernet_private_analytics`, then rebuild the backend and frontend together. The account column and character preferences default to false; deploying does not pause any account automatically. Local verification does not deploy or change live preferences.

Regression checks cover default behavior, owner-only access, independent character choices, account overrides, newly linked characters, migration defaults and rollback, existing history and analytics, and continued corrections and outcome updates. Browser verification also covers direct routes, unavailable form options, reload persistence, failed-save retry, and desktop/mobile layouts.
