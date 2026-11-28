import type { AssistantCard } from '../api/assistantTypes';

/** An in-app route for an assistant card; null when the card's id is not a valid identifier. */
export type CardRoute =
  | { pathname: '/book/[serviceId]'; params: { serviceId: string; milestoneId?: string } }
  | { pathname: '/providers/[id]' | '/facilities/[id]' | '/appointments/[id]' | '/concierge/[id]'; params: { id: string } }
  | { pathname: '/journey' | '/journey/intake' | '/concierge/new' }
  | { pathname: '/services'; params: { category: string; milestoneId?: string } };

const ID = /^[A-Za-z0-9-]{10,36}$/;

export function cardRoute(card: AssistantCard): CardRoute | null {
  switch (card.kind) {
    case 'service':
      if (!ID.test(card.id)) return null;
      return {
        pathname: '/book/[serviceId]',
        params: card.milestone_id && ID.test(card.milestone_id) ? { serviceId: card.id, milestoneId: card.milestone_id } : { serviceId: card.id },
      };
    case 'provider':
      return ID.test(card.id) ? { pathname: '/providers/[id]', params: { id: card.id } } : null;
    case 'facility':
      return ID.test(card.id) ? { pathname: '/facilities/[id]', params: { id: card.id } } : null;
    case 'appointment':
      return ID.test(card.id) ? { pathname: '/appointments/[id]', params: { id: card.id } } : null;
    case 'concierge_case':
      return ID.test(card.id) ? { pathname: '/concierge/[id]', params: { id: card.id } } : null;
    case 'handoff':
      return { pathname: '/concierge/new' };
    case 'journey_step':
      if (card.code === 'intake_assessment') return { pathname: '/journey/intake' };
      if (card.service_category && card.status !== 'completed' && ID.test(card.id)) {
        return { pathname: '/services', params: { category: card.service_category, milestoneId: card.id } };
      }
      return { pathname: '/journey' };
    default:
      return null;
  }
}
