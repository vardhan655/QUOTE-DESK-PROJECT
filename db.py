"""
Quote Desk - Database Layer (SQLite)

Zero-config file persistence using Python's standard sqlite3.
Handles schema initialization, CRUD operations, and realistic demo seed data.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_desk.db")


def _resolve_path(db_path: Optional[str] = None) -> str:
    """Resolve database path, allowing dynamic DB_FILE override."""
    return db_path if db_path is not None else DB_FILE


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection with foreign keys and Row factory."""
    path = _resolve_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize SQLite schema if tables do not exist."""
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rfqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_number TEXT NOT NULL,
                description TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                needed_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfq_id INTEGER NOT NULL REFERENCES rfqs(id) ON DELETE CASCADE,
                supplier_name TEXT NOT NULL,
                unit_price REAL NOT NULL CHECK (unit_price >= 0),
                lead_time_days INTEGER NOT NULL CHECK (lead_time_days >= 0),
                valid_until TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_quotes_rfq_id ON quotes(rfq_id);
            """
        )
        conn.commit()


def seed_demo_data(db_path: Optional[str] = None, force: bool = False) -> None:
    """
    Populate database with 4 realistic aerospace RFQs demonstrating:
    1. Open state (0 quotes, future deadline)
    2. Quoted state (Cheaper-but-late quote vs. valid on-time winning quote)
    3. Quoted state (Tie-breaker on lead time & expired quote edge case)
    4. Expired state (RFQ deadline passed)

    Note: Dates are computed relative to today so demo data remains dynamic and fresh.
    """
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0]
        if count > 0 and not force:
            return  # Already seeded

        if force:
            conn.execute("DELETE FROM quotes;")
            conn.execute("DELETE FROM rfqs;")

        today = date.today()
        now_iso = datetime.now().isoformat()

        # 1. Open RFQ
        rfq1_id = conn.execute(
            """
            INSERT INTO rfqs (part_number, description, quantity, needed_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "JA-TI-9022",
                "Titanium Grade 5 Hex Flange Bolts (NAS6704-12)",
                500,
                (today + timedelta(days=14)).isoformat(),
                now_iso,
            ),
        ).lastrowid

        # 2. Quoted RFQ (Cheaper-but-late demo)
        rfq2_id = conn.execute(
            """
            INSERT INTO rfqs (part_number, description, quantity, needed_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "JA-TRB-7810",
                "High-Pressure Turbine Stage 1 Shroud Seal Rings (Inconel 718)",
                24,
                (today + timedelta(days=10)).isoformat(),
                now_iso,
            ),
        ).lastrowid

        # Quote 2A: Cheaper by price, but arrives 6 days AFTER deadline
        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq2_id,
                "Skyline Budget Castings",
                18500.0,
                16,  # 16 days > 10 days needed_by! Disqualified
                (today + timedelta(days=30)).isoformat(),
                now_iso,
            ),
        )

        # Quote 2B: Winning quote (on-time and lowest valid price)
        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq2_id,
                "AeroPrecision Dynamics",
                24000.0,
                7,  # Arrives on time in 7 days
                (today + timedelta(days=14)).isoformat(),
                now_iso,
            ),
        )

        # Quote 2C: On-time alternative but higher price
        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq2_id,
                "Bharat Aerospace Forgings",
                27500.0,
                5,
                (today + timedelta(days=20)).isoformat(),
                now_iso,
            ),
        )

        # 3. Quoted RFQ (Tie-breaker on lead time & expired quote demo)
        rfq3_id = conn.execute(
            """
            INSERT INTO rfqs (part_number, description, quantity, needed_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "JA-AV-3104",
                "Mil-Spec Cockpit Multi-Function Display Wiring Harness (MIL-DTL-38999)",
                12,
                (today + timedelta(days=15)).isoformat(),
                now_iso,
            ),
        ).lastrowid

        # Quote 3A: Expired quote
        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq3_id,
                "Apex Avionics Spares",
                42000.0,
                4,
                (today - timedelta(days=3)).isoformat(),  # Expired
                now_iso,
            ),
        )

        # Quote 3B: Same price, 10 days lead time
        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq3_id,
                "Hindustan Aero Interconnects",
                48000.0,
                10,
                (today + timedelta(days=25)).isoformat(),
                now_iso,
            ),
        )

        # Quote 3C: Winner! Same price, 6 days lead time (tie breaker)
        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq3_id,
                "Vayu Systems Ltd",
                48000.0,
                6,
                (today + timedelta(days=21)).isoformat(),
                now_iso,
            ),
        )

        # 4. Expired RFQ (Deadline passed)
        rfq4_id = conn.execute(
            """
            INSERT INTO rfqs (part_number, description, quantity, needed_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "JA-HYD-5501",
                "Actuator Electro-Hydraulic Servo Valve Body (Stainless 15-5 PH)",
                10,
                (today - timedelta(days=5)).isoformat(),  # Deadline passed
                now_iso,
            ),
        ).lastrowid

        conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rfq4_id,
                "Delta Fluid Power",
                32000.0,
                12,
                (today - timedelta(days=6)).isoformat(),
                now_iso,
            ),
        )

        conn.commit()


# ==============================================================================
# CRUD Operations
# ==============================================================================

def create_rfq(
    part_number: str,
    description: str,
    quantity: int,
    needed_by: str,
    db_path: Optional[str] = None,
) -> int:
    """Insert a new RFQ and return its ID."""
    now_iso = datetime.now().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO rfqs (part_number, description, quantity, needed_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (part_number.strip(), description.strip(), int(quantity), needed_by.strip(), now_iso),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_rfqs(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all RFQs ordered by creation date descending."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM rfqs ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_rfq_by_id(rfq_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve an RFQ by ID."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM rfqs WHERE id = ?", (rfq_id,)
        ).fetchone()
        return dict(row) if row else None


def get_quotes_for_rfq(rfq_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all quotes for a given RFQ ordered by unit_price ascending."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM quotes 
            WHERE rfq_id = ? 
            ORDER BY unit_price ASC, lead_time_days ASC, id ASC
            """,
            (rfq_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def create_quote(
    rfq_id: int,
    supplier_name: str,
    unit_price: float,
    lead_time_days: int,
    valid_until: str,
    db_path: Optional[str] = None,
) -> int:
    """Insert a supplier quote for an RFQ and return quote ID."""
    now_iso = datetime.now().isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO quotes (rfq_id, supplier_name, unit_price, lead_time_days, valid_until, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(rfq_id),
                supplier_name.strip(),
                float(unit_price),
                int(lead_time_days),
                valid_until.strip(),
                now_iso,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def delete_rfq(rfq_id: int, db_path: Optional[str] = None) -> bool:
    """Delete an RFQ (quotes will cascade delete)."""
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM rfqs WHERE id = ?", (rfq_id,))
        conn.commit()
        return cursor.rowcount > 0
