import { randomUUID } from 'expo-crypto';
import { useRouter } from 'expo-router';
import { useRef } from 'react';

import { useAuth } from '@/auth/AuthProvider';
import { useI18n } from '@/i18n';
import { usePrefs } from '@/prefs';
import { CredentialsForm } from '@/ui/CredentialsForm';

/** Register. Uses identity: authRegister (with Idempotency-Key so retries never double-create). */
export default function Register() {
  const auth = useAuth();
  const router = useRouter();
  const { language } = useI18n();
  const { update } = usePrefs();
  // One key per form attempt: a retry after a timeout replays instead of creating a second account.
  const key = useRef<{ id: string; forIdentifier: string } | null>(null);
  return (
    <CredentialsForm
      mode="register"
      onSubmit={async (identifier, password) => {
        if (!key.current || key.current.forIdentifier !== identifier) key.current = { id: randomUUID(), forIdentifier: identifier };
        await auth.register(identifier, password, language, key.current.id);
        await update({ welcomeSeen: true });
        router.dismissTo('/account');
      }}
      onSwitch={() => router.replace('/sign-in')}
    />
  );
}
