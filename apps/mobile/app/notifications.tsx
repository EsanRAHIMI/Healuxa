/**
 * In-app inbox. Uses notification: listNotifications, markNotificationRead, markAllNotificationsRead.
 * Opening a notification marks it read and deep-links to the related appointment or concierge case.
 */
import { type Href, Stack, useRouter } from 'expo-router';

import type { InboxNotification } from '@/api/types';
import { useAuth } from '@/auth/AuthProvider';
import { formatDateTime } from '@/format/time';
import { useRemote } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, EmptyState, ErrorState, Loading, PressableCard, Screen } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';

function targetOf(n: InboxNotification): Href | null {
  if (!n.entity_id) return null;
  if (n.entity_type === 'appointment') return { pathname: '/appointments/[id]', params: { id: n.entity_id } };
  if (n.entity_type === 'concierge_case') return { pathname: '/concierge/[id]', params: { id: n.entity_id } };
  if (n.entity_type === 'provider') return { pathname: '/providers/[id]', params: { id: n.entity_id } };
  if (n.entity_type === 'facility') return { pathname: '/facilities/[id]', params: { id: n.entity_id } };
  return null;
}

export default function Inbox() {
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const signedIn = auth.status === 'signedIn';
  const inbox = useRemote(() => (signedIn ? auth.withAuth((tk) => api.notifications.inbox(tk)) : Promise.resolve(null)), [api, signedIn, auth.withAuth]);

  if (!signedIn) return <SignedOutPrompt />;

  const open = async (n: InboxNotification) => {
    if (!n.read_at) await auth.withAuth((tk) => api.notifications.markRead(tk, n.id)).catch(() => undefined);
    const target = targetOf(n);
    if (target) router.push(target);
    else inbox.reload();
  };
  const markAll = async () => {
    await auth.withAuth((tk) => api.notifications.markAllRead(tk)).catch(() => undefined);
    inbox.reload();
  };
  const items = inbox.data?.data ?? [];
  const unread = items.filter((n) => !n.read_at).length;

  return (
    <Screen testID="inbox-screen" onRefresh={inbox.reload} refreshing={inbox.refreshing}>
      <Stack.Screen options={{ title: t('inbox.title') }} />
      {unread ? <Button kind="link" label={t('inbox.markAll')} onPress={markAll} testID="inbox-mark-all" /> : null}
      {inbox.loading ? (
        <Loading />
      ) : inbox.error ? (
        <ErrorState error={inbox.error} onRetry={inbox.reload} />
      ) : !items.length ? (
        <EmptyState message={t('inbox.empty')} />
      ) : (
        items.map((n) => (
          <PressableCard key={n.id} testID={`notification-${n.id}`} accessibilityLabel={`${n.title}. ${n.body}`} onPress={() => open(n)}>
            <AppText variant="label" style={{ color: n.read_at ? theme.color.textMuted : theme.color.text }}>
              {n.read_at ? '' : '● '}
              {n.title}
            </AppText>
            <AppText variant="small" muted>{n.body}</AppText>
            <AppText variant="caption" muted>{formatDateTime(n.created_at, language)}</AppText>
          </PressableCard>
        ))
      )}
    </Screen>
  );
}
