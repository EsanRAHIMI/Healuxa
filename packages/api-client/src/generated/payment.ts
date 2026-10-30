/**
 * GENERATED from packages/api-contracts/openapi/payment.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/payments/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Public client configuration (publishable key, fee disclosure, tax status) */
        get: operations["getPaymentConfig"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payment-quotes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Price a subject server-side (appointment, concierge case, membership) with a transparent breakdown
         * @description appointment — priced from the provider-service offering of the caller's own appointment. membership — priced from the caller's own subscription (subscription.created read model). concierge_case — staff-prepared lines (requires payments:manage) for the named customer.
         */
        post: operations["createPaymentQuote"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payment-quotes/{quote_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a quote (owner or payments staff) */
        get: operations["getPaymentQuote"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List the caller's payments (payments staff may filter by user) */
        get: operations["listPayments"];
        put?: never;
        /**
         * Create a payment intent for a quote (emits payment.authorized/succeeded/failed later, from webhooks)
         * @description The Idempotency-Key header is required. The amount is the quote total. Returns the processor `client_secret` for hosted-field confirmation; the payment stays `pending` until a verified webhook (or server-side retrieval) moves it.
         */
        post: operations["createPayment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a payment (owner or payments staff) */
        get: operations["getPayment"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Re-read the payment from the processor (server-side retrieval) and apply its state */
        post: operations["refreshPayment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}/capture": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Capture an authorised (manual-capture) payment in full */
        post: operations["capturePayment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Void an uncaptured payment (releases an authorisation) */
        post: operations["cancelPayment"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}/refunds": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Refunds of a payment (owner or payments staff) */
        get: operations["listRefunds"];
        put?: never;
        /**
         * Full or partial refund with a reason (never more than captured minus refunded)
         * @description Omit `amount_minor` for a full refund of the remaining balance, or set `apply_policy` to refund what the cancellation policy allows. Concurrent refunds are serialised by a row lock and a database CHECK constraint. Emits payment.refunded and a credit note once the processor confirms.
         */
        post: operations["createRefund"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}/refund-policy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Evaluate the cancellation refund policy for a payment (hook used by booking cancellation) */
        get: operations["evaluateRefundPolicy"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/{id}/ledger": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Double-entry ledger lines of a payment (finance staff) */
        get: operations["getPaymentLedger"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/disputes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Disputes (chargebacks) recorded from processor webhooks */
        get: operations["listDisputes"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/payees/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Grant a user access to a provider's or facility's settlement report (ids from provider-service) */
        post: operations["addPayeeMember"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/settlements/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Revenue lines of one payee (provider/facility members, or finance staff) */
        get: operations["getSettlementReport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/settlements/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import processor balance transactions and payouts for a period (idempotent) */
        post: operations["importSettlements"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/reconciliation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Reconcile ledger and payments against imported processor transactions; flags mismatches */
        get: operations["getReconciliationReport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/payments/webhooks/{gateway}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Processor webhook (raw-body signature verification, idempotent by processor event id; ACL boundary) */
        post: operations["paymentWebhook"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/invoices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The caller's tax invoices and credit notes (payments staff may filter by user) */
        get: operations["listInvoices"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/invoices/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get an invoice or credit note (JSON document; pdf_url reserved for the S3/CloudFront PDF) */
        get: operations["getInvoice"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/invoices/{id}/document": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Printable HTML rendering of an invoice or credit note */
        get: operations["getInvoiceDocument"];
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
        SubjectType: "appointment" | "concierge_case" | "membership";
        /** @enum {string} */
        PaymentStatus: "pending" | "processing" | "authorized" | "succeeded" | "failed" | "canceled" | "partially_refunded" | "refunded";
        /** @enum {string} */
        CaptureMethod: "automatic" | "manual";
        PaymentConfig: {
            /** @enum {string} */
            gateway: "stripe" | "fake";
            publishable_key?: string | null;
            currency: string;
            live_mode: boolean;
            platform_fee: {
                rate_bps: number;
                fixed_minor: number;
                label: string;
            };
            tax: {
                name: string;
                rates_bps: {
                    [key: string]: number;
                };
                /** @enum {string} */
                status: "pending_accountant_review" | "reviewed";
            };
            memberships_enabled?: boolean;
        };
        QuoteLineInput: {
            /** @enum {string} */
            code: "professional_fee" | "facility_fee" | "platform_fee" | "concierge_fee" | "third_party_fee";
            description: string;
            /** @description Tax category (keys of the configured VAT rate table). */
            category: string;
            net_minor: number;
            /** @enum {string} */
            payee_type?: "provider" | "facility" | "healuxa";
            payee_id?: components["schemas"]["Id"];
        };
        CreateQuote: {
            subject_type: components["schemas"]["SubjectType"];
            subject_id: components["schemas"]["Id"];
            /** @description concierge_case only — the customer the staff-prepared quote is for. */
            user_id?: components["schemas"]["Id"];
            /** @description concierge_case only (staff). Ignored/forbidden for other subjects. */
            lines?: components["schemas"]["QuoteLineInput"][];
        };
        QuoteLine: {
            code: string;
            description: string;
            category: string;
            net_minor: number;
            vat_rate_bps: number;
            vat_minor: number;
            gross_minor: number;
            /** @enum {string} */
            payee_type: "provider" | "facility" | "healuxa";
            payee_id?: string | null;
        };
        Quote: {
            id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            subject_type: components["schemas"]["SubjectType"];
            subject_id: components["schemas"]["Id"];
            provider_id?: string | null;
            facility_id?: string | null;
            service_id?: string | null;
            currency: string;
            lines: components["schemas"]["QuoteLine"][];
            subtotal: components["schemas"]["Money"];
            tax: components["schemas"]["Money"];
            total: components["schemas"]["Money"];
            /** @enum {string} */
            tax_status?: "pending_accountant_review" | "reviewed";
            /** @enum {string} */
            status: "open" | "used" | "expired";
            expires_at: components["schemas"]["Timestamp"];
            created_at?: components["schemas"]["Timestamp"];
        };
        CreatePayment: {
            quote_id: components["schemas"]["Id"];
            /** @description Defaults per subject (appointment → manual, confirm-then-charge). Memberships are always automatic. */
            capture_method?: components["schemas"]["CaptureMethod"];
        };
        Payment: {
            id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            quote_id?: components["schemas"]["Id"];
            subject_type: components["schemas"]["SubjectType"];
            subject_id: components["schemas"]["Id"];
            amount: components["schemas"]["Money"];
            amount_authorized_minor?: number;
            amount_captured_minor?: number;
            amount_refunded_minor?: number;
            status: components["schemas"]["PaymentStatus"];
            capture_method: components["schemas"]["CaptureMethod"];
            /** @enum {string} */
            gateway: "tap_payments" | "stripe";
            /** @description Only returned to the paying customer on create/refresh while confirmation is still possible. */
            client_secret?: string | null;
            failure_code?: string | null;
            lines?: components["schemas"]["QuoteLine"][];
            invoice_id?: string | null;
            created_at?: components["schemas"]["Timestamp"];
            /** Format: date-time */
            authorized_at?: string | null;
            /** Format: date-time */
            captured_at?: string | null;
            /** Format: date-time */
            canceled_at?: string | null;
        };
        CreateRefund: {
            amount_minor?: number;
            /** @default false */
            apply_policy: boolean;
            cancelled_at?: components["schemas"]["Timestamp"];
            /** @enum {string} */
            reason: "requested_by_customer" | "appointment_cancelled" | "provider_declined" | "duplicate" | "fraudulent" | "service_issue" | "goodwill";
            note?: string;
        };
        Refund: {
            id: components["schemas"]["Id"];
            payment_id: components["schemas"]["Id"];
            amount: components["schemas"]["Money"];
            reason: string;
            note?: string | null;
            /** @enum {string} */
            status: "pending" | "succeeded" | "failed" | "canceled";
            credit_note_id?: string | null;
            created_at?: components["schemas"]["Timestamp"];
        };
        RefundPolicyDecision: {
            payment_id: string;
            refundable_minor: number;
            refund_percent?: number;
            /** @enum {string} */
            rule: "full_before_window" | "partial_inside_window" | "none_after_start" | "not_captured" | "nothing_left" | "no_schedule";
            window_hours?: number;
            /** Format: date-time */
            scheduled_at?: string | null;
        };
        Dispute: {
            id: string;
            payment_id: string;
            amount: components["schemas"]["Money"];
            reason?: string | null;
            status: string;
            /** Format: date-time */
            evidence_due_by?: string | null;
            created_at?: components["schemas"]["Timestamp"];
            updated_at?: components["schemas"]["Timestamp"];
        };
        LedgerLine: {
            journal_id: string;
            /** @enum {string} */
            kind: "capture" | "refund" | "processor_fee" | "payout" | "dispute" | "dispute_reversal";
            /** @enum {string} */
            account: "processor_clearing" | "provider_revenue" | "facility_revenue" | "healuxa_revenue" | "vat_payable" | "processor_fees" | "disputes" | "bank" | "suspense";
            line_code?: string | null;
            payee_type?: string | null;
            payee_id?: string | null;
            debit_minor: number;
            credit_minor: number;
            currency: string;
            occurred_at?: components["schemas"]["Timestamp"];
        };
        PayeeMember: {
            /** @enum {string} */
            payee_type: "provider" | "facility";
            payee_id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
        };
        SettlementReport: {
            payee_type: string;
            payee_id: string;
            currency: string;
            gross_minor: number;
            refunded_minor: number;
            net_minor: number;
            lines: {
                payment_id?: string;
                kind?: string;
                line_code?: string | null;
                /** @description Positive = earned, negative = reversed by refund. */
                amount_minor?: number;
                occurred_at?: components["schemas"]["Timestamp"];
            }[];
        };
        ReconciliationReport: {
            from: components["schemas"]["Timestamp"];
            to: components["schemas"]["Timestamp"];
            matched: number;
            totals: {
                [key: string]: number;
            };
            mismatches: {
                /** @enum {string} */
                kind: "missing_processor_transaction" | "unknown_processor_transaction" | "amount_mismatch" | "currency_mismatch" | "refund_mismatch" | "ledger_unbalanced" | "ledger_capture_mismatch" | "payout_mismatch";
                payment_id?: string | null;
                processor_ref?: string | null;
                expected_minor?: number | null;
                actual_minor?: number | null;
            }[];
        };
        Invoice: {
            id: components["schemas"]["Id"];
            /** @description Gap-free per tenant and series (INV / CN). */
            number: string;
            /** @enum {string} */
            kind: "invoice" | "credit_note";
            payment_id?: string;
            refund_id?: string | null;
            original_invoice_id?: string | null;
            user_id?: string;
            issued_at?: components["schemas"]["Timestamp"];
            currency?: string;
            seller?: {
                legal_name?: string;
                trn?: string;
                address?: string;
            };
            lines?: components["schemas"]["QuoteLine"][];
            subtotal?: components["schemas"]["Money"];
            tax?: components["schemas"]["Money"];
            total: components["schemas"]["Money"];
            /** Format: uri */
            pdf_url?: string | null;
            document_url?: string;
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
        PageMeta: {
            /** @description Cursor for the next page; null when no more pages. */
            next_cursor?: string | null;
            limit: number;
            has_more: boolean;
        };
    };
    responses: {
        /** @description The payment processor could not be reached; retry with the same Idempotency-Key. */
        ProcessorUnavailable: {
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
        /** @description Validation error. */
        BadRequest: {
            headers: {
                "X-Trace-Id": components["headers"]["X-Trace-Id"];
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        PaymentId: components["schemas"]["Id"];
        /** @description Required for money-moving requests. Same key + same body replays the original result; same key + different body returns 409 idempotency_conflict. */
        RequiredIdempotencyKey: string;
        /** @description Page size (cursor pagination). */
        Limit: number;
        /** @description Opaque cursor returned by the previous page. */
        Cursor: string;
    };
    requestBodies: never;
    headers: {
        /** @description URI of the created resource. */
        Location: string;
        /** @description OpenTelemetry trace id for correlation. */
        "X-Trace-Id": string;
    };
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getPaymentConfig: {
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
                    "application/json": components["schemas"]["PaymentConfig"];
                };
            };
        };
    };
    createPaymentQuote: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateQuote"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Quote"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getPaymentQuote: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                quote_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["Quote"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listPayments: {
        parameters: {
            query?: {
                user_id?: components["schemas"]["Id"];
                subject_id?: components["schemas"]["Id"];
                status?: components["schemas"]["PaymentStatus"];
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
                        data: components["schemas"]["Payment"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    createPayment: {
        parameters: {
            query?: never;
            header: {
                /** @description Required for money-moving requests. Same key + same body replays the original result; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key": components["parameters"]["RequiredIdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreatePayment"];
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
                    "application/json": components["schemas"]["Payment"];
                };
            };
            400: components["responses"]["BadRequest"];
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
            503: components["responses"]["ProcessorUnavailable"];
        };
    };
    getPayment: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
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
                    "application/json": components["schemas"]["Payment"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    refreshPayment: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
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
                    "application/json": components["schemas"]["Payment"];
                };
            };
            404: components["responses"]["NotFound"];
            503: components["responses"]["ProcessorUnavailable"];
        };
    };
    capturePayment: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
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
                    "application/json": components["schemas"]["Payment"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            503: components["responses"]["ProcessorUnavailable"];
        };
    };
    cancelPayment: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    /** @enum {string} */
                    reason?: "requested_by_customer" | "provider_declined" | "duplicate" | "fraudulent" | "abandoned";
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
                    "application/json": components["schemas"]["Payment"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            503: components["responses"]["ProcessorUnavailable"];
        };
    };
    listRefunds: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
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
                        data: components["schemas"]["Refund"][];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    createRefund: {
        parameters: {
            query?: never;
            header: {
                /** @description Required for money-moving requests. Same key + same body replays the original result; same key + different body returns 409 idempotency_conflict. */
                "Idempotency-Key": components["parameters"]["RequiredIdempotencyKey"];
            };
            path: {
                id: components["parameters"]["PaymentId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateRefund"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Refund"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
            503: components["responses"]["ProcessorUnavailable"];
        };
    };
    evaluateRefundPolicy: {
        parameters: {
            query?: {
                cancelled_at?: components["schemas"]["Timestamp"];
            };
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
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
                    "application/json": components["schemas"]["RefundPolicyDecision"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    getPaymentLedger: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["PaymentId"];
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
                        balanced: boolean;
                        data: components["schemas"]["LedgerLine"][];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    listDisputes: {
        parameters: {
            query?: {
                status?: string;
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
                        data: components["schemas"]["Dispute"][];
                    };
                };
            };
        };
    };
    addPayeeMember: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PayeeMember"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PayeeMember"];
                };
            };
            422: components["responses"]["Unprocessable"];
        };
    };
    getSettlementReport: {
        parameters: {
            query: {
                payee_type: "provider" | "facility";
                payee_id: components["schemas"]["Id"];
                from?: components["schemas"]["Timestamp"];
                to?: components["schemas"]["Timestamp"];
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
                    "application/json": components["schemas"]["SettlementReport"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    importSettlements: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    from: components["schemas"]["Timestamp"];
                    to: components["schemas"]["Timestamp"];
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
                        imported: number;
                        skipped: number;
                        payouts: number;
                    };
                };
            };
            503: components["responses"]["ProcessorUnavailable"];
        };
    };
    getReconciliationReport: {
        parameters: {
            query: {
                from: components["schemas"]["Timestamp"];
                to: components["schemas"]["Timestamp"];
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
                    "application/json": components["schemas"]["ReconciliationReport"];
                };
            };
        };
    };
    paymentWebhook: {
        parameters: {
            query?: never;
            header?: {
                "Stripe-Signature"?: string;
            };
            path: {
                gateway: "tap_payments" | "stripe";
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description No Content — processed, duplicate, or ignored */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            400: components["responses"]["BadRequest"];
            404: components["responses"]["NotFound"];
        };
    };
    listInvoices: {
        parameters: {
            query?: {
                user_id?: components["schemas"]["Id"];
                payment_id?: components["schemas"]["Id"];
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
                        data: components["schemas"]["Invoice"][];
                    };
                };
            };
        };
    };
    getInvoice: {
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
                    "application/json": components["schemas"]["Invoice"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    getInvoiceDocument: {
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
                    "text/html": string;
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
}
