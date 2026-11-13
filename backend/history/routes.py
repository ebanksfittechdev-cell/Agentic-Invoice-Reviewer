"""
history/routes.py — POST /api/history/import

Accepts a JSON file or JSON body containing vendors, agreed_costs, promotions,
and vendor_notices. Upserts all records for the logged-in store.

See backend/history_schema.md for the full schema.
"""

import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from auth.utils import current_user_id
from db import db, Vendor, AgreedCost, Promotion, VendorNotice

history_bp = Blueprint("history", __name__)


@history_bp.post("/import")
def import_history():
    user_id = current_user_id()

    # Accept either a JSON file upload or a raw JSON body
    if request.files.get("file"):
        try:
            data = json.loads(request.files["file"].read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return jsonify({"error": f"Invalid JSON file: {e}"}), 400
    else:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Send a JSON file (field 'file') or a JSON body"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Top-level JSON must be an object"}), 400

    counts = {"vendors": 0, "agreed_costs": 0, "promotions": 0, "vendor_notices": 0}

    # --- Vendors ---
    vendor_map: dict[str, int] = {}  # lowercased name -> id (new + pre-existing)

    for v in data.get("vendors", []):
        name = (v.get("name") or "").strip()
        if not name:
            continue
        existing = Vendor.query.filter(
            Vendor.user_id == user_id,
            db.func.lower(Vendor.name) == name.lower(),
        ).first()
        if existing:
            existing.account_no = v.get("account_no", existing.account_no)
            existing.terms = v.get("terms", existing.terms)
            vendor_map[name.lower()] = existing.id
        else:
            vendor = Vendor(
                user_id=user_id,
                name=name,
                account_no=v.get("account_no"),
                terms=v.get("terms"),
            )
            db.session.add(vendor)
            db.session.flush()
            vendor_map[name.lower()] = vendor.id
            counts["vendors"] += 1

    # Pre-load any existing vendors not in this import (for cost/promo references)
    for existing in Vendor.query.filter_by(user_id=user_id).all():
        vendor_map.setdefault(existing.name.lower(), existing.id)

    # --- Agreed costs ---
    for c in data.get("agreed_costs", []):
        vendor_name = (c.get("vendor_name") or "").strip().lower()
        item_code = (c.get("item_code") or "").strip()
        if not vendor_name or not item_code:
            continue
        vendor_id = vendor_map.get(vendor_name)
        if not vendor_id:
            continue  # unknown vendor — skip

        existing = AgreedCost.query.filter_by(
            user_id=user_id, vendor_id=vendor_id, item_code=item_code
        ).first()
        if existing:
            existing.description = c.get("description", existing.description)
            existing.unit = c.get("unit", existing.unit)
            existing.pack_size = c.get("pack_size", existing.pack_size)
            existing.cost = c["cost"]
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.session.add(AgreedCost(
                user_id=user_id,
                vendor_id=vendor_id,
                item_code=item_code,
                description=c.get("description"),
                unit=c.get("unit"),
                pack_size=c.get("pack_size"),
                cost=c["cost"],
            ))
            counts["agreed_costs"] += 1

    # --- Promotions ---
    for p in data.get("promotions", []):
        vendor_name = (p.get("vendor_name") or "").strip().lower()
        item_code = (p.get("item_code") or "").strip()
        start_date = p.get("start_date")
        if not vendor_name or not item_code or not start_date:
            continue
        vendor_id = vendor_map.get(vendor_name)
        if not vendor_id:
            continue

        existing = Promotion.query.filter_by(
            user_id=user_id, vendor_id=vendor_id,
            item_code=item_code, start_date=start_date,
        ).first()
        if existing:
            existing.description = p.get("description", existing.description)
            existing.allowance_per_case = p["allowance_per_case"]
            existing.end_date = p["end_date"]
        else:
            db.session.add(Promotion(
                user_id=user_id,
                vendor_id=vendor_id,
                item_code=item_code,
                description=p.get("description"),
                allowance_per_case=p["allowance_per_case"],
                start_date=start_date,
                end_date=p["end_date"],
            ))
            counts["promotions"] += 1

    # --- Vendor notices ---
    for n in data.get("vendor_notices", []):
        vendor_name = (n.get("vendor_name") or "").strip().lower()
        notice_date = n.get("notice_date")
        subject = (n.get("subject") or "").strip()
        if not vendor_name or not notice_date:
            continue
        vendor_id = vendor_map.get(vendor_name)
        if not vendor_id:
            continue

        existing = VendorNotice.query.filter_by(
            user_id=user_id, vendor_id=vendor_id,
            notice_date=notice_date, subject=subject,
        ).first()
        if existing:
            existing.body = n.get("body", existing.body)
        else:
            db.session.add(VendorNotice(
                user_id=user_id,
                vendor_id=vendor_id,
                notice_date=notice_date,
                subject=subject,
                body=n.get("body"),
            ))
            counts["vendor_notices"] += 1

    db.session.commit()
    return jsonify(counts), 200
