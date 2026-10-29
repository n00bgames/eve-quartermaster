# Password recovery and full asset downloads

Implemented for unreleased EQM 2.0.0. Deploy the matching frontend/API and run migration `0096_password_recovery` before starting the updated API or workers. No release/version bump or deployment is implied by committing these changes.

## Password recovery

The login page now offers **Forgot password?**. Users enter their account email and receive the same response whether the address exists, delivery is disabled, or requests are throttled. A reset link opens a new-password and confirmation form. Successful reset clears the remembered session, invalidates existing bearer/cookie sessions on every device, and requires a fresh sign-in; it does not automatically log the user in.

Under **Profile → User Administration → Accounts → Password recovery link**, an administrator confirms their own password to create a single-use private link. It can be copied and privately delivered through the administrator's chosen channel; EQM does not send it automatically. **Require reset and sign out existing sessions now** also disables the user's old-password login until recovery completes. Otherwise their existing login remains available until they use the link. Generating a replacement invalidates the earlier link. Hosts remain protected from lower-ranked admins. Administrators cannot force-reset their own signed-in account; use the profile password change instead. Existing direct admin password replacement remains available and also invalidates sessions and pending links.

Links expire after 30 minutes by default. Tokens use 32 random bytes; only SHA-256 hashes are stored. Tokens are URL fragments in links and submitted in POST bodies, never API query strings. They are single-use with transactional claims and an account-version check; expiry, retirement, password replacement and email changes invalidate them. The configured `FRONTEND_URL` supplies the trusted link origin, never the request Host header. Recovery operations use no-store responses, safe audit events, and no token/password logging. Rate counters are shared in the database and use keyed hashes rather than raw email/IP values. Self-service requests do not lock accounts.

Recovery request limits are two per email and ten per client IP per fixed 15-minute window. Admin recovery attempts are limited to ten per administrator per window. Expired rate rows and recovery records older than their expiry plus one day are pruned on recovery/admin requests. If no requests occur, they remain expired and unusable. At a reverse proxy, configure Uvicorn's trusted forwarded-proxy addresses correctly; the application uses `request.client.host` and does not directly trust arbitrary X-Forwarded-For headers.

### Email setup

Set these backend environment variables (wired through Compose and listed in `.env.example`):

| Variable | Purpose |
| --- | --- |
| `FRONTEND_URL` | Public EQM origin/path for the reset link; use HTTPS in production |
| `PASSWORD_RESET_MINUTES` | Link lifetime, default 30; permitted range 5–120 |
| `SMTP_HOST` | SMTP server; blank disables self-service email delivery |
| `SMTP_PORT` | Default 587 for STARTTLS; typically 465 for implicit TLS |
| `SMTP_FROM` | Sender address; required for email recovery |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Provider credentials if needed; never commit values |
| `SMTP_SSL` | False uses mandatory STARTTLS; true uses implicit TLS |

Certificate verification is required. Delivery runs after the generic response, with a bounded SMTP timeout; failures log only a configuration notice. An SMTP outage does not change the response or lock the account. Admin-generated links work without SMTP. No real email was sent during development; provider delivery needs verification when the operator configures SMTP.

The migration gives existing accounts version zero, preserving existing ordinary sessions until their password changes or a force-reset is requested. OAuth state tokens are not accepted as sign-in tokens. Password reset does not revoke EVE SSO grants or change roles, synced characters or data.

## Full filtered asset downloads

In **Assets → Full filtered downloads**, use **Download full filtered CSV** or **Download full Janice list**. Both export the current database contents matching the ledger's owner-kind, category, subtype and item/owner/location/flag filters across every page. Clear filters to export all accessible assets. Existing page-only CSV/clipboard actions and the richer CSV/JSON privacy-option exports remain available separately.

CSV includes item name/type ID, quantity, owner name/kind, resolved location, flag and exact item ID. Sorting matches the ledger. Names are CSV-quoted and formula-leading text is neutralized. Item IDs are emitted exactly; import that column as text in spreadsheet software to avoid the application's numeric precision conversion. This CSV contains private owner/location data and is not a public report.

Janice uses tab-separated item names and quantities, combines stacks by name, sorts names alphabetically, omits nonpositive totals, and excludes owner/location information. No data is sent to Janice automatically; upload or paste the downloaded text yourself.

The backend enforces the Assets permission and existing owner visibility. It builds a temporary download with no page-size cap and releases its database transaction before transferring it. Normal item/owner/quantity sorting hydrates 500 records at a time. Computed location/flag filtering or sorting retains candidate rows on the server to preserve the ledger's exact container/hangar semantics; especially large such queries may take longer. Temporary files are removed on completion or interrupted responses. The browser downloads a file blob rather than an all-record JSON/table snapshot; **Load all records** is not required. Downloads use a two-minute client timeout and show failures without claiming success.

## Validation and media

Automated checks cover token expiry/reuse/hash-only storage, generic/throttled requests, account/host permissions, force reset, cookie/bearer revocation, legacy sessions, profile/admin password changes, SMTP-disabled fallback, OAuth-state rejection, migration round trip, complete 601-row downloads, exact large IDs, CSV escaping, private visibility, filter/sort parity, empty files, Janice totals and temporary-file cleanup. TypeScript and the production build also pass.

Actual browser checks use disposable synthetic accounts: login recovery entry/response, reset form rendering, admin recovery controls, and downloaded CSV/Janice files while the ledger remains at 100 rows per page. A 621-row CSV and a filtered Janice total of 1,995,745 units across 611 stacks were verified. Password-changing actions are exercised through API tests, not real user accounts. [Feature screenshots](screenshots.md#password-recovery-and-full-asset-downloads) show actual UI, not mockups.
