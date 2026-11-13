"""
agent/routes.py — POST /api/agent/chat endpoint for interactive Q&A in ChatPage.
"""

import os
from flask import Blueprint, request, jsonify

from auth.utils import current_user_id
from db import db, Discrepancy, PendingAction, Vendor, AgreedCost, Invoice

agent_bp = Blueprint("agent", __name__)


@agent_bp.post("/chat")
def chat():
    user_id = current_user_id()
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({
            "reply": "How can I help you with your invoices today?",
            "steps": [],
        }), 200

    # Query store records for current user
    open_discrepancies = Discrepancy.query.filter(
        Discrepancy.user_id == user_id,
        Discrepancy.status.in_(["open", "disputed"]),
    ).all()
    pending_actions = PendingAction.query.filter_by(
        user_id=user_id, status="pending"
    ).all()
    vendors = Vendor.query.filter_by(user_id=user_id).all()
    invoices = Invoice.query.filter_by(user_id=user_id).all()

    api_key = os.environ.get("GEMINI_API_KEY")
    steps = []

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            vendor_list = ", ".join([v.name for v in vendors]) or "None"
            disc_summary = "\n".join([
                f"- Invoice #{d.invoice.invoice_number if d.invoice else d.invoice_id} "
                f"({d.invoice.vendor.name if d.invoice and d.invoice.vendor else 'Unknown'}): "
                f"type={d.type}, item={d.item_code}, amount=${d.amount or 0:.2f}, status={d.status}"
                for d in open_discrepancies[:20]
            ]) or "No open discrepancies."

            action_summary = "\n".join([
                f"- Action {a.id} ({a.action_type}): {a.details}"
                for a in pending_actions[:10]
            ]) or "No pending actions."

            prompt = (
                "You are the Invoice Reviewer AI assistant for an independent grocery store.\n"
                "Store records context:\n"
                f"- Vendors: {vendor_list}\n"
                f"- Total invoices recorded: {len(invoices)}\n"
                f"- Open/disputed discrepancies:\n{disc_summary}\n"
                f"- Pending actions waiting for owner decision:\n{action_summary}\n\n"
                f"The owner asks: \"{message}\"\n\n"
                "Instructions:\n"
                "- Answer concisely and directly in 1-3 sentences based on their store data.\n"
                "- If they ask about overcharges or money owed, provide the exact dollar figures and vendor names from discrepancies.\n"
                "- If they ask what is waiting for approval, report the pending action count and types.\n"
                "- If they ask what you check, explain price vs agreed cost, delivery quantities, line math, duplicates, promotions, and deposit fees.\n"
                "- Plain text only, no markdown bold symbols if possible."
            )

            steps.append("Queried store records & discrepancies")
            response = client.models.generate_content(
                model="gemini-1.5-pro",
                contents=prompt,
            )
            reply = (response.text or "").strip()
            if reply:
                steps.append("Evaluated records with Gemini 1.5 Pro")
                return jsonify({"reply": reply, "steps": steps}), 200
        except Exception:
            # Fall back to deterministic logic if LLM call fails
            pass

    # Deterministic fallback logic
    m = message.lower()
    total_disc = sum(float(d.amount or 0) for d in open_discrepancies)
    unique_invoices = len(set(d.invoice_id for d in open_discrepancies))

    if any(k in m for k in ["overcharg", "owe", "credit", "how much", "cost"]):
        steps.append("sum(discrepancies.amount where status in open, disputed)")
        if open_discrepancies:
            reply = (
                f"Across {unique_invoices} invoice(s), open or disputed discrepancies total ${total_disc:.2f}."
            )
        else:
            reply = "No open or disputed discrepancies were found in your store's records."
    elif any(k in m for k in ["pending", "approve", "action", "waiting"]):
        steps.append("query(pending_actions where status = pending)")
        if pending_actions:
            reply = (
                f"You have {len(pending_actions)} action{'s' if len(pending_actions) != 1 else ''} "
                "waiting for approval. Open View history → Actions to inspect and decide on them."
            )
        else:
            reply = "Nothing is waiting for your approval right now."
    elif any(k in m for k in ["what can you check", "check on an invoice", "what do you do", "help"]):
        steps.append("describe_capabilities()")
        reply = (
            "I check invoices against your agreed costs, handwritten delivery notes ('rec'd'), line math, "
            "duplicate invoice numbers, active promotional allowances, and deposit rates. Any mismatch is investigated "
            "and presented as an action for your approval."
        )
    else:
        steps.append("default_response()")
        reply = (
            "I can review an invoice if you attach a photo or PDF, or answer questions like "
            "\"How much did Lakeshore overcharge us this month?\""
        )

    return jsonify({"reply": reply, "steps": steps}), 200
