/** Convenience aliases for the generated contract schemas. */
import type { components as AssessmentComponents } from "./generated/assessment";
import type { components as IdentityComponents } from "./generated/identity";
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
