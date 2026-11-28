/**
 * Healuxa assistant (ai-orchestrator, ai.openapi.yaml). Replies come back as JSON (React Native
 * fetch has no streaming body) with action cards built server-side from verified data; tapping a
 * card opens the app's own booking, directory, journey or concierge screen. The assistant never
 * books or pays. "Talk to a person" is always one tap away.
 */
import { randomUUID } from 'expo-crypto';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { TextInput, View } from 'react-native';

import type { AssistantCard, AssistantTurn } from '@/api/assistantTypes';
import { ApiError } from '@/api/errors';
import { cardRoute } from '@/assistant/route';
import { useAuth } from '@/auth/AuthProvider';
import { formatMoney } from '@/format/money';
import { formatDateTime } from '@/format/time';
import { type MessageKey, useI18n } from '@/i18n';
import { stepLabel } from '@/journey/plan';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Badge, Button, Card, Row, Screen } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';

const MAX_CHARS = 2000;

function errorMessage(e: unknown): MessageKey {
  if (!(e instanceof ApiError)) return 'assistant.error.unavailable';
  if (e.status === 429) return 'assistant.error.rateLimited';
  if (e.status === 422) return 'assistant.error.tooLong';
  if (e.status === 401) return 'error.unauthorized';
  if (e.status === 503 || e.isNetwork) return 'assistant.error.unavailable';
  return 'error.generic';
}

export default function AssistantScreen() {
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<MessageKey | null>(null);
  const lastKey = useRef<{ text: string; key: string } | null>(null);

  if (auth.status !== 'signedIn') return <SignedOutPrompt intro={t('assistant.intro')} />;

  const send = async (raw: string) => {
    const text = raw.trim().slice(0, MAX_CHARS);
    if (!text || busy) return;
    // The same text retried after a failure reuses its Idempotency-Key (no duplicate answer).
    const key = lastKey.current?.text === text ? lastKey.current.key : randomUUID();
    lastKey.current = { text, key };
    setBusy(true);
    setError(null);
    const pending: AssistantTurn = { id: `local-${key}`, role: 'user', content: text, cards: [], created_at: new Date().toISOString() };
    setTurns((cur) => [...cur, pending]);
    setDraft('');
    try {
      const reply = await auth.withAuth(async (tk) => {
        const sid = sessionId ?? (await api.assistant.createSession(tk, language)).id;
        setSessionId(sid);
        return api.assistant.send(tk, sid, text, key);
      });
      setTurns((cur) => [...cur, reply]);
      lastKey.current = null;
    } catch (e) {
      setTurns((cur) => cur.filter((x) => x.id !== pending.id));
      setDraft(text);
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const open = (card: AssistantCard) => {
    const route = cardRoute(card);
    if (route) router.push(route as never);
  };

  const starters: MessageKey[] = ['assistant.starter.nextStep', 'assistant.starter.appointments', 'assistant.starter.person'];

  return (
    <Screen testID="assistant-screen">
      <AppText muted>{t('assistant.intro')}</AppText>
      <Row style={{ justifyContent: 'flex-end' }}>
        {turns.length ? (
          <Button kind="link" label={t('assistant.newChat')} onPress={() => { setTurns([]); setSessionId(null); setError(null); }} testID="assistant-new" />
        ) : null}
        <Button kind="secondary" label={t('assistant.talkToPerson')} onPress={() => router.push('/concierge/new')} testID="assistant-handoff" />
      </Row>

      {turns.length === 0 && !busy ? (
        <Card testID="assistant-empty">
          <AppText variant="heading">{t('assistant.emptyTitle')}</AppText>
          <View style={{ gap: theme.space(2), marginTop: theme.space(2) }}>
            {starters.map((k) => (
              <Button key={k} kind="secondary" label={t(k)} onPress={() => void send(t(k))} testID="assistant-starter" />
            ))}
          </View>
        </Card>
      ) : null}

      <View accessibilityLabel={t('assistant.title')} style={{ gap: theme.space(3) }} testID="assistant-log">
        {turns.map((turn) => (
          <View key={turn.id} style={{ alignItems: turn.role === 'user' ? 'flex-end' : 'flex-start' }} testID={`turn-${turn.role}`}>
            <Card style={{ maxWidth: '92%', backgroundColor: turn.role === 'user' ? theme.color.surfaceAlt : theme.color.surface }}>
              <AppText variant="caption" muted>
                {turn.role === 'user' ? t('assistant.you') : t('assistant.name')}
              </AppText>
              <AppText>{turn.content}</AppText>
              {turn.cards.map((card, i) => (
                <AssistantCardView key={`${card.kind}-${'id' in card ? card.id : i}`} card={card} onOpen={open} />
              ))}
            </Card>
          </View>
        ))}
        {busy ? (
          <AppText muted accessibilityLiveRegion="polite" testID="assistant-thinking">
            {t('assistant.thinking')}
          </AppText>
        ) : null}
      </View>

      {error ? (
        <Card accessibilityRole="alert" testID="assistant-error">
          <AppText>{t(error)}</AppText>
          <Row>
            <Button kind="link" label={t('common.retry')} onPress={() => void send(draft)} testID="assistant-retry" />
            <Button kind="link" label={t('assistant.talkToPerson')} onPress={() => router.push('/concierge/new')} />
          </Row>
        </Card>
      ) : null}

      <View style={{ gap: theme.space(2) }}>
        <AppText variant="label">{t('assistant.inputLabel')}</AppText>
        <TextInput
          testID="assistant-input"
          accessibilityLabel={t('assistant.inputLabel')}
          value={draft}
          onChangeText={setDraft}
          placeholder={t('assistant.placeholder')}
          placeholderTextColor={theme.color.textMuted}
          multiline
          maxLength={MAX_CHARS}
          style={{
            minHeight: 72,
            borderWidth: 1,
            borderColor: theme.color.border,
            borderRadius: theme.radius.md,
            padding: theme.space(3),
            color: theme.color.text,
            backgroundColor: theme.color.surface,
            textAlign: 'auto',
            textAlignVertical: 'top',
          }}
        />
        <Button label={t('assistant.send')} onPress={() => void send(draft)} busy={busy} disabled={!draft.trim()} testID="assistant-send" />
      </View>
      <AppText variant="caption" muted testID="assistant-notice">
        {t('assistant.notice')}
      </AppText>
    </Screen>
  );
}

function AssistantCardView({ card, onOpen }: { card: AssistantCard; onOpen: (card: AssistantCard) => void }) {
  const { t, language } = useI18n();
  const theme = useTheme();
  const box = { marginTop: theme.space(3), gap: theme.space(1), padding: theme.space(3), borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.color.border };
  switch (card.kind) {
    case 'service': {
      const price =
        card.price_type === 'on_request' || !card.price
          ? t('assistant.card.priceOnRequest')
          : card.price_type === 'from'
            ? t('assistant.card.priceFrom', { price: formatMoney(card.price, language) })
            : formatMoney(card.price, language);
      return (
        <View style={box} testID="card-service">
          <AppText variant="label">{card.title}</AppText>
          {card.provider_name ? <AppText muted>{t('assistant.card.with', { name: card.provider_name })}</AppText> : null}
          <AppText>
            {price}
            {card.duration_minutes ? ` · ${t('common.minutes', { n: card.duration_minutes })}` : ''}
          </AppText>
          {card.next_slots.length ? (
            <AppText variant="small" muted>
              {t('assistant.card.nextSlots')}: {card.next_slots.map((s) => formatDateTime(s, language, card.timezone ?? undefined)).join(' · ')}
            </AppText>
          ) : null}
          {card.milestone_id ? <Badge label={t('assistant.card.linkedStep')} tone="neutral" /> : null}
          <Button label={t('assistant.card.book')} onPress={() => onOpen(card)} testID="card-service-book" />
        </View>
      );
    }
    case 'provider':
    case 'facility':
      return (
        <View style={box} testID={`card-${card.kind}`}>
          <AppText variant="label">{card.title}</AppText>
          {card.kind === 'provider' && card.subtitle ? <AppText muted>{card.subtitle}</AppText> : null}
          <Button kind="secondary" label={t('assistant.card.open')} onPress={() => onOpen(card)} />
        </View>
      );
    case 'journey_step':
      return (
        <View style={box} testID="card-journey_step">
          <AppText variant="label">{stepLabel({ code: card.code, goal: card.goal }, t)}</AppText>
          <Button label={t('assistant.card.open')} onPress={() => onOpen(card)} />
        </View>
      );
    case 'appointment':
      return (
        <View style={box} testID="card-appointment">
          <AppText variant="label">{card.title}</AppText>
          {card.scheduled_at ? <AppText>{formatDateTime(card.scheduled_at, language, card.timezone ?? undefined)}</AppText> : null}
          <Button kind="secondary" label={t('assistant.card.open')} onPress={() => onOpen(card)} />
        </View>
      );
    case 'concierge_case':
      return (
        <View style={box} testID="card-concierge_case">
          <AppText variant="label">{t('assistant.card.caseTitle')}</AppText>
          <Button label={t('assistant.card.open')} onPress={() => onOpen(card)} />
        </View>
      );
    case 'handoff':
      return (
        <View style={box} testID="card-handoff">
          <AppText>{t('assistant.card.handoffTitle')}</AppText>
          <Button kind="secondary" label={t('assistant.card.handoffCta')} onPress={() => onOpen(card)} />
        </View>
      );
    default:
      return null;
  }
}
