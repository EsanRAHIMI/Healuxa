/**
 * GENERATED from packages/api-contracts/openapi/concierge.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/concierge/cases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List the caller's own concierge cases (newest first) */
        get: operations["listMyConciergeCases"];
        put?: never;
        /** Submit a concierge request (creates a case in `submitted`) */
        post: operations["createConciergeCase"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/queue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Coordinator work queue for the caller's tenant (oldest first) */
        get: operations["listConciergeQueue"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a case (customer owner, or coordinator/supervisor of the tenant) */
        get: operations["getConciergeCase"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/transitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Move a case to another state (validated against the state machine and the caller's role) */
        post: operations["transitionConciergeCase"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/assignment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Claim a case (coordinator) or assign it to a coordinator (supervisor) */
        post: operations["assignConciergeCase"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/escalation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Escalate a case to a supervisor (customer owner or assigned coordinator) */
        post: operations["escalateConciergeCase"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Audit trail of a case (staff only; oldest first) */
        get: operations["listConciergeCaseAudit"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Internal notes (staff only, never visible to customers) */
        get: operations["listConciergeCaseNotes"];
        put?: never;
        /** Add an internal note (staff only) */
        post: operations["addConciergeCaseNote"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/options": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Provider options proposed for a case (customer owner or staff) */
        get: operations["listConciergeCaseOptions"];
        put?: never;
        /** Propose a provider option (assigned coordinator or supervisor; references only) */
        post: operations["proposeConciergeCaseOption"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/options/{option_id}/select": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Customer selects one of the proposed options */
        post: operations["selectConciergeCaseOption"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Secure messages of a case (customer owner or assigned coordinator only; oldest first) */
        get: operations["listConciergeCaseMessages"];
        put?: never;
        /** Post a secure message (customer owner or assigned coordinator only) */
        post: operations["postConciergeCaseMessage"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/concierge/cases/{id}/messages/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark the counterparty's messages read (read receipts) */
        post: operations["markConciergeCaseMessagesRead"];
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
        CaseStatus: "submitted" | "triaged" | "assigned" | "in_progress" | "awaiting_customer" | "arranged" | "completed" | "cancelled" | "escalated";
        /** @enum {string} */
        CaseCategory: "medical_travel" | "specialist_search" | "second_opinion_coordination" | "logistics" | "other";
        Language: string;
        CaseCreate: {
            category: components["schemas"]["CaseCategory"];
            /** Format: date */
            preferred_start_date?: string | null;
            /** Format: date */
            preferred_end_date?: string | null;
            languages?: components["schemas"]["Language"][];
            destination_city?: string | null;
            /** @description Optional, NON-CLINICAL logistics needs (e.g. wheelchair access, interpreter, travel companions). Do not enter symptoms, diagnoses or medical history. */
            needs_note?: string | null;
        };
        Case: {
            id: components["schemas"]["Id"];
            customer_id: components["schemas"]["Id"];
            category: components["schemas"]["CaseCategory"];
            status: components["schemas"]["CaseStatus"];
            /** Format: date */
            preferred_start_date?: string | null;
            /** Format: date */
            preferred_end_date?: string | null;
            languages: components["schemas"]["Language"][];
            destination_city?: string | null;
            /** @description Non-clinical free text. */
            needs_note?: string | null;
            coordinator_id?: string | null;
            selected_option_id?: string | null;
            /** @description State the case was in when escalated. */
            escalated_from?: string | null;
            first_response_due_at: components["schemas"]["Timestamp"];
            /** Format: date-time */
            first_responded_at?: string | null;
            /** @description First response missed (or is overdue now). */
            sla_breached: boolean;
            /** Format: date-time */
            closed_at?: string | null;
            created_at: components["schemas"]["Timestamp"];
            updated_at: components["schemas"]["Timestamp"];
        };
        CasePage: {
            data: components["schemas"]["Case"][];
            page: components["schemas"]["PageMeta"];
        };
        TransitionRequest: {
            to_status: components["schemas"]["CaseStatus"];
            reason?: string | null;
        };
        AssignRequest: {
            /** @description Omit to claim for yourself. Assigning someone else requires `concierge:supervise`. */
            coordinator_id?: string | null;
        };
        EscalateRequest: {
            reason: string;
        };
        AuditEntry: {
            id: components["schemas"]["Id"];
            /** @enum {string} */
            action: "submitted" | "status_changed" | "assigned" | "option_proposed" | "option_selected";
            from_status?: string | null;
            to_status?: string | null;
            actor_id: string;
            /** @enum {string} */
            actor_role: "customer" | "coordinator" | "supervisor";
            reason?: string | null;
            /** @description Assignee or option id for the action. */
            subject_id?: string | null;
            created_at: components["schemas"]["Timestamp"];
        };
        NoteCreate: {
            body: string;
        };
        Note: {
            id: components["schemas"]["Id"];
            case_id: components["schemas"]["Id"];
            author_id: string;
            body: string;
            created_at: components["schemas"]["Timestamp"];
        };
        ProviderOptionCreate: {
            provider_id: components["schemas"]["Id"];
            facility_id?: string | null;
            branch_id?: string | null;
            service_id?: string | null;
            /** @description Short non-clinical label shown to the customer. */
            label?: string | null;
        };
        ProviderOption: {
            id: components["schemas"]["Id"];
            case_id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            facility_id?: string | null;
            branch_id?: string | null;
            service_id?: string | null;
            label?: string | null;
            /** @enum {string} */
            status: "proposed" | "selected" | "not_selected";
            proposed_by: string;
            created_at: components["schemas"]["Timestamp"];
        };
        MessageCreate: {
            body: string;
        };
        Message: {
            id: components["schemas"]["Id"];
            case_id: components["schemas"]["Id"];
            sender_id: string;
            /** @enum {string} */
            sender_role: "customer" | "coordinator";
            body: string;
            /**
             * Format: date-time
             * @description When the counterparty read it.
             */
            read_at?: string | null;
            created_at: components["schemas"]["Timestamp"];
        };
        ReadRequest: {
            /** @description Mark counterparty messages up to and including this one; omit for all. */
            up_to_message_id?: string | null;
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
        CaseId: components["schemas"]["Id"];
        /** @description Page size (cursor pagination). */
        Limit: number;
        /** @description Opaque cursor returned by the previous page. */
        Cursor: string;
        /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
        IdempotencyKey: string;
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
    listMyConciergeCases: {
        parameters: {
            query?: {
                status?: components["schemas"]["CaseStatus"];
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
                    "application/json": components["schemas"]["CasePage"];
                };
            };
        };
    };
    createConciergeCase: {
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
                "application/json": components["schemas"]["CaseCreate"];
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
                    "application/json": components["schemas"]["Case"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    listConciergeQueue: {
        parameters: {
            query?: {
                status?: components["schemas"]["CaseStatus"];
                category?: components["schemas"]["CaseCategory"];
                /** @description `me`, `unassigned`, or `any` (default). */
                assignee?: "me" | "unassigned" | "any";
                /** @description Only cases whose first-response SLA is breached (or not). */
                breached?: boolean;
                /** @description Exclude completed and cancelled cases (default true). */
                open_only?: boolean;
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
                    "application/json": components["schemas"]["CasePage"];
                };
            };
        };
    };
    getConciergeCase: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
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
                    "application/json": components["schemas"]["Case"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    transitionConciergeCase: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
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
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Case"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    assignConciergeCase: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Case"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    escalateConciergeCase: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EscalateRequest"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Case"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    listConciergeCaseAudit: {
        parameters: {
            query?: {
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
            };
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
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
                        data: components["schemas"]["AuditEntry"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listConciergeCaseNotes: {
        parameters: {
            query?: {
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
            };
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
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
                        data: components["schemas"]["Note"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    addConciergeCaseNote: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NoteCreate"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Note"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listConciergeCaseOptions: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
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
                        data: components["schemas"]["ProviderOption"][];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    proposeConciergeCaseOption: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderOptionCreate"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOption"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    selectConciergeCaseOption: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
                option_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["ProviderOption"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    listConciergeCaseMessages: {
        parameters: {
            query?: {
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
            };
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
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
                        data: components["schemas"]["Message"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    postConciergeCaseMessage: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MessageCreate"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Message"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    markConciergeCaseMessagesRead: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["CaseId"];
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ReadRequest"];
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
                        marked: number;
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
}
