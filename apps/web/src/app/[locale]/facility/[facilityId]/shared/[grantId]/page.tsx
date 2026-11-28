import { SharedDetail } from "@/components/records/Shared";
import { resolveLocale } from "@/lib/i18n";

export default async function FacilitySharedDetailPage({ params }: { params: Promise<{ locale: string; facilityId: string; grantId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId, grantId } = await params;
  return <SharedDetail locale={locale} grantId={grantId} backHref={`/${locale}/facility/${facilityId}/shared`} />;
}
