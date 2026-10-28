from collections.abc import Generator
import os

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def env_int(name: str, default: int, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(getattr(get_settings(), name.lower(), default))))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def engine_options(url: str) -> dict:
    options = {"pool_pre_ping": True}
    if make_url(url).get_backend_name() == "postgresql":
        options.update(
            pool_size=env_int("DB_POOL_SIZE", 10),
            max_overflow=env_int("DB_MAX_OVERFLOW", 20, 0),
            pool_timeout=env_int("DB_POOL_TIMEOUT_SECONDS", 10),
            pool_recycle=env_int("DB_POOL_RECYCLE_SECONDS", 900),
            pool_use_lifo=True,
            connect_args={"connect_timeout": 5,
                          "application_name": get_settings().db_application_name,
                          "options": f"-c idle_in_transaction_session_timeout={env_int('DB_IDLE_TRANSACTION_TIMEOUT_SECONDS', 300) * 1000}"},
        )
    return options


settings = get_settings()
engine = create_engine(settings.database_url, **engine_options(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except PoolTimeout as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is busy. Please retry shortly.", headers={"Retry-After": "5"}) from exc
    finally:
        db.close()
