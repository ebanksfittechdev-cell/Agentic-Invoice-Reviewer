"""
agent/routes.py — POST /api/agent/chat endpoint for interactive Q&A in ChatPage.
"""

import os
import re
from flask import Blueprint, request, jsonify

from auth.utils import current_user_id
from db import db, Discrepancy, PendingAction, Vendor, AgreedCost, Invoice, Promotion, VendorNotice

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
    agreed_costs = AgreedCost.query.filter_by(user_id=user_id).all()
    promotions = Promotion.query.filter_by(user_id=user_id).all()
    notices = VendorNotice.query.filter_by(user_id=user_id).all()

    api_key = os.environ.get("GEMINI_API_KEY")
    steps = []

    # 1. Try Gemini first if key exists and is valid
    if api_key and not api_key.startswith("AQ.Ab8RN6Kab7o74uomk"):
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            vendor_list = ", ".join([f"{v.name} (account {v.account_no}, terms: {v.terms})" for v in vendors]) or "None"
            cost_summary = "\n".join([
                f"- {c.item_code}: {c.description} = ${float(c.cost):.2f}/{c.unit} (pack size {c.pack_size}) from {c.vendor.name if c.vendor else 'N/A'}"
                for c in agreed_costs
            ]) or "None"
            disc_summary = "\n".join([
                f"- Invoice #{d.invoice.invoice_number if d.invoice else d.invoice_id} "
                f"({d.invoice.vendor.name if d.invoice and d.invoice.vendor else 'Unknown'}): "
                f"type={d.type}, item={d.item_code}, amount=${float(d.amount or 0):.2f}, status={d.status}"
                for d in open_discrepancies
            ]) or "No open discrepancies."
            action_summary = "\n".join([
                f"- Action {a.id} ({a.action_type}): {a.details}"
                for a in pending_actions
            ]) or "No pending actions."
            promo_summary = "\n".join([
                f"- {p.item_code} ({p.description}): ${float(p.allowance_per_case):.2f}/case allowance ({p.start_date} to {p.end_date}) from {p.vendor.name if p.vendor else 'N/A'}"
                for p in promotions
            ]) or "No active promotions."

            prompt = (
                "You are the Invoice Reviewer AI assistant for an independent grocery store.\n"
                "Here is the complete store records data from SQLite:\n"
                f"VENDORS:\n{vendor_list}\n\n"
                f"AGREED COSTS:\n{cost_summary}\n\n"
                f"PROMOTIONS:\n{promo_summary}\n\n"
                f"OPEN DISCREPANCIES:\n{disc_summary}\n\n"
                f"PENDING ACTIONS:\n{action_summary}\n\n"
                f"User Question: \"{message}\"\n\n"
                "Instructions:\n"
                "- Answer the user's question clearly, concisely, and accurately based on the data above in 1 to 3 sentences.\n"
                "- Cite exact item names, item codes, dollar figures, and vendor names when applicable.\n"
                "- Plain text only, friendly tone."
            )

            steps.append("Queried store records & discrepancies")
            for model_name in ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    reply = (response.text or "").strip()
                    if reply:
                        steps.append(f"Evaluated records with {model_name}")
                        return jsonify({"reply": reply, "steps": steps}), 200
                except Exception:
                    continue
        except Exception:
            pass

    # 2. Intelligent Data Resolver (answers with real database records)
    m = message.lower()

    # A. Search for Item Cost / Agreed Price inquiries
    m_words = set(re.findall(r"\w+", m))

    # A. Dispute details & pending action inquiries
    if "dispute" in m:
        steps.append("query(pending_actions where action_type = 'dispute')")
        disputes = [a for a in pending_actions if a.action_type == "dispute"]
        if disputes:
            d_item = disputes[0]
            details = d_item.details or {}
            items_str = ", ".join(details.get("items", []))
            vendor = Vendor.query.get(details.get("vendor_id")) if details.get("vendor_id") else None
            vendor_name = vendor.name if vendor else "Lakeshore Beverages"
            return jsonify({
                "reply": f"You have a pending dispute for {vendor_name} on item(s) {items_str}. Drafted message: \"{details.get('message', '').splitlines()[0]}\" Review it under View history → Actions to approve or reject.",
                "steps": steps,
            }), 200
        else:
            return jsonify({"reply": "There are no pending dispute actions awaiting decision right now.", "steps": steps}), 200

    # B. Search for Item Cost / Agreed Price inquiries
    matched_costs = []
    for c in agreed_costs:
        desc_words = [w.lower() for w in re.findall(r"\w+", c.description or "") if len(w) > 3]
        code_words = [w.lower() for w in re.findall(r"\w+", c.item_code or "") if len(w) > 3]
        if any(w in m_words for w in desc_words) or any(w in m_words for w in code_words):
            matched_costs.append(c)

    if matched_costs and not any(k in m for k in ["overcharg", "discrepanc"]):
        steps.append(f"query(agreed_costs where item matches '{matched_costs[0].description}')")
        lines = [
            f"{c.description} ({c.item_code}) is contracted at ${float(c.cost):.2f}/{c.unit}"
            + (f" (pack size {c.pack_size})" if c.pack_size and c.pack_size > 1 else "")
            + f" from {c.vendor.name if c.vendor else 'vendor'}."
            for c in matched_costs[:3]
        ]
        return jsonify({"reply": " ".join(lines), "steps": steps}), 200

    # C. Vendor notices / price changes
    if "notice" in m or "letter" in m or "email" in m or "price increase" in m or "price update" in m:
        steps.append("query(vendor_notices)")
        matching_notices = notices
        for v in vendors:
            if any(p in m for p in v.name.lower().split() if len(p) > 3):
                matching_notices = [n for n in notices if n.vendor_id == v.id] or notices
                break
        if matching_notices:
            n = matching_notices[0]
            return jsonify({
                "reply": f"On {n.notice_date}, {n.vendor.name if n.vendor else 'vendor'} issued notice '{n.subject}': \"{n.body}\"",
                "steps": steps,
            }), 200

    # D. Vendor inquiries & terms
    for v in vendors:
        v_parts = [p for p in v.name.lower().split() if len(p) > 3]
        if v.name.lower() in m or any(p in m for p in v_parts) or (v.account_no and v.account_no.lower() in m):
            steps.append(f"query(vendors where name = '{v.name}')")
            # If asking about terms specifically:
            if "term" in m or "deposit" in m or "rule" in m:
                return jsonify({
                    "reply": f"{v.name} (account {v.account_no}): terms are \"{v.terms}\".",
                    "steps": steps,
                }), 200
            # If asking about what we owe / overcharge for this vendor:
            v_discs = [d for d in open_discrepancies if d.invoice and d.invoice.vendor_id == v.id]
            if any(k in m for k in ["overcharg", "owe", "credit", "mismatch"]):
                v_total = sum(float(d.amount or 0) for d in v_discs)
                return jsonify({
                    "reply": f"{v.name} has {len(v_discs)} open discrepancy(ies) totaling ${v_total:.2f}. "
                             + ", ".join([f"{d.type} on {d.item_code} (${float(d.amount or 0):.2f})" for d in v_discs]),
                    "steps": steps,
                }), 200
            return jsonify({
                "reply": f"{v.name} is on account {v.account_no}. Agreed terms: {v.terms}",
                "steps": steps,
            }), 200

    # E. Promotions & allowances
    if "promo" in m or "allowance" in m or "discount" in m:
        steps.append("query(promotions)")
        if promotions:
            p = promotions[0]
            return jsonify({
                "reply": f"Active promotion: {p.vendor.name if p.vendor else 'vendor'} offers a ${float(p.allowance_per_case):.2f}/case allowance on {p.description} ({p.item_code}) valid from {p.start_date} through {p.end_date}.",
                "steps": steps,
            }), 200
        else:
            return jsonify({"reply": "There are no active promotions currently logged for your store.", "steps": steps}), 200

    # F. General overcharge / credit / open discrepancies
    if any(k in m for k in ["overcharg", "owe", "credit", "how much", "mismatch"]):
        steps.append("sum(discrepancies.amount where status in open, disputed)")
        total_disc = sum(float(d.amount or 0) for d in open_discrepancies)
        unique_invoices = len(set(d.invoice_id for d in open_discrepancies))
        if open_discrepancies:
            breakdown = ", ".join([
                f"${float(d.amount or 0):.2f} {d.type} on {d.item_code} ({d.invoice.vendor.name if d.invoice and d.invoice.vendor else 'Unknown'})"
                for d in open_discrepancies
            ])
            return jsonify({
                "reply": f"Across {unique_invoices} invoice(s), open discrepancies total ${total_disc:.2f}: {breakdown}.",
                "steps": steps,
            }), 200
        else:
            return jsonify({"reply": "No open or disputed discrepancies were found in your store's records.", "steps": steps}), 200

    # G. Pending actions
    if any(k in m for k in ["pending", "approve", "action", "waiting"]):
        steps.append("query(pending_actions where status = pending)")
        if pending_actions:
            types = ", ".join(set(a.action_type for a in pending_actions))
            return jsonify({
                "reply": f"You have {len(pending_actions)} action(s) waiting for approval ({types}). Open View history → Actions to inspect and decide on them.",
                "steps": steps,
            }), 200
        else:
            return jsonify({"reply": "Nothing is waiting for your approval right now.", "steps": steps}), 200

    # H. System capabilities
    if any(k in m for k in ["what can you check", "check on an invoice", "what do you do", "help"]):
        steps.append("describe_capabilities()")
        return jsonify({
            "reply": "I check invoices against your agreed costs, handwritten delivery notes ('rec'd'), line math, duplicate invoice numbers, active promotional allowances, and deposit rates. Any mismatch is investigated and presented as an action for your approval.",
            "steps": steps,
        }), 200

    # Fallback
    steps.append("default_response()")
    return jsonify({
        "reply": "I can review supplier invoices if you attach an image or PDF, or answer questions about your agreed costs, vendor terms, active promotions, or open overcharges.",
        "steps": steps,
    }), 200
