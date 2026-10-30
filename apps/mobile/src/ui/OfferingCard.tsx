import { useRouter } from 'expo-router';

import type { ServiceOffering } from '../api/types';
import { useI18n } from '../i18n';
import { localized } from '../i18n/labels';
import { FeeBreakdownView } from './FeeBreakdownView';
import { AppText, Button, Card, Row } from './primitives';

export function OfferingCard({ offering, showProviderLink }: { offering: ServiceOffering; showProviderLink?: boolean }) {
  const { t, language } = useI18n();
  const router = useRouter();
  const description = localized(offering.description, language);
  return (
    <Card testID={`offering-${offering.id}`}>
      <Row style={{ justifyContent: 'space-between' }}>
        <AppText variant="label" style={{ flexShrink: 1 }}>
          {offering.name}
        </AppText>
        <AppText variant="caption" muted>
          {t('common.minutes', { n: offering.duration_minutes })}
        </AppText>
      </Row>
      <AppText variant="caption" muted>
        {offering.category}
      </AppText>
      {description ? <AppText variant="small">{description}</AppText> : null}
      <FeeBreakdownView offering={offering} testID={`fees-${offering.id}`} />
      {offering.status === 'active' ? (
        <Button
          label={t('book.cta')}
          icon="calendar-outline"
          onPress={() => router.push({ pathname: '/book/[serviceId]', params: { serviceId: offering.id } })}
          testID={`book-${offering.id}`}
        />
      ) : null}
      {showProviderLink ? (
        <Button
          kind="link"
          label={t('services.byProvider')}
          onPress={() => router.push({ pathname: '/providers/[id]', params: { id: offering.provider_id } })}
        />
      ) : null}
    </Card>
  );
}
