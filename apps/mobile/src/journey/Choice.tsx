import { Ionicons } from '@expo/vector-icons';
import { Pressable, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from '../ui/primitives';

/**
 * A selectable option announced as a checkbox (multi-select) or radio (single-select). The selected
 * state is carried by an icon and a border as well as colour, so it does not rely on colour alone.
 */
export function Choice({
  label,
  selected,
  onPress,
  role,
  disabled,
  badge,
  accessibilityHint,
  testID,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  role: 'checkbox' | 'radio';
  disabled?: boolean;
  /** short marker shown instead of the tick when selected, e.g. the priority number */
  badge?: string;
  accessibilityHint?: string;
  testID?: string;
}) {
  const theme = useTheme();
  const color = selected ? theme.color.accent : theme.color.textMuted;
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole={role}
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ checked: selected, disabled: Boolean(disabled) }}
      style={({ pressed }) => ({
        minHeight: 48,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space(3),
        paddingHorizontal: theme.space(4),
        paddingVertical: theme.space(2),
        borderRadius: theme.radius.md,
        borderWidth: selected ? 2 : 1,
        borderColor: selected ? theme.color.accent : theme.color.border,
        backgroundColor: selected ? theme.color.surfaceAlt : theme.color.surface,
        opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
      })}
    >
      {selected && badge ? (
        <View
          style={{ width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.color.accent }}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
        >
          <AppText variant="caption" style={{ color: theme.color.onAccent, fontWeight: '700' }}>
            {badge}
          </AppText>
        </View>
      ) : (
        <Ionicons
          name={selected ? 'checkmark-circle' : role === 'radio' ? 'radio-button-off' : 'ellipse-outline'}
          size={22}
          color={color}
          accessibilityElementsHidden
          importantForAccessibility="no"
        />
      )}
      <AppText style={{ flex: 1, fontWeight: selected ? '600' : '400' }}>{label}</AppText>
    </Pressable>
  );
}
