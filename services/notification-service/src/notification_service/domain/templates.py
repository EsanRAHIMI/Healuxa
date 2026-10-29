"""Localized template catalog (en / ar / fa).

Templates render from entity ids and enum values only — never free text, message bodies or health
information. Parameters are declared per template; unknown parameters are rejected. Enum parameters
(``status``) are translated through ``LABELS``; timestamps are formatted, everything else is refused.

Review status: Arabic and Persian strings are drafts pending native-speaker review. Templates whose
wording has legal, policy or clinical implications are flagged ``needs_professional_review`` and
carry that flag onto every notification rendered from them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

LOCALES = ("en", "ar", "fa")
TRANSACTIONAL = "transactional"
MARKETING = "marketing"
CATEGORY_KIND = {
    "concierge": TRANSACTIONAL,
    "appointments": TRANSACTIONAL,
    "provider_account": TRANSACTIONAL,
    "account": TRANSACTIONAL,
    "marketing": MARKETING,
}

LABELS: dict[str, dict[str, dict[str, str]]] = {
    "concierge_status": {
        "submitted": {"en": "Submitted", "ar": "تم الإرسال", "fa": "ثبت شد"},
        "triaged": {"en": "Under review", "ar": "قيد المراجعة", "fa": "در حال بررسی"},
        "assigned": {"en": "Assigned to a coordinator", "ar": "تم تعيين منسق", "fa": "به هماهنگ‌کننده سپرده شد"},
        "in_progress": {"en": "In progress", "ar": "قيد التنفيذ", "fa": "در حال انجام"},
        "awaiting_customer": {"en": "Waiting for your reply", "ar": "بانتظار ردك", "fa": "در انتظار پاسخ شما"},
        "arranged": {"en": "Arranged", "ar": "تم الترتيب", "fa": "هماهنگ شد"},
        "completed": {"en": "Completed", "ar": "مكتمل", "fa": "تکمیل شد"},
        "cancelled": {"en": "Cancelled", "ar": "ملغى", "fa": "لغو شد"},
        "escalated": {"en": "Escalated to a supervisor", "ar": "تم التصعيد إلى مشرف", "fa": "به سرپرست ارجاع شد"},
    },
    "provider_status": {
        "pending": {"en": "Pending", "ar": "قيد الانتظار", "fa": "در انتظار"},
        "active": {"en": "Active", "ar": "نشط", "fa": "فعال"},
        "suspended": {"en": "Suspended", "ar": "موقوف", "fa": "تعلیق‌شده"},
        "offboarded": {"en": "Offboarded", "ar": "منتهٍ", "fa": "خارج‌شده"},
    },
    "affiliation_status": {
        "pending": {"en": "Pending", "ar": "قيد الانتظار", "fa": "در انتظار"},
        "active": {"en": "Active", "ar": "نشط", "fa": "فعال"},
        "declined": {"en": "Declined", "ar": "مرفوض", "fa": "ردشده"},
        "ended": {"en": "Ended", "ar": "منتهٍ", "fa": "پایان‌یافته"},
    },
}


@dataclass(frozen=True)
class Template:
    key: str
    category: str
    channels: tuple[str, ...]
    texts: dict[str, tuple[str, str]]  # locale -> (title, body)
    # param name -> "label:<LABELS key>" | "datetime" | "id"
    params: dict[str, str] = field(default_factory=dict)
    needs_professional_review: bool = False

    @property
    def kind(self) -> str:
        return CATEGORY_KIND[self.category]


DEFAULT_CHANNELS = ("in_app", "push", "email")

_TEMPLATES = [
    Template(
        key="concierge.case_status_changed",
        category="concierge",
        channels=DEFAULT_CHANNELS,
        params={"status": "label:concierge_status"},
        texts={
            "en": ("Concierge request update", "Your concierge request is now: {status}."),
            "ar": ("تحديث طلب الكونسيرج", "حالة طلب الكونسيرج الخاص بك الآن: {status}."),
            "fa": ("به‌روزرسانی درخواست کانسیرج", "وضعیت درخواست کانسیرج شما اکنون: {status}."),
        },
    ),
    Template(
        key="concierge.case_assigned",
        category="concierge",
        channels=("in_app", "push"),
        texts={
            "en": ("New case assigned", "A concierge case has been assigned to you."),
            "ar": ("حالة جديدة مُسندة", "تم إسناد حالة كونسيرج إليك."),
            "fa": ("پرونده جدید", "یک پرونده کانسیرج به شما سپرده شد."),
        },
    ),
    Template(
        key="concierge.message_posted",
        category="concierge",
        channels=DEFAULT_CHANNELS,
        texts={
            "en": ("New message", "You have a new message about your concierge request. Open the app to read it."),
            "ar": ("رسالة جديدة", "لديك رسالة جديدة بخصوص طلب الكونسيرج. افتح التطبيق لقراءتها."),
            "fa": ("پیام جدید", "پیام جدیدی درباره درخواست کانسیرج شما دارید. برای خواندن آن برنامه را باز کنید."),
        },
    ),
    Template(
        key="catalog.provider_status_changed",
        category="provider_account",
        channels=("in_app", "email"),
        params={"status": "label:provider_status"},
        # Suspension / offboarding wording has contractual consequences.
        needs_professional_review=True,
        texts={
            "en": ("Provider profile status", "Your provider profile status changed to: {status}."),
            "ar": ("حالة ملف مقدم الخدمة", "تغيّرت حالة ملفك كمقدم خدمة إلى: {status}."),
            "fa": ("وضعیت پروفایل ارائه‌دهنده", "وضعیت پروفایل ارائه‌دهنده شما به {status} تغییر کرد."),
        },
    ),
    Template(
        key="catalog.affiliation_changed",
        category="provider_account",
        channels=("in_app", "email"),
        params={"status": "label:affiliation_status"},
        texts={
            "en": ("Affiliation update", "A facility affiliation is now: {status}."),
            "ar": ("تحديث الانتساب", "حالة انتساب المنشأة الآن: {status}."),
            "fa": ("به‌روزرسانی وابستگی", "وضعیت وابستگی به مرکز اکنون: {status} است."),
        },
    ),
    Template(
        key="appointment.requested",
        category="appointments",
        channels=("in_app", "email"),
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment request received", "We received your appointment request for {scheduled_at}."),
            "ar": ("تم استلام طلب الموعد", "استلمنا طلب موعدك بتاريخ {scheduled_at}."),
            "fa": ("درخواست نوبت دریافت شد", "درخواست نوبت شما برای {scheduled_at} دریافت شد."),
        },
    ),
    Template(
        key="appointment.created",
        category="appointments",
        channels=DEFAULT_CHANNELS,
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment booked", "Your appointment on {scheduled_at} is booked."),
            "ar": ("تم حجز الموعد", "تم حجز موعدك بتاريخ {scheduled_at}."),
            "fa": ("نوبت رزرو شد", "نوبت شما برای {scheduled_at} رزرو شد."),
        },
    ),
    Template(
        key="appointment.accepted",
        category="appointments",
        channels=DEFAULT_CHANNELS,
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment confirmed", "Your provider confirmed your appointment on {scheduled_at}."),
            "ar": ("تم تأكيد الموعد", "أكّد مقدم الخدمة موعدك بتاريخ {scheduled_at}."),
            "fa": ("نوبت تأیید شد", "ارائه‌دهنده نوبت شما در {scheduled_at} را تأیید کرد."),
        },
    ),
    Template(
        key="appointment.declined",
        category="appointments",
        channels=DEFAULT_CHANNELS,
        params={"scheduled_at": "datetime"},
        texts={
            "en": (
                "Appointment not confirmed",
                "Your provider could not confirm the appointment on {scheduled_at}. You can choose another time.",
            ),
            "ar": ("لم يتم تأكيد الموعد", "تعذّر على مقدم الخدمة تأكيد الموعد بتاريخ {scheduled_at}. يمكنك اختيار وقت آخر."),
            "fa": ("نوبت تأیید نشد", "ارائه‌دهنده نتوانست نوبت {scheduled_at} را تأیید کند. می‌توانید زمان دیگری انتخاب کنید."),
        },
    ),
    Template(
        key="appointment.completed",
        category="appointments",
        channels=("in_app", "email"),
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment completed", "Thank you — your appointment on {scheduled_at} is marked completed."),
            "ar": ("اكتمل الموعد", "شكرًا لك — تم تسجيل موعدك بتاريخ {scheduled_at} كمكتمل."),
            "fa": ("نوبت انجام شد", "سپاس — نوبت شما در {scheduled_at} انجام‌شده ثبت شد."),
        },
    ),
    Template(
        key="appointment.no_show",
        category="appointments",
        channels=("in_app", "email"),
        params={"scheduled_at": "datetime"},
        # Missed-appointment wording may carry fee/policy implications.
        needs_professional_review=True,
        texts={
            "en": ("Missed appointment", "Your appointment on {scheduled_at} was marked as missed. Contact us if this is wrong."),
            "ar": ("موعد فائت", "تم تسجيل موعدك بتاريخ {scheduled_at} كموعد فائت. تواصل معنا إذا كان ذلك غير صحيح."),
            "fa": ("نوبت از دست رفته", "نوبت شما در {scheduled_at} به‌عنوان غیبت ثبت شد. اگر اشتباه است با ما تماس بگیرید."),
        },
    ),
    # Lifecycle events added by appointment-service's branch (see consumers/handlers.py).
    Template(
        key="appointment.cancelled",
        category="appointments",
        channels=DEFAULT_CHANNELS,
        params={"scheduled_at": "datetime"},
        # Cancellation wording may carry fee/refund policy implications.
        needs_professional_review=True,
        texts={
            "en": ("Appointment cancelled", "Your appointment on {scheduled_at} was cancelled."),
            "ar": ("تم إلغاء الموعد", "تم إلغاء موعدك بتاريخ {scheduled_at}."),
            "fa": ("نوبت لغو شد", "نوبت شما در {scheduled_at} لغو شد."),
        },
    ),
    Template(
        key="appointment.rescheduled",
        category="appointments",
        channels=DEFAULT_CHANNELS,
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment rescheduled", "Your appointment has moved to {scheduled_at}."),
            "ar": ("تم تغيير موعدك", "تم نقل موعدك إلى {scheduled_at}."),
            "fa": ("زمان نوبت تغییر کرد", "نوبت شما به {scheduled_at} منتقل شد."),
        },
    ),
    Template(
        key="appointment.expired",
        category="appointments",
        channels=("in_app", "email"),
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment request expired", "Your appointment request for {scheduled_at} expired before it was confirmed."),
            "ar": ("انتهت صلاحية طلب الموعد", "انتهت صلاحية طلب موعدك بتاريخ {scheduled_at} قبل تأكيده."),
            "fa": ("درخواست نوبت منقضی شد", "درخواست نوبت شما برای {scheduled_at} پیش از تأیید منقضی شد."),
        },
    ),
    Template(
        key="appointment.reminder_due",
        category="appointments",
        channels=DEFAULT_CHANNELS,
        params={"scheduled_at": "datetime"},
        texts={
            "en": ("Appointment reminder", "Reminder: your appointment is on {scheduled_at}."),
            "ar": ("تذكير بالموعد", "تذكير: موعدك بتاريخ {scheduled_at}."),
            "fa": ("یادآوری نوبت", "یادآوری: نوبت شما در {scheduled_at} است."),
        },
    ),
    Template(
        key="account.notice",
        category="account",
        channels=DEFAULT_CHANNELS,
        texts={
            "en": ("Account notice", "There is an update on your Healuxa account. Open the app for details."),
            "ar": ("إشعار الحساب", "يوجد تحديث على حسابك في Healuxa. افتح التطبيق لمعرفة التفاصيل."),
            "fa": ("اطلاعیه حساب", "حساب Healuxa شما به‌روزرسانی شده است. برای جزئیات برنامه را باز کنید."),
        },
    ),
    Template(
        key="marketing.newsletter",
        category="marketing",
        channels=("in_app", "email"),
        texts={
            "en": ("News from Healuxa", "Discover what's new this month."),
            "ar": ("أخبار من Healuxa", "اكتشف الجديد هذا الشهر."),
            "fa": ("اخبار Healuxa", "تازه‌های این ماه را ببینید."),
        },
    ),
]

CATALOG: dict[str, Template] = {t.key: t for t in _TEMPLATES}


class TemplateError(ValueError):
    pass


def get_template(key: str) -> Template:
    try:
        return CATALOG[key]
    except KeyError:
        raise TemplateError(f"unknown template: {key}") from None


def _format_param(kind: str, value: object, locale: str) -> str:
    if kind.startswith("label:"):
        labels = LABELS[kind.removeprefix("label:")]
        if not isinstance(value, str) or value not in labels:
            raise TemplateError(f"unsupported value {value!r}")
        return labels[value][locale]
    if kind == "datetime":
        if not isinstance(value, str):
            raise TemplateError("timestamp expected")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TemplateError(f"invalid timestamp {value!r}") from exc
        return parsed.strftime("%Y-%m-%d %H:%M UTC") if parsed.utcoffset() is not None else parsed.strftime("%Y-%m-%d %H:%M")
    if kind == "id":
        if not isinstance(value, str) or len(value) > 36:
            raise TemplateError("id expected")
        return value
    raise TemplateError(f"unknown parameter kind {kind}")


def render(template: Template, locale: str, params: dict[str, object]) -> tuple[str, str]:
    unknown = set(params) - set(template.params)
    if unknown:
        raise TemplateError(f"unknown parameters for {template.key}: {sorted(unknown)}")
    missing = set(template.params) - set(params)
    if missing:
        raise TemplateError(f"missing parameters for {template.key}: {sorted(missing)}")
    locale = locale if locale in template.texts else "en"
    values = {name: _format_param(kind, params[name], locale) for name, kind in template.params.items()}
    title, body = template.texts[locale]
    return title.format(**values), body.format(**values)
