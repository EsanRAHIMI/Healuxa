import { PracticeCalendar } from "@/components/booking/PracticeCalendar";
import { resolveLocale } from "@/lib/i18n";

export default async function FacilityBookings({ params, searchParams }: { params: Promise<{ locale: string; facilityId: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const { facilityId } = await params;
  return <PracticeCalendar scope={{ facility_id: facilityId }} locale={locale} basePath={`/${locale}/facility/${facilityId}/bookings`} from={(await searchParams).from} />;
}
