from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from auth.utils import current_user_id
from db import db, PendingAction, Discrepancy, Invoice, AgreedCost

actions_bp = Blueprint("actions", __name__)


# ---------------------------------------------------------------------------
# GET /api/actions
# ---------------------------------------------------------------------------

@actions_bp.get("")
@actions_bp.get("/")
def list_actions():
    user_id = current_user_id()
    actions = (
        PendingAction.query
        .filter_by(user_id=user_id)
        .order_by(PendingAction.created_at.desc())
        .all()
    )
    return jsonify([_action_dict(a) for a in actions]), 200


# ---------------------------------------------------------------------------
# POST /api/actions/<id>/approve
# ---------------------------------------------------------------------------

@actions_bp.post("/<int:action_id>/approve")
def approve(action_id):
    user_id = current_user_id()
    action = PendingAction.query.filter_by(id=action_id, user_id=user_id).first_or_404()

    if action.status != "pending":
        return jsonify({"error": f"Action is already '{action.status}'"}), 409

    _apply_approval(action)

    action.status = "approved"
    action.decided_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(_action_dict(action)), 200


# ---------------------------------------------------------------------------
# POST /api/actions/<id>/reject
# ---------------------------------------------------------------------------

@actions_bp.post("/<int:action_id>/reject")
def reject(action_id):
    user_id = current_user_id()
    action = PendingAction.query.filter_by(id=action_id, user_id=user_id).first_or_404()

    if action.status != "pending":
        return jsonify({"error": f"Action is already '{action.status}'"}), 409

    action.status = "rejected"
    action.decided_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(_action_dict(action)), 200


# ---------------------------------------------------------------------------
# Side-effect logic
# ---------------------------------------------------------------------------

def _apply_approval(action: PendingAction):
    """Apply the data side-effect for an approved action."""
    if action.action_type == "dispute":
        # Mark referenced discrepancies as disputed
        items = (action.details or {}).get("items", [])
        if items:
            Discrepancy.query.filter(
                Discrepancy.invoice_id == action.invoice_id,
                Discrepancy.user_id == action.user_id,
                Discrepancy.item_code.in_(items),
                Discrepancy.status == "open",
            ).update({"status": "disputed"}, synchronize_session=False)

    elif action.action_type == "cost_update":
        details = action.details or {}
        item_code = details.get("item_code")
        new_cost = details.get("new_cost")
        if item_code and new_cost is not None:
            cost_row = AgreedCost.query.filter_by(
                user_id=action.user_id,
                item_code=item_code,
            ).first()
            if cost_row:
                cost_row.cost = new_cost
                cost_row.updated_at = datetime.now(timezone.utc)

    elif action.action_type == "hold_payment":
        invoice = Invoice.query.filter_by(
            id=action.invoice_id, user_id=action.user_id
        ).first()
        if invoice:
            invoice.status = "do_not_pay"

    elif action.action_type == "question":
        # Owner's answer is stored in details by the frontend via PATCH or
        # passed in request body; record it here if provided.
        answer = (request.get_json(silent=True) or {}).get("answer")
        if answer:
            details = dict(action.details or {})
            details["answer"] = answer
            action.details = details


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

def _action_dict(a: PendingAction) -> dict:
    return {
        "id": a.id,
        "invoice_id": a.invoice_id,
        "action_type": a.action_type,
        "details": a.details,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
    }
