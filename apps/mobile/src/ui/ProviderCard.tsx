import { useRouter } from 'expo-router';

import type { Provider } from '../api/types';
import { useI18n } from '../i18n';
import { languageName, providerTypeLabel } from '../i18n/labels';
import { AppText, Badge, PressableCard, Row } from './primitives';

export function ProviderCard({ provider }: { provider: Provider }) {
  const router = useRouter();
  const { t, language } = useI18n();
  const verified = provider.verification_status === 'verified';
  const langs = provider.languages.map((l) => languageName(l, language)).join(' · ');
  const summary = [provider.title ?? providerTypeLabel(provider.type, language), provider.specialties.join(', ')]
    .filter(Boolean)
    .join(' — ');
  return (
    <PressableCard
      testID={`provider-card-${provider.id}`}
      onPress={() => router.push({ pathname: '/providers/[id]', params: { id: provider.id } })}
      accessibilityLabel={[provider.display_name, summary, verified ? t('common.verified') : '', langs].filter(Boolean).join(', ')}
    >
      <Row>
        <AppText variant="label" style={{ flexShrink: 1 }}>
          {provider.display_name}
        </AppText>
        {verified ? <Badge label={t('common.verified')} icon="shield-checkmark" /> : null}
      </Row>
      <AppText variant="small" muted numberOfLines={2}>
        {summary}
      </AppText>
      <AppText variant="caption" muted>
        {langs}
      </AppText>
    </PressableCard>
  );
}
