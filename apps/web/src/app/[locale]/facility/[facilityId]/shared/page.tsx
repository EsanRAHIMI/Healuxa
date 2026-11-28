import { SharedList } from "@/components/records/Shared";
import { resolveLocale } from "@/lib/i18n";

/** The workspace layout already 404s for non-staff; profile-service re-checks membership itself. */
export default async function FacilitySharedPage({ params }: { params: Promise<{ locale: string; facilityId: string }> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  return <SharedList locale={locale} granteeType="facility" granteeId={facilityId} basePath={`/${locale}/facility/${facilityId}/shared`} />;
}
