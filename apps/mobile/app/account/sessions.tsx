import { Redirect } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { ApiError } from '@/api/errors';
import { useAuth } from '@/auth/AuthProvider';
import { errorKey, useRemote } from '@/hooks/useRemote';
import { useI18n } from '@/i18n';
import { formatDate } from '@/i18n/labels';
import { useApi } from '@/services';
import { AppText, Badge, Button, Card, EmptyState, ErrorState, Loading, Row, Screen } from '@/ui/primitives';

/** Sessions. Uses identity: listSessions, revokeSession (sessions:revoke). */
export default function Sessions() {
  const { t, language } = useI18n();
  const api = useApi();
  const auth = useAuth();
  const [revoking, setRevoking] = useState<string | null>(null);
  const sessions = useRemote(() => auth.withAuth((token) => api.identity.listSessions(token)), [api, auth.withAuth]);

  if (auth.status !== 'signedIn') return <Redirect href="/account" />;

  const revoke = (id: string) => {
    const isCurrent = id === auth.sessionId;
    Alert.alert(t('sessions.revoke'), t('sessions.revokeConfirm'), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('sessions.revoke'),
        style: 'destructive',
        onPress: async () => {
          setRevoking(id);
          try {
            if (isCurrent) {
              await auth.signOut();
              return;
            }
            await auth.withAuth((token) => api.identity.revokeSession(token, id));
            sessions.reload();
          } catch (e) {
            Alert.alert(t('sessions.revoke'), t(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }))));
          } finally {
            setRevoking(null);
          }
        },
      },
    ]);
  };

  return (
    <Screen testID="sessions-screen" onRefresh={sessions.reload} refreshing={sessions.refreshing}>
      {sessions.loading ? (
        <Loading />
      ) : sessions.error ? (
        <ErrorState error={sessions.error} onRetry={sessions.reload} />
      ) : !sessions.data?.data.length ? (
        <EmptyState message={t('sessions.empty')} />
      ) : (
        sessions.data.data.map((s) => {
          const current = s.id === auth.sessionId;
          return (
            <Card key={s.id} testID={current ? 'session-current' : `session-${s.id}`}>
              <Row style={{ justifyContent: 'space-between' }}>
                <AppText variant="label">{s.device && s.device !== 'unknown' ? s.device : t('sessions.unknownDevice')}</AppText>
                {current ? <Badge label={t('sessions.thisDevice')} icon="phone-portrait-outline" /> : null}
              </Row>
              <AppText variant="small" muted>{t('sessions.started', { date: formatDate(s.created_at, language) })}</AppText>
              <AppText variant="small" muted>{t('sessions.lastSeen', { date: formatDate(s.last_seen_at, language) })}</AppText>
              {s.ip ? <AppText variant="caption" muted>{s.ip}</AppText> : null}
              <Button kind="danger" label={t('sessions.revoke')} onPress={() => revoke(s.id)} busy={revoking === s.id} testID={`revoke-${s.id}`} />
            </Card>
          );
        })
      )}
    </Screen>
  );
}
