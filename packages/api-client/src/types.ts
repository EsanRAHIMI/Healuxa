/** Convenience aliases for the generated contract schemas. */
import type { components as AppointmentComponents } from "./generated/appointment";
import type { components as AssessmentComponents } from "./generated/assessment";
import type { components as ConciergeComponents } from "./generated/concierge";
import type { components as IdentityComponents } from "./generated/identity";
import type { components as NotificationComponents } from "./generated/notification";
import type { components as PaymentComponents } from "./generated/payment";
import type { components as ProfileComponents } from "./generated/profile";
import type { components as ProviderComponents } from "./generated/provider";

type P = ProviderComponents["schemas"];
type I = IdentityComponents["schemas"];

export type Money = P["Money"];
export type PageMeta = P["PageMeta"];
export type LocalizedText = P["LocalizedText"];

export type Provider = P["Provider"];
export type ProviderInput = P["ProviderInput"];
export type ProviderPatch = P["ProviderPatch"];
export type ProviderType = P["ProviderType"];
export type ProviderStatus = P["ProviderStatus"];
export type VerificationStatus = P["VerificationStatus"];
export type StatusChange = P["StatusChange"];
export type Credential = P["Credential"];
export type AdminCredential = P["AdminCredential"];
export type CredentialInput = P["CredentialInput"];
export type CredentialKind = P["CredentialKind"];
export type ReviewDecision = P["ReviewDecision"];
export type Facility = P["Facility"];
export type FacilityInput = P["FacilityInput"];
export type FacilityPatch = P["FacilityPatch"];
export type FacilityType = P["FacilityType"];
export type Branch = P["Branch"];
export type BranchInput = P["BranchInput"];
export type TimeWindow = P["TimeWindow"];
export type OperatingHours = P["OperatingHours"];
export type StaffRole = P["StaffRole"];
export type StaffMember = P["StaffMember"];
export type Affiliation = P["Affiliation"];
export type AffiliationDecision = P["AffiliationDecision"];
export type ServiceOffering = P["ServiceOffering"];
export type ServiceOfferingInput = P["ServiceOfferingInput"];
export type ServiceOfferingPatch = P["ServiceOfferingPatch"];
export type AvailabilityRule = P["AvailabilityRule"];
export type AvailabilityRuleInput = P["AvailabilityRuleInput"];
export type AvailabilityException = P["AvailabilityException"];
export type AvailabilityExceptionInput = P["AvailabilityExceptionInput"];

export type TokenResponse = I["TokenResponse"];
export type RegisterRequest = I["RegisterRequest"];
export type LoginRequest = I["LoginRequest"];
export type Introspection = I["Introspection"];
export type Session = I["Session"];

export type Profile = ProfileComponents["schemas"]["Profile"];
export type Assessment = AssessmentComponents["schemas"]["Assessment"];

type A = AppointmentComponents["schemas"];
export type Appointment = A["Appointment"];
export type AppointmentStatus = A["AppointmentStatus"];
export type Slot = A["Slot"];
export type SlotList = A["SlotList"];
export type AppointmentTransition = A["StatusTransition"];
export type AppointmentTransitionRequest = A["TransitionRequest"];

type C = ConciergeComponents["schemas"];
export type ConciergeCase = C["Case"];
export type ConciergeCaseStatus = C["CaseStatus"];
export type ConciergeCaseCategory = C["CaseCategory"];
export type ConciergeCaseCreate = C["CaseCreate"];
export type ConciergeNote = C["Note"];
export type ConciergeOption = C["ProviderOption"];
export type ConciergeMessage = C["Message"];
export type ConciergeAuditEntry = C["AuditEntry"];

type N = NotificationComponents["schemas"];
export type Notification = N["Notification"];
export type NotificationPreferences = N["Preferences"];
export type NotificationPreferencesUpdate = N["PreferencesUpdate"];
export type NotificationCategory = N["Category"];
export type NotificationChannel = N["Channel"];

type Pay = PaymentComponents["schemas"];
export type PaymentConfig = Pay["PaymentConfig"];
export type PaymentQuote = Pay["Quote"];
export type Payment = Pay["Payment"];
export type PaymentStatus = Pay["PaymentStatus"];
export type Refund = Pay["Refund"];
export type RefundPolicyDecision = Pay["RefundPolicyDecision"];
export type Invoice = Pay["Invoice"];
export type Dispute = Pay["Dispute"];
export type ReconciliationReport = Pay["ReconciliationReport"];
export type SettlementReport = Pay["SettlementReport"];
