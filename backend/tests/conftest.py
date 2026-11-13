"""
conftest.py — shared fixtures for all backend tests.

Uses an in-memory SQLite database so tests run without a Postgres instance.
Each test gets a fresh DB via function-scoped fixtures.
"""

import pytest

from app import create_app
from db import db as _db


@pytest.fixture(scope="session")
def app():
    test_app = create_app()
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="test-secret",
        UPLOAD_FOLDER="/tmp/test_invoice_uploads",
        WTF_CSRF_ENABLED=False,
    )
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture()
def db(app):
    """Yield db session; roll back after each test."""
    with app.app_context():
        yield _db
        _db.session.rollback()
        # Truncate all tables between tests
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture()
def client(app, db):
    return app.test_client()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

from datetime import date, timedelta
from db import User, Vendor, AgreedCost, Promotion, Invoice, InvoiceLine
import bcrypt


def make_user(db, email="owner@store.com", store="Test Store"):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    u = User(email=email, password_hash=pw, store_name=store)
    db.session.add(u)
    db.session.flush()
    return u


def make_vendor(db, user_id, name="Vendor A"):
    v = Vendor(user_id=user_id, name=name, account_no="V-001", terms="Net 30")
    db.session.add(v)
    db.session.flush()
    return v


def make_cost(db, user_id, vendor_id, item_code, cost, unit="case", pack_size=1):
    c = AgreedCost(user_id=user_id, vendor_id=vendor_id, item_code=item_code,
                   description=item_code, unit=unit, pack_size=pack_size, cost=cost)
    db.session.add(c)
    db.session.flush()
    return c


def make_promo(db, user_id, vendor_id, item_code, allowance, start=None, end=None):
    today = date.today()
    p = Promotion(
        user_id=user_id, vendor_id=vendor_id, item_code=item_code,
        description=item_code, allowance_per_case=allowance,
        start_date=start or today - timedelta(days=5),
        end_date=end or today + timedelta(days=5),
    )
    db.session.add(p)
    db.session.flush()
    return p


def make_invoice(db, user_id, vendor_id, invoice_number="INV-001",
                 invoice_date=None, total=100.00, status="checked"):
    inv = Invoice(
        user_id=user_id, vendor_id=vendor_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date or date.today(),
        total=total, status=status,
    )
    db.session.add(inv)
    db.session.flush()
    return inv


def make_line(db, invoice_id, line_type="item", item_code="ITEM-1",
              quantity=1, unit_price=10.00, line_total=10.00,
              handwritten_note=None):
    line = InvoiceLine(
        invoice_id=invoice_id, line_type=line_type, item_code=item_code,
        quantity=quantity, unit=None, unit_price=unit_price,
        line_total=line_total, handwritten_note=handwritten_note,
    )
    db.session.add(line)
    db.session.flush()
    return line
