# EQM deployment handoff

Updated: 2026-09-11. Connection and checkout verified with read-only SSH commands.

## Remote access

On the configured Windows workstation, use `ssh eqm-server`. The existing SSH alias selects the dedicated deployment identity. Keep private keys, passwords, environment files, and private connection details out of Git. Full workstation connection details are in the local `D:\Codex\EVE\CHAT_HANDOFF.md`.

The verified remote Git checkout and active Compose working directory are **`/home/ubuntu/eqm/eve-quartermaster`**. Its parent `/home/ubuntu/eqm` is not a Git repository. The checkout uses `main`. Both production and development are now remote according to the user; a separate development checkout/service stack has not been identified, so do not assume an environment target from the alias alone.

The verified EQM services are `backend`, `frontend`, `postgres`, `redis`, and `worker`. Other applications share the host; scope operations to this checkout and Compose project.

## Update workflow

After the user requests deployment to the intended environment, connect and inspect the checkout:

```sh
ssh eqm-server
cd /home/ubuntu/eqm/eve-quartermaster
git status --short
git log -1 --oneline
```

Preserve any remote changes. For a clean checkout, use:

```sh
sh ./update-eqm.sh
docker compose ps
docker compose logs --tail=100 backend
curl --fail http://localhost:8000/api/health
```

The update script runs `git pull --ff-only` and `docker compose up --build -d`. The backend Dockerfile compiles `eqm-core` in its Rust build stage and installs it in the runtime image; no separate host Rust installation or binary copy is needed. Backend startup waits for PostgreSQL and runs `alembic upgrade head`. Updating frontend only would leave the new native PI commands unavailable.

Verify the application version, select a visible corporate station/Upwell hangar after corporation asset sync, compare inventory, and exercise the Production Calculator and green surplus rows. See [PI verification](pi-supply-and-production.md).

## Current release preparation

- Pushed implementation commit: `cb79eca70f2fa9fa5663f77407d596b7bdebba7f` (PI supply monitoring, Rust calculator, 1.0 preparation).
- Planned regular release: **v1.0 — The Bigger Slice of PI Release!** No beta/prerelease designation.
- Fitting Simulator is for informational purposes only, still in development, and not PYFA-complete.
- Remote checkout was clean at `003f4c5` when inspected on September 11. The new PI changes have not been deployed during this handoff update; recheck current state next time.
- GitHub publication/tagging remains separate from testing the pushed code on the remote server.

## Future context windows

Read this document and the local `CHAT_HANDOFF.md` before deployment work. Check current Git and container state instead of treating dated snapshots as live status. The authoritative Windows publish repository remains `D:\Codex\EVE\_publish\eve-quartermaster-20260628-092452`; `D:\Codex\EVE` is a legacy tree, not an active Git repository or the running EQM server.
