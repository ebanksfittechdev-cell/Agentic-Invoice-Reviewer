"""
agent/tools.py — ADK tools for the invoice agent and the chat agent.

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
    VendorNotice, PendingAction, Discrepancy,
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
# Store-wide read tools — used by the chat agent to answer owner questions
# ---------------------------------------------------------------------------

def _money(v):
    return float(v) if v is not None else None


def list_vendors(tool_context: ToolContext) -> dict:
    """List the store's vendors with their ids, account numbers and terms."""
    user_id = _uid(tool_context)
    vendors = Vendor.query.filter_by(user_id=user_id).order_by(Vendor.name).all()
    return {
        "vendors": [
            {"vendor_id": v.id, "name": v.name, "account_no": v.account_no, "terms": v.terms}
            for v in vendors
        ]
    }


def list_invoices(tool_context: ToolContext) -> dict:
    """List the store's invoices (newest first) with vendor, date, total and status."""
    user_id = _uid(tool_context)
    invoices = (
        Invoice.query.filter_by(user_id=user_id)
        .order_by(Invoice.uploaded_at.desc())
        .limit(50)
        .all()
    )
    return {
        "invoices": [
            {
                "invoice_id": i.id,
                "invoice_number": i.invoice_number,
                "vendor_id": i.vendor_id,
                "vendor_name": i.vendor.name if i.vendor else None,
                "invoice_date": str(i.invoice_date) if i.invoice_date else None,
                "total": _money(i.total),
                "status": i.status,
            }
            for i in invoices
        ]
    }


def list_discrepancies(status: str, tool_context: ToolContext) -> dict:
    """List discrepancies found by the invoice checks.

    status: one of "open", "explained", "disputed", or "all".
    Amounts are computed by code; report them as given, do not recalculate.
    """
    user_id = _uid(tool_context)
    q = Discrepancy.query.filter_by(user_id=user_id)
    if status and status != "all":
        q = q.filter_by(status=status)
    rows = q.order_by(Discrepancy.created_at.desc()).limit(100).all()
    return {
        "discrepancies": [
            {
                "id": d.id,
                "invoice_id": d.invoice_id,
                "invoice_number": d.invoice.invoice_number if d.invoice else None,
                "invoice_date": str(d.invoice.invoice_date) if d.invoice and d.invoice.invoice_date else None,
                "vendor_name": d.invoice.vendor.name if d.invoice and d.invoice.vendor else None,
                "type": d.type,
                "item_code": d.item_code,
                "amount": _money(d.amount),
                "status": d.status,
                "explanation": d.explanation,
            }
            for d in rows
        ]
    }


def list_pending_actions(tool_context: ToolContext) -> dict:
    """List actions the agent has proposed that are still waiting for the owner's decision."""
    user_id = _uid(tool_context)
    rows = (
        PendingAction.query.filter_by(user_id=user_id, status="pending")
        .order_by(PendingAction.created_at.desc())
        .all()
    )
    return {
        "pending_actions": [
            {
                "id": a.id,
                "invoice_id": a.invoice_id,
                "action_type": a.action_type,
                "details": a.details,
            }
            for a in rows
        ]
    }


def get_agreed_costs(vendor_id: int, tool_context: ToolContext) -> dict:
    """Return the agreed (contracted) costs for a vendor's items. Use vendor_id 0 for all vendors."""
    user_id = _uid(tool_context)
    q = AgreedCost.query.filter_by(user_id=user_id)
    if vendor_id:
        q = q.filter_by(vendor_id=vendor_id)
    return {
        "agreed_costs": [
            {
                "vendor_id": c.vendor_id,
                "vendor_name": c.vendor.name if c.vendor else None,
                "item_code": c.item_code,
                "description": c.description,
                "unit": c.unit,
                "pack_size": c.pack_size,
                "cost": _money(c.cost),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in q.order_by(AgreedCost.item_code).all()
        ]
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
