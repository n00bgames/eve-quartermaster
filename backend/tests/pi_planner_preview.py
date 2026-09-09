"""Disposable local browser-test server. Never included in application startup."""
import os
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).parents[1]))

from datetime import datetime, timezone
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api import pi_planner as api
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EveCharacter, PiPlanningJob, PiPlanningScenario, User
from tests.test_pi_planner import context, market, request

# Browser requests and the background solver run concurrently. Give each session
# its own connection so one request cannot roll back another request's transaction.
preview_directory = TemporaryDirectory(prefix="eqm-pi-preview-")
preview_database = Path(preview_directory.name) / "preview.sqlite3"
engine=create_engine(f"sqlite:///{preview_database.as_posix()}",connect_args={"check_same_thread":False,"timeout":30})
Base.metadata.create_all(engine,tables=[User.__table__,PiPlanningScenario.__table__,PiPlanningJob.__table__])
factory=sessionmaker(bind=engine,expire_on_commit=False)
with factory() as db:
    db.add(User(id=1,email="preview@example.invalid",display_name="Preview"));db.commit()
def database():
    with factory() as db:yield db
def current_user():
    with factory() as db:return db.get(User,1)
def test_context(*args):
    value=context()
    value.update(as_of=datetime.now(timezone.utc).isoformat(),planets=[p.model_dump() for p in request().planets])
    value["pilots"][0]["skills_synced_at"]=value["as_of"]
    value["baseline"]={"colonies":0,"configured_weekly_output":{},"observed_inventory":{2268:3000},"note":"Synthetic browser-test data"}
    return value
async def prices(*args):return market()
api.SessionLocal=factory
api.require_planetary_view=lambda *args:None
api.visible_characters=lambda *args:[EveCharacter(id=1,character_id=10001,name="Pilot")]
api.build_context=test_context
api.market_snapshot=prices
app=FastAPI()
app.include_router(api.router,prefix="/api")
app.dependency_overrides[get_current_user]=current_user
app.dependency_overrides[get_db]=database

if __name__=="__main__":
    import uvicorn
    try:
        uvicorn.run(app,host="127.0.0.1",port=18481)
    finally:
        engine.dispose()
        preview_directory.cleanup()
