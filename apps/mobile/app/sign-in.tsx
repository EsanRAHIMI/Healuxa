import { useRouter } from 'expo-router';

import { useAuth } from '@/auth/AuthProvider';
import { usePrefs } from '@/prefs';
import { CredentialsForm } from '@/ui/CredentialsForm';

/** Sign in. Uses identity: authLogin. */
export default function SignIn() {
  const auth = useAuth();
  const router = useRouter();
  const { update } = usePrefs();
  return (
    <CredentialsForm
      mode="signIn"
      onSubmit={async (identifier, password) => {
        await auth.signIn(identifier, password);
        await update({ welcomeSeen: true });
        router.dismissTo('/account');
      }}
      onSwitch={() => router.replace('/register')}
    />
  );
}
