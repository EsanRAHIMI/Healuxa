import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router/js-tabs';
import type { ColorValue } from 'react-native';

import { useI18n } from '@/i18n';
import { useTheme } from '@/theme';

type IconName = keyof typeof Ionicons.glyphMap;

export default function TabsLayout() {
  const { t } = useI18n();
  const theme = useTheme();
  const icon = (name: IconName) =>
    function TabIcon({ color, size }: { color: ColorValue; size: number }) {
      return <Ionicons name={name} color={color} size={size} />;
    };
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.color.accent,
        tabBarInactiveTintColor: theme.color.textMuted,
        tabBarStyle: { backgroundColor: theme.color.surface, borderTopColor: theme.color.border },
        headerStyle: { backgroundColor: theme.color.surface },
        headerTintColor: theme.color.text,
        tabBarAllowFontScaling: true,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: t('tabs.home'), tabBarIcon: icon('home-outline'), tabBarButtonTestID: 'tab-home' }}
      />
      <Tabs.Screen
        name="directory"
        options={{ title: t('tabs.directory'), tabBarIcon: icon('search-outline'), tabBarButtonTestID: 'tab-directory' }}
      />
      <Tabs.Screen
        name="bookings"
        options={{ title: t('tabs.bookings'), tabBarIcon: icon('calendar-outline'), tabBarButtonTestID: 'tab-bookings' }}
      />
      <Tabs.Screen
        name="concierge"
        options={{ title: t('tabs.concierge'), tabBarIcon: icon('chatbubbles-outline'), tabBarButtonTestID: 'tab-concierge' }}
      />
      <Tabs.Screen
        name="account"
        options={{ title: t('tabs.account'), tabBarIcon: icon('person-circle-outline'), tabBarButtonTestID: 'tab-account' }}
      />
    </Tabs>
  );
}
