/**
 * GENERATED from packages/api-contracts/openapi/identity.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register a new principal */
        post: operations["authRegister"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Authenticate and issue tokens */
        post: operations["authLogin"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Rotate refresh token, issue new access token */
        post: operations["authRefresh"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke the current session */
        post: operations["authLogout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/delete-account": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Permanently delete the caller's account (password re-confirmation)
         * @description Anonymises the identifier, removes the credential and roles, revokes all sessions and emits auth.user_deleted so every service erases or anonymises its data for this user.
         */
        post: operations["authDeleteAccount"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/introspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Token introspection (used by the edge ForwardAuth) */
        post: operations["authIntrospect"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/.well-known/jwks.json": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** JWKS public keys for offline JWT validation */
        get: operations["getJwks"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/service-token": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Issue a service-to-service JWT (client credentials) */
        post: operations["issueServiceToken"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List the caller's active sessions */
        get: operations["listSessions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/sessions/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke a session */
        delete: operations["revokeSession"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/iam/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List roles */
        get: operations["listRoles"];
        put?: never;
        /** Create a role */
        post: operations["createRole"];
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
        RegisterRequest: {
            /** @description email or phone */
            identifier: string;
            password: string;
            /** @enum {string} */
            locale?: "en" | "ar" | "fa" | "ru";
        };
        LoginRequest: {
            identifier: string;
            password: string;
            mfa_code?: string;
        };
        TokenResponse: {
            access_token: string;
            refresh_token?: string;
            /** @enum {string} */
            token_type: "Bearer";
            expires_in: number;
        };
        Introspection: {
            active?: boolean;
            sub?: components["schemas"]["Id"];
            tenant?: string;
            roles?: string[];
            perms?: string[];
            session_id?: components["schemas"]["Id"];
        };
        Session: {
            id?: components["schemas"]["Id"];
            device?: string;
            ip?: string;
            created_at?: components["schemas"]["Timestamp"];
            last_seen_at?: components["schemas"]["Timestamp"];
        };
        Role: {
            name: string;
            permissions: string[];
            tenant_id?: string;
        };
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
        /** @description ULID/UUID identifier. */
        Id: string;
        /** Format: date-time */
        Timestamp: string;
        PageMeta: {
            /** @description Cursor for the next page; null when no more pages. */
            next_cursor?: string | null;
            limit: number;
            has_more: boolean;
        };
    };
    responses: {
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
        /** @description Missing or invalid token. */
        Unauthorized: {
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
        /** @description Resource not found. */
        NotFound: {
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
    };
    parameters: {
        /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
        IdempotencyKey: string;
        /** @description Page size (cursor pagination). */
        Limit: number;
        /** @description Opaque cursor returned by the previous page. */
        Cursor: string;
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
    authRegister: {
        parameters: {
            query?: never;
            header?: {
                /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterRequest"];
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
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    authLogin: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            401: components["responses"]["Unauthorized"];
            429: components["responses"]["RateLimited"];
        };
    };
    authRefresh: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    refresh_token: string;
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
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            401: components["responses"]["Unauthorized"];
        };
    };
    authLogout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description No Content */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            401: components["responses"]["Unauthorized"];
        };
    };
    authDeleteAccount: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    password: string;
                };
            };
        };
        responses: {
            /** @description Deleted */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            401: components["responses"]["Unauthorized"];
            404: components["responses"]["NotFound"];
        };
    };
    authIntrospect: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    token: string;
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
                    "application/json": components["schemas"]["Introspection"];
                };
            };
        };
    };
    getJwks: {
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
                        keys?: {
                            [key: string]: unknown;
                        }[];
                    };
                };
            };
        };
    };
    issueServiceToken: {
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
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
        };
    };
    listSessions: {
        parameters: {
            query?: {
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
            };
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
                        data: components["schemas"]["Session"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            401: components["responses"]["Unauthorized"];
        };
    };
    revokeSession: {
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
            /** @description No Content */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    listRoles: {
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
                    "application/json": components["schemas"]["Role"][];
                };
            };
            403: components["responses"]["Forbidden"];
        };
    };
    createRole: {
        parameters: {
            query?: never;
            header?: {
                /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Role"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Role"];
                };
            };
            403: components["responses"]["Forbidden"];
            409: components["responses"]["Conflict"];
        };
    };
}
