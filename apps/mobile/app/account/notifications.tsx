import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, Linking, Switch, View } from 'react-native';

import { ApiError } from '@/api/errors';
import type { Channel, NotificationPreferences } from '@/api/types';
import { useAuth } from '@/auth/AuthProvider';
import { errorKey, useRemote } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { currentPermission, type PushPermission, pushEnabled, setUpPush } from '@/notifications/push';
import { useServices } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Card, ErrorState, Loading, Screen, Section } from '@/ui/primitives';

const CATEGORIES = ['appointments', 'concierge', 'account'] as const;
const CHANNELS: Channel[] = ['push', 'email', 'sms', 'whatsapp'];

/**
 * Notification preferences (notification: getPreferences / updatePreferences) and push opt-in
 * (OS permission → native token → notification: registerDeviceToken).
 */
export default function NotificationsScreen() {
  const { t } = useI18n();
  const theme = useTheme();
  const auth = useAuth();
  const services = useServices();
  const { api } = services;
  const [permission, setPermission] = useState<PushPermission | null>(null);
  const [pushMessage, setPushMessage] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  // Local optimistic copy; falls back to the server value until the user edits something.
  const [edited, setPrefs] = useState<NotificationPreferences | null>(null);
  const userId = auth.userId ?? '';
  const loaded = useRemote(() => auth.withAuth((tk) => api.notifications.preferences(tk, userId)), [api, userId, auth.withAuth]);

  useEffect(() => {
    if (pushEnabled()) currentPermission().then(setPermission).catch(() => setPermission('undetermined'));
  }, []);
  const prefs = edited ?? loaded.data ?? null;

  if (auth.status !== 'signedIn') return <Redirect href="/account" />;

  const save = async (patch: Partial<NotificationPreferences>) => {
    const previous = prefs;
    if (prefs) setPrefs({ ...prefs, ...patch });
    try {
      const updated = await auth.withAuth((tk) =>
        api.notifications.updatePreferences(tk, userId, { channels: patch.channels, marketing_opt_in: patch.marketing_opt_in })
      );
      setPrefs(updated);
    } catch (e) {
      setPrefs(previous);
      Alert.alert(t('prefs.title'), t(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }))));
    }
  };

  const toggleChannel = (category: string, channel: Channel, value: boolean) => {
    if (!prefs) return;
    // Send only the changed category; the server merges with the stored switches.
    void save({ channels: { [category]: { ...prefs.channels[category], [channel]: value } } });
  };

  const enablePush = async () => {
    setBusy(true);
    try {
      const r = await setUpPush({ notifications: api.notifications, session: services.session, tokenStore: services.tokenStore });
      setPermission(r.permission);
      setPushMessage(r.deviceId ? 'notifications.registered' : r.tokenError ? 'notifications.tokenUnavailable' : null);
    } catch (e) {
      Alert.alert(t('notifications.title'), t(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }))));
    } finally {
      setBusy(false);
    }
  };

  const row = (label: string, value: boolean, onChange: (v: boolean) => void, testID: string) => (
    <View key={testID} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 48, gap: theme.space(3) }}>
      <AppText style={{ flex: 1 }}>{label}</AppText>
      <Switch testID={testID} accessibilityLabel={label} value={value} onValueChange={onChange} trackColor={{ true: theme.color.accent }} />
    </View>
  );

  return (
    <Screen testID="notifications-screen">
      {pushEnabled() ? (
        <Card>
          <AppText>{t('notifications.body')}</AppText>
          {permission === 'denied' ? (
            <>
              <AppText variant="small">{t('notifications.denied')}</AppText>
              <Button kind="secondary" label={t('common.continue')} onPress={() => Linking.openSettings()} />
            </>
          ) : (
            <Button label={t('notifications.enable')} onPress={enablePush} busy={busy} testID="notifications-enable" />
          )}
          {pushMessage ? <AppText variant="small" muted>{t(pushMessage)}</AppText> : null}
        </Card>
      ) : null}

      {loaded.loading && !prefs ? (
        <Loading />
      ) : loaded.error && !prefs ? (
        <ErrorState error={loaded.error} onRetry={loaded.reload} />
      ) : prefs ? (
        <>
          {CATEGORIES.map((category) => (
            <Section key={category} title={t(`prefs.category.${category}` as MessageKey)}>
              <Card>
                {CHANNELS.map((channel) =>
                  row(
                    t(`prefs.channel.${channel}` as MessageKey),
                    Boolean(prefs.channels[category]?.[channel]),
                    (v) => toggleChannel(category, channel, v),
                    `pref-${category}-${channel}`
                  )
                )}
              </Card>
            </Section>
          ))}
          <Card>
            {row(t('prefs.marketing'), prefs.marketing_opt_in, (v) => void save({ marketing_opt_in: v }), 'pref-marketing')}
            <AppText variant="caption" muted>{t('prefs.marketingHint')}</AppText>
          </Card>
        </>
      ) : null}
    </Screen>
  );
}
