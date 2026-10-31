FROM postgres:16-alpine
COPY --chmod=755 infrastructure/production/postgres/init-databases.sh /docker-entrypoint-initdb.d/10-databases.sh
