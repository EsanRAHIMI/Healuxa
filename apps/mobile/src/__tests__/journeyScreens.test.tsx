import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { Alert } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import Book from '../../app/book/[serviceId]';
import JourneyScreen, { INTAKE_POLL_ATTEMPTS, INTAKE_POLL_INTERVAL_MS } from '../../app/journey/index';
import JourneyIntake from '../../app/journey/intake';
import Services from '../../app/services';
import type { ApiClient } from '../api/client';
import { ApiError } from '../api/errors';
import type { Journey, Roadmap } from '../api/types';
import { en } from '../i18n/en';
import { I18nProvider } from '../i18n';
import { GoalPicker } from '../journey/GoalPicker';
import { JourneyHomeCard } from '../journey/JourneyHomeCard';
import { type Services as AppServices, ServicesProvider } from '../services';

const mockRouter = { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), dismissTo: jest.fn(), back: jest.fn() };
let mockParams: Record<string, string | undefined> = {};
const mockAuth = {
  status: 'signedIn' as 'signedIn' | 'signedOut',
  userId: 'U1' as string | undefined,
  withAuth: <T,>(call: (token: string) => Promise<T>) => call('tok'),
};

jest.mock('expo-router', () => {
  const { useEffect } = jest.requireActual<typeof import('react')>('react');
  return {
    useRouter: () => mockRouter,
    useLocalSearchParams: () => mockParams,
    useFocusEffect: (effect: () => void) => useEffect(() => effect(), [effect]),
    Stack: { Screen: () => null },
  };
});
jest.mock('expo-crypto', () => {
  let n = 0;
  return { randomUUID: () => `uuid-${++n}` };
});
jest.mock('../auth/AuthProvider', () => ({ useAuth: () => mockAuth }));

const journey: Journey = { id: 'J1', user_id: 'U1', primary_goals: ['skin_health', 'longevity'], status: 'active' };

function roadmapWith(intake: 'pending' | 'completed'): Roadmap {
  const started = intake === 'completed';
  return {
    journey_id: 'J1',
    phases: [
      {
        id: 'P1',
        code: 'understand',
        name: 'Understand (server)',
        sequence: 1,
        status: started ? 'completed' : 'in_progress',
        milestones: [{ id: 'M1', title: 'Intake (server)', status: intake, code: 'intake_assessment', sequence: 1 }],
      },
      {
        id: 'P2',
        code: 'consult',
        name: 'Consult (server)',
        sequence: 2,
        status: started ? 'in_progress' : 'pending',
        milestones: [
          { id: 'M2', title: 'Consultation (server)', status: 'pending', code: 'consultation', goal: 'skin_health', service_category: 'dermatology', sequence: 1 },
          { id: 'M3', title: 'Consultation (server)', status: 'scheduled', code: 'consultation', goal: 'longevity', service_category: 'longevity', appointment_id: 'AP1', scheduled_at: '2026-12-01T05:00:00Z', sequence: 2 },
        ],
      },
      {
        id: 'P3',
        code: 'care',
        name: 'Care (server)',
        sequence: 3,
        status: 'pending',
        milestones: [{ id: 'M4', title: 'Care (server)', status: 'pending', code: 'care', goal: 'skin_health', service_category: 'dermatology', sequence: 1 }],
      },
      {
        id: 'P4',
        code: 'follow_up',
        name: 'Follow-up (server)',
        sequence: 4,
        status: 'pending',
        milestones: [{ id: 'M5', title: 'Review (server)', status: 'pending', code: 'progress_review', sequence: 1 }],
      },
    ],
  };
}

function fakeApi() {
  const api = {
    journeys: {
      create: jest.fn(async () => journey),
      getActive: jest.fn(async (): Promise<Journey | null> => journey),
      roadmap: jest.fn(async () => roadmapWith('completed')),
      nextActions: jest.fn(async () => []),
      completeMilestone: jest.fn(async () => ({ id: 'M2', title: '', status: 'completed' as const })),
      close: jest.fn(async () => ({ ...journey, status: 'churned' as const })),
    },
    assessments: {
      startIntake: jest.fn(async () => ({ id: 'A1', user_id: 'U1', kind: 'intake', status: 'in_progress' as const })),
      submit: jest.fn(async () => ({ id: 'A1', user_id: 'U1', kind: 'intake', status: 'completed' as const })),
    },
    appointments: {
      get: jest.fn(async () => ({ id: 'AP1', timezone: 'Asia/Dubai', scheduled_at: '2026-12-01T05:00:00Z' })),
      listSlots: jest.fn(async () => ({
        timezone: 'Asia/Dubai',
        slots: [{ scheduled_at: '2026-12-01T05:00:00Z', ends_at: '2026-12-01T05:30:00Z', local_start: '2026-12-01T09:00:00+04:00', local_end: '2026-12-01T09:30:00+04:00' }],
      })),
      hold: jest.fn(async () => ({ id: 'AP9', status: 'held', scheduled_at: '2026-12-01T05:00:00Z', timezone: 'Asia/Dubai' })),
      transition: jest.fn(async () => ({ id: 'AP9', status: 'cancelled' })),
    },
    directory: {
      getService: jest.fn(async () => ({ data: offering, fromCache: false })),
      listServices: jest.fn(async (q: { category?: string }) => ({
        data: { data: q.category === 'longevity' ? [] : [offering], page: { limit: 100, has_more: false } },
        fromCache: false,
      })),
    },
  };
  return api;
}

const offering = {
  id: 'S1',
  provider_id: 'PR1',
  branch_id: 'B1',
  category: 'dermatology',
  name: 'Skin consultation',
  duration_minutes: 30,
  price_type: 'on_request' as const,
  status: 'active' as const,
};

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
function wrap(ui: ReactNode, api: ReturnType<typeof fakeApi>) {
  return (
    <SafeAreaProvider initialMetrics={metrics}>
      <I18nProvider initialLanguage="en">
        <ServicesProvider services={{ api: api as unknown as ApiClient } as AppServices}>{ui}</ServicesProvider>
      </I18nProvider>
    </SafeAreaProvider>
  );
}

const checked = (testID: string) => screen.getByTestId(testID).props.accessibilityState?.checked;

beforeEach(() => {
  jest.clearAllMocks();
  mockParams = {};
  mockAuth.status = 'signedIn';
  mockAuth.userId = 'U1';
});

describe('goal picker', () => {
  it('allows at most three goals, shows what is selected and submits them in order', async () => {
    const onSubmit = jest.fn();
    await render(wrap(<GoalPicker onSubmit={onSubmit} />, fakeApi()));
    expect(screen.getByTestId('goal-submit').props.accessibilityState.disabled).toBe(true);

    for (const g of ['longevity', 'skin_health', 'dental_smile']) await fireEvent.press(screen.getByTestId(`goal-${g}`));
    expect(screen.getByText(en['journey.goals.limit'].replace('{max}', '3'))).toBeTruthy();
    expect(screen.getByTestId('goal-mental_wellbeing').props.accessibilityState).toMatchObject({ checked: false, disabled: true });

    // A fourth goal is ignored.
    await fireEvent.press(screen.getByTestId('goal-mental_wellbeing'));
    expect(checked('goal-mental_wellbeing')).toBe(false);
    expect(['longevity', 'skin_health', 'dental_smile'].map((g) => checked(`goal-${g}`))).toEqual([true, true, true]);
    expect(screen.getByTestId('goal-longevity').props.accessibilityRole).toBe('checkbox');

    // Removing one frees a place.
    await fireEvent.press(screen.getByTestId('goal-skin_health'));
    await fireEvent.press(screen.getByTestId('goal-mental_wellbeing'));
    await fireEvent.press(screen.getByTestId('goal-submit'));
    expect(onSubmit).toHaveBeenCalledWith(['longevity', 'dental_smile', 'mental_wellbeing']);
  });
});

describe('journey screen', () => {
  it('asks a signed-out visitor to sign in and makes no journey calls', async () => {
    mockAuth.status = 'signedOut';
    mockAuth.userId = undefined;
    const api = fakeApi();
    await render(wrap(<JourneyScreen />, api));
    expect(screen.getByText(en['common.signInRequired'])).toBeTruthy();
    expect(api.journeys.getActive).not.toHaveBeenCalled();
  });

  it('shows the goal picker when there is no journey (404), then creates one and opens the intake form', async () => {
    const api = fakeApi();
    api.journeys.getActive.mockResolvedValue(null);
    await render(wrap(<JourneyScreen />, api));
    expect(await screen.findByTestId('goal-picker')).toBeTruthy();
    expect(screen.queryByTestId('error-state')).toBeNull();
    expect(api.journeys.roadmap).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByTestId('goal-skin_health'));
    await fireEvent.press(screen.getByTestId('goal-longevity'));
    await fireEvent.press(screen.getByTestId('goal-submit'));
    await waitFor(() => expect(mockRouter.push).toHaveBeenCalledWith('/journey/intake'));
    expect(api.journeys.create).toHaveBeenCalledWith('tok', { user_id: 'U1', primary_goals: ['skin_health', 'longevity'] }, expect.stringMatching(/^uuid-/));
  });

  it('shows the existing journey when creating one answers 409', async () => {
    const api = fakeApi();
    api.journeys.getActive.mockResolvedValue(null);
    api.journeys.create.mockImplementation(async () => {
      api.journeys.getActive.mockResolvedValue(journey);
      throw new ApiError({ status: 409, code: 'conflict' });
    });
    await render(wrap(<JourneyScreen />, api));
    await fireEvent.press(await screen.findByTestId('goal-longevity'));
    await fireEvent.press(screen.getByTestId('goal-submit'));
    expect(await screen.findByTestId('journey-timeline')).toBeTruthy();
    expect(screen.getByText(en['journey.alreadyActive'])).toBeTruthy();
    expect(mockRouter.push).not.toHaveBeenCalled();
  });

  it('shows an error with retry when the journey cannot be loaded', async () => {
    const api = fakeApi();
    api.journeys.getActive.mockRejectedValue(new ApiError({ status: 503, code: 'service_unavailable' }));
    await render(wrap(<JourneyScreen />, api));
    expect(await screen.findByText(en['error.server'])).toBeTruthy();
    expect(screen.queryByTestId('goal-picker')).toBeNull();
    api.journeys.getActive.mockResolvedValue(journey);
    await fireEvent.press(screen.getByTestId('error-state-retry'));
    expect(await screen.findByTestId('journey-timeline')).toBeTruthy();
  });

  it('renders the four phases with localised names, progress and status', async () => {
    const api = fakeApi();
    await render(wrap(<JourneyScreen />, api));
    expect(await screen.findByTestId('journey-timeline')).toBeTruthy();
    for (const code of ['understand', 'consult', 'care', 'follow_up']) expect(screen.getByTestId(`phase-${code}`)).toBeTruthy();
    expect(screen.getByTestId('journey-progress').props.children).toBe('1 of 5 steps completed');
    expect(screen.getAllByText('Consultation · Skin health').length).toBeGreaterThan(0);
    expect(screen.queryByText(/\(server\)/)).toBeNull();
    expect(screen.getByTestId('step-status-M1').props.children).toBe(en['journey.stepStatus.completed']);
    expect(screen.getByTestId('step-status-M2').props.children).toBe(en['journey.stepStatus.pending']);
    expect(screen.getByTestId('step-status-M4').props.children).toBe(en['journey.stepStatus.upcoming']);
  });

  it('opens the services list for the step category and carries the step id', async () => {
    const api = fakeApi();
    await render(wrap(<JourneyScreen />, api));
    await fireEvent.press(await screen.findByTestId('step-book-M2'));
    expect(mockRouter.push).toHaveBeenCalledWith({ pathname: '/services', params: { category: 'dermatology', milestoneId: 'M2' } });
    await fireEvent.press(screen.getByTestId('step-concierge-M2'));
    expect(mockRouter.push).toHaveBeenCalledWith('/concierge/new');
  });

  it('links a scheduled step to its booking and leaves later phases without actions', async () => {
    const api = fakeApi();
    await render(wrap(<JourneyScreen />, api));
    await fireEvent.press(await screen.findByTestId('step-appointment-M3'));
    expect(mockRouter.push).toHaveBeenCalledWith({ pathname: '/appointments/[id]', params: { id: 'AP1' } });
    expect(api.appointments.get).toHaveBeenCalledWith('tok', 'AP1');
    expect(screen.queryByTestId('step-book-M3')).toBeNull();
    expect(screen.queryByTestId('step-book-M4')).toBeNull();
    expect(screen.queryByTestId('step-done-M4')).toBeNull();
    expect(screen.queryByTestId('step-done-M5')).toBeNull();
  });

  it('marks a step as done only after confirmation', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const api = fakeApi();
    await render(wrap(<JourneyScreen />, api));
    await fireEvent.press(await screen.findByTestId('step-done-M2'));
    expect(api.journeys.completeMilestone).not.toHaveBeenCalled();
    const [title, message, buttons] = alert.mock.calls[0]!;
    expect(title).toBe(en['journey.action.markDone']);
    expect(message).toContain('Consultation · Skin health');
    const calls = api.journeys.getActive.mock.calls.length;
    await act(async () => {
      await buttons![1]!.onPress!();
    });
    expect(api.journeys.completeMilestone).toHaveBeenCalledWith('tok', 'J1', 'M2', expect.stringMatching(/^uuid-/));
    await waitFor(() => expect(api.journeys.getActive.mock.calls.length).toBeGreaterThan(calls));
    alert.mockRestore();
  });

  it('ends the journey after confirmation and returns to the goal picker', async () => {
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const api = fakeApi();
    api.journeys.close.mockImplementation(async () => {
      api.journeys.getActive.mockResolvedValue(null);
      return { ...journey, status: 'churned' as const };
    });
    await render(wrap(<JourneyScreen />, api));
    await fireEvent.press(await screen.findByTestId('journey-end'));
    expect(api.journeys.close).not.toHaveBeenCalled();
    const buttons = alert.mock.calls[0]![2]!;
    expect(buttons[1]!.style).toBe('destructive');
    await act(async () => {
      await buttons[1]!.onPress!();
    });
    expect(api.journeys.close).toHaveBeenCalledWith('tok', 'J1');
    expect(await screen.findByTestId('goal-picker')).toBeTruthy();
    alert.mockRestore();
  });
});

describe('after the intake form', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it('re-fetches until the intake step is completed', async () => {
    mockParams = { notice: 'intake_saved' };
    const api = fakeApi();
    api.journeys.roadmap.mockResolvedValue(roadmapWith('pending'));
    await render(wrap(<JourneyScreen />, api));
    expect(await screen.findByText(en['journey.intakeSaved'])).toBeTruthy();
    expect(screen.getByTestId('step-intake-M1')).toBeTruthy();

    api.journeys.roadmap.mockResolvedValue(roadmapWith('completed'));
    await act(async () => {
      await jest.advanceTimersByTimeAsync(INTAKE_POLL_INTERVAL_MS);
    });
    expect(await screen.findByText(en['journey.intakeUpdated'])).toBeTruthy();
    expect(screen.queryByTestId('step-intake-M1')).toBeNull();

    // No further polling once the plan has caught up.
    const calls = api.journeys.roadmap.mock.calls.length;
    await act(async () => {
      await jest.advanceTimersByTimeAsync(INTAKE_POLL_INTERVAL_MS * 3);
    });
    expect(api.journeys.roadmap.mock.calls.length).toBe(calls);
  });

  it('stops polling and stays usable when the plan does not update', async () => {
    mockParams = { notice: 'intake_saved' };
    const api = fakeApi();
    api.journeys.roadmap.mockResolvedValue(roadmapWith('pending'));
    await render(wrap(<JourneyScreen />, api));
    await screen.findByText(en['journey.intakeSaved']);
    const before = api.journeys.roadmap.mock.calls.length;
    for (let i = 0; i < INTAKE_POLL_ATTEMPTS + 3; i++) {
      await act(async () => {
        await jest.advanceTimersByTimeAsync(INTAKE_POLL_INTERVAL_MS);
      });
    }
    expect(api.journeys.roadmap.mock.calls.length - before).toBe(INTAKE_POLL_ATTEMPTS);
    expect(screen.getByText(en['journey.intakeDelayed'])).toBeTruthy();
    expect(screen.getByTestId('step-intake-M1')).toBeTruthy();
    await fireEvent.press(screen.getByTestId('journey-intake-notice-close'));
    expect(screen.queryByTestId('journey-intake-notice')).toBeNull();
  });
});

describe('intake form', () => {
  it('requires a timeframe and a city, then starts and submits the intake assessment', async () => {
    const api = fakeApi();
    await render(wrap(<JourneyIntake />, api));
    expect(screen.getByTestId('intake-submit').props.accessibilityState.disabled).toBe(true);
    expect(screen.getByText(en['intake.notesHint'])).toBeTruthy();
    expect(screen.getByTestId('intake-notes').props.maxLength).toBe(1000);
    expect(screen.getByTestId('intake-city-dubai').props.accessibilityRole).toBe('radio');

    await fireEvent.press(screen.getByTestId('intake-timeframe-within_month'));
    await fireEvent.press(screen.getByTestId('intake-city-abu_dhabi'));
    await fireEvent.press(screen.getByTestId('intake-practitioner_gender-female'));
    await fireEvent.changeText(screen.getByTestId('intake-notes'), 'Evenings suit me');
    await fireEvent.press(screen.getByTestId('intake-submit'));

    await waitFor(() => expect(mockRouter.dismissTo).toHaveBeenCalledWith({ pathname: '/journey', params: { notice: 'intake_saved' } }));
    expect(api.assessments.startIntake).toHaveBeenCalledWith('tok', 'U1', expect.any(String));
    expect(api.assessments.submit).toHaveBeenCalledWith(
      'tok',
      'A1',
      [
        { question: 'timeframe', answer: 'within_month' },
        { question: 'city', answer: 'abu_dhabi' },
        { question: 'language', answer: 'en' },
        { question: 'practitioner_gender', answer: 'female' },
        { question: 'visit_mode', answer: 'no_preference' },
        { question: 'notes', answer: 'Evenings suit me' },
      ],
      expect.any(String)
    );
  });

  it('shows the error, stays on the form and does not start a second assessment on retry', async () => {
    const api = fakeApi();
    api.assessments.submit.mockRejectedValueOnce(new ApiError({ status: 0, code: 'network_error' }));
    await render(wrap(<JourneyIntake />, api));
    await fireEvent.press(screen.getByTestId('intake-timeframe-asap'));
    await fireEvent.press(screen.getByTestId('intake-city-dubai'));
    await fireEvent.press(screen.getByTestId('intake-submit'));
    expect(await screen.findByText(en['error.network'])).toBeTruthy();
    expect(mockRouter.dismissTo).not.toHaveBeenCalled();

    await fireEvent.press(screen.getByTestId('intake-submit'));
    await waitFor(() => expect(mockRouter.dismissTo).toHaveBeenCalled());
    expect(api.assessments.startIntake).toHaveBeenCalledTimes(1);
    const keys = api.assessments.submit.mock.calls.map((c) => (c as unknown[])[3]);
    expect(keys[0]).toBe(keys[1]);
  });
});

describe('booking from a journey step', () => {
  it('filters the services list to the step category and passes the step id to booking', async () => {
    mockParams = { category: 'dermatology', milestoneId: 'M2' };
    const api = fakeApi();
    await render(wrap(<Services />, api));
    expect(await screen.findByTestId('services-journey-banner')).toBeTruthy();
    expect(api.directory.listServices).toHaveBeenCalledWith({ category: 'dermatology', limit: 100 });
    await fireEvent.press(await screen.findByTestId('book-S1'));
    expect(mockRouter.push).toHaveBeenCalledWith({ pathname: '/book/[serviceId]', params: { serviceId: 'S1', milestoneId: 'M2' } });
  });

  it('offers the concierge when the step category has no services yet', async () => {
    mockParams = { category: 'longevity', milestoneId: 'M3' };
    const api = fakeApi();
    await render(wrap(<Services />, api));
    expect(await screen.findByText(en['services.empty'])).toBeTruthy();
    expect(screen.getByTestId('category-longevity').props.accessibilityState.selected).toBe(true);
    await fireEvent.press(screen.getByTestId('services-concierge'));
    expect(mockRouter.push).toHaveBeenCalledWith('/concierge/new');
  });

  it('keeps the plain catalog unchanged without journey params', async () => {
    const api = fakeApi();
    await render(wrap(<Services />, api));
    await fireEvent.press(await screen.findByTestId('book-S1'));
    expect(mockRouter.push).toHaveBeenCalledWith({ pathname: '/book/[serviceId]', params: { serviceId: 'S1' } });
    expect(screen.queryByTestId('services-journey-banner')).toBeNull();
    expect(screen.queryByTestId('services-concierge')).toBeNull();
  });

  it('creates the appointment with milestone_id', async () => {
    mockParams = { serviceId: 'S1', milestoneId: 'M2' };
    const api = fakeApi();
    await render(wrap(<Book />, api));
    await fireEvent.press(await screen.findByTestId('book-slot-2026-12-01T05:00:00Z'));
    await waitFor(() =>
      expect(api.appointments.hold).toHaveBeenCalledWith('tok', { service_id: 'S1', scheduled_at: '2026-12-01T05:00:00Z', milestone_id: 'M2' }, expect.any(String))
    );
  });

  it('creates a plain appointment without milestone_id when booking outside a journey', async () => {
    mockParams = { serviceId: 'S1' };
    const api = fakeApi();
    await render(wrap(<Book />, api));
    await fireEvent.press(await screen.findByTestId('book-slot-2026-12-01T05:00:00Z'));
    await waitFor(() => expect(api.appointments.hold).toHaveBeenCalledWith('tok', { service_id: 'S1', scheduled_at: '2026-12-01T05:00:00Z' }, expect.any(String)));
  });
});

describe('home journey card', () => {
  const state = <T,>(data: T) => ({ data, error: undefined, loading: false, refreshing: false, fromCache: false, reload: jest.fn() });

  it('invites the customer to start when there is no journey', async () => {
    await render(wrap(<JourneyHomeCard summary={state({ journey: null, roadmap: null, nextActions: [] })} />, fakeApi()));
    await fireEvent.press(screen.getByTestId('home-journey-start'));
    expect(mockRouter.push).toHaveBeenCalledWith('/journey');
  });

  it('shows the current phase and the next action', async () => {
    const summary = state({
      journey,
      roadmap: roadmapWith('completed'),
      nextActions: [{ action_type: 'book' as const, priority: 'high' as const, milestone_id: 'M2', milestone_code: 'consultation', goal: 'skin_health', service_category: 'dermatology' }],
    });
    await render(wrap(<JourneyHomeCard summary={summary} />, fakeApi()));
    expect(screen.getByTestId('home-journey-phase').props.children).toBe('Current phase: Consult');
    expect(screen.getByTestId('home-journey-next').props.children).toBe('Next: Consultation · Skin health');
    await fireEvent.press(screen.getByTestId('home-journey-open'));
    expect(mockRouter.push).toHaveBeenCalledWith('/journey');
  });

  it('offers a retry when the journey could not be loaded', async () => {
    const failed = { ...state(undefined), error: new ApiError({ status: 0, code: 'network_error' }) };
    await render(wrap(<JourneyHomeCard summary={failed} />, fakeApi()));
    expect(screen.getByText(en['journey.home.unavailable'])).toBeTruthy();
    await fireEvent.press(screen.getByTestId('home-journey-retry'));
    expect(failed.reload).toHaveBeenCalled();
  });
});
