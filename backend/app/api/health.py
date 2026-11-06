import os

from fastapi import APIRouter, Response

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    return {"status": "ok", "app": settings.app_name, "revision": os.environ.get("EQM_UPDATE_REVISION", "")}
