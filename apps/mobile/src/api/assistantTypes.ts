/**
 * Wire types of ai.openapi.yaml (AiSession / AiTurn / AiCard). Cards are built server-side from
 * verified platform data of the same turn; the app renders them and never edits their values.
 */
import type { Money } from './types';

export type AssistantMoney = Money & { amount: string };

export type AssistantCard =
  | {
      kind: 'service';
      id: string;
      title: string;
      category: string;
      duration_minutes?: number | null;
      price_type: 'fixed' | 'from' | 'on_request';
      price: AssistantMoney | null;
      provider_id?: string | null;
      provider_name?: string | null;
      milestone_id?: string | null;
      next_slots: string[];
      timezone?: string | null;
      href: string;
    }
  | { kind: 'provider'; id: string; title: string | null; subtitle?: string | null; specialties?: string[]; href: string }
  | { kind: 'facility'; id: string; title: string | null; facility_type?: string | null; href: string }
  | { kind: 'journey_step'; id: string; code?: string | null; goal?: string | null; status?: string | null; service_category?: string | null; href: string }
  | { kind: 'appointment'; id: string; title?: string | null; status?: string | null; scheduled_at?: string | null; timezone?: string | null; href: string }
  | { kind: 'concierge_case'; id: string; status?: string | null; first_response_due_at?: string | null; href: string }
  | { kind: 'handoff'; href: string };

export interface AssistantTurn {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  cards: AssistantCard[];
  guardrail?: 'emergency' | 'clinical_redirect' | 'ungrounded' | 'refusal' | 'limit' | null;
  created_at: string;
}

export interface AssistantSession {
  id: string;
  locale: 'en' | 'ar' | 'fa';
  turn_count: number;
  handoff_case_id?: string | null;
  assistant_available: boolean;
  max_message_chars: number;
  created_at: string;
  updated_at: string;
  turns: AssistantTurn[];
}
