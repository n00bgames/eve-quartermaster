from fastapi import APIRouter

router = APIRouter(tags=["metadata"])


@router.get("/metadata/schema")
def schema_metadata() -> dict[str, list[str] | dict[str, list[str]]]:
    return {
        "domains": ["identity", "static_eve_data", "assets", "industry", "esi_sync"],
        "core_tables": [
            "users",
            "eve_characters",
            "eve_corporations",
            "eve_alliances",
            "ownership_entities",
            "eve_types",
            "locations",
            "assets",
            "blueprints",
            "industry_activities",
            "industry_activity_inputs",
            "production_plans",
            "production_plan_inputs",
            "procurement_sources",
            "esi_tokens",
            "esi_sync_jobs",
        ],
        "eventual_esi_scopes": {
            "assets": ["esi-assets.read_assets.v1", "esi-assets.read_corporation_assets.v1"],
            "blueprints": ["esi-characters.read_blueprints.v1", "esi-corporations.read_blueprints.v1"],
            "industry": ["esi-industry.read_character_jobs.v1", "esi-industry.read_corporation_jobs.v1"],
            "structures": ["esi-universe.read_structures.v1", "esi-corporations.read_structures.v1"],
            "optional_market_and_finance": [
                "esi-markets.structure_markets.v1",
                "esi-wallet.read_character_wallet.v1",
                "esi-wallet.read_corporation_wallets.v1",
                "esi-contracts.read_character_contracts.v1",
                "esi-contracts.read_corporation_contracts.v1",
            ],
        },
    }
