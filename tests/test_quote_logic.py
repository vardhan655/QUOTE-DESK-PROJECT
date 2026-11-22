"""
Unit tests for Quote Desk business logic.
Covers status evaluation and best-quote selection edge cases.
"""

from datetime import date, timedelta
import pytest

from logic import (
    calculate_arrival_date,
    calculate_rfq_status,
    does_quote_meet_deadline,
    evaluate_quote_eligibility,
    get_best_quote,
    is_quote_valid,
    parse_date,
)


# Fixed reference date for deterministic testing
TODAY = date(2026, 11, 20)


@pytest.fixture
def base_rfq():
    """Sample aerospace RFQ needing parts in 10 days."""
    return {
        "id": 1,
        "part_number": "JA-TRB-4401",
        "description": "High-Pressure Turbine Seal Ring (Inconel 718)",
        "quantity": 25,
        "needed_by": TODAY + timedelta(days=10),  # 2026-11-30
    }


# ==============================================================================
# 1. BEST QUOTE SELECTION TESTS
# ==============================================================================

def test_cheaper_quote_arrives_late_vs_more_expensive_on_time(base_rfq):
    """
    Core Requirement: A cheaper quote that arrives AFTER needed_by must NOT win.
    The slightly more expensive quote arriving on-time must win.
    """
    quotes = [
        {
            "id": 101,
            "supplier_name": "Budget Aero Parts",
            "unit_price": 5000.0,  # Very cheap
            "lead_time_days": 15,  # Arrives in 15 days (after 10-day deadline!)
            "valid_until": TODAY + timedelta(days=20),
        },
        {
            "id": 102,
            "supplier_name": "Precision Flight Dynamics",
            "unit_price": 7500.0,  # More expensive, but on time
            "lead_time_days": 7,   # Arrives in 7 days (well within 10-day deadline)
            "valid_until": TODAY + timedelta(days=15),
        },
    ]

    best = get_best_quote(base_rfq, quotes, today=TODAY)
    assert best is not None
    assert best["id"] == 102
    assert best["supplier_name"] == "Precision Flight Dynamics"
    assert best["unit_price"] == 7500.0


def test_cheapest_quote_is_expired(base_rfq):
    """
    Core Requirement: A quote past its valid_until date cannot be selected,
    even if it has the lowest price and fastest lead time.
    """
    quotes = [
        {
            "id": 201,
            "supplier_name": "Expired Cheap Supplier",
            "unit_price": 3000.0,  # Lowest price
            "lead_time_days": 3,   # Very fast
            "valid_until": TODAY - timedelta(days=1),  # Expired yesterday!
        },
        {
            "id": 202,
            "supplier_name": "Active Quality Castings",
            "unit_price": 4200.0,
            "lead_time_days": 5,
            "valid_until": TODAY + timedelta(days=10),  # Valid
        },
    ]

    best = get_best_quote(base_rfq, quotes, today=TODAY)
    assert best is not None
    assert best["id"] == 202
    assert best["supplier_name"] == "Active Quality Castings"


def test_exact_boundary_date_arrives_on_needed_by(base_rfq):
    """
    Core Requirement: Boundary case where today + lead_time_days == needed_by.
    This quote qualifies (inclusive deadline) and should be eligible to win.
    """
    # RFQ needed_by is TODAY + 10 days
    quotes = [
        {
            "id": 301,
            "supplier_name": "Just-In-Time Machining",
            "unit_price": 6000.0,
            "lead_time_days": 10,  # EXACTLY hits needed_by date
            "valid_until": TODAY + timedelta(days=15),
        }
    ]

    best = get_best_quote(base_rfq, quotes, today=TODAY)
    assert best is not None
    assert best["id"] == 301
    assert calculate_arrival_date(best["lead_time_days"], TODAY) == parse_date(base_rfq["needed_by"])


def test_all_quotes_invalid_or_late_returns_none(base_rfq):
    """
    Core Requirement: When all quotes fail either validity or delivery deadline,
    get_best_quote must return None.
    """
    quotes = [
        {
            "id": 401,
            "supplier_name": "Too Late Supplier",
            "unit_price": 4000.0,
            "lead_time_days": 14,  # Deadline is 10 days
            "valid_until": TODAY + timedelta(days=20),
        },
        {
            "id": 402,
            "supplier_name": "Expired Supplier",
            "unit_price": 4500.0,
            "lead_time_days": 5,
            "valid_until": TODAY - timedelta(days=2),  # Expired
        },
    ]

    best = get_best_quote(base_rfq, quotes, today=TODAY)
    assert best is None


def test_empty_quotes_returns_none(base_rfq):
    """Empty quote list returns None cleanly."""
    assert get_best_quote(base_rfq, [], today=TODAY) is None


def test_tie_breaking_by_shortest_lead_time(base_rfq):
    """
    Core Requirement: When two qualifying quotes have identical unit_price,
    the tie must be broken by shortest lead_time_days.
    """
    quotes = [
        {
            "id": 501,
            "supplier_name": "Slower Supplier",
            "unit_price": 5500.0,
            "lead_time_days": 8,
            "valid_until": TODAY + timedelta(days=15),
        },
        {
            "id": 502,
            "supplier_name": "Faster Supplier",
            "unit_price": 5500.0,  # Same price!
            "lead_time_days": 4,  # Shorter lead time wins
            "valid_until": TODAY + timedelta(days=15),
        },
    ]

    best = get_best_quote(base_rfq, quotes, today=TODAY)
    assert best is not None
    assert best["id"] == 502
    assert best["supplier_name"] == "Faster Supplier"
    assert best["lead_time_days"] == 4


def test_valid_until_boundary_inclusive(base_rfq):
    """
    A quote valid until TODAY is still valid (inclusive).
    A quote valid until yesterday is expired.
    """
    valid_today_quote = {
        "id": 601,
        "supplier_name": "Expires Today",
        "unit_price": 3500.0,
        "lead_time_days": 5,
        "valid_until": TODAY,
    }
    assert is_quote_valid(valid_today_quote, today=TODAY) is True

    expired_quote = {
        "id": 602,
        "supplier_name": "Expired Yesterday",
        "unit_price": 3500.0,
        "lead_time_days": 5,
        "valid_until": TODAY - timedelta(days=1),
    }
    assert is_quote_valid(expired_quote, today=TODAY) is False


# ==============================================================================
# 2. RFQ STATUS LOGIC TESTS
# ==============================================================================

def test_rfq_status_open_when_zero_quotes_and_deadline_future():
    """RFQ with 0 quotes and future needed_by date is OPEN."""
    rfq = {"needed_by": TODAY + timedelta(days=5)}
    status = calculate_rfq_status(rfq, quotes=[], today=TODAY)
    assert status == "Open"


def test_rfq_status_open_boundary_needed_by_is_today():
    """RFQ with 0 quotes and needed_by == today is OPEN (inclusive)."""
    rfq = {"needed_by": TODAY}
    status = calculate_rfq_status(rfq, quotes=[], today=TODAY)
    assert status == "Open"


def test_rfq_status_expired_when_needed_by_in_past_with_no_quotes():
    """RFQ with needed_by < today is EXPIRED."""
    rfq = {"needed_by": TODAY - timedelta(days=1)}
    status = calculate_rfq_status(rfq, quotes=[], today=TODAY)
    assert status == "Expired"


def test_rfq_status_expired_when_needed_by_in_past_even_with_valid_quotes():
    """
    RFQ deadline passed (needed_by < today) is EXPIRED, even if it has quotes
    that are technically not expired in valid_until.
    """
    rfq = {"needed_by": TODAY - timedelta(days=2)}
    quotes = [
        {
            "id": 701,
            "unit_price": 1000.0,
            "lead_time_days": 3,
            "valid_until": TODAY + timedelta(days=10),
        }
    ]
    status = calculate_rfq_status(rfq, quotes=quotes, today=TODAY)
    assert status == "Expired"


def test_rfq_status_quoted_when_at_least_one_valid_quote_and_future_deadline():
    """
    RFQ with future deadline and at least one valid quote is QUOTED.
    (Even if another quote in the list is expired).
    """
    rfq = {"needed_by": TODAY + timedelta(days=10)}
    quotes = [
        {
            "id": 801,
            "unit_price": 900.0,
            "lead_time_days": 5,
            "valid_until": TODAY - timedelta(days=5),  # expired
        },
        {
            "id": 802,
            "unit_price": 1200.0,
            "lead_time_days": 6,
            "valid_until": TODAY + timedelta(days=7),  # valid
        },
    ]
    status = calculate_rfq_status(rfq, quotes=quotes, today=TODAY)
    assert status == "Quoted"


def test_rfq_status_expired_when_all_quotes_are_past_valid_until():
    """
    RFQ has future deadline, but every submitted quote has expired (valid_until < today).
    Status must be EXPIRED.
    """
    rfq = {"needed_by": TODAY + timedelta(days=10)}
    quotes = [
        {
            "id": 901,
            "unit_price": 900.0,
            "lead_time_days": 3,
            "valid_until": TODAY - timedelta(days=2),  # expired
        },
        {
            "id": 902,
            "unit_price": 950.0,
            "lead_time_days": 4,
            "valid_until": TODAY - timedelta(days=1),  # expired
        },
    ]
    status = calculate_rfq_status(rfq, quotes=quotes, today=TODAY)
    assert status == "Expired"


# ==============================================================================
# 3. ELIGIBILITY EVALUATION & REASON TESTS
# ==============================================================================

def test_evaluate_quote_eligibility_reasons():
    """Test detailed failure reasons for UI transparency."""
    needed_by = TODAY + timedelta(days=5)

    # 1. Expired and late
    both_bad = {
        "lead_time_days": 8,
        "valid_until": TODAY - timedelta(days=1),
    }
    eligible, reasons = evaluate_quote_eligibility(both_bad, needed_by, today=TODAY)
    assert eligible is False
    assert len(reasons) == 2
    assert "expired" in reasons[0].lower()
    assert "exceeds deadline" in reasons[1].lower()

    # 2. Valid and on-time
    good_quote = {
        "lead_time_days": 3,
        "valid_until": TODAY + timedelta(days=10),
    }
    eligible, reasons = evaluate_quote_eligibility(good_quote, needed_by, today=TODAY)
    assert eligible is True
    assert len(reasons) == 0


def test_secondary_tie_breaker_by_id(base_rfq):
    """
    When unit_price and lead_time_days are both identical,
    the deterministic fallback tie-breaker is quote creation ID.
    """
    quotes = [
        {
            "id": 99,
            "supplier_name": "First Submitter",
            "unit_price": 5000.0,
            "lead_time_days": 5,
            "valid_until": TODAY + timedelta(days=15),
        },
        {
            "id": 100,
            "supplier_name": "Second Submitter",
            "unit_price": 5000.0,
            "lead_time_days": 5,
            "valid_until": TODAY + timedelta(days=15),
        },
    ]
    best = get_best_quote(base_rfq, quotes, today=TODAY)
    assert best is not None
    assert best["id"] == 99


def test_zero_lead_time_in_stock(base_rfq):
    """Lead time of 0 (in-stock item) arrives today and qualifies."""
    quote = {
        "id": 88,
        "supplier_name": "Immediate Off-The-Shelf Spares",
        "unit_price": 6000.0,
        "lead_time_days": 0,
        "valid_until": TODAY + timedelta(days=5),
    }
    best = get_best_quote(base_rfq, [quote], today=TODAY)
    assert best is not None
    assert calculate_arrival_date(0, TODAY) == TODAY


def test_negative_lead_time_raises_error():
    """Negative lead time days must raise ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_arrival_date(-1, TODAY)


def test_string_dates_accepted_seamlessly():
    """Verify that pure ISO string dates are parsed without error."""
    rfq = {"needed_by": "2026-11-30"}
    quotes = [
        {
            "id": 1,
            "supplier_name": "ISO String Supplier",
            "unit_price": 1000.0,
            "lead_time_days": 4,
            "valid_until": "2026-12-05",
        }
    ]
    best = get_best_quote(rfq, quotes, today=TODAY)
    assert best is not None
    assert best["id"] == 1

