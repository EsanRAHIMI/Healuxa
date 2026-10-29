import { ApiError } from '../api/errors';
import type { MessageKey } from '../i18n';

export interface CredentialErrors {
  identifier?: MessageKey;
  password?: MessageKey;
  form?: MessageKey;
}

/** Mirrors identity-service RegisterRequest: identifier 3..320 chars, password >= 8. */
export function validateCredentials(identifier: string, password: string, mode: 'signIn' | 'register'): CredentialErrors {
  const errors: CredentialErrors = {};
  const id = identifier.trim();
  if (id.length < 3 || id.length > 320) errors.identifier = 'auth.identifierRequired';
  if (mode === 'register' ? password.length < 8 : password.length === 0) errors.password = 'auth.passwordTooShort';
  return errors;
}

export function authErrorKey(e: unknown, mode: 'signIn' | 'register'): CredentialErrors {
  if (!(e instanceof ApiError)) return { form: 'error.generic' };
  if (e.status === 401) return { form: 'auth.invalidCredentials' };
  if (e.status === 409) return { identifier: 'auth.alreadyRegistered' };
  if (e.status === 429) return { form: 'error.rateLimited' };
  if (e.status === 422) {
    const fields = e.fieldErrors.map((f) => f.field);
    if (fields.some((f) => f.includes('password'))) return { password: 'auth.passwordTooShort' };
    if (fields.some((f) => f.includes('identifier'))) return { identifier: 'auth.identifierRequired' };
    return { form: mode === 'signIn' ? 'auth.invalidCredentials' : 'error.generic' };
  }
  if (e.code === 'network_error') return { form: 'error.network' };
  if (e.code === 'timeout') return { form: 'error.timeout' };
  if (e.status >= 500) return { form: 'error.server' };
  return { form: 'error.generic' };
}
