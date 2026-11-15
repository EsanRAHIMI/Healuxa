/**
 * GENERATED from packages/api-contracts/openapi/transformation.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/journeys": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create a transformation journey */
        post: operations["createJourney"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{userId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get the active journey for a user */
        get: operations["getJourneyByUser"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/roadmap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get the journey roadmap */
        get: operations["getRoadmap"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/milestones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List milestones */
        get: operations["listMilestones"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/milestones/{milestoneId}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark a milestone complete (emits journey.milestone_completed) */
        post: operations["completeMilestone"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/next-actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get recommended next-best-actions */
        get: operations["getNextActions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/close": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** End the active journey so the customer can start another (idempotent) */
        post: operations["closeJourney"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/reassess": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Trigger a reassessment */
        post: operations["reassessJourney"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/journeys/{id}/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get journey health index */
        get: operations["getJourneyHealth"];
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
        JourneyStatus: "draft" | "onboarding" | "active" | "at_risk" | "renewing" | "completed" | "churned";
        /** @enum {string} */
        GoalCode: "skin_health" | "facial_aesthetics" | "hair_restoration" | "dental_smile" | "weight_management" | "fitness_recovery" | "preventive_checkup" | "longevity" | "mental_wellbeing";
        CreateJourney: {
            user_id: components["schemas"]["Id"];
            /** @description Goals in the customer's order of priority. The plan (phases and steps) is derived from them. */
            primary_goals: components["schemas"]["GoalCode"][];
            target_completion?: components["schemas"]["Timestamp"];
        };
        Journey: {
            id?: components["schemas"]["Id"];
            user_id?: components["schemas"]["Id"];
            primary_goals?: string[];
            status?: components["schemas"]["JourneyStatus"];
            health_index?: number;
            started_at?: components["schemas"]["Timestamp"];
            ltv_projection?: components["schemas"]["Money"];
        };
        Roadmap: {
            journey_id?: components["schemas"]["Id"];
            phases?: components["schemas"]["RoadmapPhase"][];
        };
        RoadmapPhase: {
            id: components["schemas"]["Id"];
            /** @description understand | consult | care | follow_up */
            code?: string | null;
            name: string;
            sequence: number;
            /** @enum {string} */
            status: "pending" | "in_progress" | "completed";
            /** Format: date-time */
            started_at?: string | null;
            /** Format: date-time */
            completed_at?: string | null;
            milestones: components["schemas"]["Milestone"][];
        };
        /** @description A plan step. Bookable steps (consultation, care, follow_up) name the provider-catalog `service_category` to book from; pass the step id as `milestone_id` when creating the appointment and the step then follows that appointment's lifecycle. */
        Milestone: {
            id?: components["schemas"]["Id"];
            title?: string;
            /** @enum {string} */
            status?: "pending" | "scheduled" | "in_progress" | "completed" | "blocked";
            /** Format: date-time */
            due_at?: string | null;
            /** @description intake_assessment | consultation | care | follow_up | progress_review */
            code?: string | null;
            goal?: string | null;
            phase_id?: string | null;
            sequence?: number;
            service_category?: string | null;
            appointment_id?: string | null;
            /** Format: date-time */
            scheduled_at?: string | null;
            /** Format: date-time */
            completed_at?: string | null;
        };
        /** @description Derived from the pending steps of the current phase; the first one has priority high. */
        NextAction: {
            /** @enum {string} */
            action_type?: "book" | "assess" | "renew" | "upsell" | "adherence" | "follow_up" | "contact";
            /** @enum {string} */
            priority?: "low" | "medium" | "high" | "urgent";
            /** Format: date-time */
            due_at?: string | null;
            milestone_id?: string | null;
            milestone_code?: string | null;
            goal?: string | null;
            service_category?: string | null;
        };
        /** @description ULID/UUID identifier. */
        Id: string;
        /** Format: date-time */
        Timestamp: string;
        Money: {
            /** @description Amount in minor units (e.g. fils). */
            amount_minor: number;
            /** @default AED */
            currency: string;
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
        PageMeta: {
            /** @description Cursor for the next page; null when no more pages. */
            next_cursor?: string | null;
            limit: number;
            has_more: boolean;
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
    createJourney: {
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
                "application/json": components["schemas"]["CreateJourney"];
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
                    "application/json": components["schemas"]["Journey"];
                };
            };
            401: components["responses"]["Unauthorized"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getJourneyByUser: {
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
                    "application/json": components["schemas"]["Journey"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    getRoadmap: {
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
                    "application/json": components["schemas"]["Roadmap"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listMilestones: {
        parameters: {
            query?: {
                /** @description Page size (cursor pagination). */
                limit?: components["parameters"]["Limit"];
                /** @description Opaque cursor returned by the previous page. */
                cursor?: components["parameters"]["Cursor"];
            };
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
                        data: components["schemas"]["Milestone"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    completeMilestone: {
        parameters: {
            query?: never;
            header?: {
                /** @description Client-generated unique key for safe retries of mutating requests. Same key + same body replays the original response; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                id: components["schemas"]["Id"];
                milestoneId: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["Milestone"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    getNextActions: {
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
                    "application/json": components["schemas"]["NextAction"][];
                };
            };
        };
    };
    closeJourney: {
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
                    "application/json": components["schemas"]["Journey"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    reassessJourney: {
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
        requestBody?: never;
        responses: {
            /** @description Accepted */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            404: components["responses"]["NotFound"];
        };
    };
    getJourneyHealth: {
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
                        health_index?: number;
                        status?: components["schemas"]["JourneyStatus"];
                    };
                };
            };
        };
    };
}
