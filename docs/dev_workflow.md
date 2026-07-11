# EVE Quartermaster Dev Workflow

## Working Folders

- Local working folder: `D:\Codex\EVE`
- Publish repository: `D:\Codex\EVE\_publish\eve-quartermaster-20260628-092452`
- Handoff file: `D:\Codex\EVE\CHAT_HANDOFF.md`
- Proposed future work: `D:\Codex\EVE\docs\proposed_changes.md`

The publish repository is the actual git repository used for GitHub. Keep source changes mirrored there before preparing a push.

## Common Commands

Run local frontend build checks from the local working folder:

```powershell
cd D:\Codex\EVE
npm --prefix frontend run build
```

Rebuild and restart the local Docker stack:

```powershell
cd D:\Codex\EVE
docker compose up --build -d backend worker frontend
```

Run frontend build checks in the publish repository after mirroring changes:

```powershell
cd D:\Codex\EVE\_publish\eve-quartermaster-20260628-092452
npm --prefix frontend run build
```

## Git Push Chain

When the user says `pc`, provide the push chain with the `cd` command:

```powershell
cd D:\Codex\EVE\_publish\eve-quartermaster-20260628-092452
git status
git add .
git commit -m "Describe the change"
git push origin main
```

Use a commit message that describes the current work, such as `Segment navigation frontend`.

## Version Bumps

When the user says `vb`, bump the project version. Check the current version surfaces before editing. Known surfaces include:

- `frontend/package.json`
- `frontend/src/version.ts`
- backend API/app version surfaces
- ESI user-agent strings
- Android wrapper version surfaces
- README badge/version text
- `CHANGELOG.md`

Keep `CHANGELOG.md` current with user-facing release notes. Create a fresh top section for each new version, and do not let older version bullets drift into the new release section.

## Frontend Segmentation

Keep reducing `frontend/src/main.tsx` into purpose-built modules.

Guidelines:

- Target extracted frontend files around 300-600 lines when practical.
- Keep slices small and build after each meaningful extraction.
- Mirror code changes into the publish repository after local verification.
- Avoid large rewrites that mix unrelated UI behavior.
- Preserve current behavior unless the user explicitly asks for functional changes.

Current segmentation direction:

1. Extract Characters and Profile pages.
2. Extract Analytics widgets.
3. Continue opportunistic cleanup of any remaining wrapper glue.
4. Review whether Settings/ESI/Admin should be split before deeper feature work.

## Handoff And Future Work

Update `CHAT_HANDOFF.md` after meaningful segmentation progress with:

- completed extraction files and approximate line counts
- updated `main.tsx` line count
- build status
- suggested next extraction order

Do not copy `CHAT_HANDOFF.md` into `_publish` unless explicitly requested.

Use `docs/proposed_changes.md` for future work that should not interrupt the current segmentation pass. Mirror that file into the publish repository.

## License And Comments

The publish repository uses the AGPL-3.0 license. Keep comments useful and maintainable:

- Add concise comments for non-obvious logic.
- Avoid noisy comments that restate the code.
- Preserve license and attribution context for any third-party-derived material.
- Do not paste large third-party code or text without checking license compatibility.

## Git Layout Note

The root `.git` directory was removed to avoid confusing the actual publish repository. The actual repository is inside `_publish\eve-quartermaster-20260628-092452`.

If a root-level `.git` directory ever reappears, prefer renaming it first instead of deleting it immediately:

```powershell
cd D:\Codex\EVE
Rename-Item -LiteralPath .git -NewName .git-empty-backup
```

Do not delete or rename `_publish\eve-quartermaster-20260628-092452\.git`.
