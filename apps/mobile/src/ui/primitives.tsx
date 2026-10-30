import { Ionicons } from '@expo/vector-icons';
import { forwardRef, type ReactNode, useState } from 'react';
import {
  ActivityIndicator,
  I18nManager,
  Pressable,
  type PressableProps,
  RefreshControl,
  ScrollView,
  type ScrollViewProps,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  type TextProps,
  View,
  type ViewProps,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { ApiError } from '../api/errors';
import { errorKey } from '../hooks/useRemote';
import { useI18n } from '../i18n';
import { type Theme, useTheme } from '../theme';

/** Cap Dynamic Type growth where layouts would otherwise break; still allows 2x. */
const MAX_SCALE = 2;

type Variant = 'title' | 'heading' | 'body' | 'small' | 'caption' | 'label';

export function AppText({ variant = 'body', muted, style, ...rest }: TextProps & { variant?: Variant; muted?: boolean }) {
  const theme = useTheme();
  const size: Record<Variant, number> = {
    title: theme.font.title,
    heading: theme.font.heading,
    body: theme.font.body,
    small: theme.font.small,
    caption: theme.font.caption,
    label: theme.font.small,
  };
  return (
    <Text
      maxFontSizeMultiplier={MAX_SCALE}
      accessibilityRole={variant === 'title' || variant === 'heading' ? 'header' : undefined}
      style={[
        {
          color: muted ? theme.color.textMuted : theme.color.text,
          fontSize: size[variant],
          lineHeight: Math.round(size[variant] * 1.4),
          fontWeight: variant === 'title' ? '700' : variant === 'heading' || variant === 'label' ? '600' : '400',
          textAlign: 'auto',
          writingDirection: I18nManager.isRTL ? 'rtl' : 'ltr',
        },
        style,
      ]}
      {...rest}
    />
  );
}

export function Screen({
  children,
  scroll = true,
  onRefresh,
  refreshing = false,
  edges = ['bottom'],
  testID,
  ...rest
}: ScrollViewProps & {
  children: ReactNode;
  scroll?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  edges?: ('top' | 'bottom')[];
}) {
  const theme = useTheme();
  const content = scroll ? (
    <ScrollView
      testID={testID}
      contentContainerStyle={{ padding: theme.space(5), gap: theme.space(4) }}
      keyboardShouldPersistTaps="handled"
      contentInsetAdjustmentBehavior="automatic"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.color.accent} /> : undefined}
      {...rest}
    >
      {children}
    </ScrollView>
  ) : (
    <View testID={testID} style={{ flex: 1, padding: theme.space(5), gap: theme.space(4) }}>
      {children}
    </View>
  );
  return <SafeAreaView edges={edges} style={{ flex: 1, backgroundColor: theme.color.background }}>{content}</SafeAreaView>;
}

export function Button({
  label,
  onPress,
  kind = 'primary',
  disabled,
  busy,
  accessibilityHint,
  testID,
  icon,
}: {
  label: string;
  onPress: PressableProps['onPress'];
  kind?: 'primary' | 'secondary' | 'danger' | 'link';
  disabled?: boolean;
  busy?: boolean;
  accessibilityHint?: string;
  testID?: string;
  icon?: keyof typeof Ionicons.glyphMap;
}) {
  const theme = useTheme();
  const fg =
    kind === 'primary' ? theme.color.onAccent : kind === 'danger' ? theme.color.danger : theme.color.accent;
  return (
    <Pressable
      testID={testID}
      accessibilityRole={kind === 'link' ? 'link' : 'button'}
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: Boolean(disabled || busy), busy: Boolean(busy) }}
      disabled={disabled || busy}
      onPress={onPress}
      style={({ pressed }) => [
        {
          minHeight: 48,
          borderRadius: theme.radius.md,
          paddingHorizontal: theme.space(5),
          paddingVertical: theme.space(3),
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: theme.space(2),
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
        },
        kind === 'primary' && { backgroundColor: theme.color.accent },
        (kind === 'secondary' || kind === 'danger') && {
          borderWidth: StyleSheet.hairlineWidth * 2,
          borderColor: kind === 'danger' ? theme.color.danger : theme.color.accent,
        },
        kind === 'link' && { minHeight: 44, paddingHorizontal: theme.space(1) },
      ]}
    >
      {busy ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={18} color={fg} /> : null}
      <AppText variant="label" style={{ color: fg, fontSize: theme.font.body }}>
        {label}
      </AppText>
    </Pressable>
  );
}

export const TextField = forwardRef<
  TextInput,
  TextInputProps & { label: string; error?: string; hint?: string; secureToggle?: boolean }
>(function TextField({ label, error, hint, secureToggle, secureTextEntry, testID, ...rest }, ref) {
  const theme = useTheme();
  const { t } = useI18n();
  const [hidden, setHidden] = useState(Boolean(secureTextEntry));
  return (
    <View style={{ gap: theme.space(1) }}>
      <AppText variant="label">{label}</AppText>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          borderWidth: 1,
          borderColor: error ? theme.color.danger : theme.color.border,
          borderRadius: theme.radius.md,
          backgroundColor: theme.color.surface,
        }}
      >
        <TextInput
          ref={ref}
          testID={testID}
          accessibilityLabel={label}
          accessibilityHint={hint}
          placeholderTextColor={theme.color.textMuted}
          maxFontSizeMultiplier={MAX_SCALE}
          secureTextEntry={hidden}
          style={{
            flex: 1,
            minHeight: 48,
            paddingHorizontal: theme.space(4),
            color: theme.color.text,
            fontSize: theme.font.body,
            textAlign: I18nManager.isRTL ? 'right' : 'left',
          }}
          {...rest}
        />
        {secureToggle ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={hidden ? t('auth.showPassword') : t('auth.hidePassword')}
            onPress={() => setHidden((h) => !h)}
            hitSlop={8}
            style={{ paddingHorizontal: theme.space(3), minHeight: 44, justifyContent: 'center' }}
          >
            <Ionicons name={hidden ? 'eye-outline' : 'eye-off-outline'} size={20} color={theme.color.textMuted} />
          </Pressable>
        ) : null}
      </View>
      {error ? (
        <AppText variant="small" style={{ color: theme.color.danger }} accessibilityLiveRegion="polite" testID={testID ? `${testID}-error` : undefined}>
          {error}
        </AppText>
      ) : hint ? (
        <AppText variant="small" muted>
          {hint}
        </AppText>
      ) : null}
    </View>
  );
});

export function Card({ children, style, ...rest }: ViewProps & { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: theme.color.surface,
          borderRadius: theme.radius.lg,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: theme.color.border,
          padding: theme.space(4),
          gap: theme.space(2),
        },
        style,
      ]}
      {...rest}
    >
      {children}
    </View>
  );
}

export function PressableCard({
  children,
  onPress,
  accessibilityLabel,
  accessibilityHint,
  testID,
}: {
  children: ReactNode;
  onPress: () => void;
  accessibilityLabel: string;
  accessibilityHint?: string;
  testID?: string;
}) {
  const theme = useTheme();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}
    >
      <Card style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space(3) }}>
        <View style={{ flex: 1, gap: theme.space(1) }}>{children}</View>
        <Chevron />
      </Card>
    </Pressable>
  );
}

export function Chevron() {
  const theme = useTheme();
  return (
    <Ionicons
      name={I18nManager.isRTL ? 'chevron-back' : 'chevron-forward'}
      size={18}
      color={theme.color.textMuted}
      accessibilityElementsHidden
      importantForAccessibility="no"
    />
  );
}

export function Chip({
  label,
  selected,
  onPress,
  testID,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  testID?: string;
}) {
  const theme = useTheme();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : 'text'}
      accessibilityState={onPress ? { selected: Boolean(selected) } : undefined}
      accessibilityLabel={label}
      style={{
        minHeight: onPress ? 36 : 28,
        paddingHorizontal: theme.space(3),
        borderRadius: theme.radius.pill,
        justifyContent: 'center',
        backgroundColor: selected ? theme.color.accent : theme.color.surfaceAlt,
      }}
    >
      <AppText variant="small" style={{ color: selected ? theme.color.onAccent : theme.color.text }}>
        {label}
      </AppText>
    </Pressable>
  );
}

export function Badge({ label, tone = 'success', icon }: { label: string; tone?: 'success' | 'neutral'; icon?: keyof typeof Ionicons.glyphMap }) {
  const theme = useTheme();
  const color = tone === 'success' ? theme.color.success : theme.color.textMuted;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space(1) }} accessible accessibilityLabel={label}>
      {icon ? <Ionicons name={icon} size={14} color={color} /> : null}
      <AppText variant="caption" style={{ color, fontWeight: '600' }}>
        {label}
      </AppText>
    </View>
  );
}

export function Section({ title, children, testID }: { title: string; children: ReactNode; testID?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.space(2) }} testID={testID}>
      <AppText variant="heading">{title}</AppText>
      {children}
    </View>
  );
}

export function Loading({ label }: { label?: string }) {
  const theme = useTheme();
  const { t } = useI18n();
  return (
    <View style={{ padding: theme.space(8), alignItems: 'center', gap: theme.space(2) }} accessible accessibilityLabel={label ?? t('common.loading')} accessibilityRole="progressbar">
      <ActivityIndicator color={theme.color.accent} />
    </View>
  );
}

export function ErrorState({ error, onRetry, testID = 'error-state' }: { error: ApiError; onRetry?: () => void; testID?: string }) {
  const theme = useTheme();
  const { t } = useI18n();
  return (
    <Card testID={testID} accessibilityRole="alert" style={{ alignItems: 'center', paddingVertical: theme.space(6) }}>
      <Ionicons name={error.isNetwork ? 'cloud-offline-outline' : 'alert-circle-outline'} size={28} color={theme.color.danger} />
      <AppText style={{ textAlign: 'center' }}>{t(errorKey(error))}</AppText>
      {error.traceId ? (
        <AppText variant="caption" muted selectable>
          {t('error.traceId', { id: error.traceId })}
        </AppText>
      ) : null}
      {onRetry ? <Button kind="secondary" label={t('common.retry')} onPress={onRetry} testID={`${testID}-retry`} /> : null}
    </Card>
  );
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  const theme = useTheme();
  return (
    <Card style={{ alignItems: 'center', paddingVertical: theme.space(6) }}>
      <AppText muted style={{ textAlign: 'center' }}>
        {message}
      </AppText>
      {action}
    </Card>
  );
}

export function OfflineBanner({ storedAt }: { storedAt?: number }) {
  const theme = useTheme();
  const { t, language } = useI18n();
  const time = storedAt ? new Date(storedAt).toLocaleString(language) : '';
  return (
    <View
      accessibilityRole="alert"
      testID="offline-banner"
      style={{ flexDirection: 'row', gap: theme.space(2), padding: theme.space(3), borderRadius: theme.radius.md, backgroundColor: theme.color.surfaceAlt }}
    >
      <Ionicons name="cloud-offline-outline" size={18} color={theme.color.textMuted} />
      <AppText variant="small" style={{ flex: 1 }}>
        {t('common.offlineCached', { time })}
      </AppText>
    </View>
  );
}

export function Row({ children, style }: ViewProps & { children: ReactNode }) {
  const theme = useTheme();
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap: theme.space(2), flexWrap: 'wrap' }, style]}>{children}</View>;
}

export type { Theme };
