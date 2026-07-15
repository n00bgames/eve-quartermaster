# Proposed Changes

Use this file for good ideas that should not interrupt the current frontend segmentation pass.

## Fitting Dogma Fidelity

Continue improving fitting simulation Dogma fidelity as real fittings expose gaps. Prioritize targeted, evidence-backed modifiers over broad rewrites until the full effect graph is ready.

## Password Reset

Add an account password reset flow. Prefer a secure token-based reset path for users who cannot sign in, plus clear admin controls for forced resets.

## Server-side Asset Exports

Add full filtered CSV and Janice-list exports from the backend for the Assets ledger so large inventories can export complete filtered results without loading every row into browser memory.

## Settings Maintenance Actions

Add Settings-page maintenance buttons for safe backend-worker tasks such as fetching the latest SDE into `/sde` and optionally queueing SDE import. For host-level update/rebuild controls, prefer a small explicit host helper service over mounting the Docker socket into the app container.
