"""
test_history.py — tests for POST /api/history/import upsert logic.
"""

import json
import pytest
from tests.conftest import make_user, make_vendor, make_cost
from db import Vendor, AgreedCost, Promotion, VendorNotice


def _login_new(client, email="hist@store.com"):
    client.post("/api/auth/register", json={
        "email": email, "password": "pw", "store_name": "Hist Store"
    })


def _post_import(client, payload):
    return client.post(
        "/api/history/import",
        data=json.dumps(payload),
        content_type="application/json",
    )


class TestHistoryImport:
    def test_requires_auth(self, client, db):
        resp = _post_import(client, {})
        assert resp.status_code == 401

    def test_empty_sections_returns_zero_counts(self, client, db):
        """An object with all sections present but empty returns zero counts."""
        _login_new(client)
        resp = _post_import(client, {
            "vendors": [], "agreed_costs": [], "promotions": [], "vendor_notices": []
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"vendors": 0, "agreed_costs": 0, "promotions": 0, "vendor_notices": 0}

    def test_insert_vendor(self, client, db):
        _login_new(client)
        resp = _post_import(client, {
            "vendors": [{"name": "New Vendor", "account_no": "NV-1", "terms": "Net 30"}]
        })
        assert resp.status_code == 200
        assert resp.get_json()["vendors"] == 1

    def test_upsert_vendor_no_duplicate(self, client, db):
        _login_new(client)
        _post_import(client, {"vendors": [{"name": "Vendor X", "account_no": "V-1"}]})
        resp = _post_import(client, {"vendors": [{"name": "Vendor X", "account_no": "V-2"}]})
        assert resp.status_code == 200
        # Second import updates, doesn't insert — count should be 0
        assert resp.get_json()["vendors"] == 0

    def test_vendor_upsert_updates_terms(self, app, client, db):
        _login_new(client)
        _post_import(client, {"vendors": [{"name": "Vendor Y", "terms": "Net 30"}]})
        _post_import(client, {"vendors": [{"name": "Vendor Y", "terms": "Net 14"}]})
        with app.app_context():
            from db import User
            u = User.query.filter_by(email="hist@store.com").first()
            v = Vendor.query.filter_by(user_id=u.id, name="Vendor Y").first()
            assert v.terms == "Net 14"

    def test_vendor_name_case_insensitive(self, client, db):
        _login_new(client)
        _post_import(client, {"vendors": [{"name": "Vendor Z"}]})
        resp = _post_import(client, {"vendors": [{"name": "vendor z"}]})
        assert resp.get_json()["vendors"] == 0  # treated as same vendor

    def test_insert_agreed_cost(self, client, db):
        _login_new(client)
        resp = _post_import(client, {
            "vendors": [{"name": "Acme"}],
            "agreed_costs": [{"vendor_name": "Acme", "item_code": "A-1", "cost": 5.00}],
        })
        assert resp.get_json()["agreed_costs"] == 1

    def test_upsert_cost_updates_price(self, app, client, db):
        _login_new(client)
        _post_import(client, {
            "vendors": [{"name": "Acme"}],
            "agreed_costs": [{"vendor_name": "Acme", "item_code": "A-1", "cost": 5.00}],
        })
        _post_import(client, {
            "agreed_costs": [{"vendor_name": "Acme", "item_code": "A-1", "cost": 7.00}],
        })
        with app.app_context():
            from db import User
            u = User.query.filter_by(email="hist@store.com").first()
            v = Vendor.query.filter_by(user_id=u.id, name="Acme").first()
            c = AgreedCost.query.filter_by(user_id=u.id, vendor_id=v.id, item_code="A-1").first()
            assert float(c.cost) == pytest.approx(7.00)

    def test_cost_skipped_for_unknown_vendor(self, client, db):
        _login_new(client)
        resp = _post_import(client, {
            "agreed_costs": [{"vendor_name": "Ghost Vendor", "item_code": "G-1", "cost": 1.00}],
        })
        assert resp.get_json()["agreed_costs"] == 0

    def test_insert_promotion(self, client, db):
        _login_new(client)
        resp = _post_import(client, {
            "vendors": [{"name": "PromoVend"}],
            "promotions": [{
                "vendor_name": "PromoVend", "item_code": "P-1",
                "allowance_per_case": 1.50,
                "start_date": "2026-11-01", "end_date": "2026-11-30",
            }],
        })
        assert resp.get_json()["promotions"] == 1

    def test_insert_vendor_notice(self, client, db):
        _login_new(client)
        resp = _post_import(client, {
            "vendors": [{"name": "NoticeVend"}],
            "vendor_notices": [{
                "vendor_name": "NoticeVend",
                "notice_date": "2026-11-01",
                "subject": "Price update",
                "body": "Prices going up.",
            }],
        })
        assert resp.get_json()["vendor_notices"] == 1

    def test_scoped_to_user(self, app, client, db):
        """Vendor inserted by one user must not be visible to another."""
        _login_new(client, "user1@hist.com")
        _post_import(client, {"vendors": [{"name": "SharedName"}]})

        # Login as user 2
        client.post("/api/auth/logout")
        client.post("/api/auth/register", json={
            "email": "user2@hist.com", "password": "pw", "store_name": "S2"
        })
        resp = _post_import(client, {
            "agreed_costs": [{"vendor_name": "SharedName", "item_code": "X", "cost": 1.0}]
        })
        # user2 doesn't have SharedName — cost should be skipped
        assert resp.get_json()["agreed_costs"] == 0
