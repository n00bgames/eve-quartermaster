from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.characters import router as characters_router
from app.api.contracts import router as contracts_router
from app.api.corporate_exchange import router as corporate_exchange_router
from app.api.corporate_exchange_bids import router as corporate_exchange_bids_router
from app.api.database_admin import router as database_admin_router
from app.api.context import router as context_router
from app.api.corporations import router as corporations_router
from app.api.esi import router as esi_router
from app.api.events import router as events_router
from app.api.financial_analytics import router as financial_analytics_router
from app.api.character_standings import router as character_standings_router
from app.api.fittings import router as fittings_router
from app.api.health import router as health_router
from app.api.hypernet import router as hypernet_router
from app.api.jump_clones import router as jump_clones_router
from app.api.killboard import router as killboard_router
from app.api.mail import router as mail_router
from app.api.market import router as market_router
from app.api.manufacturing import router as manufacturing_router
from app.api.mining_ledger import router as mining_ledger_router
from app.api.mining_settlements import router as mining_settlements_router
from app.api.metadata import router as metadata_router
from app.api.navigation import router as navigation_router
from app.api.notifications import router as notifications_router
from app.api.notes import router as notes_router
from app.api.planetary_industry import router as planetary_industry_router
from app.api.planetary_analytics import router as planetary_analytics_router
from app.api.quartermaster import router as quartermaster_router
from app.api.research_projects import router as research_projects_router
from app.api.recruiting import router as recruiting_router
from app.api.sde import router as sde_router
from app.api.doctrines import router as doctrines_router
from app.api.skill_plans import router as skill_plans_router
from app.api.srp import router as srp_router

api_router = APIRouter()
api_router.include_router(analytics_router)
api_router.include_router(auth_router)
api_router.include_router(characters_router)
api_router.include_router(corporations_router)
api_router.include_router(contracts_router)
api_router.include_router(corporate_exchange_router)
api_router.include_router(corporate_exchange_bids_router)
api_router.include_router(database_admin_router)
api_router.include_router(context_router)
api_router.include_router(events_router)
api_router.include_router(financial_analytics_router)
api_router.include_router(fittings_router)
api_router.include_router(health_router)
api_router.include_router(hypernet_router)
api_router.include_router(jump_clones_router)
api_router.include_router(killboard_router)
api_router.include_router(mail_router)
api_router.include_router(market_router)
api_router.include_router(manufacturing_router)
api_router.include_router(mining_ledger_router)
api_router.include_router(mining_settlements_router)
api_router.include_router(metadata_router)
api_router.include_router(navigation_router)
api_router.include_router(notifications_router)
api_router.include_router(notes_router)
api_router.include_router(planetary_industry_router)
api_router.include_router(planetary_analytics_router)
api_router.include_router(quartermaster_router)
api_router.include_router(research_projects_router)
api_router.include_router(recruiting_router)
api_router.include_router(sde_router)
api_router.include_router(esi_router)
api_router.include_router(character_standings_router)
api_router.include_router(doctrines_router)
api_router.include_router(skill_plans_router)
api_router.include_router(srp_router)
