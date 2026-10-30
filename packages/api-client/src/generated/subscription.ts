/**
 * GENERATED from packages/api-contracts/openapi/subscription.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/subscriptions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The caller's subscriptions */
        get: operations["listSubscriptions"];
        put?: never;
        /**
         * Subscribe to a plan (emits subscription.created; status incomplete until the first charge succeeds)
         * @description Idempotency-Key is required. Next step for the client: POST /v1/payments/quotes with subject_type=membership and subject_id=<subscription id>, then POST /v1/payments.
         */
        post: operations["createSubscription"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/subscriptions/me/entitlements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Entitlements and credits granted by the caller's active membership */
        get: operations["getMyEntitlements"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/subscriptions/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a subscription (owner or subscriptions staff) */
        get: operations["getSubscription"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/subscriptions/{id}/change-plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upgrade/downgrade plan (emits subscription.upgraded/downgraded; payment-service re-prices the processor subscription) */
        post: operations["changePlan"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/subscriptions/{id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel at the end of the current period (emits subscription.cancellation_scheduled) */
        post: operations["cancelSubscription"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List active subscription plans (public) */
        get: operations["listPlans"];
        put?: never;
        /** Create a plan (staff) */
        post: operations["createPlan"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/plans/{plan_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update price, entitlements or status of a plan (staff; existing subscriptions keep their price) */
        patch: operations["updatePlan"];
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** @enum {string} */
        BillingCycle: "monthly" | "quarterly" | "annual";
        Entitlement: {
            key: string;
            /** @description null = unlimited */
            quantity?: number | null;
        };
        CreateSubscription: {
            /** @description Optional; must equal the caller. */
            user_id?: components["schemas"]["Id"];
            plan_id: string;
            billing_cycle?: components["schemas"]["BillingCycle"];
            offer_id?: components["schemas"]["Id"];
        };
        Subscription: {
            id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            plan_id: string;
            /** @enum {string} */
            status: "incomplete" | "active" | "past_due" | "paused" | "cancelled" | "expired";
            price: components["schemas"]["Money"];
            billing_cycle: components["schemas"]["BillingCycle"];
            credits_remaining?: number | null;
            cancel_at_period_end?: boolean;
            /** Format: date-time */
            current_period_end?: string | null;
            version?: number;
            created_at?: components["schemas"]["Timestamp"];
        };
        Plan: {
            id: string;
            name: string;
            price: components["schemas"]["Money"];
            billing_cycle: components["schemas"]["BillingCycle"];
            /** @description null = unlimited */
            credits?: number | null;
            entitlements?: components["schemas"]["Entitlement"][];
            /** @enum {string} */
            status: "active" | "retired";
        };
        PlanInput: {
            id: string;
            name: string;
            /** @description Net price per cycle (VAT added by payment-service quote). */
            price_minor: number;
            /** @default AED */
            currency: string;
            billing_cycle: components["schemas"]["BillingCycle"];
            credits?: number | null;
            entitlements?: components["schemas"]["Entitlement"][];
        };
        PlanPatch: {
            name?: string;
            price_minor?: number;
            credits?: number | null;
            entitlements?: components["schemas"]["Entitlement"][];
            /** @enum {string} */
            status?: "active" | "retired";
        };
        Entitlements: {
            user_id: string;
            subscription_id?: string | null;
            plan_id?: string | null;
            status?: string | null;
            credits?: number | null;
            /** Format: date-time */
            valid_until?: string | null;
            entitlements: components["schemas"]["Entitlement"][];
        };
        /** @description ULID/UUID identifier. */
        Id: string;
        Money: {
            /** @description Amount in minor units (e.g. fils). */
            amount_minor: number;
            /** @default AED */
            currency: string;
        };
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
        /** @description Semantically invalid request. */
        Unprocessable: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        RequiredIdempotencyKey: string;
        /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
        IdempotencyKey: string;
        /** @description Optimistic concurrency control (ETag) for updates. */
        IfMatch: string;
    };
    requestBodies: never;
    headers: {
        /** @description URI of the created resource. */
        Location: string;
    };
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listSubscriptions: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
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
                    "application/json": {
                        data: components["schemas"]["Subscription"][];
                    };
                };
            };
        };
    };
    createSubscription: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": components["parameters"]["RequiredIdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateSubscription"];
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
                    "application/json": components["schemas"]["Subscription"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getMyEntitlements: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
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
                    "application/json": components["schemas"]["Entitlements"];
                };
            };
        };
    };
    getSubscription: {
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
                    "application/json": components["schemas"]["Subscription"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    changePlan: {
        parameters: {
            query?: never;
            header?: {
                /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
                /** @description Optimistic concurrency control (ETag) for updates. */
                "If-Match"?: components["parameters"]["IfMatch"];
            };
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    to_plan_id: string;
                    offer_id?: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["Subscription"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    cancelSubscription: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    reason?: string;
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
                    "application/json": components["schemas"]["Subscription"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    listPlans: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
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
                    "application/json": components["schemas"]["Plan"][];
                };
            };
        };
    };
    createPlan: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanInput"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    updatePlan: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanPatch"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Plan"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
}
