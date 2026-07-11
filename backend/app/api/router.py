from fastapi import APIRouter

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.characters import router as characters_router
from app.api.contracts import router as contracts_router
from app.api.context import router as context_router
from app.api.corporations import router as corporations_router
from app.api.esi import router as esi_router
from app.api.fittings import router as fittings_router
from app.api.health import router as health_router
from app.api.mail import router as mail_router
from app.api.market import router as market_router
from app.api.metadata import router as metadata_router
from app.api.navigation import router as navigation_router
from app.api.notifications import router as notifications_router
from app.api.quartermaster import router as quartermaster_router
from app.api.sde import router as sde_router

api_router = APIRouter()
api_router.include_router(analytics_router)
api_router.include_router(auth_router)
api_router.include_router(characters_router)
api_router.include_router(corporations_router)
api_router.include_router(contracts_router)
api_router.include_router(context_router)
api_router.include_router(fittings_router)
api_router.include_router(health_router)
api_router.include_router(mail_router)
api_router.include_router(market_router)
api_router.include_router(metadata_router)
api_router.include_router(navigation_router)
api_router.include_router(notifications_router)
api_router.include_router(quartermaster_router)
api_router.include_router(sde_router)
api_router.include_router(esi_router)


