"""
Quote Desk - Flask Application
Web interface for RFQ and Supplier Quote management.
"""

import os
from datetime import date, datetime
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

import db
from logic import (
    calculate_arrival_date,
    calculate_rfq_status,
    evaluate_quote_eligibility,
    get_best_quote,
    parse_date,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "quote-desk-aerospace-secret-key-2026")

# Ensure DB is initialized and seeded on app startup
db.init_db()
db.seed_demo_data()


# ==============================================================================
# Jinja Template Filters
# ==============================================================================

@app.template_filter("inr")
def format_inr(value: float) -> str:
    """Format float into Indian Rupee string with symbol: ₹ 1,23,456.00"""
    try:
        val = float(value)
        # Format as standard currency with two decimals
        return f"₹ {val:,.2f}"
    except (ValueError, TypeError):
        return str(value)


@app.template_filter("human_date")
def format_human_date(value: str) -> str:
    """Format ISO date string (YYYY-MM-DD) into readable format (e.g. 20 Nov 2026)."""
    try:
        dt = parse_date(value)
        return dt.strftime("%d %b %Y")
    except Exception:
        return str(value)


# ==============================================================================
# Helper Services
# ==============================================================================

def enrich_rfq_summary(rfq: dict, today: date = None) -> dict:
    """Enrich an RFQ with computed status, quote count, and best quote preview."""
    ref_today = today or date.today()
    quotes = db.get_quotes_for_rfq(rfq["id"])
    status = calculate_rfq_status(rfq, quotes, ref_today)
    best_quote = get_best_quote(rfq, quotes, ref_today)

    if best_quote:
        best_quote = {
            **best_quote,
            "total_price": float(best_quote["unit_price"]) * int(rfq["quantity"]),
            "arrival_date": calculate_arrival_date(best_quote["lead_time_days"], ref_today).isoformat(),
        }

    needed_by_dt = parse_date(rfq["needed_by"])
    days_remaining = (needed_by_dt - ref_today).days

    return {
        **rfq,
        "status": status,
        "quote_count": len(quotes),
        "best_quote": best_quote,
        "days_remaining": days_remaining,
    }


def enrich_rfq_detail(rfq: dict, today: date = None) -> dict:
    """Enrich an RFQ and all its quotes with computed eligibility, totals, and best quote."""
    ref_today = today or date.today()
    quotes = db.get_quotes_for_rfq(rfq["id"])
    status = calculate_rfq_status(rfq, quotes, ref_today)
    raw_best_quote = get_best_quote(rfq, quotes, ref_today)

    enriched_quotes = []
    for q in quotes:
        arrival_date = calculate_arrival_date(q["lead_time_days"], ref_today)
        is_eligible, reasons = evaluate_quote_eligibility(q, rfq["needed_by"], ref_today)
        is_best = bool(raw_best_quote and q["id"] == raw_best_quote["id"])
        total_price = float(q["unit_price"]) * int(rfq["quantity"])

        enriched_quotes.append({
            **q,
            "total_price": total_price,
            "arrival_date": arrival_date.isoformat(),
            "is_eligible": is_eligible,
            "disqualification_reasons": reasons,
            "is_best": is_best,
        })

    best_enriched_quote = next((q for q in enriched_quotes if q["is_best"]), None)
    needed_by_dt = parse_date(rfq["needed_by"])
    days_remaining = (needed_by_dt - ref_today).days

    return {
        "rfq": {
            **rfq,
            "status": status,
            "days_remaining": days_remaining,
        },
        "quotes": enriched_quotes,
        "best_quote": best_enriched_quote,
        "total_quotes": len(quotes),
        "eligible_quotes_count": sum(1 for q in enriched_quotes if q["is_eligible"]),
    }


# ==============================================================================
# UI Web Routes
# ==============================================================================

@app.route("/")
def index():
    """Dashboard view listing all RFQs with filter and metrics."""
    status_filter = request.args.get("status", "all").strip().capitalize()
    search_query = request.args.get("q", "").strip().lower()

    raw_rfqs = db.get_all_rfqs()
    all_rfqs = [enrich_rfq_summary(r) for r in raw_rfqs]

    # Metrics
    metrics = {
        "total": len(all_rfqs),
        "open": sum(1 for r in all_rfqs if r["status"] == "Open"),
        "quoted": sum(1 for r in all_rfqs if r["status"] == "Quoted"),
        "expired": sum(1 for r in all_rfqs if r["status"] == "Expired"),
    }

    # Filter by status
    filtered_rfqs = all_rfqs
    if status_filter in ["Open", "Quoted", "Expired"]:
        filtered_rfqs = [r for r in filtered_rfqs if r["status"] == status_filter]

    # Search filter by part number or description
    if search_query:
        filtered_rfqs = [
            r for r in filtered_rfqs
            if search_query in r["part_number"].lower() or search_query in r["description"].lower()
        ]

    return render_template(
        "index.html",
        rfqs=filtered_rfqs,
        metrics=metrics,
        current_filter=status_filter,
        search_query=search_query,
        today=date.today().isoformat(),
    )


@app.route("/rfq/<int:rfq_id>")
def rfq_detail(rfq_id: int):
    """RFQ detail page displaying specs, supplier quotes, best quote spotlight, and quote submission form."""
    raw_rfq = db.get_rfq_by_id(rfq_id)
    if not raw_rfq:
        flash(f"RFQ #{rfq_id} not found.", "error")
        return redirect(url_for("index"))

    detail = enrich_rfq_detail(raw_rfq)
    return render_template(
        "rfq_detail.html",
        rfq=detail["rfq"],
        quotes=detail["quotes"],
        best_quote=detail["best_quote"],
        total_quotes=detail["total_quotes"],
        eligible_quotes_count=detail["eligible_quotes_count"],
        today=date.today().isoformat(),
    )


@app.route("/rfq/create", methods=["POST"])
def create_rfq_action():
    """Handle RFQ creation form submission."""
    part_number = request.form.get("part_number", "").strip().upper()
    description = request.form.get("description", "").strip()
    quantity_raw = request.form.get("quantity", "").strip()
    needed_by = request.form.get("needed_by", "").strip()

    # Form validation
    errors = []
    if not part_number:
        errors.append("Part number is required.")
    if not description:
        errors.append("Part description is required.")

    try:
        quantity = int(quantity_raw)
        if quantity <= 0:
            errors.append("Quantity must be a positive integer (> 0).")
    except (ValueError, TypeError):
        errors.append("Quantity must be a valid whole number.")

    try:
        target_date = parse_date(needed_by)
    except Exception:
        errors.append("Needed By must be a valid date in YYYY-MM-DD format.")

    if errors:
        for err in errors:
            flash(err, "error")
        return redirect(url_for("index"))

    rfq_id = db.create_rfq(
        part_number=part_number,
        description=description,
        quantity=quantity,
        needed_by=needed_by,
    )

    flash(f"RFQ #{rfq_id} for '{part_number}' successfully created!", "success")
    return redirect(url_for("rfq_detail", rfq_id=rfq_id))


@app.route("/rfq/<int:rfq_id>/quote", methods=["POST"])
def create_quote_action(rfq_id: int):
    """Handle Supplier Quote submission for an RFQ."""
    raw_rfq = db.get_rfq_by_id(rfq_id)
    if not raw_rfq:
        flash(f"RFQ #{rfq_id} not found.", "error")
        return redirect(url_for("index"))

    supplier_name = request.form.get("supplier_name", "").strip()
    unit_price_raw = request.form.get("unit_price", "").strip()
    lead_time_raw = request.form.get("lead_time_days", "").strip()
    valid_until = request.form.get("valid_until", "").strip()

    errors = []
    if not supplier_name:
        errors.append("Supplier name is required.")

    try:
        unit_price = float(unit_price_raw)
        if unit_price <= 0:
            errors.append("Unit price must be greater than zero.")
    except (ValueError, TypeError):
        errors.append("Unit price must be a valid positive number.")

    try:
        lead_time_days = int(lead_time_raw)
        if lead_time_days < 0:
            errors.append("Lead time cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Lead time must be a non-negative integer.")

    try:
        parse_date(valid_until)
    except Exception:
        errors.append("Valid Until must be a valid date in YYYY-MM-DD format.")

    if errors:
        for err in errors:
            flash(err, "error")
        return redirect(url_for("rfq_detail", rfq_id=rfq_id))

    quote_id = db.create_quote(
        rfq_id=rfq_id,
        supplier_name=supplier_name,
        unit_price=unit_price,
        lead_time_days=lead_time_days,
        valid_until=valid_until,
    )

    flash(f"Quote #{quote_id} from '{supplier_name}' added successfully!", "success")
    return redirect(url_for("rfq_detail", rfq_id=rfq_id))


@app.route("/rfq/<int:rfq_id>/delete", methods=["POST"])
def delete_rfq_action(rfq_id: int):
    """Delete an RFQ."""
    deleted = db.delete_rfq(rfq_id)
    if deleted:
        flash(f"RFQ #{rfq_id} deleted successfully.", "info")
    else:
        flash(f"Could not delete RFQ #{rfq_id}.", "error")
    return redirect(url_for("index"))


@app.route("/demo/reset", methods=["POST"])
def reset_demo_data():
    """Reset database to initial realistic aerospace demo seed."""
    db.seed_demo_data(force=True)
    flash("Database reset to default aerospace demo seed data successfully!", "success")
    return redirect(url_for("index"))


# ==============================================================================
# REST API Endpoints (Useful for automation, scripting, and testing)
# ==============================================================================

@app.route("/api/rfqs", methods=["GET"])
def api_get_rfqs():
    """JSON API returning all RFQs with computed status and best quote."""
    raw_rfqs = db.get_all_rfqs()
    all_rfqs = [enrich_rfq_summary(r) for r in raw_rfqs]
    return jsonify({"rfqs": all_rfqs, "count": len(all_rfqs)})


@app.route("/api/rfq/<int:rfq_id>", methods=["GET"])
def api_get_rfq_detail(rfq_id: int):
    """JSON API returning single RFQ with enriched quotes and best quote analysis."""
    raw_rfq = db.get_rfq_by_id(rfq_id)
    if not raw_rfq:
        return jsonify({"error": f"RFQ #{rfq_id} not found"}), 404
    detail = enrich_rfq_detail(raw_rfq)
    return jsonify(detail)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Quote Desk on http://127.0.0.1:{port} ...")
    app.run(host="127.0.0.1", port=port, debug=True)
