# syntax=docker/dockerfile:1.7
# Healuxa profile-service — production image for Dokploy (built on the server, never on the dev Mac).
# Build context: repository root.  docker build -f services/profile-service/Dockerfile .
FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY packages/py-common ./packages/py-common
COPY services/profile-service ./services/profile-service
RUN pip install --prefix=/install ./packages/py-common ./services/profile-service

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PORT=8002 WEB_CONCURRENCY=2 FORWARDED_ALLOW_IPS=*
RUN groupadd --system --gid 10001 healuxa \
 && useradd --system --uid 10001 --gid healuxa --home-dir /app --shell /usr/sbin/nologin healuxa
COPY --from=builder /install /usr/local
WORKDIR /app/services/profile-service
USER 10001:10001
EXPOSE 8002
# Liveness only; readiness (/ready) checks dependencies and is for the orchestrator/proxy.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8002'), timeout=2)"]
# Traefik terminates TLS; trust its X-Forwarded-* headers (the container is only reachable on the
# internal network). Narrow FORWARDED_ALLOW_IPS to the proxy subnet in Dokploy if it is known.
CMD ["sh", "-c", "exec uvicorn profile_service.main:app --host 0.0.0.0 --port \"$PORT\" --workers \"$WEB_CONCURRENCY\" --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\" --no-server-header"]
