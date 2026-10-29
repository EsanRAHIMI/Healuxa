# @healuxa/api-client

Typed client for identity, provider, profile and assessment services, generated from
`packages/api-contracts/openapi/*.openapi.yaml` (openapi-typescript 7.13.0 + openapi-fetch 0.17.0).
Ships TypeScript source (`exports` -> `src/index.ts`): Next.js consumes it via `transpilePackages`,
Expo/Metro and Vitest compile it directly. No Node-only APIs (works in browsers, Node 18+, React Native).

```ts
import { createHealuxaClient, unwrap, unwrapResponse, idempotencyHeader, isApiError } from "@healuxa/api-client";

const api = createHealuxaClient({
  baseUrls: { identity: "https://api.healuxa.com/v1", provider: "https://api.healuxa.com/v1" },
  auth: {
    getAccessToken: () => store.accessToken,          // SecureStore on mobile, httpOnly cookie on web (server side)
    refresh: async () => rotateAndPersist(),           // called ONCE for concurrent 401s; return new token or null
    onSessionExpired: () => signOut(),
  },
  headers: { "Accept-Language": "ar" },
  timeoutMs: 8000,
});

const page = await unwrap(api.provider.GET("/providers", { params: { query: { specialty: "cardiology" } } }));
const { data, etag } = await unwrapResponse(api.provider.GET("/providers/{id}", { params: { path: { id } } }));
await unwrap(api.provider.PATCH("/providers/{id}", { params: { path: { id }, header: { "If-Match": etag! } }, body }));
await unwrap(api.identity.POST("/auth/register", { params: { header: idempotencyHeader() }, body }));
```

- Errors: every non-2xx throws a `HealuxaApiError` subclass (`NotFoundError`, `ConflictError`,
  `ValidationError` with `fieldErrors`/`fieldMessage()`, `RateLimitedError` with `retryAfter`,
  `NetworkError` for no response…). RFC 9457 bodies and FastAPI `{detail: …}` shapes are normalised.
- Refresh: identity-service revokes all sessions when a refresh token is reused — the client's
  single-flight guarantees one rotation per burst of 401s; persist the new pair before resolving.
- Idempotency: create one key per user intent and reuse it on retries (`newIdempotencyKey()`).
- Regenerate after contract changes: `npm run generate -w @healuxa/api-client` (CI runs `check:generated`).
