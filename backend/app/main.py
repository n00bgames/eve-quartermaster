from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.api.esi import resume_pending_contact_sync_jobs

    from app.services.intel_collection import start_worker, stop_worker

    from app.db.watchdog import start_watchdog, stop_watchdog
    start_watchdog()
    resume_pending_contact_sync_jobs()
    start_worker()
    from app.services.local_scan import start_cleanup, stop_cleanup
    start_cleanup()
    try:
        yield
    finally:
        await stop_watchdog()
        await stop_worker()
        await stop_cleanup()
        from app.services.esi_transport import close_esi_transport
        await close_esi_transport()


app = FastAPI(title="eve-quartermaster", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)
