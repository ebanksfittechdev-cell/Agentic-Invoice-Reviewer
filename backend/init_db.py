"""
init_db.py — create schema and seed a demo account.

Usage:
    python init_db.py            # create tables + seed demo data
    python init_db.py --schema   # create tables only, no seed
"""

import sys
from datetime import date, timedelta

import bcrypt
from dotenv import load_dotenv

load_dotenv()

DEMO_EMAIL = "demo@store.com"
DEMO_PASSWORD = "demo1234"
DEMO_STORE = "Green Valley Market"


def main():
    schema_only = "--schema" in sys.argv

    from app import create_app
    from db import db, User, Vendor, AgreedCost, Promotion, VendorNotice, Invoice, InvoiceLine, Discrepancy, PendingAction

    app = create_app()
    with app.app_context():
        db.create_all()
        print("Schema applied.")
        print(f"Database: {db.engine.url.database}")

        if not schema_only:
            _seed_demo(db, User, Vendor, AgreedCost, Promotion, VendorNotice, Invoice, InvoiceLine, Discrepancy, PendingAction)


def _seed_demo(db, User, Vendor, AgreedCost, Promotion, VendorNotice, Invoice, InvoiceLine, Discrepancy, PendingAction):
    if User.query.filter_by(email=DEMO_EMAIL).first():
        print(f"Demo user '{DEMO_EMAIL}' already exists — skipping seed.")
        return

    # User
    pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    user = User(email=DEMO_EMAIL, password_hash=pw_hash, store_name=DEMO_STORE)
    db.session.add(user)
    db.session.flush()  # get user.id before inserting dependents

    # Vendors
    lsb = Vendor(
        user_id=user.id,
        name="Lakeshore Beverages",
        account_no="LSB-0042",
        terms="Net 30. Deposits: $0.10/bottle. Fuel surcharge 1.5% on orders under $500.",
    )
    sf = Vendor(
        user_id=user.id,
        name="Summit Foods",
        account_no="SF-1187",
        terms="Net 14. No substitutions without prior approval. Price changes require 30-day notice.",
    )
    db.session.add_all([lsb, sf])
    db.session.flush()

    # Agreed costs
    db.session.add_all([
        AgreedCost(user_id=user.id, vendor_id=lsb.id, item_code="LB-SPARKLING-12", description="Sparkling Water 12-pk", unit="case", pack_size=12, cost=8.40),
        AgreedCost(user_id=user.id, vendor_id=lsb.id, item_code="LB-STILL-24",     description="Still Water 24-pk",     unit="case", pack_size=24, cost=6.00),
        AgreedCost(user_id=user.id, vendor_id=lsb.id, item_code="LB-OJ-6",         description="Orange Juice 6-pk",     unit="case", pack_size=6,  cost=11.50),
        AgreedCost(user_id=user.id, vendor_id=lsb.id, item_code="LB-DEPOSIT",      description="Bottle Deposit",        unit="bottle", pack_size=1, cost=0.10),
        AgreedCost(user_id=user.id, vendor_id=sf.id,  item_code="SF-BREAD-WW",     description="Whole Wheat Bread",     unit="loaf",   pack_size=1, cost=2.85),
        AgreedCost(user_id=user.id, vendor_id=sf.id,  item_code="SF-CHIPS-BBQ",    description="BBQ Chips 1oz",         unit="bag",    pack_size=1, cost=0.75),
        AgreedCost(user_id=user.id, vendor_id=sf.id,  item_code="SF-CHIPS-PLAIN",  description="Plain Chips 1oz",       unit="bag",    pack_size=1, cost=0.72),
        AgreedCost(user_id=user.id, vendor_id=sf.id,  item_code="SF-GRANOLA-16",   description="Granola 16oz",          unit="bag",    pack_size=1, cost=4.20),
    ])

    # Active promotion (Lakeshore sparkling water display allowance)
    today = date.today()
    db.session.add(Promotion(
        user_id=user.id, vendor_id=lsb.id,
        item_code="LB-SPARKLING-12",
        description="Fall display allowance",
        allowance_per_case=1.20,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=20),
    ))

    # Vendor notice (Summit Foods price update)
    db.session.add(VendorNotice(
        user_id=user.id, vendor_id=sf.id,
        notice_date=today - timedelta(days=5),
        subject="Price update: BBQ Chips",
        body=(
            "Effective immediately, BBQ Chips 1oz (SF-CHIPS-BBQ) will be priced at $0.80/bag "
            "due to increased commodity costs. All invoices dated on or after today reflect the new price."
        ),
    ))

    db.session.flush()

    # Demo invoice (Lakeshore, two open discrepancies)
    invoice_date = today - timedelta(days=2)
    invoice = Invoice(
        user_id=user.id, vendor_id=lsb.id,
        invoice_number="LSB-20261101",
        invoice_date=invoice_date,
        total=162.60,
        status="checked",
        image_path=None,
    )
    db.session.add(invoice)
    db.session.flush()

    db.session.add_all([
        InvoiceLine(invoice_id=invoice.id, line_type="item",    item_code="LB-SPARKLING-12", description="Sparkling Water 12-pk", quantity=10, unit="case",   unit_price=9.00,  line_total=90.00, handwritten_note="rec'd 10"),
        InvoiceLine(invoice_id=invoice.id, line_type="item",    item_code="LB-STILL-24",     description="Still Water 24-pk",     quantity=8,  unit="case",   unit_price=6.00,  line_total=48.00, handwritten_note="rec'd 8"),
        InvoiceLine(invoice_id=invoice.id, line_type="item",    item_code="LB-OJ-6",         description="Orange Juice 6-pk",     quantity=2,  unit="case",   unit_price=11.50, line_total=23.00, handwritten_note="rec'd 2"),
        InvoiceLine(invoice_id=invoice.id, line_type="deposit", item_code="LB-DEPOSIT",      description="Bottle Deposit",        quantity=48, unit="bottle", unit_price=0.10,  line_total=4.80,  handwritten_note=None),
        InvoiceLine(invoice_id=invoice.id, line_type="fee",     item_code=None,              description="Fuel Surcharge",        quantity=1,  unit=None,     unit_price=None,  line_total=2.80,  handwritten_note=None),
    ])

    # Discrepancies: price overcharge + missing promo credit
    db.session.add_all([
        Discrepancy(user_id=user.id, invoice_id=invoice.id, type="price",     item_code="LB-SPARKLING-12", amount=6.00,  status="open", explanation=None),
        Discrepancy(user_id=user.id, invoice_id=invoice.id, type="promotion", item_code="LB-SPARKLING-12", amount=12.00, status="open", explanation=None),
    ])
    db.session.flush()

    # Pending actions for demo (pre-populated as if agent already ran)
    db.session.add_all([
        PendingAction(
            user_id=user.id, invoice_id=invoice.id,
            action_type="dispute",
            details={
                "vendor_id": lsb.id,
                "items": ["LB-SPARKLING-12"],
                "message": (
                    "Dear Lakeshore Beverages,\n\n"
                    "Invoice LSB-20261101 shows Sparkling Water 12-pk at $9.00/case. "
                    "Our agreed cost is $8.40/case. On 10 cases this is a $6.00 overcharge. "
                    "Please issue a corrected invoice or credit memo.\n\n"
                    "Regards,\nGreen Valley Market"
                ),
            },
            status="pending",
        ),
        PendingAction(
            user_id=user.id, invoice_id=invoice.id,
            action_type="cost_update",
            details={
                "item_code": "LB-SPARKLING-12",
                "new_cost": 9.00,
                "evidence": "Invoiced at $9.00/case on LSB-20261101. Verify against current price list before approving.",
            },
            status="pending",
        ),
    ])

    db.session.commit()
    print(f"Demo account seeded: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
