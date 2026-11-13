"""
agent/tools.py — all 9 ADK tools for the invoice agent.

Read tools query the DB; every query filters by user_id from ADK session state.
Write tools insert exactly one pending_actions row — nothing else is written.

user_id is NEVER passed through the model prompt; it comes exclusively from
tool_context.state["user_id"] which is set by runner.py before the agent runs.
"""

import os
from datetime import date

from google.adk.tools.tool_context import ToolContext

from db import (
    db, Invoice, InvoiceLine, Vendor, AgreedCost, Promotion,
    VendorNotice, PendingAction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid(tool_context: ToolContext) -> int:
    uid = tool_context.state.get("user_id")
    if not uid:
        raise PermissionError("user_id missing from agent session state")
    return int(uid)


def _invoice_app():
    """Return the Flask app context. Called lazily inside each tool."""
    from app import create_app
    return create_app()


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

def get_invoice(invoice_id: int, tool_context: ToolContext) -> dict:
    """Return extracted lines and handwritten notes for an invoice."""
    user_id = _uid(tool_context)
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=user_id).first()
    if not invoice:
        return {"error": f"Invoice {invoice_id} not found"}
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": str(invoice.invoice_date) if invoice.invoice_date else None,
        "total": float(invoice.total) if invoice.total is not None else None,
        "status": invoice.status,
        "lines": [
            {
                "line_type": l.line_type,
                "item_code": l.item_code,
                "description": l.description,
                "quantity": float(l.quantity) if l.quantity is not None else None,
                "unit": l.unit,
                "unit_price": float(l.unit_price) if l.unit_price is not None else None,
                "line_total": float(l.line_total) if l.line_total is not None else None,
                "handwritten_note": l.handwritten_note,
            }
            for l in invoice.lines
        ],
    }


def get_vendor_terms(vendor_id: int, tool_context: ToolContext) -> dict:
    """Return terms text for a vendor (fees, substitution rules, etc.)."""
    user_id = _uid(tool_context)
    vendor = Vendor.query.filter_by(id=vendor_id, user_id=user_id).first()
    if not vendor:
        return {"error": f"Vendor {vendor_id} not found"}
    return {
        "vendor_id": vendor.id,
        "name": vendor.name,
        "account_no": vendor.account_no,
        "terms": vendor.terms,
    }


def search_vendor_notices(vendor_id: int, keyword: str, tool_context: ToolContext) -> dict:
    """Search price-change and promo emails for a vendor by keyword."""
    user_id = _uid(tool_context)
    notices = VendorNotice.query.filter(
        VendorNotice.user_id == user_id,
        VendorNotice.vendor_id == vendor_id,
        db.or_(
            VendorNotice.subject.ilike(f"%{keyword}%"),
            VendorNotice.body.ilike(f"%{keyword}%"),
        ),
    ).order_by(VendorNotice.notice_date.desc()).limit(5).all()
    return {
        "results": [
            {
                "notice_date": str(n.notice_date),
                "subject": n.subject,
                "body": n.body,
            }
            for n in notices
        ]
    }


def get_promotions(vendor_id: int, item_code: str, tool_context: ToolContext) -> dict:
    """Return active allowances and date ranges for an item."""
    user_id = _uid(tool_context)
    today = date.today()
    promos = Promotion.query.filter(
        Promotion.user_id == user_id,
        Promotion.vendor_id == vendor_id,
        Promotion.item_code == item_code,
    ).all()
    return {
        "promotions": [
            {
                "item_code": p.item_code,
                "description": p.description,
                "allowance_per_case": float(p.allowance_per_case),
                "start_date": str(p.start_date),
                "end_date": str(p.end_date),
                "active_today": p.start_date <= today <= p.end_date,
            }
            for p in promos
        ]
    }


def get_invoice_history(vendor_id: int, item_code: str, tool_context: ToolContext) -> dict:
    """Return past prices, quantities, and invoice numbers for an item."""
    user_id = _uid(tool_context)
    rows = (
        db.session.query(
            Invoice.invoice_number,
            Invoice.invoice_date,
            InvoiceLine.quantity,
            InvoiceLine.unit_price,
            InvoiceLine.line_total,
        )
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .filter(
            Invoice.user_id == user_id,
            Invoice.vendor_id == vendor_id,
            InvoiceLine.item_code == item_code,
        )
        .order_by(Invoice.invoice_date.desc())
        .limit(10)
        .all()
    )
    return {
        "item_code": item_code,
        "history": [
            {
                "invoice_number": r.invoice_number,
                "invoice_date": str(r.invoice_date) if r.invoice_date else None,
                "quantity": float(r.quantity) if r.quantity is not None else None,
                "unit_price": float(r.unit_price) if r.unit_price is not None else None,
                "line_total": float(r.line_total) if r.line_total is not None else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Write tools — each inserts exactly one pending_actions row
# ---------------------------------------------------------------------------

def draft_dispute(
    vendor_id: int,
    items: list[str],
    message: str,
    invoice_id: int,
    tool_context: ToolContext,
) -> dict:
    """Propose a dispute email for the owner to approve and send."""
    user_id = _uid(tool_context)
    action = PendingAction(
        user_id=user_id,
        invoice_id=invoice_id,
        action_type="dispute",
        details={"vendor_id": vendor_id, "items": items, "message": message},
        status="pending",
    )
    db.session.add(action)
    db.session.commit()
    return {"action_id": action.id, "status": "pending"}


def propose_cost_update(
    item_code: str,
    new_cost: float,
    evidence: str,
    invoice_id: int,
    tool_context: ToolContext,
) -> dict:
    """Propose updating the agreed cost for an item."""
    user_id = _uid(tool_context)
    action = PendingAction(
        user_id=user_id,
        invoice_id=invoice_id,
        action_type="cost_update",
        details={"item_code": item_code, "new_cost": new_cost, "evidence": evidence},
        status="pending",
    )
    db.session.add(action)
    db.session.commit()
    return {"action_id": action.id, "status": "pending"}


def hold_payment(
    invoice_id: int,
    reason: str,
    tool_context: ToolContext,
) -> dict:
    """Propose holding payment on an invoice pending investigation."""
    user_id = _uid(tool_context)
    action = PendingAction(
        user_id=user_id,
        invoice_id=invoice_id,
        action_type="hold_payment",
        details={"reason": reason},
        status="pending",
    )
    db.session.add(action)
    db.session.commit()
    return {"action_id": action.id, "status": "pending"}


def ask_owner(
    question: str,
    invoice_id: int,
    tool_context: ToolContext,
) -> dict:
    """Surface a question to the owner when there is not enough information to decide."""
    user_id = _uid(tool_context)
    action = PendingAction(
        user_id=user_id,
        invoice_id=invoice_id,
        action_type="question",
        details={"question": question},
        status="pending",
    )
    db.session.add(action)
    db.session.commit()
    return {"action_id": action.id, "status": "pending"}
