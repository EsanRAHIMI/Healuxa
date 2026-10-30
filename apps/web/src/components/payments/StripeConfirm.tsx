"use client";

import { loadStripe, type Stripe, type StripeElements } from "@stripe/stripe-js";
import { useEffect, useRef, useState } from "react";

import { buttonClass } from "@/components/ui/primitives";

/**
 * Stripe Payment Element (hosted fields): card data goes browser -> Stripe only. Confirmation here
 * is NOT proof of payment — payment-service updates status from verified webhooks / server-side
 * retrieval, and the page re-reads it after Stripe redirects back to `returnUrl`.
 */
export function StripeConfirm({
  publishableKey,
  clientSecret,
  returnUrl,
  locale,
  labels,
}: {
  publishableKey: string;
  clientSecret: string;
  returnUrl: string;
  locale: string;
  labels: { pay: string; processing: string; error: string; loading: string };
}) {
  const mount = useRef<HTMLDivElement>(null);
  const stripeRef = useRef<Stripe | null>(null);
  const elementsRef = useRef<StripeElements | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadStripe(publishableKey, { locale: (locale === "fa" ? "auto" : locale) as "auto" })
      .then((stripe) => {
        if (cancelled || !stripe || !mount.current) return;
        stripeRef.current = stripe;
        const css = getComputedStyle(document.documentElement);
        const elements = stripe.elements({
          clientSecret,
          appearance: {
            theme: "stripe",
            variables: {
              colorPrimary: css.getPropertyValue("--hx-color-primary").trim() || "#0D5962",
              colorText: css.getPropertyValue("--hx-color-text").trim() || "#1B2427",
              colorBackground: css.getPropertyValue("--hx-color-surface").trim() || "#FFFFFF",
              borderRadius: "10px",
            },
          },
        });
        elementsRef.current = elements;
        const element = elements.create("payment", { layout: "tabs" });
        element.on("ready", () => setReady(true));
        element.mount(mount.current);
      })
      .catch(() => setError(labels.error));
    return () => {
      cancelled = true;
    };
  }, [publishableKey, clientSecret, locale, labels.error]);

  const pay = async () => {
    const stripe = stripeRef.current;
    const elements = elementsRef.current;
    if (!stripe || !elements) return;
    setBusy(true);
    setError(null);
    const { error: confirmError } = await stripe.confirmPayment({ elements, confirmParams: { return_url: returnUrl } });
    // Only reached on immediate errors (validation, declined); success redirects to returnUrl.
    if (confirmError) setError(confirmError.message ?? labels.error);
    setBusy(false);
  };

  return (
    <div className="space-y-4">
      <div ref={mount} aria-busy={!ready} />
      {!ready && !error ? <p className="text-sm text-text-muted">{labels.loading}</p> : null}
      {error ? (
        <p role="alert" className="text-sm font-medium text-danger">
          {error}
        </p>
      ) : null}
      <button type="button" className={buttonClass("primary", "md")} onClick={pay} disabled={!ready || busy}>
        {busy ? labels.processing : labels.pay}
      </button>
    </div>
  );
}
