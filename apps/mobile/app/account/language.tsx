import { Ionicons } from '@expo/vector-icons';
import { Pressable } from 'react-native';

import { LANGUAGES, useI18n } from '@/i18n';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Screen } from '@/ui/primitives';

export default function LanguageScreen() {
  const { t, language, setLanguage, restartRequired, restart } = useI18n();
  const theme = useTheme();
  return (
    <Screen testID="language-screen">
      <Card accessibilityRole="radiogroup">
        {LANGUAGES.map((l) => {
          const selected = l.code === language;
          return (
            <Pressable
              key={l.code}
              testID={`language-${l.code}`}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected }}
              accessibilityLabel={l.nativeName}
              accessibilityLanguage={l.code}
              onPress={() => setLanguage(l.code)}
              style={{ flexDirection: 'row', alignItems: 'center', minHeight: 52, gap: theme.space(3) }}
            >
              <AppText style={{ flex: 1 }}>{l.nativeName}</AppText>
              {selected ? <Ionicons name="checkmark" size={20} color={theme.color.accent} /> : null}
            </Pressable>
          );
        })}
      </Card>
      {restartRequired ? (
        <Card testID="language-restart">
          <AppText>{t('language.restart')}</AppText>
          <Button label={t('language.restartNow')} onPress={restart} testID="language-restart-now" />
        </Card>
      ) : null}
    </Screen>
  );
}
