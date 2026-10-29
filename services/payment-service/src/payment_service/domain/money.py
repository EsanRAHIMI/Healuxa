"""Integer minor-unit money math. No floats anywhere: rates are basis points (1 bp = 0.01%)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

BPS = 10_000


def apply_bps(amount_minor: int, rate_bps: int) -> int:
    """amount × rate, rounded half-up to the nearest minor unit (fils). Amounts are non-negative."""
    if amount_minor < 0 or rate_bps < 0:
        raise ValueError("amount and rate must be non-negative")
    return (amount_minor * rate_bps * 2 + BPS) // (2 * BPS)


@dataclass(frozen=True)
class Line:
    code: str
    description: str
    category: str
    net_minor: int
    vat_rate_bps: int
    vat_minor: int
    gross_minor: int
    payee_type: str
    payee_id: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def make_line(
    *, code: str, description: str, category: str, net_minor: int, vat_rates_bps: dict[str, int], payee_type: str, payee_id: str | None
) -> Line:
    if category not in vat_rates_bps:
        raise KeyError(category)
    rate = vat_rates_bps[category]
    vat = apply_bps(net_minor, rate)  # VAT per line, then summed (line-level rounding, see README)
    return Line(code, description, category, net_minor, rate, vat, net_minor + vat, payee_type, payee_id)


def totals(lines: list[Line] | list[dict]) -> tuple[int, int, int]:
    def get(line, key):
        return line[key] if isinstance(line, dict) else getattr(line, key)

    subtotal = sum(get(line, "net_minor") for line in lines)
    tax = sum(get(line, "vat_minor") for line in lines)
    return subtotal, tax, subtotal + tax


def allocate(amount_minor: int, capacities: list[int]) -> list[int]:
    """Split ``amount_minor`` across buckets proportionally to their remaining ``capacities``.

    Largest-remainder rounding (ties to the earliest bucket): the parts always sum exactly to the
    amount, never exceed a bucket's capacity, and refunding the whole remaining balance returns each
    bucket's capacity exactly.
    """
    total = sum(capacities)
    if amount_minor < 0 or any(c < 0 for c in capacities):
        raise ValueError("negative allocation")
    if amount_minor > total:
        raise ValueError("allocation exceeds capacity")
    if total == 0:
        return [0 for _ in capacities]
    floors = [amount_minor * c // total for c in capacities]
    remainders = [(amount_minor * c) % total for c in capacities]
    short = amount_minor - sum(floors)
    order = sorted(range(len(capacities)), key=lambda i: (-remainders[i], i))
    for i in order[:short]:
        floors[i] += 1
    return floors
