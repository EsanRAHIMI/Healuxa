/**
 * Wire types for the authenticated care services (re-exported by ./types):
 *   appointment.openapi.yaml 3.4.0, concierge.openapi.yaml 1.0.0, notification.openapi.yaml.
 */
import type { Money } from './types';

// appointment ------------------------------------------------------------------
export type AppointmentStatus =
  | 'held'
  | 'requested'
  | 'confirmed'
  | 'checked_in'
  | 'completed'
  | 'cancelled'
  | 'declined'
  | 'no_show'
  | 'expired'
  | 'rescheduled';

export interface Slot {
  scheduled_at: string;
  ends_at: string;
  /** branch-local ISO 8601 with UTC offset, e.g. 2026-11-02T09:00:00+04:00 */
  local_start: string;
  local_end: string;
}

export interface SlotList {
  service_id: string;
  provider_id: string;
  branch_id: string;
  timezone: string;
  duration_minutes: number;
  buffer_minutes: number;
  from: string;
  to: string;
  slots: Slot[];
}

export interface Appointment {
  id: string;
  user_id: string;
  provider_id: string;
  facility_id: string;
  branch_id: string;
  service_id: string;
  status: AppointmentStatus;
  scheduled_at: string;
  ends_at: string;
  local_start?: string;
  timezone: string;
  duration_minutes: number;
  buffer_minutes: number;
  service_name?: string | null;
  price?: Money | null;
  payment_status: 'not_required' | 'pending' | 'authorized' | 'captured' | 'refunded';
  hold_expires_at?: string | null;
  cancelled_by?: string | null;
  decline_reason?: string | null;
  rescheduled_from_id?: string | null;
  rescheduled_to_id?: string | null;
  version: number;
  created_at: string;
}

/** The customer-side transitions (accept/decline/check_in/… belong to providers). */
export type CustomerTransition = 'submit' | 'cancel';

export interface StatusTransition {
  id: string;
  appointment_id: string;
  from_status?: AppointmentStatus | null;
  to_status: AppointmentStatus;
  actor_type: 'customer' | 'provider' | 'facility' | 'platform' | 'system';
  reason_code?: string | null;
  occurred_at: string;
}

// concierge --------------------------------------------------------------------
export type CaseStatus =
  | 'submitted'
  | 'triaged'
  | 'assigned'
  | 'in_progress'
  | 'awaiting_customer'
  | 'arranged'
  | 'completed'
  | 'cancelled'
  | 'escalated';

export type CaseCategory = 'medical_travel' | 'specialist_search' | 'second_opinion_coordination' | 'logistics' | 'other';

export interface CaseCreate {
  category: CaseCategory;
  preferred_start_date?: string | null;
  preferred_end_date?: string | null;
  languages?: string[];
  destination_city?: string | null;
  /** NON-CLINICAL logistics needs only (no symptoms, diagnoses or history). */
  needs_note?: string | null;
}

export interface ConciergeCase {
  id: string;
  customer_id: string;
  category: CaseCategory;
  status: CaseStatus;
  preferred_start_date?: string | null;
  preferred_end_date?: string | null;
  languages: string[];
  destination_city?: string | null;
  needs_note?: string | null;
  coordinator_id?: string | null;
  selected_option_id?: string | null;
  first_response_due_at: string;
  first_responded_at?: string | null;
  sla_breached: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderOption {
  id: string;
  case_id: string;
  provider_id: string;
  facility_id?: string | null;
  service_id?: string | null;
  label?: string | null;
  status: 'proposed' | 'selected' | 'not_selected';
  created_at: string;
}

export interface CaseMessage {
  id: string;
  case_id: string;
  sender_id: string;
  sender_role: 'customer' | 'coordinator';
  body: string;
  read_at?: string | null;
  created_at: string;
}

// notification -----------------------------------------------------------------
export type NotificationCategory = 'concierge' | 'appointments' | 'provider_account' | 'account' | 'marketing';
export type Channel = 'in_app' | 'email' | 'sms' | 'whatsapp' | 'push';

export interface InboxNotification {
  id: string;
  category: NotificationCategory;
  template: string;
  locale: 'en' | 'ar' | 'fa';
  title: string;
  body: string;
  entity_type?: string | null;
  entity_id?: string | null;
  read_at?: string | null;
  created_at: string;
}

export type ChannelSwitches = Partial<Record<Channel, boolean>>;

export interface NotificationPreferences {
  user_id: string;
  locale: 'en' | 'ar' | 'fa';
  timezone: string;
  quiet_hours?: { start: string; end: string } | null;
  marketing_opt_in: boolean;
  /** effective switches per category (server merges defaults) */
  channels: Record<string, ChannelSwitches>;
  updated_at?: string | null;
}

export type NotificationPreferencesUpdate = Partial<Omit<NotificationPreferences, 'user_id' | 'updated_at'>>;

export interface DeviceToken {
  id: string;
  platform: 'ios' | 'android' | 'web';
  token_suffix: string;
  created_at: string;
}
