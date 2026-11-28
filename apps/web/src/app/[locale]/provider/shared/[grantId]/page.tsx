import { SharedDetail } from "@/components/records/Shared";
import { resolveLocale } from "@/lib/i18n";

export default async function ProviderSharedDetailPage({ params }: { params: Promise<{ locale: string; grantId: string }> }) {
  const locale = await resolveLocale(params);
  const { grantId } = await params;
  return <SharedDetail locale={locale} grantId={grantId} backHref={`/${locale}/provider/shared`} />;
}
