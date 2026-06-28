<p align="center">
  <img src="static/eqm-logo.png" alt="EVE Quartermaster" width="900">
</p>

<p align="center">
  <a href="https://github.com/n00bgames/eve-quartermaster"><img alt="Project" src="https://img.shields.io/badge/project-eve--quartermaster-e8b84d?style=for-the-badge"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-0.0.2--alpha-4fb3c7?style=for-the-badge">
  <img alt="License" src="https://img.shields.io/badge/license-AGPL--3.0--or--later-70c894?style=for-the-badge">
</p>

<p align="center">
  <img alt="Backend" src="https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square">
  <img alt="Frontend" src="https://img.shields.io/badge/frontend-React%20%2B%20Vite-646cff?style=flat-square">
  <img alt="Database" src="https://img.shields.io/badge/database-PostgreSQL-4169e1?style=flat-square">
  <img alt="Containers" src="https://img.shields.io/badge/runtime-Docker%20Compose-2496ed?style=flat-square">
  <img alt="EVE ESI" src="https://img.shields.io/badge/EVE-ESI%20SSO-c23b22?style=flat-square">
</p>

# eve-quartermaster

A containerized, database-first EVE Online quartermaster application for tracking characters, corporations, assets, blueprints, recipes, recipe inputs, production plans, procurement, and ESI sync history.

## Current checkpoint

This repo now contains the first usable quartermaster slice:

- FastAPI backend named `eve-quartermaster`
- PostgreSQL schema modeled with SQLAlchemy
- Alembic migration `0001_initial_schema`
- Redis-backed worker container placeholder for future sync jobs
- React/Vite frontend with overview, ownership, asset, industry, and ESI tabs
- Core list/create API routes for owners, locations, item types, assets, blueprints, recipes, and recipe inputs
- Public ESI status, name resolution, and import endpoints for public IDs
- EVE SSO auth URL scaffolding for authenticated sync
- Idempotent dev seed endpoint for realistic starter data
- Docker Compose stack for local development
- Admin invite flow for generating one-time account creation links with assigned roles
- Corporations workspace for discovering enrolled corporations and syncing corporation asset ledgers
- Corp member/CEO metadata, stale sync warnings, corp blueprint sync, and asset owner-type filters

## Run locally

```powershell
docker compose up --build
```

Then test:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health
- Schema metadata: http://localhost:8000/api/metadata/schema
- OpenAPI docs: http://localhost:8000/docs

## EVE SSO configuration

Local EVE SSO settings live in `.env`, which is ignored by source control:

- `EVE_SSO_CLIENT_ID`
- `EVE_SSO_CLIENT_SECRET`
- `EVE_SSO_CALLBACK_URL`
- `TOKEN_ENCRYPTION_KEY`

The configured callback must exactly match the callback in the EVE developer portal. The local default is `http://localhost:8000/api/esi/auth/callback`.

What I still need from you later:

1. Which characters/corporations should be linked first.
2. Whether this will stay local-only or eventually be hosted for alliance users.

## First testing checkpoint

After `docker compose up --build`, confirm:

1. The frontend loads and shows API status `ok`.
2. Click `Seed` once to add starter EVE data.
3. The overview totals update with owners, asset units, blueprints, and recipes.
4. The Ownership tab shows sample character/corp owners and locations.
5. The Assets tab lets you add a manual asset.
6. The Industry tab shows the sample Retriever blueprint recipe and lets you add recipe inputs.
7. The ESI tab can check server status, resolve names, and import a public type ID like `34`.
8. The backend docs open at `/docs` and include the `quartermaster` and `esi` routes.

If the page shows that the backend API is offline, run:

```powershell
docker compose ps
docker compose logs backend
```

The frontend can load by itself, but it needs the backend listening on port `8000` before the data views populate.

## Expanded ESI scope note

The EVE developer app is intentionally configured with broad scopes so eve-quartermaster can become a full-featured project. When scopes are added or changed, linked characters need to run EVE SSO again before the new permissions are available to sync workers.

## Planned next slices

1. Add EVE SSO token exchange and encrypted refresh-token storage.
2. Add ESI sync workers for character assets, corporation assets, and blueprints.
3. Add edit/delete flows and better validation for the core records.
4. Add SDE import for authoritative item, blueprint, and recipe data.
5. Add production plans that calculate owned vs missing materials.
6. Add market/procurement planning for build-vs-buy decisions.



