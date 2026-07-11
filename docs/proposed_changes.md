# Proposed Changes

## Pilot Security Status In Intel Views

When we return to route checker, jump planner, and local threat work, investigate whether ESI can provide useful pilot security status for pilots shown in kill/intel displays. If available, show that status alongside pilot identity in those views.

Do not implement this during the current frontend segmentation pass; keep prioritizing reducing `frontend/src/main.tsx` into manageable 300-600 line modules first.
## Sync All Characters From Skills Page

Add a "sync all characters" action to the Skills page. It should enqueue backend worker jobs rather than running inline, skip any character that has opted out or flagged itself not to be synced, and show progress/status with the usual queue/status badge pattern.