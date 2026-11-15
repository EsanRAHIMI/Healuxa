"""Deterministic, localised assistant replies used by code guardrails (never produced by the model).

Kept short on purpose: one friendly sentence, no stacked disclaimers. Clinical/emergency wording is
part of the professional-review scope (packages/i18n/manifest.json covers the UI copy; these three
service-side strings need the same sign-off before launch).
"""

from __future__ import annotations

LOCALES = ("en", "ar", "fa")

_MESSAGES: dict[str, dict[str, str]] = {
    "emergency": {
        "en": "If this could be an emergency, please call {number} or go to the nearest emergency department now — I can help with booking once you are safe.",
        "ar": "إذا كانت الحالة طارئة، يُرجى الاتصال بالرقم {number} أو التوجه إلى أقرب قسم طوارئ الآن — وسأساعدك في الحجز بعد أن تكون بأمان.",
        "fa": "اگر وضعیت اضطراری است، لطفاً همین حالا با {number} تماس بگیرید یا به نزدیک‌ترین اورژانس بروید — بعد از آن در رزرو کمکتان می‌کنم.",
    },
    "clinical_redirect": {
        "en": "That is best answered by a practitioner — I can help you book a consultation or connect you with a coordinator.",
        "ar": "الأفضل أن يجيبك مختص عن ذلك — يمكنني مساعدتك في حجز استشارة أو وصلك بمنسّق.",
        "fa": "بهتر است متخصص به این پرسش پاسخ دهد — می‌توانم برای رزرو مشاوره یا ارتباط با هماهنگ‌کننده کمکتان کنم.",
    },
    "ungrounded": {
        "en": "Here is what I could verify on Healuxa — prices and availability are shown on the options below.",
        "ar": "هذا ما تمكّنت من التحقق منه على هيلوكسا — الأسعار والمواعيد المتاحة معروضة في الخيارات أدناه.",
        "fa": "این چیزی است که توانستم در هیلوکسا تأیید کنم — قیمت‌ها و زمان‌های موجود در گزینه‌های زیر آمده است.",
    },
    "unable": {
        "en": "I could not finish that just now. A coordinator can pick this up for you.",
        "ar": "لم أتمكن من إكمال ذلك الآن. يمكن لمنسّق أن يتولى الأمر عنك.",
        "fa": "الان نتوانستم این کار را کامل کنم. یک هماهنگ‌کننده می‌تواند ادامه دهد.",
    },
    "refusal": {
        "en": "I can't help with that here, but a coordinator can assist you.",
        "ar": "لا أستطيع المساعدة في ذلك هنا، لكن يمكن لمنسّق أن يساعدك.",
        "fa": "اینجا نمی‌توانم در این مورد کمک کنم، اما یک هماهنگ‌کننده می‌تواند کمکتان کند.",
    },
}


def message(key: str, locale: str, **params: str) -> str:
    variants = _MESSAGES[key]
    return variants.get(locale, variants["en"]).format(**params)
