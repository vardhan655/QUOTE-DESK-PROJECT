"""
Quote Desk - Core Business Logic Module

This module contains pure, deterministic domain functions for Request for Quotation (RFQ)
status determination and Best Quote selection.

Separation of Concerns:
- Zero database or web framework dependencies.
- Every function accepts an optional `today` parameter (defaults to date.today())
  to enable deterministic, edge-case unit testing without clock mocking.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union


def parse_date(value: Union[str, date, datetime]) -> date:
    """
    Safely normalize date input into a datetime.date instance.
    Accepts ISO-formatted strings (YYYY-MM-DD), date, or datetime objects.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # Handle string YYYY-MM-DD
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    raise ValueError(f"Cannot parse date from value: {value!r}")


def calculate_arrival_date(lead_time_days: int, today: Optional[date] = None) -> date:
    """
    Calculate estimated arrival date based on supplier lead time.

    Assumption:
        Arrival Date = Order Date (today) + Lead Time (in days).
        We assume order placement occurs today (calendar day precision, non-business-day
        agnostic, matching standard aerospace initial RFQ screening conventions).
    """
    ref_today = today or date.today()
    if lead_time_days < 0:
        raise ValueError("Lead time cannot be negative.")
    return ref_today + timedelta(days=lead_time_days)


def is_quote_valid(quote: Dict[str, Any], today: Optional[date] = None) -> bool:
    """
    Check if a quote is currently valid (valid_until >= today).
    Assumption: Dates are inclusive; a quote valid until today is still valid throughout today.
    """
    ref_today = today or date.today()
    valid_until = parse_date(quote["valid_until"])
    return valid_until >= ref_today


def does_quote_meet_deadline(
    quote: Dict[str, Any], needed_by: Union[str, date], today: Optional[date] = None
) -> bool:
    """
    Check if a quote's goods will arrive on or before the RFQ's needed_by deadline.
    Condition: today + timedelta(days=lead_time_days) <= needed_by (inclusive).
    """
    ref_today = today or date.today()
    target_needed_by = parse_date(needed_by)
    arrival = calculate_arrival_date(int(quote["lead_time_days"]), ref_today)
    return arrival <= target_needed_by


def evaluate_quote_eligibility(
    quote: Dict[str, Any], needed_by: Union[str, date], today: Optional[date] = None
) -> Tuple[bool, List[str]]:
    """
    Evaluate why a quote is eligible or disqualified for 'Best Quote' consideration.
    Returns:
        (is_eligible, reasons_if_disqualified)
    """
    ref_today = today or date.today()
    reasons: List[str] = []

    valid = is_quote_valid(quote, ref_today)
    if not valid:
        valid_until = parse_date(quote["valid_until"])
        reasons.append(f"Quote expired on {valid_until.isoformat()} (prior to today {ref_today.isoformat()})")

    meets_deadline = does_quote_meet_deadline(quote, needed_by, ref_today)
    if not meets_deadline:
        arrival = calculate_arrival_date(int(quote["lead_time_days"]), ref_today)
        target = parse_date(needed_by)
        days_late = (arrival - target).days
        reasons.append(
            f"Estimated arrival ({arrival.isoformat()}) exceeds deadline ({target.isoformat()}) by {days_late} day(s)"
        )

    is_eligible = valid and meets_deadline
    return is_eligible, reasons


def calculate_rfq_status(
    rfq: Dict[str, Any], quotes: List[Dict[str, Any]], today: Optional[date] = None
) -> str:
    """
    Compute RFQ status strictly following the business specification.

    Status Evaluation Precedence & Rules:
    1. EXPIRED (by deadline):
       If the RFQ's needed_by date has passed (needed_by < today), the RFQ is EXPIRED.
       (Even if quotes exist, an RFQ whose need date has lapsed can no longer accept orders).

    2. OPEN:
       If needed_by >= today AND the RFQ has 0 quotes, it is OPEN.

    3. EXPIRED (by quotes expiry):
       If the RFQ has at least 1 quote, AND EVERY quote has expired (valid_until < today),
       it is EXPIRED.

    4. QUOTED:
       If needed_by >= today AND at least one quote is currently valid (valid_until >= today),
       it is QUOTED.

    Returns: 'Open' | 'Quoted' | 'Expired'
    """
    ref_today = today or date.today()
    needed_by = parse_date(rfq["needed_by"])

    # Rule 1: Deadline has passed
    if needed_by < ref_today:
        return "Expired"

    # Rule 2: No quotes submitted yet
    if not quotes:
        return "Open"

    # Evaluate quote validities
    any_quote_valid = any(is_quote_valid(q, ref_today) for q in quotes)

    # Rule 3: All existing quotes have expired
    if not any_quote_valid:
        return "Expired"

    # Rule 4: At least one quote is currently valid and needed_by >= today
    return "Quoted"


def get_best_quote(
    rfq: Dict[str, Any], quotes: List[Dict[str, Any]], today: Optional[date] = None
) -> Optional[Dict[str, Any]]:
    """
    Select the BEST quote for an RFQ based on explicit criteria.

    Criteria for BEST quote:
    1. Quote is still valid (`valid_until >= today`).
    2. Quote can arrive on or before deadline (`today + lead_time_days <= needed_by`).
    3. Lowest `unit_price` among qualifying quotes.
    4. Tie-breaker: Shortest `lead_time_days`.
    5. Secondary tie-breaker: Earlier quote creation/ID.

    A cheaper quote that arrives after `needed_by` or is expired MUST NOT be selected.
    If no quotes meet both validity and delivery criteria, returns None.
    """
    if not quotes:
        return None

    ref_today = today or date.today()
    needed_by = parse_date(rfq["needed_by"])

    # Filter strictly for eligible quotes
    eligible_quotes = []
    for q in quotes:
        eligible, _ = evaluate_quote_eligibility(q, needed_by, ref_today)
        if eligible:
            eligible_quotes.append(q)

    if not eligible_quotes:
        return None

    # Sort qualifying quotes:
    # 1. unit_price ascending (float)
    # 2. lead_time_days ascending (int)
    # 3. quote id ascending (fallback deterministic tie-breaker)
    best = min(
        eligible_quotes,
        key=lambda q: (
            float(q["unit_price"]),
            int(q["lead_time_days"]),
            int(q.get("id") or 0),
        ),
    )
    return best
