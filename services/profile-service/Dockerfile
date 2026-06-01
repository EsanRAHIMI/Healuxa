# Healuxa profile-service — Dokploy / Docker (TechSpec §24).
# Build context: repository root (apps/).
FROM python:3.12-slim AS builder
WORKDIR /build
COPY packages/py-common ./packages/py-common
COPY services/profile-service ./services/profile-service
RUN pip install --no-cache-dir ./packages/py-common ./services/profile-service

FROM python:3.12-slim
WORKDIR /app/services/profile-service
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
ENV PYTHONUNBUFFERED=1
EXPOSE 8002
CMD ["uvicorn", "profile_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
