import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * Build-time app configuration. Everything here ends up in the app bundle, so it must never
 * contain secrets. Environment variables (all optional):
 *
 *   APP_ENV                 development | e2e | staging | production   (default: development)
 *   APP_BUNDLE_ID           iOS bundle id / Android application id     (default: ae.healuxa.app)
 *   APP_LINK_DOMAIN         universal-link / App Links domain          (default: healuxa.ae)
 *   API_BASE_URL            single edge base URL for every service (e.g. https://api.healuxa.com)
 *   IDENTITY_BASE_URL       per-service override (local development: http://localhost:8201)
 *   PROVIDER_BASE_URL       per-service override (local development: http://localhost:8205)
 *   SUPPORT_EMAIL           account-deletion / support mailbox        (placeholder until confirmed)
 *   FEATURE_PUSH            "1" enables the notification permission + token flow
 *   EAS_PROJECT_ID          Expo project id (needed for Expo push tokens; owner provides)
 */
type AppEnv = 'development' | 'e2e' | 'staging' | 'production';

const APP_ENV = (process.env.APP_ENV ?? 'development') as AppEnv;
const BUNDLE_ID = process.env.APP_BUNDLE_ID ?? 'ae.healuxa.app';
const LINK_DOMAIN = process.env.APP_LINK_DOMAIN ?? 'healuxa.ae';
const IS_LOCAL = APP_ENV === 'development' || APP_ENV === 'e2e';

function baseUrl(specific: string | undefined, localDefault: string): string {
  const url = specific ?? process.env.API_BASE_URL ?? (IS_LOCAL ? localDefault : 'https://api.healuxa.com');
  if (!IS_LOCAL && !url.startsWith('https://')) {
    // TLS-only for every non-local build: fail the build instead of shipping cleartext traffic.
    throw new Error(`[app.config] ${APP_ENV} builds require https base URLs, got ${url}`);
  }
  return url.replace(/\/+$/, '');
}

const identityBaseUrl = baseUrl(process.env.IDENTITY_BASE_URL, 'http://localhost:8201');
const providerBaseUrl = baseUrl(process.env.PROVIDER_BASE_URL, 'http://localhost:8205');

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'Healuxa',
  slug: 'healuxa',
  owner: process.env.EXPO_OWNER,
  version: '0.1.0',
  orientation: 'portrait',
  scheme: 'healuxa',
  userInterfaceStyle: 'automatic',
  icon: './assets/icon.png',
  ios: {
    bundleIdentifier: BUNDLE_ID,
    buildNumber: '1',
    supportsTablet: false,
    // applinks: universal links; webcredentials: password AutoFill for the sign-in form.
    associatedDomains: [`applinks:${LINK_DOMAIN}`, `webcredentials:${LINK_DOMAIN}`],
    config: { usesNonExemptEncryption: false },
    infoPlist: {
      CFBundleAllowMixedLocalizations: true,
      CFBundleLocalizations: ['en', 'ar', 'fa'],
      LSApplicationQueriesSchemes: ['mailto'],
      NSFaceIDUsageDescription:
        'Healuxa uses Face ID to unlock your signed-in session on this device when you turn on biometric unlock.',
    },
    privacyManifests: {
      NSPrivacyTracking: false,
      NSPrivacyTrackingDomains: [],
      NSPrivacyCollectedDataTypes: [
        {
          NSPrivacyCollectedDataType: 'NSPrivacyCollectedDataTypeEmailAddress',
          NSPrivacyCollectedDataTypeLinked: true,
          NSPrivacyCollectedDataTypeTracking: false,
          NSPrivacyCollectedDataTypePurposes: ['NSPrivacyCollectedDataTypePurposeAppFunctionality'],
        },
        {
          NSPrivacyCollectedDataType: 'NSPrivacyCollectedDataTypePhoneNumber',
          NSPrivacyCollectedDataTypeLinked: true,
          NSPrivacyCollectedDataTypeTracking: false,
          NSPrivacyCollectedDataTypePurposes: ['NSPrivacyCollectedDataTypePurposeAppFunctionality'],
        },
        {
          NSPrivacyCollectedDataType: 'NSPrivacyCollectedDataTypeUserID',
          NSPrivacyCollectedDataTypeLinked: true,
          NSPrivacyCollectedDataTypeTracking: false,
          NSPrivacyCollectedDataTypePurposes: ['NSPrivacyCollectedDataTypePurposeAppFunctionality'],
        },
      ],
      NSPrivacyAccessedAPITypes: [
        {
          // expo-file-system / React Native read file timestamps for the public directory cache.
          NSPrivacyAccessedAPIType: 'NSPrivacyAccessedAPICategoryFileTimestamp',
          NSPrivacyAccessedAPITypeReasons: ['C617.1'],
        },
        {
          // React Native and Expo modules use NSUserDefaults for their own settings.
          NSPrivacyAccessedAPIType: 'NSPrivacyAccessedAPICategoryUserDefaults',
          NSPrivacyAccessedAPITypeReasons: ['CA92.1'],
        },
        {
          NSPrivacyAccessedAPIType: 'NSPrivacyAccessedAPICategorySystemBootTime',
          NSPrivacyAccessedAPITypeReasons: ['35F9.1'],
        },
        {
          NSPrivacyAccessedAPIType: 'NSPrivacyAccessedAPICategoryDiskSpace',
          NSPrivacyAccessedAPITypeReasons: ['E174.1'],
        },
      ],
    },
  },
  android: {
    package: BUNDLE_ID,
    versionCode: 1,
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#F7F4EF',
    },
    // Only what the app needs; expo-notifications adds POST_NOTIFICATIONS on Android 13+.
    permissions: ['USE_BIOMETRIC', 'USE_FINGERPRINT'],
    blockedPermissions: [
      'android.permission.SYSTEM_ALERT_WINDOW',
      'android.permission.READ_EXTERNAL_STORAGE',
      'android.permission.WRITE_EXTERNAL_STORAGE',
      'android.permission.RECORD_AUDIO',
    ],
    intentFilters: [
      {
        action: 'VIEW',
        autoVerify: true,
        data: [
          { scheme: 'https', host: LINK_DOMAIN, pathPrefix: '/providers' },
          { scheme: 'https', host: LINK_DOMAIN, pathPrefix: '/facilities' },
          { scheme: 'https', host: LINK_DOMAIN, pathPrefix: '/services' },
        ],
        category: ['BROWSABLE', 'DEFAULT'],
      },
    ],
  },
  plugins: [
    'expo-router',
    'expo-secure-store',
    ['expo-localization', { supportsRTL: true, supportedLocales: ['en', 'ar', 'fa'] }],
    [
      'expo-local-authentication',
      {
        faceIDPermission:
          'Healuxa uses Face ID to unlock your signed-in session on this device when you turn on biometric unlock.',
      },
    ],
    [
      'expo-notifications',
      {
        // Permission is only requested from the in-app opt-in when FEATURE_PUSH is enabled.
        color: '#8C6A43',
      },
    ],
    [
      'expo-splash-screen',
      {
        image: './assets/splash-icon.png',
        imageWidth: 160,
        resizeMode: 'contain',
        backgroundColor: '#F7F4EF',
        dark: { image: './assets/splash-icon.png', backgroundColor: '#14110F' },
      },
    ],
    [
      'expo-build-properties',
      {
        android: {
          // Cleartext only for local development/E2E builds that talk to http://10.0.2.2.
          usesCleartextTraffic: IS_LOCAL,
        },
        ios: {},
      },
    ],
    './plugins/withAndroidReleaseSigning',
  ],
  experiments: { typedRoutes: true },
  extra: {
    appEnv: APP_ENV,
    identityBaseUrl,
    providerBaseUrl,
    linkDomain: LINK_DOMAIN,
    supportEmail: process.env.SUPPORT_EMAIL ?? 'privacy@healuxa.ae',
    privacyPolicyUrl: process.env.PRIVACY_POLICY_URL ?? `https://${LINK_DOMAIN}/privacy`,
    features: {
      push: process.env.FEATURE_PUSH === '1',
    },
    eas: process.env.EAS_PROJECT_ID ? { projectId: process.env.EAS_PROJECT_ID } : undefined,
  },
});
