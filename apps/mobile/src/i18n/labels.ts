import type { CredentialKind, FacilityType, ProviderType } from '../api/types';
import type { Language } from './index';

type L = Record<Language, string>;

const LANGUAGE_NAMES: Record<string, L> = {
  en: { en: 'English', ar: 'الإنجليزية', fa: 'انگلیسی' },
  ar: { en: 'Arabic', ar: 'العربية', fa: 'عربی' },
  fa: { en: 'Persian', ar: 'الفارسية', fa: 'فارسی' },
  fr: { en: 'French', ar: 'الفرنسية', fa: 'فرانسوی' },
  de: { en: 'German', ar: 'الألمانية', fa: 'آلمانی' },
  ru: { en: 'Russian', ar: 'الروسية', fa: 'روسی' },
  hi: { en: 'Hindi', ar: 'الهندية', fa: 'هندی' },
  ur: { en: 'Urdu', ar: 'الأردية', fa: 'اردو' },
};

export const DIRECTORY_LANGUAGES = ['en', 'ar', 'fa', 'fr', 'ru'] as const;

export function languageName(code: string, ui: Language): string {
  return LANGUAGE_NAMES[code]?.[ui] ?? code.toUpperCase();
}

const PROVIDER_TYPES: Record<ProviderType, L> = {
  doctor: { en: 'Doctor', ar: 'طبيب', fa: 'پزشک' },
  clinic: { en: 'Clinic', ar: 'عيادة', fa: 'کلینیک' },
  therapist: { en: 'Therapist', ar: 'معالج', fa: 'درمانگر' },
  trainer: { en: 'Trainer', ar: 'مدرّب', fa: 'مربی' },
  nutritionist: { en: 'Nutritionist', ar: 'أخصائي تغذية', fa: 'متخصص تغذیه' },
  pharmacy: { en: 'Pharmacy', ar: 'صيدلية', fa: 'داروخانه' },
  brand: { en: 'Brand', ar: 'علامة تجارية', fa: 'برند' },
  home_visit: { en: 'Home visit', ar: 'زيارة منزلية', fa: 'ویزیت در منزل' },
};
export const DIRECTORY_TYPES: readonly ProviderType[] = ['doctor', 'therapist', 'nutritionist', 'trainer'];
export const providerTypeLabel = (t: ProviderType, ui: Language) => PROVIDER_TYPES[t]?.[ui] ?? t;

const FACILITY_TYPES: Record<FacilityType, L> = {
  clinic: { en: 'Clinic', ar: 'عيادة', fa: 'کلینیک' },
  hospital: { en: 'Hospital', ar: 'مستشفى', fa: 'بیمارستان' },
  medical_center: { en: 'Medical centre', ar: 'مركز طبي', fa: 'مرکز پزشکی' },
  day_surgery: { en: 'Day surgery', ar: 'جراحة اليوم الواحد', fa: 'جراحی سرپایی' },
  diagnostic_center: { en: 'Diagnostic centre', ar: 'مركز تشخيص', fa: 'مرکز تشخیصی' },
  pharmacy: { en: 'Pharmacy', ar: 'صيدلية', fa: 'داروخانه' },
  wellness_center: { en: 'Wellness centre', ar: 'مركز عافية', fa: 'مرکز تندرستی' },
};
export const facilityTypeLabel = (t: FacilityType, ui: Language) => FACILITY_TYPES[t]?.[ui] ?? t;

const CREDENTIAL_KINDS: Record<CredentialKind, L> = {
  professional_license: { en: 'Professional licence', ar: 'ترخيص مهني', fa: 'پروانهٔ حرفه‌ای' },
  board_certification: { en: 'Board certification', ar: 'شهادة البورد', fa: 'گواهی بورد' },
  malpractice_insurance: { en: 'Malpractice insurance', ar: 'تأمين ضد الأخطاء الطبية', fa: 'بیمهٔ مسئولیت حرفه‌ای' },
  other: { en: 'Credential', ar: 'اعتماد', fa: 'مدرک' },
};
export const credentialKindLabel = (k: CredentialKind | undefined, ui: Language) => CREDENTIAL_KINDS[k ?? 'other'][ui];

const WEEKDAYS: Record<Language, string[]> = {
  en: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
  ar: ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'],
  fa: ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه'],
};
/** ISO weekday: 0 = Monday … 6 = Sunday (provider.openapi.yaml TimeWindow). */
export const weekdayName = (isoWeekday: number, ui: Language) => WEEKDAYS[ui][isoWeekday] ?? String(isoWeekday);

/** Picks the best LocalizedText entry for the UI language. */
export function localized(text: Record<string, string> | undefined, ui: Language): string | undefined {
  if (!text) return undefined;
  return text[ui] ?? text.en ?? Object.values(text)[0];
}

export function formatDate(iso: string | null | undefined, ui: Language): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const tag = ui === 'en' ? 'en-AE' : ui === 'ar' ? 'ar-AE' : 'fa-IR';
  try {
    return new Intl.DateTimeFormat(tag, { year: 'numeric', month: 'short', day: 'numeric' }).format(d);
  } catch {
    return d.toISOString().slice(0, 10);
  }
}
