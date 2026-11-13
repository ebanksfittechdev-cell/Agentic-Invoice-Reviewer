"""
test_agent_tools.py — tests for the 9 ADK tool functions.

Tools are called directly (not via the agent runner) with a mock ToolContext
that injects user_id from state. No Gemini call is made.
"""

import pytest
from unittest.mock import MagicMock
from datetime import date, timedelta

from tests.conftest import (
    make_user, make_vendor, make_cost, make_promo,
    make_invoice, make_line,
)
from db import PendingAction


def _ctx(user_id: int):
    """Build a minimal mock ToolContext with user_id in state."""
    ctx = MagicMock()
    ctx.state = {"user_id": user_id}
    return ctx


class TestGetInvoice:
    def test_returns_lines(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            make_line(db, inv.id, item_code="X-1", quantity=3, unit_price=5.00, line_total=15.00)
            db.session.commit()

            from agent.tools import get_invoice
            result = get_invoice(inv.id, _ctx(u.id))
            assert result["invoice_number"] == inv.invoice_number
            assert len(result["lines"]) == 1
            assert result["lines"][0]["item_code"] == "X-1"

    def test_wrong_user_returns_error(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.commit()

            from agent.tools import get_invoice
            result = get_invoice(inv.id, _ctx(u.id + 999))
            assert "error" in result


class TestGetVendorTerms:
    def test_returns_terms(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id, name="Acme")
            db.session.commit()

            from agent.tools import get_vendor_terms
            result = get_vendor_terms(v.id, _ctx(u.id))
            assert result["name"] == "Acme"
            assert "terms" in result

    def test_wrong_user_returns_error(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            db.session.commit()

            from agent.tools import get_vendor_terms
            result = get_vendor_terms(v.id, _ctx(u.id + 999))
            assert "error" in result


class TestSearchVendorNotices:
    def test_keyword_match(self, app, db):
        with app.app_context():
            from db import VendorNotice
            u = make_user(db)
            v = make_vendor(db, u.id)
            db.session.add(VendorNotice(
                user_id=u.id, vendor_id=v.id,
                notice_date=date.today(), subject="Price increase",
                body="Prices going up on item ABC",
            ))
            db.session.commit()

            from agent.tools import search_vendor_notices
            result = search_vendor_notices(v.id, "ABC", _ctx(u.id))
            assert len(result["results"]) == 1
            assert "ABC" in result["results"][0]["body"]

    def test_no_match_returns_empty(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            db.session.commit()

            from agent.tools import search_vendor_notices
            result = search_vendor_notices(v.id, "nomatch", _ctx(u.id))
            assert result["results"] == []


class TestGetPromotions:
    def test_returns_promotions(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            make_promo(db, u.id, v.id, "ITEM-P", allowance=1.50)
            db.session.commit()

            from agent.tools import get_promotions
            result = get_promotions(v.id, "ITEM-P", _ctx(u.id))
            assert len(result["promotions"]) == 1
            assert result["promotions"][0]["allowance_per_case"] == pytest.approx(1.50)
            assert result["promotions"][0]["active_today"] is True

    def test_no_promo_returns_empty(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            db.session.commit()

            from agent.tools import get_promotions
            result = get_promotions(v.id, "NOITEM", _ctx(u.id))
            assert result["promotions"] == []


class TestGetInvoiceHistory:
    def test_returns_history(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id, invoice_number="HIST-001")
            make_line(db, inv.id, item_code="H-1", quantity=5, unit_price=3.00, line_total=15.00)
            db.session.commit()

            from agent.tools import get_invoice_history
            result = get_invoice_history(v.id, "H-1", _ctx(u.id))
            assert len(result["history"]) == 1
            assert result["history"][0]["invoice_number"] == "HIST-001"

    def test_scoped_to_user(self, app, db):
        with app.app_context():
            u1 = make_user(db, email="h1@store.com")
            u2 = make_user(db, email="h2@store.com")
            v1 = make_vendor(db, u1.id, name="V1")
            v2 = make_vendor(db, u2.id, name="V2")
            inv1 = make_invoice(db, u1.id, v1.id)
            make_line(db, inv1.id, item_code="H-1")
            db.session.commit()

            from agent.tools import get_invoice_history
            # u2 querying v1 should return nothing
            result = get_invoice_history(v1.id, "H-1", _ctx(u2.id))
            assert result["history"] == []


class TestWriteTools:
    def test_draft_dispute_creates_pending_action(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.commit()

            from agent.tools import draft_dispute
            result = draft_dispute(v.id, ["ITEM-1"], "Dispute msg", inv.id, _ctx(u.id))
            assert "action_id" in result

            action = PendingAction.query.get(result["action_id"])
            assert action.action_type == "dispute"
            assert action.status == "pending"
            assert action.user_id == u.id

    def test_propose_cost_update_creates_pending_action(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.commit()

            from agent.tools import propose_cost_update
            result = propose_cost_update("ITEM-C", 9.99, "Evidence", inv.id, _ctx(u.id))
            action = PendingAction.query.get(result["action_id"])
            assert action.action_type == "cost_update"
            assert action.details["new_cost"] == pytest.approx(9.99)

    def test_hold_payment_creates_pending_action(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.commit()

            from agent.tools import hold_payment
            result = hold_payment(inv.id, "Duplicate invoice", _ctx(u.id))
            action = PendingAction.query.get(result["action_id"])
            assert action.action_type == "hold_payment"

    def test_ask_owner_creates_pending_action(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.commit()

            from agent.tools import ask_owner
            result = ask_owner("Is this a promo price?", inv.id, _ctx(u.id))
            action = PendingAction.query.get(result["action_id"])
            assert action.action_type == "question"
            assert action.details["question"] == "Is this a promo price?"

    def test_write_tool_missing_user_id_raises(self, app, db):
        with app.app_context():
            u = make_user(db)
            v = make_vendor(db, u.id)
            inv = make_invoice(db, u.id, v.id)
            db.session.commit()

            ctx = MagicMock()
            ctx.state = {}  # no user_id

            from agent.tools import ask_owner
            with pytest.raises(PermissionError):
                ask_owner("Q?", inv.id, ctx)
