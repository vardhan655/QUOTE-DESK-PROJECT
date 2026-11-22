# Quote Desk ✈️

> **Production-grade Request for Quotation (RFQ) and Supplier Quote Management System for Aerospace Procurement.**

Quote Desk is a clean, interview-focused full-stack web application designed to evaluate supplier quotations against engineering delivery deadlines and validity periods, automatically determining RFQ status and highlighting the **"BEST"** winning quote.

---

## 🛠️ Architecture & Tech Stack

The architecture emphasizes **simplicity, readability, and clean separation of concerns** so that any part of the domain logic or web layer can be easily explained, extended, or live-refactored during technical interviews:

```
jane_aerospace/
├── app.py                  # Flask web controller, routes, filters & REST API
├── db.py                   # SQLite persistence layer (schema, queries, dynamic seed)
├── logic.py                # Pure domain logic (status evaluation & best-quote algorithm)
├── requirements.txt        # Minimal dependencies (Flask, pytest)
├── quote_desk.db           # Zero-config SQLite database (auto-created on startup)
├── templates/
│   ├── base.html           # Layout with Tailwind CSS CDN, header, nav, & modal
│   ├── index.html          # RFQ dashboard, metrics cards, filters & summary table
│   └── rfq_detail.html     # Detail view, Best Quote spotlight, quote table & live calculator
├── static/
│   ├── css/style.css       # Clean aesthetics and custom styling
│   └── js/main.js          # Modal toggles and real-time quote preview calculator
└── tests/
    ├── __init__.py
    ├── test_quote_logic.py # 18 unit tests covering all core logic edge cases
    └── test_app.py         # 5 integration tests covering routes and REST API
```

- **Backend:** Python 3 + Flask 3. Lightweight, standard, and understandable with zero ORM abstraction overhead.
- **Database:** Local SQLite (`quote_desk.db`) via Python's standard `sqlite3` module. Supports foreign keys (`PRAGMA foreign_keys = ON;`) and WAL mode for zero-setup ACID persistence.
- **Frontend:** Jinja2 server-rendered templates styled with Tailwind CSS (via CDN) and reactive client-side JavaScript for live order total and arrival date calculation. Runs with **one command** with no `npm` or build pipeline required.
- **Testing:** `pytest` test suite with 23 unit and integration tests passing in ~0.3s.

---

## 🚀 Quickstart & Run Instructions

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14)
- `pip`

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python app.py
```
Open your browser to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

*Note: On startup, Quote Desk automatically initializes the SQLite schema and seeds 4 realistic aerospace RFQs with dynamic dates relative to today.*

### 4. Run the Test Suite
```bash
python -m pytest -v
```
To run only unit tests for core domain logic:
```bash
python -m pytest tests/test_quote_logic.py -v
```

---

## 📐 Key Domain Assumptions

### 1. Estimated Arrival Date (`today + lead_time_days`)
- **Assumption:** Arrival date is computed as `Order Date (today) + lead_time_days`.
- **Calendar Day Precision:** Lead times represent contiguous calendar days (consistent with standard Tier-1 aerospace RFQ initial screening conventions).
- **Injection for Determinism:** All business logic functions in `logic.py` accept an optional `today: date` argument. If not provided, it defaults to `date.today()`. This allows 100% deterministic unit testing across any reference date without monkeypatching system time.

### 2. Date Boundaries (Inclusive of `today`)
- **Quote Validity:** `valid_until >= today`. A quote expiring today is considered valid throughout the business day.
- **Delivery Deadline:** `arrival_date <= needed_by`. A quote arriving on the exact day of `needed_by` qualifies as on-time.
- **RFQ Needed-By Boundary:** An RFQ whose `needed_by == today` is still considered active on that day. If `needed_by < today`, the RFQ is expired.

### 3. Status Evaluation Logic & Precedence
The RFQ status is dynamically evaluated via `calculate_rfq_status(rfq, quotes, today)` in `logic.py` in the following strict order:

```
                    ┌───────────────────────────┐
                    │  needed_by < today?       │─── YES ───►  EXPIRED
                    └─────────────┬─────────────┘
                                  │ NO
                    ┌─────────────▼─────────────┐
                    │  0 quotes received?       │─── YES ───►  OPEN
                    └─────────────┬─────────────┘
                                  │ NO
                    ┌─────────────▼─────────────┐
                    │  Are ALL quotes expired?  │─── YES ───►  EXPIRED
                    │  (valid_until < today)    │
                    └─────────────┬─────────────┘
                                  │ NO
                                  ▼
                               QUOTED
```

1. **`Expired` (Deadline Lapsed):** If `needed_by < today`, the RFQ is expired regardless of quotes.
2. **`Open`:** If `needed_by >= today` and the RFQ has **0 quotes**.
3. **`Expired` (All Quotes Lapsed):** If the RFQ has quotes, but **every quote** has `valid_until < today`.
4. **`Quoted`:** If `needed_by >= today` and **at least one quote** has `valid_until >= today`.

### 4. "BEST" Quote Selection Criteria
Isolated in `get_best_quote(rfq, quotes, today)` in `logic.py`:
1. **Validity:** Must have `valid_until >= today`.
2. **On-Time Delivery:** Must satisfy `today + lead_time_days <= needed_by`.
3. **Lowest Unit Price:** Lowest `unit_price` among qualifying bids.
4. **Tie-Breaker 1:** Shortest `lead_time_days`.
5. **Tie-Breaker 2:** Lowest quote ID (earlier submission).

> **Crucial Rule:** A cheaper quote that arrives late or is expired is **disqualified** and will never be selected as best. If quotes exist but none qualify, the UI displays a clear notice with the exact disqualification reasons (e.g., *"Exceeds deadline by 6 days"* or *"Expired on 2026-11-16"*).

---

## 🗄️ Why SQLite?

1. **Zero-Config File Persistence:** Unlike PostgreSQL or MySQL, SQLite requires no external server process, credentials, or container setup. The database persists cleanly in `quote_desk.db` across server restarts.
2. **ACID Compliant:** Ensures atomic transactions and referential integrity via foreign key cascades (`PRAGMA foreign_keys = ON;`).
3. **Interview-Friendly:** Uses standard SQL queries with parameterized statements (no SQL injection vulnerabilities). There is no hidden ORM magic, lazy-loading gotchas, or complex migration tooling to troubleshoot during a live demo.
4. **Fast and Lightweight:** In-memory or local disk operations execute in microseconds, allowing our entire test suite to run in under 0.35 seconds.

---

## 🧪 Realistic Demo Seed Data

On startup (or via the **"Reset Seed Data"** button in the header), the application seeds 4 realistic aerospace RFQs demonstrating each status and edge case:

| Part Number | Description | Qty | Deadline | State | Demonstration Value |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **JA-TI-9022** | Titanium Gr 5 Hex Flange Bolts (NAS6704-12) | 500 | +14 days | **Open** | 0 quotes submitted; ready for new bids. |
| **JA-TRB-7810** | HP Turbine Shroud Seal Rings (Inconel 718) | 24 | +10 days | **Quoted** | **Cheaper-but-Late vs. Best:** Skyline Budget bid ₹18,500 arrives in 16d (disqualified for being late); AeroPrecision bid ₹24,000 arrives in 7d (wins). |
| **JA-AV-3104** | Cockpit MFD Wiring Harness (MIL-DTL-38999) | 12 | +15 days | **Quoted** | **Tie-Breaker & Expired Quote:** Apex bid ₹42,000 is expired; Vayu Systems and Hindustan bid identical ₹48,000, and Vayu wins via shorter lead time (6d vs 10d). |
| **JA-HYD-5501** | Electro-Hydraulic Servo Valve Body | 10 | -5 days | **Expired** | RFQ deadline passed; procurement period elapsed. |

---

## 🔮 What I Would Do Next (With One More Day)

1. **Multi-Currency & Tax/Duties Handling:** Support quotes in USD, EUR, and INR with exchange rate conversions, freight costs, and GST/customs duty calculations.
2. **RFQ Revision & Quote Amendment History:** Implement an immutable audit log tracking revisions to part requirements or revised supplier quotes over time.
3. **Supplier Master Directory & Ratings:** Maintain a verified supplier directory with historical on-time delivery (OTD) scores, quality ratings (AS9100 / ISO 9001 certifications), and contact management.
4. **Side-by-Side Quote Comparison Matrix:** Interactive matrix view plotting quotes along Price vs. Lead Time Pareto frontiers.
5. **PDF Export & Purchase Order Generation:** One-click generation of formalized Purchase Orders (PO) for winning quotes.

---

## 🚫 What Was Left Out & Why

1. **Authentication & RBAC (Role-Based Access Control):** Left out to keep code accessible and focused entirely on the core procurement domain logic. Adding authentication would introduce session handling, password hashing, and user tables without adding value to the quotation screening logic.
2. **Heavy Frontend Build Tooling (npm/Webpack/Vite):** Avoided complex node-based frontend build steps. Tailwind via CDN and clean vanilla JavaScript allow the application to start with a single `python app.py` command on any clean machine.
3. **Email/Webhook Notification Services:** Omitted external email dispatchers (e.g., SendGrid/SES) to maintain zero external dependencies and ensure the app operates completely offline.
4. **Heavy ORM (Django/SQLAlchemy migrations):** Used Python's built-in `sqlite3` to ensure zero version mismatches, transparent SQL queries, and zero-configuration portability.
