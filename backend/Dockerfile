FROM rust:1.89-slim AS eqm-core-builder

WORKDIR /build/rust/eqm-core

COPY rust/eqm-core/Cargo.toml rust/eqm-core/Cargo.lock ./
COPY rust/eqm-core/src ./src

RUN cargo build --locked --release --bin eqm-core

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .
COPY --from=eqm-core-builder /build/rust/eqm-core/target/release/eqm-core /usr/local/bin/eqm-core

FROM base AS test

COPY backend/requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY backend/tests ./tests

CMD ["python", "-m", "pytest", "-q", "tests"]

FROM base AS runtime

CMD ["sh", "-c", "python -m app.db.wait_for_db && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
