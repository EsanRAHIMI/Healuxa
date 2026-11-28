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
    "/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The caller's own medical records, each with the organisations it is currently shared with */
        get: operations["listRecords"];
        put?: never;
        /**
         * Upload a document (PDF, JPEG or PNG; type verified from content; encrypted at rest)
         * @description multipart/form-data with one `file` part (max 10 MB by default) and the metadata fields. The file type is taken from its leading bytes; a declared type or extension that contradicts them is refused. Per-user soft limits apply (count and total bytes).
         */
        post: operations["uploadRecord"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/records/{record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        /** One of the caller's records (404 for anyone else's) */
        get: operations["getRecord"];
        put?: never;
        post?: never;
        /** Delete a record and its file bytes; any share of it ends immediately */
        delete: operations["deleteRecord"];
        options?: never;
        head?: never;
        /** Edit a record's title, type, document date or note */
        patch: operations["updateRecord"];
        trace?: never;
    };
    "/records/{record_id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download the file (owner, or a member of an organisation holding an active grant)
         * @description Always served as an attachment with `X-Content-Type-Options: nosniff` and `no-store`. Grantees are authorised on every request: the grant must be active and provider-service must confirm the caller owns the granted practitioner profile or currently staffs the granted facility (facility_admin or scheduler). Refusals are logged; a record the caller has no relationship with answers 404.
         */
        get: operations["downloadRecord"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/record-grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The caller's consent grants (active, expired and revoked), newest first */
        get: operations["listRecordGrants"];
        put?: never;
        /**
         * Share selected records with one provider or facility until an expiry (default 30 days)
         * @description Replaces any active grant of the same records to the same organisation. Emits profile.record_grant_created.
         */
        post: operations["createRecordGrant"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/record-grants/{grant_id}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revoke a grant (or some of its records) with immediate effect; idempotent */
        post: operations["revokeRecordGrant"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/record-access-log": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Who accessed the caller's records, when, from which organisation (append-only, newest first) */
        get: operations["listRecordAccessLog"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/shared-records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Active grants to an organisation the caller currently belongs to ("shared with me") */
        get: operations["listSharedRecords"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/shared-records/{grant_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The records of one active grant (logged as a view of each record) */
        get: operations["getSharedRecords"];
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
        /** @enum {string} */
        RecordType: "lab_result" | "imaging_report" | "prescription" | "referral_letter" | "discharge_summary" | "other";
        /** @enum {string} */
        GranteeType: "provider" | "facility";
        /** @enum {string} */
        GrantPurpose: "consultation" | "treatment" | "second_opinion" | "follow_up" | "other";
        /** @enum {string} */
        GrantStatus: "active" | "expired" | "revoked";
        RecordShare: {
            grant_id: components["schemas"]["Id"];
            grantee_type: components["schemas"]["GranteeType"];
            grantee_id: components["schemas"]["Id"];
            grantee_name: string;
            purpose: components["schemas"]["GrantPurpose"];
            expires_at: components["schemas"]["Timestamp"];
        };
        Record: {
            id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            title: string;
            type: components["schemas"]["RecordType"];
            /** Format: date */
            document_date: string | null;
            note: string | null;
            file_name: string;
            /** @enum {string} */
            content_type: "application/pdf" | "image/jpeg" | "image/png";
            size_bytes: number;
            created_at: components["schemas"]["Timestamp"];
            updated_at: components["schemas"]["Timestamp"];
            shares: components["schemas"]["RecordShare"][];
        };
        RecordUsage: {
            record_count: number;
            total_bytes: number;
            max_records: number;
            max_total_bytes: number;
            max_file_bytes: number;
        };
        RecordList: {
            data: components["schemas"]["Record"][];
            usage: components["schemas"]["RecordUsage"];
        };
        RecordUpload: {
            /**
             * Format: binary
             * @description PDF, JPEG or PNG
             */
            file: string;
            title: string;
            type: components["schemas"]["RecordType"];
            /** Format: date */
            document_date?: string;
            note?: string;
        };
        RecordUpdate: {
            title?: string;
            type?: components["schemas"]["RecordType"];
            /** Format: date */
            document_date?: string | null;
            note?: string | null;
        };
        RecordGrantCreate: {
            grantee_type: components["schemas"]["GranteeType"];
            grantee_id: components["schemas"]["Id"];
            record_ids: components["schemas"]["Id"][];
            purpose: components["schemas"]["GrantPurpose"];
            /** @default 30 */
            expires_in_days: number;
            /** @description Booking the share was offered from */
            appointment_id?: components["schemas"]["Id"];
        };
        RecordGrant: {
            id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            grantee_type: components["schemas"]["GranteeType"];
            grantee_id: components["schemas"]["Id"];
            grantee_name: string;
            record_ids: components["schemas"]["Id"][];
            purpose: components["schemas"]["GrantPurpose"];
            appointment_id: string | null;
            status: components["schemas"]["GrantStatus"];
            created_at: components["schemas"]["Timestamp"];
            expires_at: components["schemas"]["Timestamp"];
            /** Format: date-time */
            revoked_at: string | null;
        };
        RecordAccessLogEntry: {
            id: components["schemas"]["Id"];
            record_id: components["schemas"]["Id"];
            grant_id: string | null;
            /** @enum {string} */
            action: "view" | "download" | "grant" | "revoke" | "delete" | "denied";
            /** @enum {string|null} */
            attempted: "view" | "download" | null;
            /** @description For denied attempts — no_grant, not_member, grant_revoked, grant_expired, missing_permission, verification_unavailable. */
            reason: string | null;
            actor: {
                /** @enum {string} */
                kind: "owner" | "practitioner" | "facility_staff" | "other";
                user_id: string | null;
            };
            organisation: null | {
                type: components["schemas"]["GranteeType"];
                id: components["schemas"]["Id"];
                name: string | null;
            };
            /** @description Coarse only — network prefix (/24 or /48) and browser family. */
            client: {
                network: string | null;
                agent: string | null;
            };
            occurred_at: components["schemas"]["Timestamp"];
        };
        SharedGrant: {
            id: components["schemas"]["Id"];
            patient_user_id: components["schemas"]["Id"];
            grantee_type: components["schemas"]["GranteeType"];
            grantee_id: components["schemas"]["Id"];
            purpose: components["schemas"]["GrantPurpose"];
            appointment_id: string | null;
            record_count: number;
            created_at: components["schemas"]["Timestamp"];
            expires_at: components["schemas"]["Timestamp"];
        };
        SharedRecord: {
            id: components["schemas"]["Id"];
            title: string;
            type: components["schemas"]["RecordType"];
            /** Format: date */
            document_date: string | null;
            note: string | null;
            file_name: string;
            content_type: string;
            size_bytes: number;
        };
        SharedGrantDetail: components["schemas"]["SharedGrant"] & {
            records: components["schemas"]["SharedRecord"][];
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
        /** @description Optimistic concurrency control (ETag) for updates. */
        IfMatch: string;
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
    };
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
    listRecords: {
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
                    "application/json": components["schemas"]["RecordList"];
                };
            };
        };
    };
    uploadRecord: {
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
                "multipart/form-data": components["schemas"]["RecordUpload"];
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
                    "application/json": components["schemas"]["Record"];
                };
            };
            409: components["responses"]["Conflict"];
            /** @description File larger than the limit. */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            422: components["responses"]["Unprocessable"];
            /** @description Records unavailable (encryption not configured). */
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
    getRecord: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["Record"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    deleteRecord: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: components["schemas"]["Id"];
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
    updateRecord: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordUpdate"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Record"];
                };
            };
            404: components["responses"]["NotFound"];
            422: components["responses"]["Unprocessable"];
        };
    };
    downloadRecord: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                record_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description File bytes */
            200: {
                headers: {
                    /** @description attachment; filename=... */
                    "Content-Disposition"?: string;
                    /** @description nosniff */
                    "X-Content-Type-Options"?: string;
                    [name: string]: unknown;
                };
                content: {
                    "application/pdf": string;
                    "image/jpeg": string;
                    "image/png": string;
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            /** @description Membership could not be verified, or the file is temporarily unavailable. */
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
    listRecordGrants: {
        parameters: {
            query?: {
                record_id?: components["schemas"]["Id"];
                status?: components["schemas"]["GrantStatus"];
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
                        data: components["schemas"]["RecordGrant"][];
                    };
                };
            };
        };
    };
    createRecordGrant: {
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
                "application/json": components["schemas"]["RecordGrantCreate"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecordGrant"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    revokeRecordGrant: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                grant_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    record_ids?: components["schemas"]["Id"][];
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
                    "application/json": components["schemas"]["RecordGrant"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listRecordAccessLog: {
        parameters: {
            query?: {
                record_id?: components["schemas"]["Id"];
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
                        data: components["schemas"]["RecordAccessLogEntry"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    listSharedRecords: {
        parameters: {
            query: {
                grantee_type: components["schemas"]["GranteeType"];
                grantee_id: components["schemas"]["Id"];
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
                        data: components["schemas"]["SharedGrant"][];
                    };
                };
            };
            403: components["responses"]["Forbidden"];
            /** @description Membership could not be verified. */
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
    getSharedRecords: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                grant_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["SharedGrantDetail"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
}
