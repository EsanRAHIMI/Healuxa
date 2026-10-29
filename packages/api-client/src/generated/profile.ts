/**
 * GENERATED from packages/api-contracts/openapi/profile.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/profiles/{userId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a customer profile */
        get: operations["getProfile"];
        /** Upsert a profile (emits profile.updated) */
        put: operations["upsertProfile"];
        post?: never;
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
        Profile: {
            user_id?: components["schemas"]["Id"];
            /** @enum {string} */
            lifecycle_stage?: "lead" | "onboarding" | "active" | "at_risk" | "churned" | "reactivated";
            /** @enum {string} */
            vip_tier?: "none" | "silver" | "gold" | "black";
            scores?: {
                [key: string]: number;
            };
            consent?: {
                [key: string]: unknown;
            };
        };
        /** @description ULID/UUID identifier. */
        Id: string;
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
    };
    parameters: {
        /** @description Optimistic concurrency control (ETag) for updates. */
        IfMatch: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getProfile: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                userId: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["Profile"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    upsertProfile: {
        parameters: {
            query?: never;
            header?: {
                /** @description Optimistic concurrency control (ETag) for updates. */
                "If-Match"?: components["parameters"]["IfMatch"];
            };
            path: {
                userId: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Profile"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Profile"];
                };
            };
            409: components["responses"]["Conflict"];
        };
    };
}
