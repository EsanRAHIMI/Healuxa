/**
 * Push notifications: permission (user-initiated only), native token retrieval (APNs on iOS, FCM on
 * Android) and registration with notification-service (registerDeviceToken). The registered
 * device id is kept in the secure store so sign-out can remove it (deleteDeviceToken) before the
 * session is revoked — see installPushSignOutHook.
 */
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { NotificationsApi } from '../api/client';
import type { SessionManager } from '../auth/sessionManager';
import type { TokenStore } from '../auth/tokenStore';
import { config } from '../config';

export type PushPermission = 'granted' | 'denied' | 'undetermined';

export interface PushSetupResult {
  permission: PushPermission;
  /** notification-service device id when registration succeeded */
  deviceId?: string;
  /** set when the OS could not issue a token (e.g. Android build without FCM config) */
  tokenError?: string;
}

export const pushEnabled = () => config.features.push;

export async function currentPermission(): Promise<PushPermission> {
  const { status } = await Notifications.getPermissionsAsync();
  return status as PushPermission;
}

export async function setUpPush(deps: {
  notifications: NotificationsApi;
  session: SessionManager;
  tokenStore: TokenStore;
}): Promise<PushSetupResult> {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Healuxa',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
  if (status !== 'granted') return { permission: status as PushPermission };

  let token: string;
  try {
    token = String((await Notifications.getDevicePushTokenAsync()).data);
  } catch (e) {
    return { permission: 'granted', tokenError: e instanceof Error ? e.message : String(e) };
  }
  const platform = Platform.OS === 'ios' ? 'ios' : 'android';
  const device = await deps.session.withAuth((t) => deps.notifications.registerDevice(t, platform, token));
  await deps.tokenStore.setPushDeviceId(device.id);
  return { permission: 'granted', deviceId: device.id };
}

/** Removes this device's push registration server-side when the user signs out. */
export function installPushSignOutHook(deps: {
  notifications: NotificationsApi;
  session: SessionManager;
  tokenStore: TokenStore;
}): () => void {
  return deps.session.addSignOutHook(async (accessToken) => {
    const id = await deps.tokenStore.getPushDeviceId();
    if (!id) return;
    try {
      await deps.notifications.deleteDevice(accessToken, id);
    } finally {
      await deps.tokenStore.setPushDeviceId(null);
    }
  });
}
