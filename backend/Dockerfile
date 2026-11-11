# READY ROOM backend — FastAPI + SQLAlchemy, SQLite by default.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    READY_ROOM_DATABASE_URL=sqlite:////data/ready_room.db

WORKDIR /app

# curl is used by the container healthcheck. tzdata provides zoneinfo data so
# the operator timezone resolves correctly in the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1.0" \
    "uvicorn[standard]>=0.30,<1.0" \
    "pydantic>=2.7,<3.0" \
    "pydantic-settings>=2.3,<3.0" \
    "sqlalchemy>=2.0,<3.0" \
    "tzdata>=2024.1"

COPY app ./app

# Persistent SQLite lives on a named volume mounted at /data.
RUN mkdir -p /data

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
