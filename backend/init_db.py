"""
init_db.py — create schema and seed a demo account.

Usage:
    python init_db.py            # create tables + seed demo data
    python init_db.py --schema   # create tables only, no seed
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import bcrypt
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEMO_EMAIL = "demo@store.com"
DEMO_PASSWORD = "demo1234"
DEMO_STORE = "Green Valley Market"


def get_conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("ERROR: DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return psycopg2.connect(dsn)


def create_schema(conn):
    sql = SCHEMA_PATH.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Schema applied.")


def seed_demo(conn):
    with conn.cursor() as cur:
        # Check if demo user already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (DEMO_EMAIL,))
        row = cur.fetchone()
        if row:
            print(f"Demo user '{DEMO_EMAIL}' already exists — skipping seed.")
            return
        user_id = _insert_user(cur)
        vendor_ids = _insert_vendors(cur, user_id)
        _insert_agreed_costs(cur, user_id, vendor_ids)
        _insert_promotions(cur, user_id, vendor_ids)
        _insert_vendor_notices(cur, user_id, vendor_ids)
        invoice_id = _insert_demo_invoice(cur, user_id, vendor_ids)
        _insert_discrepancies(cur, user_id, invoice_id)
        _insert_pending_actions(cur, user_id, invoice_id)
    conn.commit()
    print(f"Demo account seeded: {DEMO_EMAIL} / {DEMO_PASSWORD}")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _insert_user(cur) -> int:
    pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        "INSERT INTO users (email, password_hash, store_name) VALUES (%s, %s, %s) RETURNING id",
        (DEMO_EMAIL, pw_hash, DEMO_STORE),
    )
    return cur.fetchone()[0]


def _insert_vendors(cur, user_id: int) -> dict:
    vendors = [
        ("Lakeshore Beverages", "LSB-0042", "Net 30. Deposits: $0.10/bottle. Fuel surcharge 1.5% on orders under $500."),
        ("Summit Foods", "SF-1187", "Net 14. No substitutions without prior approval. Price changes require 30-day notice."),
    ]
    ids = {}
    for name, account_no, terms in vendors:
        cur.execute(
            "INSERT INTO vendors (user_id, name, account_no, terms) VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, name, account_no, terms),
        )
        ids[name] = cur.fetchone()[0]
    return ids


def _insert_agreed_costs(cur, user_id: int, vendor_ids: dict):
    lsb = vendor_ids["Lakeshore Beverages"]
    sf = vendor_ids["Summit Foods"]
    costs = [
        (user_id, lsb, "LB-SPARKLING-12", "Sparkling Water 12-pk",    "case", 12,  8.40),
        (user_id, lsb, "LB-STILL-24",     "Still Water 24-pk",         "case", 24,  6.00),
        (user_id, lsb, "LB-OJ-6",         "Orange Juice 6-pk",         "case",  6, 11.50),
        (user_id, lsb, "LB-DEPOSIT",      "Bottle Deposit",            "bottle", 1,  0.10),
        (user_id, sf,  "SF-BREAD-WW",     "Whole Wheat Bread",         "loaf",   1,  2.85),
        (user_id, sf,  "SF-CHIPS-BBQ",    "BBQ Chips 1oz",             "bag",    1,  0.75),
        (user_id, sf,  "SF-CHIPS-PLAIN",  "Plain Chips 1oz",           "bag",    1,  0.72),
        (user_id, sf,  "SF-GRANOLA-16",   "Granola 16oz",              "bag",    1,  4.20),
    ]
    cur.executemany(
        "INSERT INTO agreed_costs (user_id, vendor_id, item_code, description, unit, pack_size, cost) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        costs,
    )


def _insert_promotions(cur, user_id: int, vendor_ids: dict):
    lsb = vendor_ids["Lakeshore Beverages"]
    today = date.today()
    cur.execute(
        "INSERT INTO promotions (user_id, vendor_id, item_code, description, allowance_per_case, start_date, end_date) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (user_id, lsb, "LB-SPARKLING-12", "Fall display allowance", 1.20,
         today - timedelta(days=10), today + timedelta(days=20)),
    )


def _insert_vendor_notices(cur, user_id: int, vendor_ids: dict):
    sf = vendor_ids["Summit Foods"]
    cur.execute(
        "INSERT INTO vendor_notices (user_id, vendor_id, notice_date, subject, body) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, sf, date.today() - timedelta(days=5),
         "Price update: BBQ Chips",
         "Effective immediately, BBQ Chips 1oz (SF-CHIPS-BBQ) will be priced at $0.80/bag "
         "due to increased commodity costs. All invoices dated on or after today reflect the new price."),
    )


def _insert_demo_invoice(cur, user_id: int, vendor_ids: dict) -> int:
    lsb = vendor_ids["Lakeshore Beverages"]
    invoice_date = date.today() - timedelta(days=2)
    # Stated total is intentionally correct so the invoice reaches 'checked'
    cur.execute(
        "INSERT INTO invoices (user_id, vendor_id, invoice_number, invoice_date, total, status, image_path) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (user_id, lsb, "LSB-20261101", invoice_date, 162.60, "checked", None),
    )
    invoice_id = cur.fetchone()[0]

    lines = [
        # (invoice_id, line_type, item_code, description, qty, unit, unit_price, line_total, note)
        (invoice_id, "item",    "LB-SPARKLING-12", "Sparkling Water 12-pk", 10, "case",  9.00, 90.00, "rec'd 10"),
        (invoice_id, "item",    "LB-STILL-24",     "Still Water 24-pk",      8, "case",  6.00, 48.00, "rec'd 8"),
        (invoice_id, "item",    "LB-OJ-6",         "Orange Juice 6-pk",      2, "case", 11.50, 23.00, "rec'd 2"),
        # Deposit line
        (invoice_id, "deposit", "LB-DEPOSIT",      "Bottle Deposit",        48, "bottle", 0.10,  4.80, None),
        # Promo credit is missing — discrepancy will be flagged
        # Fuel surcharge fee
        (invoice_id, "fee",     None,              "Fuel Surcharge",         1, None,    None,  2.80, None),
        # Arithmetic error: 10 * 9.00 = 90.00 is fine; total doesn't match sum to demonstrate needs_review path
        # (kept consistent here so status = 'checked')
    ]
    cur.executemany(
        "INSERT INTO invoice_lines (invoice_id, line_type, item_code, description, quantity, unit, unit_price, line_total, handwritten_note) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        lines,
    )
    return invoice_id


def _insert_discrepancies(cur, user_id: int, invoice_id: int):
    discrepancies = [
        # price mismatch: agreed $8.40, billed $9.00 × 10 cases = $6.00 overcharge
        (user_id, invoice_id, "price",     "LB-SPARKLING-12",  6.00, "open", None),
        # promo not applied: $1.20/case × 10 cases = $12.00 missing credit
        (user_id, invoice_id, "promotion", "LB-SPARKLING-12", 12.00, "open", None),
    ]
    cur.executemany(
        "INSERT INTO discrepancies (user_id, invoice_id, type, item_code, amount, status, explanation) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        discrepancies,
    )


def _insert_pending_actions(cur, user_id: int, invoice_id: int):
    import json
    actions = [
        (
            user_id, invoice_id, "dispute",
            json.dumps({
                "vendor_id": None,  # resolved at runtime; placeholder for demo
                "items": ["LB-SPARKLING-12"],
                "message": (
                    "Dear Lakeshore Beverages,\n\n"
                    "Invoice LSB-20261101 shows Sparkling Water 12-pk at $9.00/case. "
                    "Our agreed cost is $8.40/case. On 10 cases this is a $6.00 overcharge. "
                    "Please issue a corrected invoice or credit memo.\n\n"
                    "Regards,\nGreen Valley Market"
                ),
            }),
            "pending",
        ),
        (
            user_id, invoice_id, "cost_update",
            json.dumps({
                "item_code": "LB-SPARKLING-12",
                "new_cost": 9.00,
                "evidence": "Invoiced at $9.00/case on LSB-20261101. Verify against current price list before approving.",
            }),
            "pending",
        ),
    ]
    cur.executemany(
        "INSERT INTO pending_actions (user_id, invoice_id, action_type, details, status) "
        "VALUES (%s, %s, %s, %s, %s)",
        actions,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    schema_only = "--schema" in sys.argv
    conn = get_conn()
    try:
        create_schema(conn)
        if not schema_only:
            seed_demo(conn)
    finally:
        conn.close()
