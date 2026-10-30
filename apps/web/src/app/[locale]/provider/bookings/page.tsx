import { redirect } from "next/navigation";

import { PracticeCalendar } from "@/components/booking/PracticeCalendar";
import { PageHeader } from "@/components/ui/primitives";
import { getT, resolveLocale } from "@/lib/i18n";
import { getMyProvider } from "@/lib/portal";

export default async function ProviderBookings({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const locale = await resolveLocale(params);
  const t = getT(locale);
  const mine = await getMyProvider();
  if (!mine) redirect(`/${locale}/provider`);
  return (
    <>
      <PageHeader title={t("bookings.calendar")} lead={t("bookings.providerLead")} />
      <PracticeCalendar scope={{ provider_id: mine.provider.id }} locale={locale} basePath={`/${locale}/provider/bookings`} from={(await searchParams).from} />
    </>
  );
}
