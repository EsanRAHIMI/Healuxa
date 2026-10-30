/**
 * Wire types used by the mobile app. They mirror packages/api-contracts/openapi:
 *   identity.openapi.yaml 3.3.0, provider.openapi.yaml 3.4.0, _shared/components.yaml.
 *
 * These live behind the adapter in ./client.ts so they can be swapped for the shared
 * `@healuxa/api-client` package once it lands on main (see apps/mobile/README.md#api-client).
 */

export interface PageMeta {
  next_cursor?: string | null;
  limit: number;
  has_more: boolean;
}

export interface Page<T> {
  data: T[];
  page: PageMeta;
}

export interface Money {
  amount_minor: number;
  currency: string;
}

export type LocalizedText = Record<string, string>;

// identity -------------------------------------------------------------------
export type Locale = 'en' | 'ar' | 'fa' | 'ru';

export interface RegisterRequest {
  identifier: string;
  password: string;
  locale?: Locale;
}

export interface LoginRequest {
  identifier: string;
  password: string;
  mfa_code?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: 'Bearer';
  expires_in: number;
}

export interface Session {
  id: string;
  device?: string | null;
  ip?: string | null;
  created_at: string;
  last_seen_at: string;
}

// provider -------------------------------------------------------------------
export type ProviderType =
  | 'doctor'
  | 'clinic'
  | 'therapist'
  | 'trainer'
  | 'nutritionist'
  | 'pharmacy'
  | 'brand'
  | 'home_visit';

export type VerificationStatus = 'unverified' | 'under_review' | 'verified' | 'rejected';

export type CredentialKind =
  | 'professional_license'
  | 'board_certification'
  | 'malpractice_insurance'
  | 'other';

export interface VerifiedCredentialSummary {
  kind?: CredentialKind;
  issuing_authority?: string;
  valid_until?: string | null;
}

export interface Provider {
  id: string;
  type: ProviderType;
  display_name: string;
  title?: string;
  bio?: LocalizedText;
  specialties: string[];
  languages: string[];
  quality_score?: number | null;
  success_score?: number | null;
  status: 'pending' | 'active' | 'suspended' | 'offboarded';
  verification_status: VerificationStatus;
  verified_credentials?: VerifiedCredentialSummary[];
  created_at?: string;
  updated_at?: string;
}

export interface ProviderSearch {
  type?: ProviderType;
  specialty?: string;
  language?: string;
  city?: string;
  limit?: number;
  cursor?: string;
}

export type FacilityType =
  | 'clinic'
  | 'hospital'
  | 'medical_center'
  | 'day_surgery'
  | 'diagnostic_center'
  | 'pharmacy'
  | 'wellness_center';

export interface Facility {
  id: string;
  type: FacilityType;
  name: string;
  description?: LocalizedText;
  website?: string | null;
  phone?: string | null;
  status: 'pending' | 'active' | 'suspended' | 'offboarded';
  verification_status: VerificationStatus;
  created_at?: string;
}

export interface Branch {
  id: string;
  facility_id: string;
  name: string;
  address_line?: string;
  city: string;
  emirate?: string | null;
  country: string;
  timezone: string;
  latitude?: number | null;
  longitude?: number | null;
  phone?: string | null;
  status?: 'active' | 'closed';
}

export interface TimeWindow {
  weekday: number;
  start: string;
  end: string;
}

export interface OperatingHours {
  branch_id?: string;
  timezone?: string;
  windows: TimeWindow[];
}

export type PriceType = 'fixed' | 'from' | 'on_request';

export interface ServiceOffering {
  id: string;
  provider_id: string;
  facility_id?: string;
  branch_id: string;
  category: string;
  name: string;
  description?: LocalizedText;
  duration_minutes: number;
  buffer_minutes?: number;
  mode?: 'in_person' | 'home_visit';
  price_type: PriceType;
  price?: Money | null;
  professional_fee?: Money | null;
  facility_fee?: Money | null;
  status: 'draft' | 'active' | 'retired';
}

export * from './careTypes';

export interface ServiceSearch {
  category?: string;
  provider_id?: string;
  facility_id?: string;
  limit?: number;
  cursor?: string;
}
