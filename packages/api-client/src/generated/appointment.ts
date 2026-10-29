/**
 * GENERATED from packages/api-contracts/openapi/appointment.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/appointments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List appointments */
        get: operations["listAppointments"];
        put?: never;
        /** Create an appointment (emits appointment.created) */
        post: operations["createAppointment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/appointments/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get an appointment */
        get: operations["getAppointment"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/appointments/{id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Transition status (accept/decline/complete/no_show) — emits appointment.* events */
        post: operations["transitionAppointment"];
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
        AppointmentStatus: "requested" | "created" | "accepted" | "declined" | "completed" | "no_show" | "cancelled";
        CreateAppointment: {
            user_id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            service_id: components["schemas"]["Id"];
            milestone_id?: components["schemas"]["Id"];
            scheduled_at: components["schemas"]["Timestamp"];
        };
        Appointment: {
            id?: components["schemas"]["Id"];
            user_id?: components["schemas"]["Id"];
            provider_id?: components["schemas"]["Id"];
            service_id?: components["schemas"]["Id"];
            milestone_id?: components["schemas"]["Id"];
            status?: components["schemas"]["AppointmentStatus"];
            scheduled_at?: components["schemas"]["Timestamp"];
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
        /** @description Resource not found. */
        NotFound: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        /** @description Page size (cursor pagination). */
        Limit: number;
        /** @description Opaque cursor returned by the previous page. */
        Cursor: string;
        /** @description Sort field; prefix with '-' for descending. Allow-list per endpoint. */
        Sort: string;
        /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
        IdempotencyKey: string;
        /** @description Optimistic concurrency control (ETag) for updates. */
        IfMatch: string;
    };
    requestBodies: never;
    headers: {
        /** @description URI of the created resource. */
        Location: string;
        /** @description Entity version for optimistic concurrency. */
        ETag: string;
    };
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listAppointments: {
        parameters: {
            query?: {
                user_id?: components["schemas"]["Id"];
                provider_id?: components["schemas"]["Id"];
                status?: components["schemas"]["AppointmentStatus"];
                from?: components["schemas"]["Timestamp"];
                to?: components["schemas"]["Timestamp"];
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
                /** @description Sort field; prefix with '-' for descending. Allow-list per endpoint. */
                sort?: components["parameters"]["Sort"];
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
                        data: components["schemas"]["Appointment"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    createAppointment: {
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
                "application/json": components["schemas"]["CreateAppointment"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    Location: components["headers"]["Location"];
                    ETag: components["headers"]["ETag"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Appointment"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getAppointment: {
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
                    "application/json": components["schemas"]["Appointment"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    transitionAppointment: {
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
                    /** @enum {string} */
                    transition: "accept" | "decline" | "complete" | "no_show" | "reschedule";
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
                    "application/json": components["schemas"]["Appointment"];
                };
            };
            409: components["responses"]["Conflict"];
        };
    };
}
