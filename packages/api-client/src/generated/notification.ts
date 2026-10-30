/**
 * GENERATED from packages/api-contracts/openapi/notification.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/notifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The caller's in-app inbox (newest first) */
        get: operations["listNotifications"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/unread-count": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Number of unread inbox notifications for the caller */
        get: operations["getUnreadNotificationCount"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/{id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark one of the caller's notifications read (idempotent) */
        post: operations["markNotificationRead"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/read-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark every unread inbox notification of the caller read */
        post: operations["markAllNotificationsRead"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/send": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Send a notification (internal; respects consent + quiet hours) */
        post: operations["sendNotification"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/preferences/{userId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get channel preferences + quiet hours (own user only; defaults when never set) */
        get: operations["getPreferences"];
        /** Update channel preferences (own user only; omitted fields keep their value) */
        put: operations["updatePreferences"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notification-devices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register (or re-register) a push device token for the caller */
        post: operations["registerDeviceToken"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notification-devices/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove one of the caller's device tokens */
        delete: operations["deleteDeviceToken"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/recipient-links": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register who is notified about an entity (internal; e.g. a provider profile's owner) */
        post: operations["registerRecipientLink"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/notifications/recipient-links/{entity_type}/{entity_id}/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Stop notifying a user about an entity (internal) */
        delete: operations["removeRecipientLink"];
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
        Channel: "in_app" | "email" | "sms" | "whatsapp" | "push";
        /**
         * @description concierge, appointments, provider_account and account are transactional; marketing needs consent.
         * @enum {string}
         */
        Category: "concierge" | "appointments" | "provider_account" | "account" | "marketing";
        /** @enum {string} */
        Locale: "en" | "ar" | "fa";
        /** @enum {string} */
        EntityType: "provider" | "facility" | "concierge_case" | "appointment" | "user";
        SendRequest: {
            user_id: components["schemas"]["Id"];
            /** @description Defaults to the caller's tenant. */
            tenant_id?: string | null;
            /**
             * @description Restrict to one channel (`web_push` is accepted as an alias of `push`).
             * @enum {string|null}
             */
            channel?: "push" | "web_push" | "email" | "sms" | "in_app" | "whatsapp" | null;
            channels?: components["schemas"]["Channel"][];
            /** @description Template key from the service's catalog. */
            template: string;
            /** @description Template parameters only (ids, enum values, timestamps; strings ≤ 200 chars). Unknown keys are rejected. */
            data?: {
                [key: string]: unknown;
            };
            entity_type?: components["schemas"]["EntityType"] | null;
            entity_id?: string | null;
        };
        SendResult: {
            notification_id: components["schemas"]["Id"];
            deliveries: {
                channel: components["schemas"]["Channel"];
                /** @enum {string} */
                status: "pending" | "sent" | "skipped" | "dead_letter";
                skip_reason?: string | null;
            }[];
        };
        Notification: {
            id: components["schemas"]["Id"];
            category: components["schemas"]["Category"];
            template: string;
            locale: components["schemas"]["Locale"];
            title: string;
            body: string;
            entity_type?: string | null;
            entity_id?: string | null;
            /** Format: date-time */
            read_at?: string | null;
            created_at: components["schemas"]["Timestamp"];
        };
        QuietHours: {
            start: string;
            end: string;
        };
        ChannelSwitches: {
            in_app?: boolean;
            email?: boolean;
            sms?: boolean;
            whatsapp?: boolean;
            push?: boolean;
        };
        Preferences: {
            user_id: string;
            locale: components["schemas"]["Locale"];
            /** @description IANA time zone used for quiet hours. */
            timezone: string;
            quiet_hours?: components["schemas"]["QuietHours"] | null;
            /** @description Consent for marketing; false by default. */
            marketing_opt_in: boolean;
            /** @description Effective switches per category (defaults merged with the user's choices). */
            channels: {
                [key: string]: components["schemas"]["ChannelSwitches"];
            };
            /** Format: date-time */
            updated_at?: string | null;
        };
        PreferencesUpdate: {
            locale?: components["schemas"]["Locale"];
            timezone?: string;
            quiet_hours?: components["schemas"]["QuietHours"] | null;
            marketing_opt_in?: boolean;
            channels?: {
                [key: string]: components["schemas"]["ChannelSwitches"];
            };
        };
        DeviceTokenCreate: {
            /** @enum {string} */
            platform: "ios" | "android" | "web";
            token: string;
        };
        DeviceToken: {
            id: components["schemas"]["Id"];
            /** @enum {string} */
            platform: "ios" | "android" | "web";
            /** @description Last characters only; tokens are never returned. */
            token_suffix: string;
            created_at: components["schemas"]["Timestamp"];
        };
        RecipientLink: {
            tenant_id?: string | null;
            entity_type: components["schemas"]["EntityType"];
            entity_id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            role?: string | null;
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
        /** @description Page size (cursor pagination). */
        Limit: number;
        /** @description Opaque cursor returned by the previous page. */
        Cursor: string;
        /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
        IdempotencyKey: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listNotifications: {
        parameters: {
            query?: {
                unread_only?: boolean;
                category?: components["schemas"]["Category"];
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
                        data: components["schemas"]["Notification"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    getUnreadNotificationCount: {
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
                        unread: number;
                    };
                };
            };
        };
    };
    markNotificationRead: {
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
                    "application/json": components["schemas"]["Notification"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    markAllNotificationsRead: {
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
                        marked: number;
                    };
                };
            };
        };
    };
    sendNotification: {
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
                "application/json": components["schemas"]["SendRequest"];
            };
        };
        responses: {
            /** @description Accepted (deliveries are queued; skipped channels are reported) */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SendResult"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getPreferences: {
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
                    "application/json": components["schemas"]["Preferences"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    updatePreferences: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                userId: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreferencesUpdate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Preferences"];
                };
            };
            404: components["responses"]["NotFound"];
            422: components["responses"]["Unprocessable"];
        };
    };
    registerDeviceToken: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeviceTokenCreate"];
            };
        };
        responses: {
            /** @description Registered */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeviceToken"];
                };
            };
            422: components["responses"]["Unprocessable"];
        };
    };
    deleteDeviceToken: {
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
            /** @description Removed */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            404: components["responses"]["NotFound"];
        };
    };
    registerRecipientLink: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecipientLink"];
            };
        };
        responses: {
            /** @description Registered (idempotent) */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecipientLink"];
                };
            };
        };
    };
    removeRecipientLink: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entity_type: components["schemas"]["EntityType"];
                entity_id: components["schemas"]["Id"];
                user_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Removed */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            404: components["responses"]["NotFound"];
        };
    };
}
