# Architecture

## Backend

- FastAPI serves API routes and OpenAPI docs.
- SQLAlchemy owns the data model.
- Alembic owns migrations.
- PostgreSQL stores application and EVE data.
- Redis plus an RQ worker is reserved for ESI and SDE import jobs.

## Frontend

- React + TypeScript + Vite.
- The current page is a foundation checkpoint, not the final app.
- The final UI should add inventory, ownership, industry planning, procurement, and sync administration views after CRUD endpoints exist.

## Authentication

The intended auth model is local app users plus linked EVE SSO identities.

- Users log into eve-quartermaster.
- Users link one or more EVE characters through EVE SSO.
- Public ESI imports work without SSO. ESI refresh tokens are encrypted server-side once authenticated sync is enabled.
- Corporation sync is enabled only for linked characters with the correct corporation grants and ESI scopes. Live assets and blueprints are never pulled through public endpoints; those require EVE SSO.

## Major model relationships

- `users` own app access.
- `eve_characters`, `eve_corporations`, and `eve_alliances` mirror EVE identities.
- `ownership_entities` normalize character, corporation, alliance, and manual ownership buckets.
- `eve_types`, `eve_groups`, and `eve_categories` hold item reference data.
- `locations` can represent stations, structures, systems, containers, and unknown locations.
- `assets` belong to ownership entities, point to EVE item types, and can nest under parent assets.
- `blueprints` may link to asset rows and point to blueprint/product type IDs.
- `industry_activities` and `industry_activity_inputs` represent SDE recipe data.
- `production_plans` and `production_plan_inputs` represent planned builds and material gaps.
- `procurement_sources` records preferred ways to source missing materials.
- `esi_tokens` and `esi_sync_jobs` track linked auth and sync execution history.

## ESI capability roadmap

The app is configured to request a broad ESI scope set so it can grow into a full quartermaster console. Existing linked characters must re-authenticate when scopes change.

Near-term sync modules:

- Character and corporation assets
- Character and corporation blueprints
- Character and corporation industry jobs
- Character and corporation mining ledgers
- Character contact writes for standings propagation
- Corporation standings reads and alliance contact reads
- Corporation structures and structure name resolution
- Character corporation roles, titles, and access context

Expansion modules:

- Character and corporation wallets
- Character and corporation market orders
- Planetary industry management and customs office reads
- Character and corporation contracts
- Skills and skill queue
- Clones and implants
- Fittings read/write
- Killmails
- Loyalty, medals, standings, faction warfare stats, and research agents
- UI helpers such as opening EVE windows and setting waypoints

The backend keeps the requested scope list centralized in `app/api/esi.py` so the auth URL, diagnostics, and frontend display stay consistent.



