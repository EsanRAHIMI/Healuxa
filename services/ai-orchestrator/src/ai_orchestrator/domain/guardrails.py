"""Guardrails enforced in code (the system prompt states the same rules, but is not relied on).

* ``classify_input`` short-circuits a turn before any model call: urgent-symptom language gets an
  emergency-services pointer; requests for a diagnosis or a medication/treatment choice get a
  one-sentence redirect. The patterns are deliberately narrow — the assistant must stay useful for
  coordination questions ("which clinics offer hair treatments?").
* ``check_output`` is the backstop on model text: any price not present in this turn's tool results,
  or dosing/diagnosis wording, replaces the whole reply with a safe localised sentence.

These are heuristics over en/ar/fa wording, not a clinical classifier.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Literal

InputVerdict = Literal["emergency", "clinical"] | None
OutputVerdict = Literal["ungrounded", "clinical_redirect"] | None

_I = re.IGNORECASE

_EMERGENCY = re.compile(
    r"\b(chest pain|heart attack|can'?t breathe|cannot breathe|difficulty breathing|not breathing|stroke|"
    r"unconscious|passed out|seizure|severe bleeding|bleeding heavily|won'?t stop bleeding|overdos\w*|"
    r"suicid\w*|kill myself|end my life|anaphyla\w*|choking|poisoned|severe allergic)\b"
    r"|ألم في الصدر|ألم بالصدر|نوبة قلبية|لا أستطيع التنفس|صعوبة في التنفس|ضيق تنفس|سكتة|فاقد الوعي|فقد الوعي|"
    r"نزيف شديد|نزيف حاد|جرعة زائدة|انتحار|أنتحر|تشنج|اختناق|تسمم"
    r"|درد قفسه سینه|حمله قلبی|نمی‌توانم نفس بکشم|نمیتوانم نفس بکشم|تنگی نفس|سکته|بیهوش|بی‌هوش|خونریزی شدید|"
    r"مصرف بیش از حد|اوردوز|خودکشی|تشنج|خفگی|مسمومیت",
    _I,
)

_CLINICAL_INPUT = re.compile(
    r"\b(do i have|have i got|diagnos\w*|what (is|are) (the |my )?(dose|dosage)|how (much|many) .{0,40}\b(mg|milligram|pills?|tablets?)\b|"
    r"dosage|should i (take|stop taking|start taking|stop|use)\b.{0,60}|can i take\b|which (medication|medicine|drug|antibiotic|pill|supplement)|"
    r"what (medication|medicine|drug|antibiotic)|prescri\w*|is (it|this) (cancer|serious|dangerous|normal|infected)|"
    r"what treatment (do i need|should i (get|have|choose))|which treatment (is best|should i)|side effects? of)\b"
    r"|هل أنا مصاب|هل لدي|تشخيص|شخّص|ما الجرعة|كم جرعة|جرعة|أي دواء|ما الدواء|هل آخذ|هل أتناول|هل أتوقف عن|وصفة|"
    r"هل هذا خطير|هل هو سرطان|أي علاج أحتاج|ما العلاج المناسب لي"
    r"|آیا من .{0,30}دارم|تشخیص|چه دوز|دوز|مقدار مصرف|چه دارویی|کدام دارو|آیا مصرف کنم|مصرف کنم|قطع کنم|نسخه|"
    r"آیا خطرناک است|آیا سرطان است|چه درمانی لازم دارم|کدام درمان برای من",
    _I,
)

_CLINICAL_OUTPUT = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:mg|mcg|µg|ml|iu|milligrams?)\b"
    r"|\byou (?:probably|likely|may|might|seem to|appear to|most likely) have\b"
    r"|\b(?:it|this) (?:sounds|looks|seems) like (?:you have|a case of)\b"
    r"|\bi (?:would )?(?:recommend|suggest|advise) (?:that you )?(?:taking|take|starting|start|using|use|stopping|stop)\b"
    r"|\byour diagnosis\b|\bmy diagnosis\b|\byou should (?:take|stop taking|start taking)\b"
    r"|ملغ|ملليغرام|أنت مصاب ب|تشخيصك هو|أنصحك بتناول|میلی‌گرم|میلی گرم|شما مبتلا به|تشخیص شما|توصیه می‌کنم مصرف",
    _I,
)

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
_CURRENCY = r"(?:AED|USD|EUR|GBP|SAR|QAR|KWD|BHD|OMR|IRR|\$|€|£|د\.?\s?إ|درهم(?:اً|ا)?|دراهم|dirhams?|dhs?\.?|dollars?|euros?|ريال|ریال|تومان)"
_NUMBER = r"\d[\d.,]*"
_PRICE = re.compile(rf"{_CURRENCY}\s*({_NUMBER})|({_NUMBER})\s*{_CURRENCY}", _I)


def classify_input(text: str) -> InputVerdict:
    if _EMERGENCY.search(text):
        return "emergency"
    if _CLINICAL_INPUT.search(text):
        return "clinical"
    return None


def _to_decimal(raw: str) -> Decimal | None:
    cleaned = raw.strip(".,")
    # "1,250.00" / "1,250" → thousands separators; a lone "450,50" is not a format Healuxa emits.
    cleaned = cleaned.replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def prices_in(text: str) -> list[Decimal]:
    found: list[Decimal] = []
    for match in _PRICE.finditer(text.translate(_DIGITS)):
        value = _to_decimal(match.group(1) or match.group(2))
        if value is not None:
            found.append(value)
    return found


def check_output(text: str, grounded_amounts: Iterable[Decimal]) -> OutputVerdict:
    if _CLINICAL_OUTPUT.search(text):
        return "clinical_redirect"
    allowed = {amount.normalize() for amount in grounded_amounts}
    for price in prices_in(text):
        if price.normalize() not in allowed:
            return "ungrounded"
    return None
