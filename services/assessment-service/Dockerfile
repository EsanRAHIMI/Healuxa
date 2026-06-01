# Healuxa assessment-service — Dokploy / Docker (TechSpec §24).
# Build context: repository root (apps/).
FROM python:3.12-slim AS builder
WORKDIR /build
COPY packages/py-common ./packages/py-common
COPY services/assessment-service ./services/assessment-service
RUN pip install --no-cache-dir ./packages/py-common ./services/assessment-service

FROM python:3.12-slim
WORKDIR /app/services/assessment-service
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
ENV PYTHONUNBUFFERED=1
EXPOSE 8003
CMD ["uvicorn", "assessment_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
