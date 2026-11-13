"""
test_discrepancy_checks.py — pytest tests for all six checks and the
/api/invoices/discrepancies route's user-scoping.
"""

import pytest
from datetime import date, timedelta

from tests.conftest import (
    make_user, make_vendor, make_cost, make_promo,
    make_invoice, make_line,
)
from invoices.discrepancy_checks import run_checks


# ---------------------------------------------------------------------------
# 1. Price check
# ---------------------------------------------------------------------------

class TestPriceCheck:
    def test_overcharge_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_cost(db, u.id, v.id, "ITEM-1", cost=8.00)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=10, unit_price=9.00, line_total=90.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert len(result) == 1
            d = result[0]
            assert d.type == "price"
            assert d.item_code == "ITEM-1"
            assert float(d.amount) == pytest.approx(10.00)   # (9-8) * 10

    def test_undercharge_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_cost(db, u.id, v.id, "ITEM-1", cost=10.00)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=5, unit_price=9.00, line_total=45.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            price_checks = [d for d in result if d.type == "price"]
            assert len(price_checks) == 1
            assert float(price_checks[0].amount) == pytest.approx(-5.00)  # (9-10)*5

    def test_matching_price_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_cost(db, u.id, v.id, "ITEM-1", cost=10.00)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=3, unit_price=10.00, line_total=30.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "price" for d in result)

    def test_no_agreed_cost_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="UNKNOWN", quantity=1, unit_price=5.00, line_total=5.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "price" for d in result)


# ---------------------------------------------------------------------------
# 2. Quantity check
# ---------------------------------------------------------------------------

class TestQuantityCheck:
    def test_recd_mismatch_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=10, unit_price=5.00,
                      line_total=50.00, handwritten_note="rec'd 8")
            db.session.commit()

            result = run_checks(inv.id, u.id)
            qty_checks = [d for d in result if d.type == "quantity"]
            assert len(qty_checks) == 1
            assert float(qty_checks[0].amount) == pytest.approx(10.00)  # |10-8| * 5

    def test_recd_match_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=5, unit_price=4.00,
                      line_total=20.00, handwritten_note="rec'd 5")
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "quantity" for d in result)

    def test_no_note_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=5, unit_price=4.00,
                      line_total=20.00, handwritten_note=None)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "quantity" for d in result)


# ---------------------------------------------------------------------------
# 3. Line arithmetic check
# ---------------------------------------------------------------------------

class TestLineArithmeticCheck:
    def test_arithmetic_error_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            # 3 × 10.00 = 30.00 but billed as 31.00
            make_line(db, inv.id, item_code="ITEM-1", quantity=3, unit_price=10.00, line_total=31.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            arith = [d for d in result if d.type == "line_arithmetic"]
            assert len(arith) == 1
            assert float(arith[0].amount) == pytest.approx(1.00)

    def test_correct_arithmetic_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=4, unit_price=2.50, line_total=10.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "line_arithmetic" for d in result)


# ---------------------------------------------------------------------------
# 4. Duplicate invoice check
# ---------------------------------------------------------------------------

class TestDuplicateInvoiceCheck:
    def test_duplicate_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_invoice(db, u.id, v.id, invoice_number="INV-DUP", total=50.00)
            inv2 = make_invoice(db, u.id, v.id, invoice_number="INV-DUP", total=50.00)
            db.session.commit()

            result = run_checks(inv2.id, u.id)
            dupes = [d for d in result if d.type == "duplicate_invoice"]
            assert len(dupes) == 1

    def test_unique_invoice_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_invoice(db, u.id, v.id, invoice_number="INV-001")
            inv2 = make_invoice(db, u.id, v.id, invoice_number="INV-002")
            db.session.commit()

            result = run_checks(inv2.id, u.id)
            assert all(d.type != "duplicate_invoice" for d in result)

    def test_duplicate_different_vendor_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v1 = make_vendor(db, u.id, name="Vendor A")
            v2 = make_vendor(db, u.id, name="Vendor B")
            make_invoice(db, u.id, v1.id, invoice_number="INV-SAME")
            inv2 = make_invoice(db, u.id, v2.id, invoice_number="INV-SAME")
            db.session.commit()

            result = run_checks(inv2.id, u.id)
            assert all(d.type != "duplicate_invoice" for d in result)


# ---------------------------------------------------------------------------
# 5. Promotion check
# ---------------------------------------------------------------------------

class TestPromotionCheck:
    def test_missing_credit_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_promo(db, u.id, v.id, "ITEM-1", allowance=1.20)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=10, unit_price=9.00, line_total=90.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            promos = [d for d in result if d.type == "promotion"]
            assert len(promos) == 1
            assert float(promos[0].amount) == pytest.approx(12.00)  # 1.20 * 10

    def test_partial_credit_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_promo(db, u.id, v.id, "ITEM-1", allowance=1.20)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=10, unit_price=9.00, line_total=90.00)
            # Credit for only 5 cases worth: 1.20 * 5 = 6.00 — shortfall = 6.00
            make_line(db, inv.id, line_type="credit", item_code="ITEM-1",
                      quantity=5, unit_price=1.20, line_total=6.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            promos = [d for d in result if d.type == "promotion"]
            assert len(promos) == 1
            assert float(promos[0].amount) == pytest.approx(6.00)  # shortfall

    def test_full_credit_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_promo(db, u.id, v.id, "ITEM-1", allowance=1.20)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="ITEM-1", quantity=10, unit_price=9.00, line_total=90.00)
            make_line(db, inv.id, line_type="credit", item_code="ITEM-1",
                      quantity=10, unit_price=1.20, line_total=12.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "promotion" for d in result)

    def test_expired_promo_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            yesterday = date.today() - timedelta(days=1)
            make_promo(db, u.id, v.id, "ITEM-1", allowance=1.20,
                       start=yesterday - timedelta(days=10), end=yesterday)
            inv = make_invoice(db, u.id, v.id, invoice_date=date.today())
            make_line(db, inv.id, item_code="ITEM-1", quantity=5, unit_price=9.00, line_total=45.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "promotion" for d in result)


# ---------------------------------------------------------------------------
# 6. Deposit check
# ---------------------------------------------------------------------------

class TestDepositCheck:
    def test_deposit_mismatch_flagged(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_cost(db, u.id, v.id, "DEP-BTL", cost=0.10, unit="bottle")
            inv = make_invoice(db, u.id, v.id)
            # 48 bottles × $0.10 = $4.80 but billed $5.00
            make_line(db, inv.id, line_type="deposit", item_code="DEP-BTL",
                      quantity=48, unit_price=0.10, line_total=5.00)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            deps = [d for d in result if d.type == "deposit"]
            assert len(deps) == 1
            assert float(deps[0].amount) == pytest.approx(0.20)

    def test_correct_deposit_no_flag(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_cost(db, u.id, v.id, "DEP-BTL", cost=0.10, unit="bottle")
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, line_type="deposit", item_code="DEP-BTL",
                      quantity=48, unit_price=0.10, line_total=4.80)
            db.session.commit()

            result = run_checks(inv.id, u.id)
            assert all(d.type != "deposit" for d in result)


# ---------------------------------------------------------------------------
# User scoping — GET /api/invoices/discrepancies
# ---------------------------------------------------------------------------

class TestDiscrepanciesScoping:
    def _login(self, client, email, password="pw"):
        return client.post("/api/auth/login",
                           json={"email": email, "password": password})

    def test_only_own_discrepancies_returned(self, app, db, client):
        with app.app_context():
            import bcrypt
            pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()

            from db import User, Vendor, Invoice, InvoiceLine, Discrepancy
            u1 = User(email="owner1@store.com", password_hash=pw, store_name="Store 1")
            u2 = User(email="owner2@store.com", password_hash=pw, store_name="Store 2")
            db.session.add_all([u1, u2])
            db.session.flush()

            v1 = Vendor(user_id=u1.id, name="V1")
            v2 = Vendor(user_id=u2.id, name="V2")
            db.session.add_all([v1, v2])
            db.session.flush()

            inv1 = Invoice(user_id=u1.id, vendor_id=v1.id, invoice_number="A",
                           status="checked", total=10.0)
            inv2 = Invoice(user_id=u2.id, vendor_id=v2.id, invoice_number="B",
                           status="checked", total=20.0)
            db.session.add_all([inv1, inv2])
            db.session.flush()

            d1 = Discrepancy(user_id=u1.id, invoice_id=inv1.id,
                             type="price", item_code="X", amount=5.0, status="open")
            d2 = Discrepancy(user_id=u2.id, invoice_id=inv2.id,
                             type="price", item_code="Y", amount=3.0, status="open")
            db.session.add_all([d1, d2])
            db.session.commit()

        # Login as user 1
        self._login(client, "owner1@store.com")
        resp = client.get("/api/invoices/discrepancies")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["item_code"] == "X"

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/invoices/discrepancies")
        assert resp.status_code == 401
