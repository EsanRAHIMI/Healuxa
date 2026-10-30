/**
 * GENERATED from packages/api-contracts/openapi/provider.openapi.yaml by openapi-typescript.
 * Do not edit by hand: run `npm run generate -w @healuxa/api-client`.
 */

export interface paths {
    "/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search the public provider directory (verified, active providers only) */
        get: operations["searchProviders"];
        put?: never;
        /** Submit a provider application for the authenticated user */
        post: operations["createProvider"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get the provider profile owned by the authenticated user */
        get: operations["getMyProvider"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        /** Get a provider (public view unless caller is the owner or staff) */
        get: operations["getProvider"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update profile fields (owner or staff). Identity fields reset verification. */
        patch: operations["updateProvider"];
        trace?: never;
    };
    "/providers/{id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Activate, suspend or offboard a provider (staff only) */
        post: operations["changeProviderStatus"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}/credentials": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        /** List a provider's credentials (owner or staff) */
        get: operations["listCredentials"];
        put?: never;
        /** Submit a license or certification for review (owner) */
        post: operations["submitCredential"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}/credentials/{credential_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
                credential_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify or reject a credential after checking the issuing authority (staff only) */
        post: operations["reviewCredential"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}/affiliations": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        /** List a provider's facility affiliations (owner or staff) */
        get: operations["listProviderAffiliations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}/services": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add a service offering at an affiliated branch (owner, or that facility's admin) */
        post: operations["createServiceOffering"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}/availability-rules": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        /** List weekly availability rules (owner, affiliated facility schedulers, staff, services) */
        get: operations["listAvailabilityRules"];
        put?: never;
        /** Add a weekly working window at an active affiliation's branch */
        post: operations["createAvailabilityRule"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/providers/{id}/availability-exceptions": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        /** List date-specific unavailability (leave, holidays) */
        get: operations["listAvailabilityExceptions"];
        put?: never;
        /** Block a time range (leave, holiday, training) */
        post: operations["createAvailabilityException"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/availability-rules/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove a weekly availability rule */
        delete: operations["deleteAvailabilityRule"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/services": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Public service catalog (bookable offerings of verified, active, affiliated providers) */
        get: operations["listServices"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/services/{service_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                service_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        /** Get one service offering (public if bookable) */
        get: operations["getServiceOffering"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update price, duration or status of an offering */
        patch: operations["updateServiceOffering"];
        trace?: never;
    };
    "/facilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Public facility directory (verified, active facilities) */
        get: operations["searchFacilities"];
        put?: never;
        /** Register a facility; the caller becomes its first facility_admin */
        post: operations["createFacility"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/mine": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Facilities where the caller holds a staff role (private view) */
        get: operations["listMyFacilities"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/{facility_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        /** Get a facility (public view unless caller is its staff or platform staff) */
        get: operations["getFacility"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update facility details (facility_admin) */
        patch: operations["updateFacility"];
        trace?: never;
    };
    "/facilities/{facility_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify or reject the facility license, activating or rejecting it (staff only) */
        post: operations["reviewFacility"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/{facility_id}/branches": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        /** List a facility's branches */
        get: operations["listBranches"];
        put?: never;
        /** Add a branch (facility_admin) */
        post: operations["createBranch"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/branches/{branch_id}/operating-hours": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                branch_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        /** Weekly opening hours of a branch (branch-local time) */
        get: operations["getOperatingHours"];
        /** Replace the weekly opening hours (facility_admin) */
        put: operations["replaceOperatingHours"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/{facility_id}/staff": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        /** List staff memberships (facility_admin or platform staff) */
        get: operations["listFacilityStaff"];
        put?: never;
        /** Grant a user a facility role (facility_admin) */
        post: operations["addFacilityStaff"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/{facility_id}/staff/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
                user_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke a user's facility role (facility_admin; the last admin cannot be removed) */
        delete: operations["removeFacilityStaff"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/facilities/{facility_id}/affiliations": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        /** List practitioners affiliated with a facility (facility staff) */
        get: operations["listFacilityAffiliations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/affiliations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Provider requests, or facility_admin invites, an affiliation at a branch */
        post: operations["requestAffiliation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/affiliations/{affiliation_id}/decision": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                affiliation_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Counterparty approves/declines a pending affiliation, or either side ends an active one */
        post: operations["decideAffiliation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/scheduling/services/{service_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Raw scheduling facts for one offering (service-to-service, consumed by appointment-service)
         * @description Offering duration/buffer and status, provider/facility/branch status, branch time zone, whether the affiliation is active, branch opening hours, the provider's availability rules at the offering's branch, and availability exceptions overlapping [from, to). `bookable` mirrors the public catalog rule. Mesh-internal; requires a service token (`service` permission).
         */
        get: operations["getSchedulingContext"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/scheduling/actors/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Providers a user owns and their facility staff roles (service-to-service authorization input) */
        get: operations["getSchedulingActor"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Staff queue of providers in this tenant, filterable by status (oldest first) */
        get: operations["listAdminProviders"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/credentials": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Staff credential review queue (defaults to submitted; oldest first) */
        get: operations["listAdminCredentials"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/admin/facilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Staff facility verification queue, filterable by status (oldest first) */
        get: operations["listAdminFacilities"];
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
        SchedulingContext: {
            offering: {
                id: string;
                provider_id: string;
                facility_id: string;
                branch_id: string;
                name: string;
                category: string;
                duration_minutes: number;
                buffer_minutes: number;
                mode: string;
                status: string;
                price_type: string;
                professional_fee_minor: number | null;
                facility_fee_minor: number | null;
                currency: string;
            };
            provider: {
                id: string;
                user_id: string;
                status: string;
                verification_status: string;
            };
            facility: {
                id: string;
                status: string;
                verification_status: string;
            };
            branch: {
                id: string;
                facility_id: string;
                /** @description IANA time zone */
                timezone: string;
                status: string;
            };
            affiliation_active: boolean;
            bookable: boolean;
            operating_hours: {
                /** @description 0 = Monday (ISO) */
                weekday: number;
                /** @description Branch-local minutes since midnight */
                start_minute: number;
                end_minute: number;
            }[];
            availability_rules: {
                id: string;
                weekday: number;
                start_minute: number;
                end_minute: number;
                /** Format: date */
                effective_from: string;
                /** Format: date */
                effective_until: string | null;
            }[];
            exceptions: {
                id: string;
                branch_id: string | null;
                /** Format: date-time */
                starts_at: string;
                /** Format: date-time */
                ends_at: string;
                reason: string;
            }[];
        };
        SchedulingActor: {
            user_id: string;
            provider_ids: string[];
            facility_roles: {
                facility_id: string;
                /** @enum {string} */
                role: "facility_admin" | "scheduler" | "billing";
            }[];
        };
        /** @enum {string} */
        ProviderType: "doctor" | "clinic" | "therapist" | "trainer" | "nutritionist" | "pharmacy" | "brand" | "home_visit";
        /** @enum {string} */
        ProviderStatus: "pending" | "active" | "suspended" | "offboarded";
        /** @enum {string} */
        VerificationStatus: "unverified" | "under_review" | "verified" | "rejected";
        /** @description Text keyed by BCP 47 language tag (en, ar, fa, fr, de). */
        LocalizedText: {
            [key: string]: string;
        };
        Provider: {
            id: components["schemas"]["Id"];
            type: components["schemas"]["ProviderType"];
            display_name: string;
            /** @description Professional title, e.g. 'Consultant Infectious Diseases'. */
            title?: string;
            bio?: components["schemas"]["LocalizedText"];
            specialties: string[];
            languages: string[];
            /** @description Read-model cache owned by Review service. */
            readonly quality_score?: number | null;
            /** @description Read-model cache owned by Provider Success. */
            readonly success_score?: number | null;
            status: components["schemas"]["ProviderStatus"];
            verification_status: components["schemas"]["VerificationStatus"];
            /** @description Public summary of verified credentials (authority, kind, expiry) — never numbers. */
            readonly verified_credentials?: {
                kind?: components["schemas"]["CredentialKind"];
                issuing_authority?: string;
                /** Format: date */
                valid_until?: string | null;
            }[];
            /** @description Owner account; returned to owner and staff only. */
            readonly user_id?: string;
            readonly version?: number;
            created_at?: components["schemas"]["Timestamp"];
            updated_at?: components["schemas"]["Timestamp"];
        };
        ProviderInput: {
            type: components["schemas"]["ProviderType"];
            display_name: string;
            title?: string;
            bio?: components["schemas"]["LocalizedText"];
            specialties: string[];
            languages: string[];
        };
        ProviderPatch: {
            display_name?: string;
            title?: string;
            bio?: components["schemas"]["LocalizedText"];
            specialties?: string[];
            languages?: string[];
        };
        StatusChange: {
            status: components["schemas"]["ProviderStatus"];
            reason: string;
        };
        /** @enum {string} */
        CredentialKind: "professional_license" | "board_certification" | "malpractice_insurance" | "other";
        Credential: {
            id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            kind: components["schemas"]["CredentialKind"];
            /** @description e.g. DHA, DOH, MOHAP */
            issuing_authority: string;
            /** @description ISO 3166-2, e.g. AE-DU */
            jurisdiction?: string;
            number: string;
            /** Format: date */
            valid_from?: string | null;
            /** Format: date */
            valid_until?: string | null;
            /** @description Encrypted object-storage key of the uploaded document. */
            document_ref?: string | null;
            /** @enum {string} */
            status: "submitted" | "verified" | "rejected" | "expired";
            review_note?: string | null;
            /** Format: date-time */
            reviewed_at?: string | null;
        };
        CredentialInput: {
            kind: components["schemas"]["CredentialKind"];
            issuing_authority: string;
            jurisdiction?: string;
            number: string;
            /** Format: date */
            valid_from?: string;
            /** Format: date */
            valid_until?: string;
            document_ref?: string;
        };
        AdminCredential: components["schemas"]["Credential"] & {
            submitted_at: components["schemas"]["Timestamp"];
        };
        ReviewDecision: {
            /** @enum {string} */
            decision: "verify" | "reject";
            /** @description Required when rejecting. */
            note?: string;
        };
        /** @enum {string} */
        FacilityType: "clinic" | "hospital" | "medical_center" | "day_surgery" | "diagnostic_center" | "pharmacy" | "wellness_center";
        Facility: {
            id: components["schemas"]["Id"];
            type: components["schemas"]["FacilityType"];
            name: string;
            description?: components["schemas"]["LocalizedText"];
            /** @description Returned to facility staff and platform staff only. */
            license_authority?: string;
            /** @description Returned to facility staff and platform staff only. */
            license_number?: string;
            website?: string | null;
            phone?: string | null;
            /** @enum {string} */
            status: "pending" | "active" | "suspended" | "offboarded";
            verification_status: components["schemas"]["VerificationStatus"];
            created_at?: components["schemas"]["Timestamp"];
        };
        FacilityInput: {
            type: components["schemas"]["FacilityType"];
            name: string;
            description?: components["schemas"]["LocalizedText"];
            license_authority: string;
            license_number: string;
            website?: string;
            phone?: string;
        };
        FacilityPatch: {
            name?: string;
            description?: components["schemas"]["LocalizedText"];
            website?: string;
            phone?: string;
        };
        Branch: {
            id: components["schemas"]["Id"];
            facility_id: components["schemas"]["Id"];
            name: string;
            address_line?: string;
            city: string;
            emirate?: string | null;
            /** @description ISO 3166-1 alpha-2 */
            country: string;
            /** @description IANA zone, e.g. Asia/Dubai */
            timezone: string;
            latitude?: number | null;
            longitude?: number | null;
            phone?: string | null;
            /** @enum {string} */
            status?: "active" | "closed";
        };
        BranchInput: {
            name: string;
            address_line: string;
            city: string;
            emirate?: string;
            country: string;
            timezone: string;
            latitude?: number;
            longitude?: number;
            phone?: string;
        };
        TimeWindow: {
            /** @description 0 = Monday … 6 = Sunday (ISO) */
            weekday: number;
            start: string;
            end: string;
        };
        OperatingHours: {
            readonly branch_id?: string;
            readonly timezone?: string;
            windows: components["schemas"]["TimeWindow"][];
        };
        /** @enum {string} */
        StaffRole: "facility_admin" | "scheduler" | "billing";
        StaffMember: {
            facility_id: components["schemas"]["Id"];
            user_id: components["schemas"]["Id"];
            role: components["schemas"]["StaffRole"];
            created_at?: components["schemas"]["Timestamp"];
        };
        StaffMemberInput: {
            user_id: components["schemas"]["Id"];
            role: components["schemas"]["StaffRole"];
        };
        Affiliation: {
            id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            facility_id: components["schemas"]["Id"];
            branch_id: components["schemas"]["Id"];
            /** @enum {string} */
            status: "pending" | "active" | "declined" | "ended";
            /** @enum {string} */
            initiated_by: "provider" | "facility";
            /** Format: date-time */
            decided_at?: string | null;
            created_at?: components["schemas"]["Timestamp"];
        };
        AffiliationInput: {
            provider_id: components["schemas"]["Id"];
            branch_id: components["schemas"]["Id"];
        };
        AffiliationDecision: {
            /** @enum {string} */
            decision: "approve" | "decline" | "end";
        };
        ServiceOffering: {
            id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            facility_id?: components["schemas"]["Id"];
            branch_id: components["schemas"]["Id"];
            category: string;
            name: string;
            description?: components["schemas"]["LocalizedText"];
            duration_minutes: number;
            /** @description Turnaround after each appointment. */
            buffer_minutes?: number;
            /** @enum {string} */
            mode?: "in_person" | "home_visit";
            /** @enum {string} */
            price_type: "fixed" | "from" | "on_request";
            /** @description Total = professional_fee + facility_fee. Null when on_request. */
            price?: components["schemas"]["Money"] | null;
            professional_fee?: components["schemas"]["Money"] | null;
            facility_fee?: components["schemas"]["Money"] | null;
            /** @enum {string} */
            status: "draft" | "active" | "retired";
        };
        ServiceOfferingInput: {
            branch_id: components["schemas"]["Id"];
            category: string;
            name: string;
            description?: components["schemas"]["LocalizedText"];
            duration_minutes: number;
            /** @default 0 */
            buffer_minutes: number;
            /**
             * @default in_person
             * @enum {string}
             */
            mode: "in_person" | "home_visit";
            /** @enum {string} */
            price_type: "fixed" | "from" | "on_request";
            professional_fee_minor?: number;
            facility_fee_minor?: number;
            /** @default AED */
            currency: string;
        };
        ServiceOfferingPatch: {
            name?: string;
            description?: components["schemas"]["LocalizedText"];
            duration_minutes?: number;
            buffer_minutes?: number;
            /** @enum {string} */
            price_type?: "fixed" | "from" | "on_request";
            professional_fee_minor?: number;
            facility_fee_minor?: number;
            /** @enum {string} */
            status?: "draft" | "active" | "retired";
        };
        AvailabilityRule: {
            id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            branch_id: components["schemas"]["Id"];
            /** @description Branch timezone the times are expressed in. */
            readonly timezone?: string;
            weekday: number;
            start: string;
            end: string;
            /** Format: date */
            effective_from: string;
            /** Format: date */
            effective_until?: string | null;
        };
        AvailabilityRuleInput: {
            branch_id: components["schemas"]["Id"];
            weekday: number;
            start: string;
            end: string;
            /** Format: date */
            effective_from: string;
            /** Format: date */
            effective_until?: string;
        };
        AvailabilityException: {
            id: components["schemas"]["Id"];
            provider_id: components["schemas"]["Id"];
            /** @description Null = applies at every branch. */
            branch_id?: string | null;
            /** Format: date-time */
            starts_at: string;
            /** Format: date-time */
            ends_at: string;
            /** @enum {string} */
            reason: "leave" | "public_holiday" | "training" | "other";
        };
        AvailabilityExceptionInput: {
            branch_id?: components["schemas"]["Id"];
            /** Format: date-time */
            starts_at: string;
            /** Format: date-time */
            ends_at: string;
            /** @enum {string} */
            reason: "leave" | "public_holiday" | "training" | "other";
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
        Money: {
            /** @description Amount in minor units (e.g. fils). */
            amount_minor: number;
            /** @default AED */
            currency: string;
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
        /** @description Missing or invalid token. */
        Unauthorized: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        ProviderId: components["schemas"]["Id"];
        FacilityId: components["schemas"]["Id"];
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
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    searchProviders: {
        parameters: {
            query?: {
                type?: components["schemas"]["ProviderType"];
                specialty?: string;
                language?: string;
                city?: string;
                /** @description lat,lng */
                near?: string;
                radius_km?: number;
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
                        data: components["schemas"]["Provider"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    createProvider: {
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
                "application/json": components["schemas"]["ProviderInput"];
            };
        };
        responses: {
            /** @description Created (status pending, verification unverified) */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Provider"];
                };
            };
            409: components["responses"]["Conflict"];
        };
    };
    getMyProvider: {
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
                    "application/json": components["schemas"]["Provider"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    getProvider: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
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
                    "application/json": components["schemas"]["Provider"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    updateProvider: {
        parameters: {
            query?: never;
            header?: {
                /** @description Optimistic concurrency control (ETag) for updates. */
                "If-Match"?: components["parameters"]["IfMatch"];
            };
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderPatch"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Provider"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    changeProviderStatus: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusChange"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Provider"];
                };
            };
            404: components["responses"]["NotFound"];
            422: components["responses"]["Unprocessable"];
        };
    };
    listCredentials: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
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
                        data: components["schemas"]["Credential"][];
                    };
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    submitCredential: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CredentialInput"];
            };
        };
        responses: {
            /** @description Created (status submitted) */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Credential"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    reviewCredential: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
                credential_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewDecision"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Credential"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    listProviderAffiliations: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
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
                        data: components["schemas"]["Affiliation"][];
                    };
                };
            };
        };
    };
    createServiceOffering: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServiceOfferingInput"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServiceOffering"];
                };
            };
            422: components["responses"]["Unprocessable"];
        };
    };
    listAvailabilityRules: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
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
                        data: components["schemas"]["AvailabilityRule"][];
                    };
                };
            };
        };
    };
    createAvailabilityRule: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AvailabilityRuleInput"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityRule"];
                };
            };
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    listAvailabilityExceptions: {
        parameters: {
            query?: {
                from?: string;
                to?: string;
            };
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
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
                        data: components["schemas"]["AvailabilityException"][];
                    };
                };
            };
        };
    };
    createAvailabilityException: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: components["parameters"]["ProviderId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AvailabilityExceptionInput"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AvailabilityException"];
                };
            };
            422: components["responses"]["Unprocessable"];
        };
    };
    deleteAvailabilityRule: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: components["schemas"]["Id"];
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
    listServices: {
        parameters: {
            query?: {
                category?: string;
                provider_id?: components["schemas"]["Id"];
                facility_id?: components["schemas"]["Id"];
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
                        data: components["schemas"]["ServiceOffering"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    getServiceOffering: {
        parameters: {
            query?: never;
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
                    "application/json": components["schemas"]["ServiceOffering"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    updateServiceOffering: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                service_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServiceOfferingPatch"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServiceOffering"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    searchFacilities: {
        parameters: {
            query?: {
                type?: components["schemas"]["FacilityType"];
                city?: string;
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
                        data: components["schemas"]["Facility"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
        };
    };
    createFacility: {
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
                "application/json": components["schemas"]["FacilityInput"];
            };
        };
        responses: {
            /** @description Created (status pending, verification unverified) */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Facility"];
                };
            };
        };
    };
    listMyFacilities: {
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
                        data: components["schemas"]["Facility"][];
                    };
                };
            };
        };
    };
    getFacility: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
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
                    "application/json": components["schemas"]["Facility"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    updateFacility: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FacilityPatch"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Facility"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    reviewFacility: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewDecision"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Facility"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
        };
    };
    listBranches: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
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
                        data: components["schemas"]["Branch"][];
                    };
                };
            };
        };
    };
    createBranch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BranchInput"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Branch"];
                };
            };
        };
    };
    getOperatingHours: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                branch_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["OperatingHours"];
                };
            };
            404: components["responses"]["NotFound"];
        };
    };
    replaceOperatingHours: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                branch_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OperatingHours"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperatingHours"];
                };
            };
            422: components["responses"]["Unprocessable"];
        };
    };
    listFacilityStaff: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
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
                        data: components["schemas"]["StaffMember"][];
                    };
                };
            };
        };
    };
    addFacilityStaff: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StaffMemberInput"];
            };
        };
        responses: {
            /** @description Created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StaffMember"];
                };
            };
            409: components["responses"]["Conflict"];
        };
    };
    removeFacilityStaff: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
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
            409: components["responses"]["Conflict"];
        };
    };
    listFacilityAffiliations: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                facility_id: components["parameters"]["FacilityId"];
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
                        data: components["schemas"]["Affiliation"][];
                    };
                };
            };
        };
    };
    requestAffiliation: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AffiliationInput"];
            };
        };
        responses: {
            /** @description Created (status pending) */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Affiliation"];
                };
            };
            409: components["responses"]["Conflict"];
        };
    };
    decideAffiliation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                affiliation_id: components["schemas"]["Id"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AffiliationDecision"];
            };
        };
        responses: {
            /** @description OK */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Affiliation"];
                };
            };
            404: components["responses"]["NotFound"];
            409: components["responses"]["Conflict"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getSchedulingContext: {
        parameters: {
            query: {
                tenant_id: string;
                from: components["schemas"]["Timestamp"];
                /** @description At most 62 days after from. */
                to: components["schemas"]["Timestamp"];
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
                    "application/json": components["schemas"]["SchedulingContext"];
                };
            };
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            422: components["responses"]["Unprocessable"];
        };
    };
    getSchedulingActor: {
        parameters: {
            query: {
                tenant_id: string;
            };
            header?: never;
            path: {
                user_id: components["schemas"]["Id"];
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
                    "application/json": components["schemas"]["SchedulingActor"];
                };
            };
            403: components["responses"]["Forbidden"];
        };
    };
    listAdminProviders: {
        parameters: {
            query?: {
                status?: components["schemas"]["ProviderStatus"];
                verification_status?: components["schemas"]["VerificationStatus"];
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
            /** @description OK (private provider view) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Provider"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
        };
    };
    listAdminCredentials: {
        parameters: {
            query?: {
                status?: "submitted" | "verified" | "rejected";
                provider_id?: components["schemas"]["Id"];
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
                        data: components["schemas"]["AdminCredential"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
        };
    };
    listAdminFacilities: {
        parameters: {
            query?: {
                status?: components["schemas"]["ProviderStatus"];
                verification_status?: components["schemas"]["VerificationStatus"];
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
            /** @description OK (private facility view, including license fields) */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        data: components["schemas"]["Facility"][];
                        page: components["schemas"]["PageMeta"];
                    };
                };
            };
            401: components["responses"]["Unauthorized"];
            403: components["responses"]["Forbidden"];
        };
    };
}
