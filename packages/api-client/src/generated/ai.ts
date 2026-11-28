/**
 * GENERATED from packages/api-contracts/openapi/ai.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/ai/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start an assistant conversation for the caller */
        post: operations["createAiSession"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ai/sessions/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        /**
         * Get one of the caller's conversations with its turns (oldest first)
         * @description Sessions of other users or tenants answer 404 (no existence leaks).
         */
        get: operations["getAiSession"];
        put?: never;
        post?: never;
        /** Delete one of the caller's conversations and all its turns */
        delete: operations["deleteAiSession"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ai/sessions/{id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Send a customer message and receive the assistant's reply (SSE stream or JSON)
         * @description With `Accept: text/event-stream` the reply is streamed as Server-Sent Events: `turn` (`{user_turn_id}`), any number of `status` (`{tool}` — a tool is running) and `delta` (`{text}` — append), at most one `replace` (`{text}` — a code guardrail replaced the streamed text; show this instead), then exactly one terminal event: `done` (`{turn}` — the persisted AiTurn, whose `content` and `cards` are authoritative) or `error` (`{code}`). Otherwise the persisted assistant AiTurn is returned as JSON. A reply that could not be produced is not stored, and neither is the question. Replaying an `Idempotency-Key` returns the stored answer without calling the model again.
         */
        post: operations["postAiMessage"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/ai/roadmap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate a roadmap draft (internal; consumed by Transformation) — planned, not implemented
         * @description Reserved by the architecture; not served by ai-orchestrator yet.
         */
        post: operations["aiRoadmap"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** @enum {string} */
        AiLocale: "en" | "ar" | "fa";
        AiSessionCreate: {
            locale?: components["schemas"]["AiLocale"];
        };
        AiMessageCreate: {
            /** @description Customer message. The service enforces a lower configured limit (`AiSession.max_message_chars`, default 2000). */
            content: string;
        };
        AiSession: {
            id: components["schemas"]["Id"];
            locale: components["schemas"]["AiLocale"];
            turn_count: number;
            /** @description Concierge case opened by a hand-off in this session. */
            handoff_case_id?: string | null;
            /** @description False when no model is configured; messages then answer 503. */
            assistant_available: boolean;
            max_message_chars: number;
            created_at: components["schemas"]["Timestamp"];
            updated_at: components["schemas"]["Timestamp"];
            turns: components["schemas"]["AiTurn"][];
        };
        AiTurn: {
            id: components["schemas"]["Id"];
            /** @enum {string} */
            role: "user" | "assistant";
            content: string;
            cards: components["schemas"]["AiCard"][];
            /**
             * @description Which code guardrail shaped this reply, if any.
             * @enum {string|null}
             */
            guardrail?: "emergency" | "clinical_redirect" | "ungrounded" | "refusal" | "limit" | null;
            created_at: components["schemas"]["Timestamp"];
        };
        AiCardMoney: {
            /** @description Amount in minor units */
            amount_minor: number;
            /** @description Decimal major units, e.g. "450.00". */
            amount: string;
            currency: string;
        };
        /** @description Action card built server-side from verified tool data of the same turn. `href` is a path relative to the locale root of the client (e.g. `/book/{serviceId}?milestone=...`). */
        AiCard: components["schemas"]["AiServiceCard"] | components["schemas"]["AiProviderCard"] | components["schemas"]["AiFacilityCard"] | components["schemas"]["AiJourneyStepCard"] | components["schemas"]["AiAppointmentCard"] | components["schemas"]["AiConciergeCaseCard"] | components["schemas"]["AiHandoffCard"];
        AiServiceCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "service";
            id: components["schemas"]["Id"];
            title: string;
            category: string;
            duration_minutes?: number | null;
            /** @enum {string} */
            price_type: "fixed" | "from" | "on_request";
            price: components["schemas"]["AiCardMoney"] | null;
            provider_id?: string | null;
            provider_name?: string | null;
            /** @description Open journey step of the caller this booking would complete. */
            milestone_id?: string | null;
            /** @description Up to three real slot start times (UTC) when slots were looked up. */
            next_slots: string[];
            timezone?: string | null;
            href: string;
        };
        AiProviderCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "provider";
            id: components["schemas"]["Id"];
            title: string | null;
            subtitle?: string | null;
            specialties?: string[];
            href: string;
        };
        AiFacilityCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "facility";
            id: components["schemas"]["Id"];
            title: string | null;
            facility_type?: string | null;
            href: string;
        };
        AiJourneyStepCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "journey_step";
            id: components["schemas"]["Id"];
            code?: string | null;
            goal?: string | null;
            status?: string | null;
            service_category?: string | null;
            href: string;
        };
        AiAppointmentCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "appointment";
            id: components["schemas"]["Id"];
            title?: string | null;
            status?: string | null;
            /** Format: date-time */
            scheduled_at?: string | null;
            timezone?: string | null;
            href: string;
        };
        AiConciergeCaseCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "concierge_case";
            id: components["schemas"]["Id"];
            status?: string | null;
            /** Format: date-time */
            first_response_due_at?: string | null;
            href: string;
        };
        AiHandoffCard: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "handoff";
            href: string;
        };
        /** @description ULID/UUID identifier. */
        Id: string;
        /** Format: date-time */
        Timestamp: string;
        /** @description RFC 9457-compatible problem details. Used by ALL non-2xx responses. */
        Error: {
            /**
             * Format: uri
             * @description URI identifying the problem type.
             */
            type?: string;
            /** @description Short, human-readable summary. */
            title: string;
            /** @description HTTP status code. */
            status: number;
            /**
             * @description Stable machine-readable error code.
             * @enum {string}
             */
            code: "validation_error" | "unauthorized" | "forbidden" | "not_found" | "conflict" | "idempotency_conflict" | "rate_limited" | "unprocessable" | "internal_error" | "service_unavailable";
            /** @description Human-readable explanation specific to this occurrence. */
            detail?: string;
            /** @description Path of the request that produced the error. */
            instance?: string;
            /** @description Always present; correlate with logs/traces. */
            trace_id: string;
            /** @description Optional field-level validation details. */
            errors?: {
                field: string;
                code: string;
                message?: string;
            }[];
        };
    };
    responses: {
        /** @description Missing or invalid token. */
        Unauthorized: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description Authenticated but lacks permission/scope/ownership. */
        Forbidden: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description Semantically invalid request. */
        Unprocessable: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description Resource not found. */
        NotFound: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description Conflict (including idempotency_conflict). */
        Conflict: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description Too many requests. */
        RateLimited: {
            headers: {
                "RateLimit-Remaining": components["headers"]["RateLimit-Remaining"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
        IdempotencyKey: string;
    };
    requestBodies: never;
    headers: {
        /** @description URI of the created resource. */
        Location: string;
        /** @description Remaining requests in the current window. */
        "RateLimit-Remaining": number;
    };
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    createAiSession: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["AiSessionCreate"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    Location: components["headers"]["Location"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AiSession"];
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getAiSession: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AiSession"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    deleteAiSession: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Deleted */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            404: components["responses"]["NotFound"];
        };
    };
    postAiMessage: {
        parameters: {
            query?: never;
            header?: {
                /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AiMessageCreate"];
            };
        };
        responses: {
            /** @description The assistant's reply. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AiTurn"];
                    "text/event-stream": string;
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
            429: components["responses"]["RateLimited"];
            /** @description The assistant is unavailable (no model configured or the provider failed). */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    aiRoadmap: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    user_id: components["schemas"]["Id"];
                    goals: string[];
                };
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
}
