import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, type TextInput } from 'react-native';

import { authErrorKey, type CredentialErrors, validateCredentials } from '../auth/validation';
import { config } from '../config';
import { useI18n } from '../i18n';
import { useTheme } from '../theme';
import { AppText, Button, Card, Screen, TextField } from './primitives';

export function CredentialsForm({
  mode,
  onSubmit,
  onSwitch,
}: {
  mode: 'signIn' | 'register';
  onSubmit: (identifier: string, password: string) => Promise<void>;
  onSwitch: () => void;
}) {
  const { t } = useI18n();
  const theme = useTheme();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<CredentialErrors>({});
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<TextInput>(null);
  const prefix = mode === 'signIn' ? 'sign-in' : 'register';

  const submit = async () => {
    const local = validateCredentials(identifier, password, mode);
    setErrors(local);
    if (local.identifier || local.password) return;
    setBusy(true);
    try {
      await onSubmit(identifier, password);
    } catch (e) {
      setErrors(authErrorKey(e, mode));
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen testID={`${prefix}-screen`}>
        <TextField
          label={t('auth.identifier')}
          value={identifier}
          onChangeText={setIdentifier}
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete={mode === 'signIn' ? 'username' : 'email'}
          textContentType={mode === 'signIn' ? 'username' : 'emailAddress'}
          keyboardType="email-address"
          returnKeyType="next"
          onSubmitEditing={() => passwordRef.current?.focus()}
          error={errors.identifier ? t(errors.identifier) : undefined}
          testID={`${prefix}-identifier`}
        />
        <TextField
          ref={passwordRef}
          label={t('auth.password')}
          hint={mode === 'register' ? t('auth.passwordHint') : undefined}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          secureToggle
          autoCapitalize="none"
          autoComplete={mode === 'signIn' ? 'current-password' : 'new-password'}
          textContentType={mode === 'signIn' ? 'password' : 'newPassword'}
          returnKeyType="go"
          onSubmitEditing={submit}
          error={errors.password ? t(errors.password) : undefined}
          testID={`${prefix}-password`}
        />
        {errors.form ? (
          <Card accessibilityRole="alert" testID={`${prefix}-form-error`} style={{ borderColor: theme.color.danger }}>
            <AppText style={{ color: theme.color.danger }}>{t(errors.form)}</AppText>
          </Card>
        ) : null}
        {mode === 'register' ? (
          <AppText variant="small" muted>
            {t('auth.consent')}{' '}
            <AppText variant="small" style={{ color: theme.color.accent }} accessibilityRole="link" onPress={() => Linking.openURL(config.privacyPolicyUrl)}>
              {t('auth.privacyPolicy')}
            </AppText>
          </AppText>
        ) : null}
        <Button
          label={mode === 'signIn' ? t('auth.signInCta') : t('auth.registerCta')}
          onPress={submit}
          busy={busy}
          testID={`${prefix}-submit`}
        />
        <Button kind="link" label={mode === 'signIn' ? t('auth.noAccount') : t('auth.haveAccount')} onPress={onSwitch} testID={`${prefix}-switch`} />
      </Screen>
    </KeyboardAvoidingView>
  );
}
