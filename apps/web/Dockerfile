# Healuxa web (Next.js standalone). Build context: REPOSITORY ROOT
#   docker build -f apps/web/Dockerfile -t healuxa-web .
# Runtime config is environment-only (see apps/web/.env.example); nothing secret is baked in.

ARG NODE_IMAGE=node:22.22-alpine

FROM ${NODE_IMAGE} AS deps
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
COPY packages/api-contracts/package.json packages/api-contracts/
COPY packages/event-contracts/package.json packages/event-contracts/
COPY packages/ts-common/package.json packages/ts-common/
COPY packages/api-client/package.json packages/api-client/
COPY packages/design-tokens/package.json packages/design-tokens/
COPY packages/i18n/package.json packages/i18n/
COPY apps/web/package.json apps/web/
RUN npm ci --no-audit --no-fund --ignore-scripts

FROM ${NODE_IMAGE} AS build
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production
# Installed tree (root + any nested workspace node_modules), then sources on top.
COPY --from=deps /repo ./
COPY packages/api-client packages/api-client
COPY packages/design-tokens packages/design-tokens
COPY packages/i18n packages/i18n
COPY apps/web apps/web
# next/font downloads Google fonts once at build time and self-hosts them.
RUN npm run build -w @healuxa/web

FROM ${NODE_IMAGE} AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN apk add --no-cache tini
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "apps/web/server.js"]
