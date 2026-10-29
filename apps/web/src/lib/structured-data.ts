/**
 * schema.org builders. Emitted ONLY for data provider-service has verified (public reads already
 * return verified + active records; we re-check here so a future private view can never leak).
 * No ratings, outcomes or claims are included — the platform has no verified source for them.
 */
import type { Branch, Facility, OperatingHours, Provider } from "@healuxa/api-client";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const isPublic = (x: { status: string; verification_status: string }) => x.status === "active" && x.verification_status === "verified";

export function providerStructuredData(provider: Provider, url: string, languageNames: string[]): Record<string, unknown> | null {
  if (!isPublic(provider)) return null;
  const type = provider.type === "doctor" ? "Physician" : provider.type === "clinic" ? "MedicalClinic" : null;
  if (!type) return null;
  return {
    "@context": "https://schema.org",
    "@type": type,
    "@id": url,
    url,
    name: provider.display_name,
    ...(provider.title ? { jobTitle: provider.title } : {}),
    ...(provider.specialties.length ? { medicalSpecialty: provider.specialties } : {}),
    ...(languageNames.length ? { knowsLanguage: languageNames } : {}),
    ...(provider.verified_credentials?.length
      ? {
          hasCredential: provider.verified_credentials.map((c) => ({
            "@type": "EducationalOccupationalCredential",
            credentialCategory: c.kind === "professional_license" ? "license" : "certification",
            recognizedBy: { "@type": "Organization", name: c.issuing_authority },
            ...(c.valid_until ? { validUntil: c.valid_until } : {}),
          })),
        }
      : {}),
  };
}

export function facilityStructuredData(
  facility: Facility,
  url: string,
  branches: Branch[],
  hours: Map<string, OperatingHours>,
): Record<string, unknown> | null {
  if (!isPublic(facility)) return null;
  const type = facility.type === "hospital" || facility.type === "pharmacy" || facility.type === "wellness_center" ? "MedicalOrganization" : "MedicalClinic";
  const locations = branches
    .filter((b) => b.status !== "closed")
    .map((b) => ({
      "@type": "MedicalClinic",
      name: `${facility.name} — ${b.name}`,
      address: {
        "@type": "PostalAddress",
        streetAddress: b.address_line,
        addressLocality: b.city,
        ...(b.emirate ? { addressRegion: b.emirate } : {}),
        addressCountry: b.country,
      },
      ...(b.phone ? { telephone: b.phone } : {}),
      ...(b.latitude != null && b.longitude != null ? { geo: { "@type": "GeoCoordinates", latitude: b.latitude, longitude: b.longitude } } : {}),
      ...((hours.get(b.id)?.windows.length ?? 0) > 0
        ? {
            openingHoursSpecification: hours.get(b.id)!.windows.map((w) => ({
              "@type": "OpeningHoursSpecification",
              dayOfWeek: `https://schema.org/${DAYS[w.weekday]}`,
              opens: w.start,
              closes: w.end === "24:00" ? "23:59" : w.end,
            })),
          }
        : {}),
    }));
  return {
    "@context": "https://schema.org",
    "@type": type,
    "@id": url,
    url,
    name: facility.name,
    ...(facility.website ? { sameAs: [facility.website] } : {}),
    ...(facility.phone ? { telephone: facility.phone } : {}),
    ...(locations.length === 1 ? { address: locations[0]!.address } : {}),
    ...(locations.length ? { department: locations } : {}),
  };
}
