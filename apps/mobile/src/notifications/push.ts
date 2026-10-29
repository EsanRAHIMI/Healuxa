import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { config } from '../config';

export type PushPermission = 'granted' | 'denied' | 'undetermined';

export interface PushSetupResult {
  permission: PushPermission;
  /** native APNs / FCM token, only present when permission was granted */
  deviceToken?: string;
  tokenError?: string;
  /**
   * Backend registration status. The notification-service device-token endpoint does not exist
   * yet (packages/api-contracts/openapi/notification.openapi.yaml has no device-token operation),
   * so the token is never sent anywhere.
   */
  registration: 'backend_pending';
}

export const pushEnabled = () => config.features.push;

export async function currentPermission(): Promise<PushPermission> {
  const { status } = await Notifications.getPermissionsAsync();
  return status as PushPermission;
}

/** Asks for permission (user-initiated only) and retrieves the native token. Never registers it. */
export async function setUpPush(): Promise<PushSetupResult> {
  if (!pushEnabled()) throw new Error('push feature flag is off');
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Healuxa',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  let { status } = await Notifications.getPermissionsAsync();
  if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
  if (status !== 'granted') return { permission: status as PushPermission, registration: 'backend_pending' };
  try {
    const token = await Notifications.getDevicePushTokenAsync();
    return { permission: 'granted', deviceToken: String(token.data), registration: 'backend_pending' };
  } catch (e) {
    return { permission: 'granted', tokenError: e instanceof Error ? e.message : String(e), registration: 'backend_pending' };
  }
}
