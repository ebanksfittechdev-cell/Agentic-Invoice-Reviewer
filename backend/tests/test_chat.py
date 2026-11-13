"""
test_chat.py — tests for POST /api/agent/chat endpoint.
"""

import pytest
from tests.conftest import make_user, make_vendor, make_invoice
from db import Discrepancy, PendingAction


def _login(client, email="chat_user@store.com"):
    client.post("/api/auth/register", json={
        "email": email, "password": "pw", "store_name": "Corner Market"
    })


class TestAgentChat:
    def test_chat_requires_auth(self, client, db):
        resp = client.post("/api/agent/chat", json={"message": "Hello"})
        assert resp.status_code == 401

    def test_empty_message(self, client, db):
        _login(client)
        resp = client.post("/api/agent/chat", json={"message": ""})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reply" in data
        assert "steps" in data

    def test_chat_overcharge_query(self, app, client, db):
        _login(client, "disc_chat@store.com")
        with app.app_context():
            from db import User
            u = User.query.filter_by(email="disc_chat@store.com").first()
            v = make_vendor(db, u.id, name="Lakeshore Dairy")
            inv = make_invoice(db, u.id, v.id, total=100.0)
            db.session.add(Discrepancy(
                user_id=u.id,
                invoice_id=inv.id,
                type="price",
                item_code="ITEM-1",
                amount=14.50,
                status="open",
            ))
            db.session.commit()

        resp = client.post("/api/agent/chat", json={
            "message": "How much did Lakeshore overcharge us this month?"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "$14.50" in data["reply"]
        assert isinstance(data["steps"], list)

    def test_chat_pending_actions_query(self, app, client, db):
        _login(client, "actions_chat@store.com")
        with app.app_context():
            from db import User
            u = User.query.filter_by(email="actions_chat@store.com").first()
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.add(PendingAction(
                user_id=u.id,
                invoice_id=inv.id,
                action_type="dispute",
                details={"items": ["ITEM-1"], "amount": 10.0},
                status="pending",
            ))
            db.session.commit()

        resp = client.post("/api/agent/chat", json={
            "message": "What's waiting for my approval?"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "1 action" in data["reply"]
        assert isinstance(data["steps"], list)

    def test_chat_capabilities_query(self, client, db):
        _login(client, "cap_chat@store.com")
        resp = client.post("/api/agent/chat", json={
            "message": "What can you check on an invoice?"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "agreed costs" in data["reply"]
        assert isinstance(data["steps"], list)
