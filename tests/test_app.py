"""
Integration tests for Quote Desk Flask Web Application.
"""

import os
from datetime import date, timedelta
import pytest
from app import app
import db

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_quote_desk.db")


@pytest.fixture
def client():
    """Create a Flask test client with an isolated temporary SQLite database."""
    app.config["TESTING"] = True

    # Remove any existing test db
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass

    # Point DB_FILE to TEST_DB_PATH
    original_db = db.DB_FILE
    db.DB_FILE = TEST_DB_PATH

    # Initialize schema and demo seed data
    db.init_db(TEST_DB_PATH)
    db.seed_demo_data(TEST_DB_PATH, force=True)

    with app.test_client() as client:
        yield client

    # Cleanup
    db.DB_FILE = original_db
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass


def test_index_dashboard_loads(client):
    """Verify that index dashboard loads with status 200 and displays RFQs."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Quote Desk" in html
    assert "Aerospace RFQ" in html
    assert "JA-TI-9022" in html  # Seed RFQ
    assert "JA-TRB-7810" in html  # Seed RFQ


def test_rfq_detail_page_loads(client):
    """Verify RFQ detail page loads with specs and quote spotlight."""
    rfqs = db.get_all_rfqs(TEST_DB_PATH)
    assert len(rfqs) > 0
    # Find the turbine RFQ
    trb_rfq = next(r for r in rfqs if r["part_number"] == "JA-TRB-7810")

    response = client.get(f"/rfq/{trb_rfq['id']}")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "High-Pressure Turbine" in html
    # Check that best quote winner is displayed
    assert "AeroPrecision Dynamics" in html


def test_create_rfq_via_post(client):
    """Verify creating a new RFQ via form POST."""
    target_date = (date.today() + timedelta(days=20)).isoformat()
    response = client.post(
        "/rfq/create",
        data={
            "part_number": "JA-WING-1001",
            "description": "Carbon Fiber Wingtip Fairing",
            "quantity": "50",
            "needed_by": target_date,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "JA-WING-1001" in html
    assert "Carbon Fiber Wingtip Fairing" in html


def test_add_quote_via_post(client):
    """Verify submitting a supplier quote for an RFQ."""
    rfqs = db.get_all_rfqs(TEST_DB_PATH)
    open_rfq = next(r for r in rfqs if r["part_number"] == "JA-TI-9022")

    valid_until = (date.today() + timedelta(days=30)).isoformat()
    response = client.post(
        f"/rfq/{open_rfq['id']}/quote",
        data={
            "supplier_name": "Titan Precision Fasteners Ltd",
            "unit_price": "245.50",
            "lead_time_days": "5",
            "valid_until": valid_until,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Titan Precision Fasteners Ltd" in html
    assert "245.50" in html


def test_api_rfqs_json_endpoint(client):
    """Verify REST API endpoint returns valid JSON."""
    response = client.get("/api/rfqs")
    assert response.status_code == 200
    data = response.get_json()
    assert "rfqs" in data
    assert data["count"] >= 4
    # Check enriched fields
    rfq0 = data["rfqs"][0]
    assert "status" in rfq0
    assert rfq0["status"] in ["Open", "Quoted", "Expired"]
