# EVE SSO sign-in and Ship Reports

Unreleased 2.0.0 development changes. Apply migration `0098_account_sso` before starting the matching API/worker and frontend. This change does not alter the configured EVE application callback URL or register a new CCP application.

## Sign in and accept invitations

The login page offers **Log in with EVE SSO**, alongside password sign-in. Use a character already linked to your EQM account. The existing Remember me checkbox applies to either method; otherwise SSO uses a browser-session HttpOnly cookie with the normal account-token expiry. No EQM session token or EVE token is placed in a frontend redirect URL.

An existing administrator invitation now offers **Create account with EVE SSO**. It consumes the invite once, creates the account with the invite's current combined roles, links the selected character, and chooses that first character as main. The character's verified name supplies the initial display name. Password acceptance remains available. SSO-created accounts have no known password; configured password recovery or an administrator-generated reset link can establish one later.

Both login and invitation SSO request only `publicData` identity consent. They do not collect assets, skills, wallets, corporation data or industry. Additional ESI integrations remain separate, explicit authorizations constrained by the user's combined roles. New identity links do not immediately have waypoint or structure scopes.

Existing links record CCP's character owner hash on reauthorization. Legacy links without that hash must prove ownership using their existing encrypted refresh token before SSO login is enabled. Invalid/revoked legacy authorizations require password sign-in and character relinking. Character ID alone never grants access: a transferred character with a different owner hash cannot unlock its former owner's EQM account. Unlinking/revoking the character authorization prevents future sign-in through that character. Deleted accounts and forced password resets also block SSO login.

New callbacks use ten-minute, database-backed, single-use state, an HttpOnly browser binding, and PKCE. The verifier is encrypted at rest. CCP JWT signature/issuer/audience/client checks use the existing validator. Expired/revoked/accepted invitations, removed roles, demoted inviters, account collisions, and already linked characters are rejected. An invitation never merges with an existing account or transfers a linked character. Password and SSO invitation acceptance share an atomic claim. A shared per-IP start limit bounds attempts; proxy address forwarding must remain correctly configured.

Use the existing `EVE_SSO_CLIENT_ID`, `EVE_SSO_CLIENT_SECRET`, `EVE_SSO_CALLBACK_URL`, `TOKEN_ENCRYPTION_KEY`, `FRONTEND_URL` and API-prefix settings. Public HTTPS and same-origin API proxying are required for production cookie handling. Starting a second flow in the same browser supersedes the first flow's browser binding. Expired state rows are removed on subsequent starts.

Protocol reference: [CCP's official SSO documentation](https://developers.eveonline.com/docs/services/sso/).

## Private Ship Reports

Open **Inventory & Industry → Ship Reports**. Generate a snapshot of all synchronized ship assets within your existing asset visibility. Below Fleet Commander, Ship Report, Inventory Report and Assets permissions are all required. Fleet Commander and higher can use the ship-only scope without general Assets/Inventory access. The section defaults to Inventory Report roles plus Fleet Commander. Existing customized navigation picks up the new module, and it can also be added as a Quicklaunch shortcut.

The report leads with **total ships** and **number of ship types**, then totals by hull type/class, then character/corporation and location details. Packaged stacks count their full quantity; assembled ships count as individual hulls. SDE category 6 identifies ships, so drones, modules and ship blueprints are excluded. Ship hulls carried inside other assets remain included with their resolved location. Non-positive quantities are omitted. An unresolved SDE type cannot safely be classified as a ship; import current SDE data and resync assets if expected hulls are missing. No current piloted/assembled/fitted status is inferred from this report.

Sortable tables, CSV and branded PDF exports include the overall total and per-type quantities. Snapshots use synchronized database inventory, not a fresh live ESI query. Sync first and generate again for current counts. Reports include generation/data timestamps, configurable retention, saved history and individual/date-range/all deletion. They are creator-only, including against admins/directors, with no public routes, links or public listing. Ship deletion never affects Inventory or Industry Reports. Existing saved reports keep their original inventory contents except that capsules are removed when reopened/exported. Per-class exclusions, the Subcaps preset, Fleet Commander access and historical hull Analytics are documented in [Ship filters and Analytics](ship-filters-and-analytics.md).

## API responsiveness and login spacing

Expensive Industry/Inventory/Ship Report builds, storage indexing and exports run outside the main async request loop. At most two heavy report operations run per API process; overload receives HTTP 503 with `Retry-After: 5`, including dynamic public reports. Permission, selected-storage and expiry checks remain in place. This is bounded thread offloading, not a durable report queue, a cross-process limit, or a promise that large reports finish within the reverse proxy's timeout.

`/api/health` remains a basic liveness check. A single successful response does not establish that login/report requests are responsive; check request latency and the affected endpoint as well. The recovery link is centered below the sign-in actions with padding.

## Verification

Automated ASGI tests cover identity-only consent, PKCE exchange, state replay/expiry/browser binding, ownership transfers, legacy proof and revocation races, invitation lifecycle/roles/collisions, password acceptance, migration upgrade/downgrade, ship quantities/privacy/exports/deletion, navigation persistence and report responsiveness. A report deliberately blocked in a worker must leave health responsive. Existing account/recruiting/report privacy regressions are included.

Actual UI captures use isolated synthetic fixtures. The browser exercises the unconfigured-SSO error path; upstream exchanges are mocked in API tests. No real CCP sign-in, live account creation, production migration or deployment was performed. The synthetic Ship Report PDF was rendered and visually checked. Existing frontend chunk-size and local Poppler font-fallback advisories remain.

Final local verification: **158 targeted tests passed**, plus seven subtests; TypeScript and Vite production build passed. The existing chunk-size advisory remains.
