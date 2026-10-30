import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { type ReactNode, useEffect, useState } from 'react';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider, useAuth } from '@/auth/AuthProvider';
import { applyDirection, deviceLanguage, I18nProvider, type Language, useI18n } from '@/i18n';
import { loadPrefs, type Prefs, PrefsProvider, usePrefs } from '@/prefs';
import { biometrics, createServices, ServicesProvider } from '@/services';
import { useTheme } from '@/theme';
import { LockScreen } from '@/ui/LockScreen';

SplashScreen.preventAutoHideAsync().catch(() => undefined);

const services = createServices();

export default function RootLayout() {
  const [prefs, setPrefs] = useState<Prefs | null>(null);

  useEffect(() => {
    loadPrefs(services.prefs).then((p) => {
      applyDirection(p.language ?? deviceLanguage());
      setPrefs(p);
    });
  }, []);

  if (!prefs) return null;
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ServicesProvider services={services}>
          <PrefsProvider initial={prefs} store={services.prefs}>
            <LanguageRoot initial={prefs.language ?? deviceLanguage()}>
              <AuthProvider manager={services.session} tokenStore={services.tokenStore} biometrics={biometrics}>
                <Navigation />
              </AuthProvider>
            </LanguageRoot>
          </PrefsProvider>
        </ServicesProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

function LanguageRoot({ initial, children }: { initial: Language; children: ReactNode }) {
  const { update } = usePrefs();
  return (
    <I18nProvider initialLanguage={initial} onPersist={(language) => update({ language })}>
      {children}
    </I18nProvider>
  );
}

function Navigation() {
  const theme = useTheme();
  const { t } = useI18n();
  const auth = useAuth();

  useEffect(() => {
    if (auth.status !== 'booting') SplashScreen.hideAsync().catch(() => undefined);
  }, [auth.status]);

  const navTheme = theme.dark ? DarkTheme : DefaultTheme;
  return (
    <ThemeProvider
      value={{
        ...navTheme,
        colors: {
          ...navTheme.colors,
          primary: theme.color.accent,
          background: theme.color.background,
          card: theme.color.surface,
          text: theme.color.text,
          border: theme.color.border,
        },
      }}
    >
      <StatusBar style={theme.dark ? 'light' : 'dark'} />
      {auth.status === 'booting' ? null : auth.status === 'locked' ? (
        <LockScreen />
      ) : (
        <Stack screenOptions={{ headerBackButtonDisplayMode: 'minimal', headerTintColor: theme.color.accent }}>
          <Stack.Screen name="(tabs)" options={{ headerShown: false, title: t('tabs.home') }} />
          <Stack.Screen name="welcome" options={{ headerShown: false, gestureEnabled: false }} />
          <Stack.Screen name="sign-in" options={{ presentation: 'modal', title: t('auth.signInTitle') }} />
          <Stack.Screen name="register" options={{ presentation: 'modal', title: t('auth.registerTitle') }} />
          <Stack.Screen name="providers/[id]" options={{ title: '' }} />
          <Stack.Screen name="facilities/[id]" options={{ title: '' }} />
          <Stack.Screen name="account/sessions" options={{ title: t('sessions.title') }} />
          <Stack.Screen name="account/language" options={{ title: t('language.title') }} />
          <Stack.Screen name="account/security" options={{ title: t('security.title') }} />
          <Stack.Screen name="account/notifications" options={{ title: t('prefs.title') }} />
          <Stack.Screen name="account/delete" options={{ title: t('delete.title') }} />
          <Stack.Screen name="services" options={{ title: t('services.title') }} />
          <Stack.Screen name="book/[serviceId]" options={{ title: t('book.title') }} />
          <Stack.Screen name="appointments/[id]" options={{ title: '' }} />
          <Stack.Screen name="concierge/new" options={{ presentation: 'modal', title: t('concierge.new') }} />
          <Stack.Screen name="concierge/[id]" options={{ title: '' }} />
          <Stack.Screen name="notifications" options={{ title: t('inbox.title') }} />
        </Stack>
      )}
    </ThemeProvider>
  );
}
