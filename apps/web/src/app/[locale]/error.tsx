"use client";

import { useParams } from "next/navigation";

// Client boundary: keeps a tiny inline dictionary instead of shipping catalogs to the browser.
const COPY: Record<string, { title: string; body: string; retry: string }> = {
  en: { title: "Something went wrong", body: "We couldn’t load this page. Please try again.", retry: "Try again" },
  ar: { title: "حدث خطأ ما", body: "تعذّر تحميل هذه الصفحة. يرجى المحاولة مرة أخرى.", retry: "حاول مرة أخرى" },
  fa: { title: "مشکلی پیش آمد", body: "بارگذاری این صفحه ممکن نشد. لطفاً دوباره تلاش کنید.", retry: "تلاش دوباره" },
};

export default function ErrorBoundary({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const params = useParams<{ locale: string }>();
  const copy = COPY[params?.locale ?? "en"] ?? COPY.en!;
  return (
    <div className="hx-container py-20 text-center" role="alert">
      <h1 className="text-3xl">{copy.title}</h1>
      <p className="mx-auto mt-3 max-w-prose text-text-muted">{copy.body}</p>
      {error.digest ? <p className="mt-2 text-xs text-text-muted hx-ltr-nums">{error.digest}</p> : null}
      <button type="button" onClick={reset} className="mt-8 inline-flex min-h-11 items-center rounded-md bg-primary px-4 text-on-primary">
        {copy.retry}
      </button>
    </div>
  );
}
