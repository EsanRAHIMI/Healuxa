/**
 * Healuxa Event Registry — the machine-readable source of truth for event ownership.
 *
 * Enforces DDD boundaries: every event has exactly ONE producer (owner). A service that
 * is not the registered owner MUST NOT publish that event. Consumers conform to the
 * published schema. `scripts/validate.mjs` checks this registry against the JSON Schemas.
 *
 * Companion to Healuxa_DDD_Boundaries.md §6 and Healuxa_TechSpec.md §9.
 */

export type ServiceName =
  | "transformation-engine"
  | "identity-service"
  | "profile-service"
  | "assessment-service"
  | "treatment-service"
  | "provider-service"
  | "matching-service"
  | "appointment-service"
  | "review-service"
  | "subscription-service"
  | "payment-service"
  | "marketplace-service"
  | "medication-service"
  | "crm-service"
  | "marketing-service"
  | "notification-service"
  | "media-service"
  | "ai-orchestrator"
  | "ml-service"
  | "provider-success-engine"
  | "commercial-intelligence-engine"
  | "whatsapp-service"
  | "realtime-gateway"
  | "monitoring-service";

export interface EventDescriptor {
  /** Fully-qualified event type `<context>.<event>`. */
  readonly type: string;
  /** JetStream stream this subject belongs to. */
  readonly stream: string;
  /** The single owning service allowed to publish this event. */
  readonly owner: ServiceName;
  /** Services that subscribe to this event. `"*"` means "all services / fan-out". */
  readonly consumers: readonly (ServiceName | "*")[];
  /** Current major version. */
  readonly version: number;
  /** Path (relative to package root) of the payload schema $def. */
  readonly schema: string;
}

const ALL = "*" as const;

export const EVENTS = {
  // ── Transformation (Customer Success) ──────────────────────────────────────
  "journey.created": { type: "journey.created", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyCreated", consumers: ["commercial-intelligence-engine", "ml-service", "monitoring-service", "notification-service"] },
  "journey.roadmap_updated": { type: "journey.roadmap_updated", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyRoadmapUpdated", consumers: ["ml-service", "monitoring-service"] },
  "journey.milestone_completed": { type: "journey.milestone_completed", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyMilestoneCompleted", consumers: ["provider-success-engine", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "journey.phase_completed": { type: "journey.phase_completed", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyPhaseCompleted", consumers: ["commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "journey.next_action": { type: "journey.next_action", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyNextAction", consumers: ["notification-service", "whatsapp-service", "monitoring-service"] },
  "journey.at_risk": { type: "journey.at_risk", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyAtRisk", consumers: ["crm-service", "marketing-service", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "journey.reassessment_due": { type: "journey.reassessment_due", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyReassessmentDue", consumers: ["assessment-service", "notification-service", "monitoring-service"] },
  "journey.completed": { type: "journey.completed", stream: "JOURNEY", owner: "transformation-engine", version: 1, schema: "schemas/journey.schema.json#/$defs/JourneyCompleted", consumers: ["commercial-intelligence-engine", "ml-service", "monitoring-service"] },

  // ── Appointment (Scheduling) ───────────────────────────────────────────────
  "appointment.requested": { type: "appointment.requested", stream: "APPOINTMENT", owner: "appointment-service", version: 1, schema: "schemas/appointment.schema.json#/$defs/AppointmentRequested", consumers: ["provider-success-engine", "monitoring-service"] },
  "appointment.created": { type: "appointment.created", stream: "APPOINTMENT", owner: "appointment-service", version: 1, schema: "schemas/appointment.schema.json#/$defs/AppointmentCreated", consumers: ["transformation-engine", "notification-service", "monitoring-service"] },
  "appointment.accepted": { type: "appointment.accepted", stream: "APPOINTMENT", owner: "appointment-service", version: 1, schema: "schemas/appointment.schema.json#/$defs/AppointmentAccepted", consumers: ["provider-success-engine", "monitoring-service"] },
  "appointment.declined": { type: "appointment.declined", stream: "APPOINTMENT", owner: "appointment-service", version: 1, schema: "schemas/appointment.schema.json#/$defs/AppointmentDeclined", consumers: ["provider-success-engine", "matching-service", "monitoring-service"] },
  "appointment.completed": { type: "appointment.completed", stream: "APPOINTMENT", owner: "appointment-service", version: 1, schema: "schemas/appointment.schema.json#/$defs/AppointmentCompleted", consumers: ["transformation-engine", "provider-success-engine", "commercial-intelligence-engine", "review-service", "ml-service", "monitoring-service"] },
  "appointment.no_show": { type: "appointment.no_show", stream: "APPOINTMENT", owner: "appointment-service", version: 1, schema: "schemas/appointment.schema.json#/$defs/AppointmentNoShow", consumers: ["transformation-engine", "provider-success-engine", "monitoring-service"] },

  // ── Payment (money ledger) ─────────────────────────────────────────────────
  "payment.succeeded": { type: "payment.succeeded", stream: "BILLING", owner: "payment-service", version: 1, schema: "schemas/payment.schema.json#/$defs/PaymentSucceeded", consumers: ["transformation-engine", "subscription-service", "provider-success-engine", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "payment.failed": { type: "payment.failed", stream: "BILLING", owner: "payment-service", version: 1, schema: "schemas/payment.schema.json#/$defs/PaymentFailed", consumers: ["transformation-engine", "subscription-service", "crm-service", "commercial-intelligence-engine", "notification-service", "monitoring-service"] },
  "commission.computed": { type: "commission.computed", stream: "BILLING", owner: "payment-service", version: 1, schema: "schemas/payment.schema.json#/$defs/CommissionComputed", consumers: ["provider-success-engine", "commercial-intelligence-engine", "monitoring-service"] },

  // ── Subscription ───────────────────────────────────────────────────────────
  "subscription.created": { type: "subscription.created", stream: "BILLING", owner: "subscription-service", version: 1, schema: "schemas/subscription.schema.json#/$defs/SubscriptionCreated", consumers: ["transformation-engine", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "subscription.renewed": { type: "subscription.renewed", stream: "BILLING", owner: "subscription-service", version: 1, schema: "schemas/subscription.schema.json#/$defs/SubscriptionRenewed", consumers: ["transformation-engine", "commercial-intelligence-engine", "monitoring-service"] },
  "subscription.upgraded": { type: "subscription.upgraded", stream: "BILLING", owner: "subscription-service", version: 1, schema: "schemas/subscription.schema.json#/$defs/SubscriptionUpgraded", consumers: ["commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "subscription.downgraded": { type: "subscription.downgraded", stream: "BILLING", owner: "subscription-service", version: 1, schema: "schemas/subscription.schema.json#/$defs/SubscriptionDowngraded", consumers: ["commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "subscription.churned": { type: "subscription.churned", stream: "BILLING", owner: "subscription-service", version: 1, schema: "schemas/subscription.schema.json#/$defs/SubscriptionChurned", consumers: ["transformation-engine", "crm-service", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },

  // ── Provider Success ───────────────────────────────────────────────────────
  "provider.score_updated": { type: "provider.score_updated", stream: "PROVIDER", owner: "provider-success-engine", version: 1, schema: "schemas/provider.schema.json#/$defs/ProviderScoreUpdated", consumers: ["matching-service", "provider-service", "monitoring-service"] },
  "provider.capacity_updated": { type: "provider.capacity_updated", stream: "PROVIDER", owner: "provider-success-engine", version: 1, schema: "schemas/provider.schema.json#/$defs/ProviderCapacityUpdated", consumers: ["matching-service", "monitoring-service"] },
  "provider.at_risk": { type: "provider.at_risk", stream: "PROVIDER", owner: "provider-success-engine", version: 1, schema: "schemas/provider.schema.json#/$defs/ProviderAtRisk", consumers: ["crm-service", "notification-service", "monitoring-service"] },
  "provider.lifecycle_changed": { type: "provider.lifecycle_changed", stream: "PROVIDER", owner: "provider-success-engine", version: 1, schema: "schemas/provider.schema.json#/$defs/ProviderLifecycleChanged", consumers: ["matching-service", "monitoring-service"] },
  "provider.incentive_awarded": { type: "provider.incentive_awarded", stream: "PROVIDER", owner: "provider-success-engine", version: 1, schema: "schemas/provider.schema.json#/$defs/ProviderIncentiveAwarded", consumers: ["notification-service", "payment-service", "monitoring-service"] },

  // ── Commercial Intelligence ────────────────────────────────────────────────
  "commercial.offer_recommended": { type: "commercial.offer_recommended", stream: "COMMERCIAL", owner: "commercial-intelligence-engine", version: 1, schema: "schemas/commercial.schema.json#/$defs/CommercialOfferRecommended", consumers: ["transformation-engine", "notification-service", "whatsapp-service", "monitoring-service"] },
  "commercial.upsell_opportunity": { type: "commercial.upsell_opportunity", stream: "COMMERCIAL", owner: "commercial-intelligence-engine", version: 1, schema: "schemas/commercial.schema.json#/$defs/CommercialUpsellOpportunity", consumers: ["transformation-engine", "crm-service", "monitoring-service"] },
  "commercial.segment_updated": { type: "commercial.segment_updated", stream: "COMMERCIAL", owner: "commercial-intelligence-engine", version: 1, schema: "schemas/commercial.schema.json#/$defs/CommercialSegmentUpdated", consumers: ["marketing-service", "ml-service", "monitoring-service"] },
  "commercial.price_suggestion": { type: "commercial.price_suggestion", stream: "COMMERCIAL", owner: "commercial-intelligence-engine", version: 1, schema: "schemas/commercial.schema.json#/$defs/CommercialPriceSuggestion", consumers: ["subscription-service", "marketing-service", "monitoring-service"] },
  "commercial.forecast_updated": { type: "commercial.forecast_updated", stream: "COMMERCIAL", owner: "commercial-intelligence-engine", version: 1, schema: "schemas/commercial.schema.json#/$defs/CommercialForecastUpdated", consumers: ["monitoring-service"] },
  "commercial.kpi_alert": { type: "commercial.kpi_alert", stream: "COMMERCIAL", owner: "commercial-intelligence-engine", version: 1, schema: "schemas/commercial.schema.json#/$defs/CommercialKpiAlert", consumers: ["monitoring-service", "notification-service"] },

  // ── Review & Quality ───────────────────────────────────────────────────────
  "review.created": { type: "review.created", stream: "QUALITY", owner: "review-service", version: 1, schema: "schemas/review.schema.json#/$defs/ReviewCreated", consumers: ["transformation-engine", "provider-success-engine", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },
  "review.moderated": { type: "review.moderated", stream: "QUALITY", owner: "review-service", version: 1, schema: "schemas/review.schema.json#/$defs/ReviewModerated", consumers: ["provider-success-engine", "monitoring-service"] },

  // ── Assessment ─────────────────────────────────────────────────────────────
  "assessment.completed": { type: "assessment.completed", stream: "CLINICAL", owner: "assessment-service", version: 1, schema: "schemas/assessment.schema.json#/$defs/AssessmentCompleted", consumers: ["transformation-engine", "ai-orchestrator", "ml-service", "monitoring-service"] },

  // ── Profile ────────────────────────────────────────────────────────────────
  "profile.updated": { type: "profile.updated", stream: "GROWTH", owner: "profile-service", version: 1, schema: "schemas/profile.schema.json#/$defs/ProfileUpdated", consumers: ["transformation-engine", "commercial-intelligence-engine", "ml-service", "monitoring-service"] },

  // ── Identity ───────────────────────────────────────────────────────────────
  "auth.user_registered": { type: "auth.user_registered", stream: "IDENTITY", owner: "identity-service", version: 1, schema: "schemas/identity.schema.json#/$defs/AuthUserRegistered", consumers: ["profile-service", "crm-service", "monitoring-service"] },
  "auth.session_revoked": { type: "auth.session_revoked", stream: "IDENTITY", owner: "identity-service", version: 1, schema: "schemas/identity.schema.json#/$defs/AuthSessionRevoked", consumers: ["realtime-gateway", "monitoring-service"] },
  "auth.security_event": { type: "auth.security_event", stream: "IDENTITY", owner: "identity-service", version: 1, schema: "schemas/identity.schema.json#/$defs/AuthSecurityEvent", consumers: ["monitoring-service"] },

  // ── Medication ─────────────────────────────────────────────────────────────
  "medication.intake_missed": { type: "medication.intake_missed", stream: "CLINICAL", owner: "medication-service", version: 1, schema: "schemas/medication.schema.json#/$defs/MedicationIntakeMissed", consumers: ["transformation-engine", "notification-service", "ml-service", "monitoring-service"] },
  "medication.refill_due": { type: "medication.refill_due", stream: "CLINICAL", owner: "medication-service", version: 1, schema: "schemas/medication.schema.json#/$defs/MedicationRefillDue", consumers: ["notification-service", "marketplace-service", "monitoring-service"] },

  // ── Marketing ──────────────────────────────────────────────────────────────
  "marketing.campaign_sent": { type: "marketing.campaign_sent", stream: "GROWTH", owner: "marketing-service", version: 1, schema: "schemas/marketing.schema.json#/$defs/MarketingCampaignSent", consumers: ["commercial-intelligence-engine", "monitoring-service"] },
  "marketing.engagement": { type: "marketing.engagement", stream: "GROWTH", owner: "marketing-service", version: 1, schema: "schemas/marketing.schema.json#/$defs/MarketingEngagement", consumers: ["commercial-intelligence-engine", "ml-service", "monitoring-service"] },

  // ── ML platform ────────────────────────────────────────────────────────────
  "ml.model_promoted": { type: "ml.model_promoted", stream: "PLATFORM", owner: "ml-service", version: 1, schema: "schemas/ml.schema.json#/$defs/MlModelPromoted", consumers: ["matching-service", "commercial-intelligence-engine", "provider-success-engine", "transformation-engine", "monitoring-service"] },
  "ml.prediction_ready": { type: "ml.prediction_ready", stream: "PLATFORM", owner: "ml-service", version: 1, schema: "schemas/ml.schema.json#/$defs/MlPredictionReady", consumers: ["commercial-intelligence-engine", "provider-success-engine", "monitoring-service"] },
} as const satisfies Record<string, EventDescriptor>;

export type EventType = keyof typeof EVENTS;

/** Returns the single owning service for an event type. */
export function ownerOf(type: EventType): ServiceName {
  return EVENTS[type].owner;
}

/** Guard used by the shared publisher (py-common / ts-common) to reject mismatched producers. */
export function assertCanPublish(type: EventType, service: ServiceName): void {
  const expected = EVENTS[type].owner;
  if (expected !== service) {
    throw new Error(
      `Boundary violation: '${service}' may not publish '${type}'. Owner is '${expected}'. See Healuxa_DDD_Boundaries.md §6.`,
    );
  }
}

/** All events a given service is allowed to consume (for subscription wiring). */
export function subscriptionsOf(service: ServiceName): EventType[] {
  return (Object.keys(EVENTS) as EventType[]).filter((t) => {
    const c = EVENTS[t].consumers as readonly string[];
    return c.includes(service) || c.includes(ALL);
  });
}
