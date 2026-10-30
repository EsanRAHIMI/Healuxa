/**
 * GENERATED from packages/api-contracts/openapi/appointment.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/services/{service_id}/slots": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Bookable slots of a service offering (derived from provider-service availability)
         * @description Slots are derived from the offering's duration and buffer, the provider's weekly availability rules (effective dates), the branch's opening hours, availability exceptions, and existing holds/appointments. Returned in UTC together with the branch IANA time zone and local time. `from` and `to` are branch-local calendar dates (inclusive, at most 31 days).
         */
        get: operations["listAvailableSlots"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/appointments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List appointments (own as customer, or a provider/branch/facility calendar)
         * @description Without a scope filter, returns the caller's own appointments. With `provider_id` the caller must own that provider (or be a facility_admin/scheduler where it practises); with `branch_id` or `facility_id` the caller must be a facility_admin/scheduler of that facility. Holders of `appointments:manage` may list any appointment of their tenant. Sorted by `scheduled_at`.
         */
        get: operations["listAppointments"];
        put?: never;
        /**
         * Place a reservation hold on a slot (status `held`)
         * @description Creates a short hold (default 10 minutes, `hold_expires_at`) on a slot returned by listAvailableSlots. The hold becomes a booking request with transition `submit`. An `Idempotency-Key` replay returns the original appointment; the same key with a different body is rejected with `idempotency_conflict`.
         */
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
        /**
         * Transition status (submit/accept/decline/cancel/check_in/complete/no_show) — emits appointment.* events
         * @description Allowed transitions and actors: `submit` held→requested (customer); `accept` requested→confirmed and `decline` requested→declined (provider owner, facility facility_admin/scheduler, or `appointments:manage`); `cancel` held|requested|confirmed→cancelled (customer — confirmed only until the cancellation cut-off — or provider/facility/manager before the start); `check_in` confirmed→checked_in (provider/facility, from the check-in window before start); `complete` confirmed|checked_in→completed (provider/facility, after the start); `no_show` confirmed→no_show (provider/facility for `party: customer` after the grace period; `party: provider` only with `appointments:manage`). Every transition is recorded in the audit trail.
         */
        post: operations["transitionAppointment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/appointments/{id}/reschedule": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Move a requested/confirmed appointment to another slot (closes it as `rescheduled`, creates a linked appointment)
         * @description Atomically marks the original `rescheduled` and creates a new appointment at `scheduled_at` (`rescheduled_from_id` links them). A customer reschedule needs fresh provider confirmation (new status `requested`) and must happen before the cancellation cut-off; a provider/facility reschedule of a confirmed appointment stays `confirmed`.
         */
        post: operations["rescheduleAppointment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/appointments/{id}/transitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Audit trail of status transitions (who, when, from, to, reason) */
        get: operations["listAppointmentTransitions"];
        put?: never;
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
        /** @enum {string} */
        AppointmentStatus: "held" | "requested" | "confirmed" | "checked_in" | "completed" | "cancelled" | "declined" | "no_show" | "expired" | "rescheduled";
        /**
         * @description Payment hook for Stage D. `not_required` unless payment gating is enabled.
         * @enum {string}
         */
        PaymentStatus: "not_required" | "pending" | "authorized" | "captured" | "refunded";
        /** @enum {string} */
        Party: "customer" | "provider" | "facility" | "platform" | "system";
        Slot: {
            scheduled_at: components["schemas"]["Timestamp"];
            ends_at: components["schemas"]["Timestamp"];
            /** @description Branch-local start, ISO 8601 with UTC offset. */
            local_start: string;
            /** @description Branch-local end, ISO 8601 with UTC offset. */
            local_end: string;
        };
        SlotList: {
            service_id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            branch_id: components["schemas"]["Id"];
            /** @description Branch IANA time zone, e.g. Asia/Dubai. */
            timezone: string;
            duration_minutes: number;
            buffer_minutes: number;
            /** Format: date */
            from: string;
            /** Format: date */
            to: string;
            slots: components["schemas"]["Slot"][];
        };
        CreateAppointment: {
            service_id: components["schemas"]["Id"];
            /** @description Slot start (must equal a slot returned by listAvailableSlots). */
            scheduled_at: components["schemas"]["Timestamp"];
            milestone_id?: components["schemas"]["Id"];
            /** @enum {string} */
            channel?: "app" | "web" | "whatsapp" | "concierge";
            /** @description Book on behalf of a customer — only with `appointments:manage`. Defaults to the caller. */
            user_id?: components["schemas"]["Id"];
        };
        TransitionRequest: {
            /** @enum {string} */
            transition: "submit" | "accept" | "decline" | "cancel" | "check_in" | "complete" | "no_show";
            /**
             * @description decline: no_capacity|out_of_scope|schedule_conflict|other. cancel: customer_request|provider_unavailable|facility_closed|other.
             * @enum {string}
             */
            reason_code?: "no_capacity" | "out_of_scope" | "schedule_conflict" | "customer_request" | "provider_unavailable" | "facility_closed" | "other";
            /** @description Free-text note kept in the audit trail only (never in events). */
            reason?: string;
            /**
             * @description no_show only: who did not show (default customer).
             * @enum {string}
             */
            party?: "customer" | "provider";
        };
        RescheduleRequest: {
            scheduled_at: components["schemas"]["Timestamp"];
            reason?: string;
        };
        Reminder: {
            id: components["schemas"]["Id"];
            /** @description Minutes before scheduled_at. */
            offset_minutes: number;
            due_at: components["schemas"]["Timestamp"];
            /** @enum {string} */
            status: "scheduled" | "dispatched" | "skipped" | "cancelled";
        };
        StatusTransition: {
            id: components["schemas"]["Id"];
            appointment_id: components["schemas"]["Id"];
            from_status?: components["schemas"]["AppointmentStatus"] | null;
            to_status: components["schemas"]["AppointmentStatus"];
            actor_type: components["schemas"]["Party"];
            actor_id?: string | null;
            reason_code?: string | null;
            reason?: string | null;
            occurred_at: components["schemas"]["Timestamp"];
        };
        Appointment: {
            id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            facility_id: components["schemas"]["Id"];
            branch_id: components["schemas"]["Id"];
            service_id: components["schemas"]["Id"];
            milestone_id?: string | null;
            status: components["schemas"]["AppointmentStatus"];
            scheduled_at: components["schemas"]["Timestamp"];
            ends_at: components["schemas"]["Timestamp"];
            /** @description Branch-local start with UTC offset. */
            local_start?: string;
            timezone: string;
            duration_minutes: number;
            buffer_minutes: number;
            service_name?: string | null;
            price?: components["schemas"]["Money"] | null;
            payment_status: components["schemas"]["PaymentStatus"];
            channel?: string | null;
            /** Format: date-time */
            hold_expires_at?: string | null;
            /** Format: date-time */
            requested_at?: string | null;
            /** Format: date-time */
            confirmed_at?: string | null;
            /** Format: date-time */
            checked_in_at?: string | null;
            /** Format: date-time */
            completed_at?: string | null;
            /** Format: date-time */
            cancelled_at?: string | null;
            cancelled_by?: components["schemas"]["Party"] | null;
            decline_reason?: string | null;
            no_show_party?: string | null;
            rescheduled_from_id?: string | null;
            rescheduled_to_id?: string | null;
            reminders?: components["schemas"]["Reminder"][];
            version: number;
            created_at: components["schemas"]["Timestamp"];
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
        Money: {
            /** @description Amount in minor units (e.g. fils). */
            amount_minor: number;
            /** @default AED */
            currency: string;
        };
        PageMeta: {
            /** @description Cursor for the next page; null when no more pages. */
            next_cursor?: string | null;
            limit: number;
            has_more: boolean;
        };
    };
    responses: {
        /** @description provider-service (availability source) is unreachable — no slots are invented. */
        DependencyUnavailable: {
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
        /** @description Semantically invalid request. */
        Unprocessable: {
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
        /** @description Page size (cursor pagination). */
        Limit: number;
        /** @description Opaque cursor returned by the previous page. */
        Cursor: string;
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
    listAvailableSlots: {
        parameters: {
            query: {
                from: string;
                to: string;
            };
            header?: never;
            path: {
                service_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["SlotList"];
                };
            };
            404: components["responses"]["NotFound"];
            422: components["responses"]["Unprocessable"];
            503: components["responses"]["DependencyUnavailable"];
        };
    };
    listAppointments: {
        parameters: {
            query?: {
                user_id?: components["schemas"]["Id"];
                provider_id?: components["schemas"]["Id"];
                branch_id?: components["schemas"]["Id"];
                facility_id?: components["schemas"]["Id"];
                status?: components["schemas"]["AppointmentStatus"];
                from?: components["schemas"]["Timestamp"];
                to?: components["schemas"]["Timestamp"];
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
                /** @description `scheduled_at` (default) or `-scheduled_at`. */
                sort?: "scheduled_at" | "-scheduled_at";
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
            403: components["responses"]["Forbidden"];
            503: components["responses"]["DependencyUnavailable"];
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
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
            503: components["responses"]["DependencyUnavailable"];
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
                    ETag: components["headers"]["ETag"];
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
                "application/json": components["schemas"]["TransitionRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    ETag: components["headers"]["ETag"];
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Appointment"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
            503: components["responses"]["DependencyUnavailable"];
        };
    };
    rescheduleAppointment: {
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
                "application/json": components["schemas"]["RescheduleRequest"];
            };
        };
        responses: {
            /** @description The new appointment */
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
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
            503: components["responses"]["DependencyUnavailable"];
        };
    };
    listAppointmentTransitions: {
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
                    "application/json": {
                        data: components["schemas"]["StatusTransition"][];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
}
