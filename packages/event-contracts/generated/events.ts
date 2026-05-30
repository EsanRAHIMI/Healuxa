/* Curated, import-stable type surface for @healuxa/event-contracts.
 * Payload interfaces below are kept in sync with schemas/*.json; run `npm run generate:ts`
 * to (re)produce payloads.generated.ts and diff against this file for drift.
 */

// ── shared ───────────────────────────────────────────────────────────────────
export type Ulid = string;
export type TenantId = string;
export type Timestamp = string; // ISO 8601 UTC
export type CurrencyCode = string; // ISO 4217
export interface Money { amount_minor: number; currency: CurrencyCode }
export type Channel = "app" | "web" | "whatsapp" | "email" | "sms" | "push" | "in_app" | "system";
export type Score01 = number;

// ── envelope ─────────────────────────────────────────────────────────────────
export interface EventEnvelope<T = unknown> {
  event_id: Ulid;
  type: string;
  version: number;
  schema_ref: string;
  occurred_at: Timestamp;
  tenant_id: TenantId;
  producer: string;
  trace_id?: string;
  correlation_id?: string;
  causation_id?: Ulid;
  actor?: { type: "user" | "provider" | "service" | "system"; id?: string };
  payload: T;
}

// ── journey (transformation-engine) ───────────────────────────────────────────
export interface JourneyCreated { journey_id: Ulid; user_id: Ulid; primary_goals: string[]; status: "draft" | "onboarding" | "active"; started_at: Timestamp; target_completion?: Timestamp; ltv_projection?: Money }
export interface JourneyRoadmapUpdated { journey_id: Ulid; user_id: Ulid; milestone_count: number; reason: "assessment" | "reassessment" | "outcome" | "manual" | "ai_recommendation" }
export interface JourneyMilestoneCompleted { journey_id: Ulid; user_id: Ulid; milestone_id: Ulid; phase_id?: Ulid; provider_id?: Ulid; appointment_id?: Ulid; outcome_delta?: Score01; completed_at: Timestamp }
export interface JourneyPhaseCompleted { journey_id: Ulid; user_id: Ulid; phase_id: Ulid; completed_at: Timestamp }
export interface JourneyNextAction { journey_id: Ulid; user_id: Ulid; action_type: "book" | "assess" | "renew" | "upsell" | "adherence" | "follow_up" | "contact"; priority?: "low" | "medium" | "high" | "urgent"; due_at?: Timestamp }
export interface JourneyAtRisk { journey_id: Ulid; user_id: Ulid; risk_reason: "payment_failed" | "low_adherence" | "no_show" | "negative_review" | "inactivity" | "churn_model"; churn_risk: Score01 }
export interface JourneyReassessmentDue { journey_id: Ulid; user_id: Ulid; due_at: Timestamp }
export interface JourneyCompleted { journey_id: Ulid; user_id: Ulid; completed_at: Timestamp; outcome_score: Score01; realized_ltv?: Money }

// ── appointment (appointment-service) ─────────────────────────────────────────
export interface AppointmentRequested { appointment_id: Ulid; user_id: Ulid; provider_id: Ulid; service_id: Ulid; milestone_id?: Ulid; scheduled_at: Timestamp; requested_at: Timestamp }
export interface AppointmentCreated { appointment_id: Ulid; user_id: Ulid; provider_id: Ulid; service_id: Ulid; milestone_id?: Ulid; scheduled_at: Timestamp; channel?: Channel }
export interface AppointmentAccepted { appointment_id: Ulid; user_id: Ulid; provider_id: Ulid; service_id: Ulid; milestone_id?: Ulid; scheduled_at: Timestamp; response_seconds?: number }
export interface AppointmentDeclined { appointment_id: Ulid; user_id: Ulid; provider_id: Ulid; service_id: Ulid; milestone_id?: Ulid; scheduled_at: Timestamp; reason: "no_capacity" | "out_of_scope" | "schedule_conflict" | "other"; response_seconds?: number }
export interface AppointmentCompleted { appointment_id: Ulid; user_id: Ulid; provider_id: Ulid; service_id: Ulid; milestone_id?: Ulid; scheduled_at: Timestamp; completed_at: Timestamp; duration_minutes?: number; amount?: Money }
export interface AppointmentNoShow { appointment_id: Ulid; user_id: Ulid; provider_id: Ulid; service_id: Ulid; milestone_id?: Ulid; scheduled_at: Timestamp; party: "customer" | "provider" }

// ── payment (payment-service) ─────────────────────────────────────────────────
export interface PaymentSucceeded { payment_id: Ulid; user_id: Ulid; subscription_id?: Ulid; invoice_id?: Ulid; amount: Money; gateway: "tap_payments" | "stripe"; purpose?: "subscription" | "marketplace_order" | "add_on" | "top_up"; captured_at: Timestamp }
export interface PaymentFailed { payment_id: Ulid; user_id: Ulid; subscription_id?: Ulid; amount: Money; gateway: "tap_payments" | "stripe"; failure_code: string; dunning_attempt?: number; failed_at: Timestamp }
export interface CommissionComputed { commission_id: Ulid; provider_id: Ulid; payment_id?: Ulid; appointment_id?: Ulid; gross?: Money; amount: Money; rate?: Score01; computed_at: Timestamp }

// ── subscription (subscription-service) ───────────────────────────────────────
export interface SubscriptionCreated { subscription_id: Ulid; user_id: Ulid; plan_id: string; price: Money; billing_cycle: "monthly" | "quarterly" | "annual"; started_at: Timestamp }
export interface SubscriptionRenewed { subscription_id: Ulid; user_id: Ulid; plan_id: string; price: Money; renewed_at: Timestamp; period_end: Timestamp }
export interface SubscriptionUpgraded { subscription_id: Ulid; user_id: Ulid; from_plan_id: string; to_plan_id: string; mrr_delta?: Money; triggered_by_offer_id?: Ulid; changed_at: Timestamp }
export interface SubscriptionDowngraded { subscription_id: Ulid; user_id: Ulid; from_plan_id: string; to_plan_id: string; mrr_delta?: Money; changed_at: Timestamp }
export interface SubscriptionChurned { subscription_id: Ulid; user_id: Ulid; plan_id: string; reason: "voluntary" | "payment_failure" | "downgrade_to_none" | "expired"; lost_mrr?: Money; churned_at: Timestamp }

// ── provider (provider-success-engine) ────────────────────────────────────────
export type ProviderStage = "onboarding" | "ramping" | "active" | "top_performer" | "underperforming" | "probation" | "offboarded";
export interface ProviderScoreUpdated { provider_id: Ulid; success_score: Score01; quality_score?: Score01; tier: "bronze" | "silver" | "gold" | "platinum"; computed_at: Timestamp }
export interface ProviderCapacityUpdated { provider_id: Ulid; utilization: Score01; available: boolean; open_slots_next_7d?: number; updated_at: Timestamp }
export interface ProviderAtRisk { provider_id: Ulid; risk_reason: "low_acceptance" | "slow_response" | "low_satisfaction" | "sla_breach" | "complaints" | "inactivity"; success_score?: Score01; detected_at: Timestamp }
export interface ProviderLifecycleChanged { provider_id: Ulid; from_stage: ProviderStage; to_stage: ProviderStage; changed_at: Timestamp }
export interface ProviderIncentiveAwarded { provider_id: Ulid; program_id: Ulid; award: Money; reason?: string; awarded_at: Timestamp }

// ── commercial (commercial-intelligence-engine) ───────────────────────────────
export interface CommercialOfferRecommended { offer_id: Ulid; user_id: Ulid; offer_type: "upgrade" | "add_on" | "bundle" | "renewal" | "win_back" | "cross_sell"; segment_id?: Ulid; expected_uplift?: Money; price?: Money; channel?: Channel; valid_to: Timestamp }
export interface CommercialUpsellOpportunity { user_id: Ulid; recommendation: string; target_plan_id?: string; uplift_score: Score01; best_moment?: "onboarding" | "milestone" | "renewal" | "post_outcome" | "reactivation" }
export interface CommercialSegmentUpdated { segment_id: Ulid; name?: string; type: "rfm" | "behavioral" | "value" | "lifecycle" | "luxury_spend"; size: number; updated_at: Timestamp }
export interface CommercialPriceSuggestion { scope: "plan" | "add_on" | "bundle" | "segment"; scope_ref?: string; suggested_price: Money; elasticity?: number; confidence?: Score01; experiment_id?: Ulid; generated_at: Timestamp }
export interface CommercialForecastUpdated { metric: "mrr" | "arr" | "churn_revenue" | "expansion" | "nrr"; horizon_days: number; point_estimate?: Money; ci_low?: Money; ci_high?: Money; model_version?: string; generated_at: Timestamp }
export interface CommercialKpiAlert { kpi: string; severity: "info" | "warning" | "critical"; value: number; target?: number; delta_pct?: number; triggered_at: Timestamp }

// ── review (review-service) ───────────────────────────────────────────────────
export interface ReviewCreated { review_id: Ulid; provider_id: Ulid; user_id: Ulid; appointment_id?: Ulid; rating: number; dimensions?: Record<string, number>; verified?: boolean; created_at: Timestamp }
export interface ReviewModerated { review_id: Ulid; decision: "approved" | "rejected" | "flagged"; moderated_at: Timestamp }

// ── assessment / profile / identity / medication / marketing / ml ─────────────
export interface AssessmentCompleted { assessment_id: Ulid; user_id: Ulid; kind: "beauty" | "body" | "wellness" | "longevity" | "intake" | "reassessment"; recommended_goals?: string[]; scores?: Record<string, Score01>; completed_at: Timestamp }
export interface ProfileUpdated { user_id: Ulid; updated_fields: string[]; lifecycle_stage?: "lead" | "onboarding" | "active" | "at_risk" | "churned" | "reactivated"; vip_tier?: "none" | "silver" | "gold" | "black"; updated_at: Timestamp }
export interface AuthUserRegistered { user_id: Ulid; channel?: Channel; registered_at: Timestamp }
export interface AuthSessionRevoked { user_id: Ulid; session_id?: Ulid; scope: "single" | "all"; reason?: "logout" | "logout_all" | "token_reuse" | "admin" | "security"; revoked_at: Timestamp }
export interface AuthSecurityEvent { user_id?: Ulid; kind: "brute_force" | "impossible_travel" | "new_device" | "token_reuse" | "mfa_failure" | "lockout"; severity: "info" | "warning" | "critical"; ip?: string; detected_at: Timestamp }
export interface MedicationIntakeMissed { prescription_id: Ulid; user_id: Ulid; schedule_entry_id?: Ulid; scheduled_for: Timestamp; missed_at: Timestamp }
export interface MedicationRefillDue { prescription_id: Ulid; user_id: Ulid; due_at: Timestamp }
export interface MarketingCampaignSent { campaign_id: Ulid; channel: Channel; offer_id?: Ulid; segment_id?: Ulid; audience_size: number; sent_at: Timestamp }
export interface MarketingEngagement { campaign_id: Ulid; user_id: Ulid; action: "delivered" | "opened" | "clicked" | "converted" | "unsubscribed"; occurred_at: Timestamp }
export interface MlModelPromoted { model: string; version: string; metric?: string; metric_value?: number; promoted_at: Timestamp }
export interface MlPredictionReady { model: string; batch_id: Ulid; count: number; ready_at: Timestamp }

// ── type → payload map (compile-time safety for publishers/consumers) ──────────
export interface EventPayloadMap {
  "journey.created": JourneyCreated;
  "journey.roadmap_updated": JourneyRoadmapUpdated;
  "journey.milestone_completed": JourneyMilestoneCompleted;
  "journey.phase_completed": JourneyPhaseCompleted;
  "journey.next_action": JourneyNextAction;
  "journey.at_risk": JourneyAtRisk;
  "journey.reassessment_due": JourneyReassessmentDue;
  "journey.completed": JourneyCompleted;
  "appointment.requested": AppointmentRequested;
  "appointment.created": AppointmentCreated;
  "appointment.accepted": AppointmentAccepted;
  "appointment.declined": AppointmentDeclined;
  "appointment.completed": AppointmentCompleted;
  "appointment.no_show": AppointmentNoShow;
  "payment.succeeded": PaymentSucceeded;
  "payment.failed": PaymentFailed;
  "commission.computed": CommissionComputed;
  "subscription.created": SubscriptionCreated;
  "subscription.renewed": SubscriptionRenewed;
  "subscription.upgraded": SubscriptionUpgraded;
  "subscription.downgraded": SubscriptionDowngraded;
  "subscription.churned": SubscriptionChurned;
  "provider.score_updated": ProviderScoreUpdated;
  "provider.capacity_updated": ProviderCapacityUpdated;
  "provider.at_risk": ProviderAtRisk;
  "provider.lifecycle_changed": ProviderLifecycleChanged;
  "provider.incentive_awarded": ProviderIncentiveAwarded;
  "commercial.offer_recommended": CommercialOfferRecommended;
  "commercial.upsell_opportunity": CommercialUpsellOpportunity;
  "commercial.segment_updated": CommercialSegmentUpdated;
  "commercial.price_suggestion": CommercialPriceSuggestion;
  "commercial.forecast_updated": CommercialForecastUpdated;
  "commercial.kpi_alert": CommercialKpiAlert;
  "review.created": ReviewCreated;
  "review.moderated": ReviewModerated;
  "assessment.completed": AssessmentCompleted;
  "profile.updated": ProfileUpdated;
  "auth.user_registered": AuthUserRegistered;
  "auth.session_revoked": AuthSessionRevoked;
  "auth.security_event": AuthSecurityEvent;
  "medication.intake_missed": MedicationIntakeMissed;
  "medication.refill_due": MedicationRefillDue;
  "marketing.campaign_sent": MarketingCampaignSent;
  "marketing.engagement": MarketingEngagement;
  "ml.model_promoted": MlModelPromoted;
  "ml.prediction_ready": MlPredictionReady;
}

export type AnyEventType = keyof EventPayloadMap;
export type TypedEnvelope<K extends AnyEventType> = EventEnvelope<EventPayloadMap[K]> & { type: K };
