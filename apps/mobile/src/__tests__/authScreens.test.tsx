import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ApiError } from '../api/errors';
import { en } from '../i18n/en';
import { I18nProvider } from '../i18n';
import { CredentialsForm } from '../ui/CredentialsForm';
import { ErrorState } from '../ui/primitives';

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
const wrap = (ui: ReactNode) => (
  <SafeAreaProvider initialMetrics={metrics}>
    <I18nProvider initialLanguage="en">{ui}</I18nProvider>
  </SafeAreaProvider>
);

describe('auth screens', () => {
  it('validates input before calling the backend', async () => {
    const onSubmit = jest.fn();
    await render(wrap(<CredentialsForm mode="register" onSubmit={onSubmit} onSwitch={jest.fn()} />));
    await fireEvent.changeText(screen.getByTestId('register-identifier'), 'a@example.test');
    await fireEvent.changeText(screen.getByTestId('register-password'), 'short');
    await fireEvent.press(screen.getByTestId('register-submit'));
    expect(await screen.findByText(en['auth.passwordTooShort'])).toBeTruthy();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits trimmed credentials on sign in', async () => {
    const onSubmit = jest.fn(async () => undefined);
    await render(wrap(<CredentialsForm mode="signIn" onSubmit={onSubmit} onSwitch={jest.fn()} />));
    await fireEvent.changeText(screen.getByTestId('sign-in-identifier'), 'a@example.test');
    await fireEvent.changeText(screen.getByTestId('sign-in-password'), 'whatever');
    await fireEvent.press(screen.getByTestId('sign-in-submit'));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith('a@example.test', 'whatever'));
  });

  it('shows invalid credentials for a 401 without leaking server text', async () => {
    const onSubmit = jest.fn(async () => {
      throw new ApiError({ status: 401, code: 'unauthorized', detail: 'Invalid credentials' });
    });
    await render(wrap(<CredentialsForm mode="signIn" onSubmit={onSubmit} onSwitch={jest.fn()} />));
    await fireEvent.changeText(screen.getByTestId('sign-in-identifier'), 'a@example.test');
    await fireEvent.changeText(screen.getByTestId('sign-in-password'), 'wrong-password');
    await fireEvent.press(screen.getByTestId('sign-in-submit'));
    expect(await screen.findByText(en['auth.invalidCredentials'])).toBeTruthy();
  });

  it('shows the already-registered message for a 409', async () => {
    const onSubmit = jest.fn(async () => {
      throw new ApiError({ status: 409, code: 'conflict' });
    });
    await render(wrap(<CredentialsForm mode="register" onSubmit={onSubmit} onSwitch={jest.fn()} />));
    await fireEvent.changeText(screen.getByTestId('register-identifier'), 'taken@example.test');
    await fireEvent.changeText(screen.getByTestId('register-password'), 'long-enough-1');
    await fireEvent.press(screen.getByTestId('register-submit'));
    expect(await screen.findByText(en['auth.alreadyRegistered'])).toBeTruthy();
  });

  it('shows the lockout message for a 429', async () => {
    const onSubmit = jest.fn(async () => {
      throw new ApiError({ status: 429, code: 'rate_limited' });
    });
    await render(wrap(<CredentialsForm mode="signIn" onSubmit={onSubmit} onSwitch={jest.fn()} />));
    await fireEvent.changeText(screen.getByTestId('sign-in-identifier'), 'a@example.test');
    await fireEvent.changeText(screen.getByTestId('sign-in-password'), 'x');
    await fireEvent.press(screen.getByTestId('sign-in-submit'));
    expect(await screen.findByText(en['error.rateLimited'])).toBeTruthy();
  });

  it('shows the network error with a retry action', async () => {
    const retry = jest.fn();
    await render(wrap(<ErrorState error={new ApiError({ status: 0, code: 'network_error' })} onRetry={retry} />));
    expect(screen.getByText(en['error.network'])).toBeTruthy();
    await fireEvent.press(screen.getByTestId('error-state-retry'));
    expect(retry).toHaveBeenCalled();
  });

  it('shows a generic server message and the trace id for 5xx', async () => {
    await render(wrap(<ErrorState error={new ApiError({ status: 500, code: 'internal_error', detail: 'Traceback…', traceId: 'abc123' })} />));
    expect(screen.getByText(en['error.server'])).toBeTruthy();
    expect(screen.getByText('Reference: abc123')).toBeTruthy();
    expect(screen.queryByText(/Traceback/)).toBeNull();
  });
});
