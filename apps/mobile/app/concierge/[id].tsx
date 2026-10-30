/**
 * Concierge case detail with secure messaging. Uses concierge: getConciergeCase,
 * listConciergeCaseOptions, selectConciergeCaseOption, listConciergeCaseMessages,
 * postConciergeCaseMessage, markConciergeCaseMessagesRead and transitionConciergeCase(cancelled).
 * Messages are polled while the screen is open (no realtime channel exists yet) and never cached.
 */
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, View } from 'react-native';

import { ApiError } from '@/api/errors';
import { useAuth } from '@/auth/AuthProvider';
import { formatDateTime } from '@/format/time';
import { errorKey, useRemote } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Card, ErrorState, Loading, Row, Screen, Section, TextField } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';
import { StatusBadge } from '@/ui/StatusBadge';

const POLL_MS = 15_000;
const CLOSED = new Set(['completed', 'cancelled']);

export default function ConciergeCaseScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const signedIn = auth.status === 'signedIn';
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const run = <T,>(fn: (tk: string) => Promise<T>) => (signedIn ? auth.withAuth(fn) : Promise.resolve(null));

  const kase = useRemote(() => run((tk) => api.concierge.get(tk, id)), [api, id, signedIn]);
  const options = useRemote(() => run((tk) => api.concierge.options(tk, id)), [api, id, signedIn, kase.data?.status]);
  const messages = useRemote(() => run((tk) => api.concierge.messages(tk, id)), [api, id, signedIn]);

  // Poll for new messages and mark the coordinator's messages read.
  const reloadMessages = messages.reload;
  useEffect(() => {
    if (!signedIn) return;
    const timer = setInterval(() => reloadMessages(), POLL_MS);
    return () => clearInterval(timer);
  }, [signedIn, reloadMessages]);
  const unreadFromCoordinator = (messages.data?.data ?? []).some((m) => m.sender_role === 'coordinator' && !m.read_at);
  useEffect(() => {
    if (unreadFromCoordinator) auth.withAuth((tk) => api.concierge.markRead(tk, id)).catch(() => undefined);
  }, [unreadFromCoordinator, api, auth, id]);

  if (!signedIn) return <SignedOutPrompt />;
  if (kase.loading) return <Screen><Loading /></Screen>;
  if (kase.error || !kase.data) return <Screen>{kase.error ? <ErrorState error={kase.error} onRetry={kase.reload} /> : null}</Screen>;
  const c = kase.data;

  const report = (e: unknown) =>
    Alert.alert(t('concierge.title'), t(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }))));

  const send = async () => {
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    try {
      await auth.withAuth((tk) => api.concierge.postMessage(tk, id, body));
      setDraft('');
      messages.reload();
    } catch (e) {
      report(e);
    } finally {
      setSending(false);
    }
  };

  const select = async (optionId: string) => {
    try {
      await auth.withAuth((tk) => api.concierge.selectOption(tk, id, optionId));
      kase.reload();
      options.reload();
    } catch (e) {
      report(e);
    }
  };

  const cancel = () =>
    Alert.alert(t('concierge.cancel'), t('concierge.cancelConfirm'), [
      { text: t('common.close'), style: 'cancel' },
      {
        text: t('concierge.cancel'),
        style: 'destructive',
        onPress: async () => {
          try {
            await auth.withAuth((tk) => api.concierge.cancel(tk, id));
            kase.reload();
          } catch (e) {
            report(e);
          }
        },
      },
    ]);

  const canMessage = Boolean(c.coordinator_id) && !CLOSED.has(c.status);
  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <Screen testID="concierge-case-screen" onRefresh={() => { kase.reload(); messages.reload(); }} refreshing={kase.refreshing}>
        <Stack.Screen options={{ title: t(`concierge.category.${c.category}` as MessageKey) }} />
        <StatusBadge kind="concierge" status={c.status} />
        {!c.first_responded_at && c.status === 'submitted' ? (
          <AppText variant="small" muted>{t('concierge.responseDue', { time: formatDateTime(c.first_response_due_at, language) })}</AppText>
        ) : null}
        {c.needs_note ? <Card><AppText variant="small">{c.needs_note}</AppText></Card> : null}

        {options.data?.data.length ? (
          <Section title={t('concierge.options')}>
            {options.data.data.map((o) => (
              <Card key={o.id} testID={`option-${o.id}`}>
                <AppText variant="label">{o.label ?? ''}</AppText>
                <Button kind="link" label={t('services.byProvider')} onPress={() => router.push({ pathname: '/providers/[id]', params: { id: o.provider_id } })} />
                {o.status === 'selected' ? (
                  <AppText variant="small" style={{ color: theme.color.success }}>{t('concierge.selected')}</AppText>
                ) : o.status === 'proposed' && (c.status === 'in_progress' || c.status === 'awaiting_customer') ? (
                  <Button kind="secondary" label={t('concierge.select')} onPress={() => select(o.id)} />
                ) : null}
              </Card>
            ))}
          </Section>
        ) : null}

        <Section title={t('concierge.messages')}>
          {messages.error ? (
            <ErrorState error={messages.error} onRetry={messages.reload} />
          ) : !messages.data?.data.length ? (
            <AppText variant="small" muted>{t('concierge.noMessages')}</AppText>
          ) : (
            messages.data.data.map((m) => {
              const mine = m.sender_role === 'customer';
              return (
                <View key={m.id} style={{ alignItems: mine ? 'flex-end' : 'flex-start' }}>
                  <Card style={{ maxWidth: '85%', backgroundColor: mine ? theme.color.surfaceAlt : theme.color.surface }}>
                    <AppText variant="caption" muted>{mine ? t('concierge.you') : t('concierge.coordinator')}</AppText>
                    <AppText selectable>{m.body}</AppText>
                    <Row>
                      <AppText variant="caption" muted>{formatDateTime(m.created_at, language)}</AppText>
                      {mine && m.read_at ? <AppText variant="caption" muted>· {t('concierge.read')}</AppText> : null}
                    </Row>
                  </Card>
                </View>
              );
            })
          )}
          {canMessage ? (
            <>
              <AppText variant="caption" muted>{t('concierge.messageWarning')}</AppText>
              <TextField label={t('concierge.messagePlaceholder')} value={draft} onChangeText={setDraft} multiline maxLength={4000} testID="concierge-message" />
              <Button label={t('common.send')} onPress={send} busy={sending} disabled={!draft.trim()} icon="send-outline" testID="concierge-send" />
            </>
          ) : null}
        </Section>

        {!CLOSED.has(c.status) ? <Button kind="danger" label={t('concierge.cancel')} onPress={cancel} testID="concierge-cancel" /> : null}
      </Screen>
    </KeyboardAvoidingView>
  );
}
