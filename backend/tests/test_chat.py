"""
test_chat.py — tests for POST /api/agent/chat and the chat agent's read tools.

The model is never called: run_chat is replaced where a reply is needed, and
the read tools are called directly with a mock ToolContext.
"""

from unittest.mock import MagicMock

import pytest

from tests.conftest import make_user, make_vendor, make_invoice, make_cost
from db import Discrepancy, PendingAction


def _login(client, email="chat_user@store.com"):
    client.post("/api/auth/register", json={
        "email": email, "password": "pw", "store_name": "Corner Market"
    })


def _ctx(user_id):
    ctx = MagicMock()
    ctx.state = {"user_id": user_id}
    return ctx


class TestChatEndpoint:
    def test_chat_requires_auth(self, client, db):
        resp = client.post("/api/agent/chat", json={"message": "Hello"})
        assert resp.status_code == 401

    def test_empty_message_is_rejected(self, client, db):
        _login(client)
        resp = client.post("/api/agent/chat", json={"message": "   "})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_returns_model_reply_and_steps(self, client, db, monkeypatch):
        _login(client, "reply@store.com")
        seen = {}

        def fake_run_chat(user_id, message, history):
            seen.update(user_id=user_id, message=message, history=history)
            return {"reply": "model says hi", "steps": ["list_vendors()"]}

        monkeypatch.setattr("agent.runner.run_chat", fake_run_chat)
        resp = client.post("/api/agent/chat", json={
            "message": "Who are my vendors?",
            "history": [
                {"role": "user", "text": "earlier question"},
                {"role": "assistant", "text": "earlier answer"},
                {"role": "system", "text": "dropped — not a chat role"},
            ],
        })
        assert resp.status_code == 200
        assert resp.get_json() == {"reply": "model says hi", "steps": ["list_vendors()"]}
        assert seen["message"] == "Who are my vendors?"
        assert [t["role"] for t in seen["history"]] == ["user", "assistant"]

    def test_missing_key_returns_error_not_canned_reply(self, client, db, monkeypatch):
        _login(client, "nokey@store.com")
        monkeypatch.setenv("GEMINI_API_KEY", "your-gemini-api-key-here")
        resp = client.post("/api/agent/chat", json={"message": "How much were we overcharged?"})
        assert resp.status_code == 503
        data = resp.get_json()
        assert "GEMINI_API_KEY" in data["error"]
        assert "reply" not in data

    def test_model_failure_returns_error(self, client, db, monkeypatch):
        _login(client, "fail@store.com")
        from agent.runner import AgentUnavailable

        def boom(*_a, **_k):
            raise AgentUnavailable("The model call failed: 404 model not found")

        monkeypatch.setattr("agent.runner.run_chat", boom)
        resp = client.post("/api/agent/chat", json={"message": "hi"})
        assert resp.status_code == 503
        assert "404" in resp.get_json()["error"]


class TestChatReadTools:
    def test_list_discrepancies_scoped_and_filtered(self, app, db):
        with app.app_context():
            u = make_user(db)
            other = make_user(db, email="other@store.com")
            v = make_vendor(db, u.id, name="Lakeshore Dairy")
            inv = make_invoice(db, u.id, v.id)
            ov = make_vendor(db, other.id)
            oinv = make_invoice(db, other.id, ov.id)
            db.session.add_all([
                Discrepancy(user_id=u.id, invoice_id=inv.id, type="price", item_code="A", amount=14.5, status="open"),
                Discrepancy(user_id=u.id, invoice_id=inv.id, type="price", item_code="B", amount=3, status="explained"),
                Discrepancy(user_id=other.id, invoice_id=oinv.id, type="price", item_code="X", amount=99, status="open"),
            ])
            db.session.commit()

            from agent.tools import list_discrepancies
            open_ = list_discrepancies("open", _ctx(u.id))["discrepancies"]
            assert [d["item_code"] for d in open_] == ["A"]
            assert open_[0]["amount"] == 14.5
            assert open_[0]["vendor_name"] == "Lakeshore Dairy"
            assert len(list_discrepancies("all", _ctx(u.id))["discrepancies"]) == 2

    def test_list_pending_actions_only_pending(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.add_all([
                PendingAction(user_id=u.id, invoice_id=inv.id, action_type="dispute", details={}, status="pending"),
                PendingAction(user_id=u.id, invoice_id=inv.id, action_type="question", details={}, status="approved"),
            ])
            db.session.commit()

            from agent.tools import list_pending_actions
            rows = list_pending_actions(_ctx(u.id))["pending_actions"]
            assert [r["action_type"] for r in rows] == ["dispute"]

    def test_vendors_invoices_costs_scoped(self, app, db):
        with app.app_context():
            u = make_user(db)
            other = make_user(db, email="other2@store.com")
            v = make_vendor(db, u.id, name="Mine")
            make_vendor(db, other.id, name="Theirs")
            make_invoice(db, u.id, v.id, invoice_number="INV-9")
            make_cost(db, u.id, v.id, "MILK", 14.2)
            db.session.commit()

            from agent.tools import list_vendors, list_invoices, get_agreed_costs
            assert [x["name"] for x in list_vendors(_ctx(u.id))["vendors"]] == ["Mine"]
            assert [x["invoice_number"] for x in list_invoices(_ctx(u.id))["invoices"]] == ["INV-9"]
            costs = get_agreed_costs(0, _ctx(u.id))["agreed_costs"]
            assert [(c["item_code"], c["cost"]) for c in costs] == [("MILK", 14.2)]
            assert get_agreed_costs(v.id, _ctx(other.id))["agreed_costs"] == []
