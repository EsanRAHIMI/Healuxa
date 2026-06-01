# Healuxa identity-service — Dokploy / Docker (TechSpec §24).
# Build context: repository root (apps/).
# Migrations: run `alembic upgrade head` as a pre-deploy step (not on container start).
FROM python:3.12-slim AS builder
WORKDIR /build
COPY packages/py-common ./packages/py-common
COPY services/identity-service ./services/identity-service
RUN pip install --no-cache-dir ./packages/py-common ./services/identity-service

FROM python:3.12-slim
WORKDIR /app/services/identity-service
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/services/identity-service/alembic.ini ./alembic.ini
COPY --from=builder /build/services/identity-service/migrations ./migrations
ENV PYTHONUNBUFFERED=1
EXPOSE 8001
CMD ["uvicorn", "identity_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
