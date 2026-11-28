import { notFound } from "next/navigation";

import { SharedList } from "@/components/records/Shared";
import { getMyProvider } from "@/lib/portal";
import { resolveLocale } from "@/lib/i18n";

export default async function ProviderSharedPage({ params }: { params: Promise<{ locale: string }> }) {
  const locale = await resolveLocale(params);
  const mine = await getMyProvider();
  if (!mine) notFound();
  return <SharedList locale={locale} granteeType="provider" granteeId={mine.provider.id} basePath={`/${locale}/provider/shared`} />;
}
