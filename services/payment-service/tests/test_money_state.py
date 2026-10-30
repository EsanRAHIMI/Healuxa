"""Pure unit tests: minor-unit rounding, VAT, allocation, state machine."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from payment_service.domain.money import allocate, apply_bps, make_line, totals
from payment_service.domain.quotes import appointment_lines
from payment_service.domain.state import IllegalTransition, can_transition, require_transition, should_apply

RATES = {"professional_service": 500, "zero": 0}


@pytest.mark.parametrize(
    ("amount", "bps", "expected"),
    [
        (10_000, 500, 500),  # AED 100.00 @5% = 5.00
        (10, 500, 1),  # 0.5 fils rounds half up
        (9, 500, 0),  # 0.45 rounds down
        (30, 500, 2),  # 1.5 rounds up
        (12_345, 500, 617),  # 617.25 -> 617
        (12_350, 500, 618),  # 617.5 -> 618
        (0, 500, 0),
        (99_999, 0, 0),
    ],
)
def test_apply_bps_rounds_half_up_in_minor_units(amount: int, bps: int, expected: int) -> None:
    assert apply_bps(amount, bps) == expected


def test_apply_bps_rejects_negative() -> None:
    with pytest.raises(ValueError):
        apply_bps(-1, 500)


def test_vat_is_computed_per_line_and_summed() -> None:
    a = make_line(code="x", description="x", category="professional_service", net_minor=10, vat_rates_bps=RATES, payee_type="healuxa", payee_id=None)
    b = make_line(code="y", description="y", category="professional_service", net_minor=10, vat_rates_bps=RATES, payee_type="healuxa", payee_id=None)
    assert (a.vat_minor, a.gross_minor) == (1, 11)
    assert totals([a, b]) == (20, 2, 22)


def test_zero_rated_category_has_no_vat() -> None:
    line = make_line(code="x", description="x", category="zero", net_minor=50_000, vat_rates_bps=RATES, payee_type="provider", payee_id="p")
    assert line.vat_minor == 0 and line.gross_minor == 50_000


def test_unknown_tax_category_is_refused() -> None:
    with pytest.raises(KeyError):
        make_line(code="x", description="x", category="nope", net_minor=1, vat_rates_bps=RATES, payee_type="healuxa", payee_id=None)


def test_appointment_breakdown_is_transparent() -> None:
    lines = appointment_lines(50_000, 20_000, "prov", "fac")
    codes = [(line.code, line.net_minor, line.vat_minor, line.payee_type) for line in lines]
    # default platform fee 5% of 700.00 = 35.00; VAT 5% on every line
    assert codes == [
        ("professional_fee", 50_000, 2_500, "provider"),
        ("facility_fee", 20_000, 1_000, "facility"),
        ("platform_fee", 3_500, 175, "healuxa"),
    ]
    assert totals(lines) == (73_500, 3_675, 77_175)


def test_allocate_is_exact_bounded_and_complete() -> None:
    caps = [50_000, 2_500, 20_000, 1_000, 3_500, 175]
    for amount in [1, 7, 333, 38_587, 77_174, 77_175]:
        parts = allocate(amount, caps)
        assert sum(parts) == amount
        assert all(0 <= p <= c for p, c in zip(parts, caps, strict=True))
    assert allocate(sum(caps), caps) == caps


def test_successive_partial_refunds_never_exceed_any_bucket() -> None:
    caps = [50_000, 2_500, 20_000, 1_000, 3_500, 175]
    remaining = list(caps)
    for amount in [10_001, 3, 25_000, 40_000, 2_171]:
        parts = allocate(amount, remaining)
        remaining = [r - p for r, p in zip(remaining, parts, strict=True)]
        assert min(remaining) >= 0
    assert sum(remaining) == 0


def test_allocate_refuses_more_than_capacity() -> None:
    with pytest.raises(ValueError):
        allocate(11, [5, 5])


def test_illegal_transitions_are_rejected() -> None:
    for current, target in [("succeeded", "failed"), ("canceled", "succeeded"), ("refunded", "succeeded"), ("authorized", "pending"), ("succeeded", "authorized")]:
        assert not can_transition(current, target)
        with pytest.raises(IllegalTransition):
            require_transition(current, target)
    require_transition("authorized", "succeeded")
    require_transition("pending", "authorized")


def test_terminal_states_have_no_exit_except_refunds() -> None:
    statuses = ["pending", "processing", "authorized", "succeeded", "failed", "canceled", "partially_refunded", "refunded"]
    for current, target in itertools.product(["canceled", "refunded"], statuses):
        assert not can_transition(current, target)


def test_out_of_order_lower_rank_events_need_a_newer_timestamp() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    # A failure older than the processing we applied is ignored; a newer one applies.
    assert not should_apply("processing", "failed", event_at=t0, last_event_at=t0 + timedelta(seconds=5))
    assert should_apply("processing", "failed", event_at=t0 + timedelta(seconds=6), last_event_at=t0 + timedelta(seconds=5))
    # Progress always applies, even from an older event (e.g. succeeded delivered late).
    assert should_apply("failed", "succeeded", event_at=t0, last_event_at=t0 + timedelta(seconds=5))
    assert not should_apply("succeeded", "failed", event_at=t0 + timedelta(days=1), last_event_at=t0)
