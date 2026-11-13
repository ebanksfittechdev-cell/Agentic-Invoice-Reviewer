"""
test_actions.py — tests for approve/reject endpoints and their side-effects.
"""

import pytest
from datetime import date
from tests.conftest import make_user, make_vendor, make_cost, make_invoice, make_line
from db import PendingAction, Discrepancy, Invoice, AgreedCost


def _login(client, email, password="pw"):
    import bcrypt
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _make_full_setup(app, db):
    """Create user, vendor, invoice and return (user, vendor, invoice)."""
    import bcrypt
    from db import User, Vendor, Invoice
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    u = User(email="actions@store.com", password_hash=pw, store_name="Store")
    db.session.add(u)
    db.session.flush()
    v = make_vendor(db, u.id)
    inv = make_invoice(db, u.id, v.id, status="checked")
    db.session.commit()
    return u, v, inv


def _make_action(db, user_id, invoice_id, action_type, details):
    a = PendingAction(
        user_id=user_id, invoice_id=invoice_id,
        action_type=action_type, details=details, status="pending",
    )
    db.session.add(a)
    db.session.commit()
    return a


class TestListActions:
    def test_list_requires_auth(self, client, db):
        assert client.get("/api/actions/").status_code == 401

    def test_list_returns_own_actions(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            _make_action(db, u.id, inv.id, "question", {"question": "Is this right?"})

        _login(client, "actions@store.com")
        resp = client.get("/api/actions/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["action_type"] == "question"

    def test_list_scoped_to_user(self, app, client, db):
        """Actions from another user must not appear."""
        import bcrypt
        from db import User, Vendor, Invoice
        with app.app_context():
            pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
            u1 = User(email="u1@store.com", password_hash=pw, store_name="S1")
            u2 = User(email="u2@store.com", password_hash=pw, store_name="S2")
            db.session.add_all([u1, u2])
            db.session.flush()
            v1 = make_vendor(db, u1.id, name="V1")
            v2 = make_vendor(db, u2.id, name="V2")
            inv1 = make_invoice(db, u1.id, v1.id)
            inv2 = make_invoice(db, u2.id, v2.id)
            _make_action(db, u1.id, inv1.id, "question", {"question": "Q1"})
            _make_action(db, u2.id, inv2.id, "question", {"question": "Q2"})

        _login(client, "u1@store.com")
        resp = client.get("/api/actions/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["details"]["question"] == "Q1"


class TestApprove:
    def test_approve_requires_auth(self, client, db):
        assert client.post("/api/actions/999/approve").status_code == 401

    def test_approve_dispute_sets_discrepancy_disputed(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            make_line(db, inv.id, item_code="ITEM-X")
            disc = Discrepancy(user_id=u.id, invoice_id=inv.id,
                               type="price", item_code="ITEM-X",
                               amount=5.00, status="open")
            db.session.add(disc)
            action = _make_action(db, u.id, inv.id, "dispute",
                                  {"items": ["ITEM-X"], "message": "Dispute text"})
            action_id = action.id
            db.session.commit()

        _login(client, "actions@store.com")
        resp = client.post(f"/api/actions/{action_id}/approve")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "approved"

        with app.app_context():
            disc = Discrepancy.query.filter_by(item_code="ITEM-X").first()
            assert disc.status == "disputed"

    def test_approve_cost_update_writes_new_cost(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            make_cost(db, u.id, v.id, "ITEM-C", cost=5.00)
            action = _make_action(db, u.id, inv.id, "cost_update",
                                  {"item_code": "ITEM-C", "new_cost": 7.50,
                                   "evidence": "invoiced at 7.50"})
            action_id = action.id
            db.session.commit()

        _login(client, "actions@store.com")
        client.post(f"/api/actions/{action_id}/approve")

        with app.app_context():
            cost = AgreedCost.query.filter_by(item_code="ITEM-C").first()
            assert float(cost.cost) == pytest.approx(7.50)

    def test_approve_hold_payment_sets_do_not_pay(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            action = _make_action(db, u.id, inv.id, "hold_payment",
                                  {"reason": "Duplicate invoice"})
            action_id = action.id
            inv_id = inv.id
            db.session.commit()

        _login(client, "actions@store.com")
        client.post(f"/api/actions/{action_id}/approve")

        with app.app_context():
            inv = Invoice.query.get(inv_id)
            assert inv.status == "do_not_pay"

    def test_approve_already_decided_returns_409(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            action = _make_action(db, u.id, inv.id, "question", {"question": "Q?"})
            action.status = "approved"
            db.session.commit()
            action_id = action.id

        _login(client, "actions@store.com")
        resp = client.post(f"/api/actions/{action_id}/approve")
        assert resp.status_code == 409

    def test_approve_other_users_action_returns_404(self, app, client, db):
        import bcrypt
        from db import User
        with app.app_context():
            pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
            other = User(email="other@store.com", password_hash=pw, store_name="Other")
            db.session.add(other)
            db.session.flush()
            v = make_vendor(db, other.id)
            inv = make_invoice(db, other.id, v.id)
            action = _make_action(db, other.id, inv.id, "question", {"question": "Q"})
            action_id = action.id
            db.session.commit()

        # Login as a different user
        client.post("/api/auth/register", json={
            "email": "attacker@store.com", "password": "pw", "store_name": "Bad"
        })
        resp = client.post(f"/api/actions/{action_id}/approve")
        assert resp.status_code == 404


class TestReject:
    def test_reject_sets_rejected_no_side_effects(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            make_cost(db, u.id, v.id, "ITEM-R", cost=5.00)
            action = _make_action(db, u.id, inv.id, "cost_update",
                                  {"item_code": "ITEM-R", "new_cost": 9.99})
            action_id = action.id
            db.session.commit()

        _login(client, "actions@store.com")
        resp = client.post(f"/api/actions/{action_id}/reject")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "rejected"

        with app.app_context():
            # Cost must NOT have changed
            cost = AgreedCost.query.filter_by(item_code="ITEM-R").first()
            assert float(cost.cost) == pytest.approx(5.00)
            # decided_at must be set
            action = PendingAction.query.get(action_id)
            assert action.decided_at is not None

    def test_reject_already_decided_returns_409(self, app, client, db):
        with app.app_context():
            u, v, inv = _make_full_setup(app, db)
            action = _make_action(db, u.id, inv.id, "question", {"question": "Q?"})
            action.status = "rejected"
            db.session.commit()
            action_id = action.id

        _login(client, "actions@store.com")
        resp = client.post(f"/api/actions/{action_id}/reject")
        assert resp.status_code == 409
