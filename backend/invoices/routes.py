import os
import uuid

from flask import Blueprint, request, jsonify, current_app

from auth.utils import current_user_id
from db import db, Vendor, Invoice, InvoiceLine
from invoices.checks import verify_total
from invoices.extractor import extract_invoice, ExtractionError

invoices_bp = Blueprint("invoices", __name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
}


# ---------------------------------------------------------------------------
# POST /api/invoices/upload
# ---------------------------------------------------------------------------

@invoices_bp.post("/upload")
def upload():
    user_id = current_user_id()

    if "file" not in request.files:
        return jsonify({"error": "No file attached — send a multipart/form-data request with a 'file' field"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    mime_type = file.mimetype or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES:
        return jsonify({"error": f"Unsupported file type: {mime_type}. Send a JPEG, PNG, WebP, GIF, or PDF."}), 415

    # Resolve vendor — caller may pass vendor_id or we look it up after extraction
    vendor_id = request.form.get("vendor_id", type=int)

    # Save file to disk with a UUID name
    ext = os.path.splitext(file.filename)[1].lower() or _ext_from_mime(mime_type)
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    image_path = os.path.join(upload_folder, filename)
    file_bytes = file.read()
    with open(image_path, "wb") as f:
        f.write(file_bytes)

    # Create invoice row (status = uploaded)
    invoice = Invoice(
        user_id=user_id,
        vendor_id=vendor_id or _get_or_create_unknown_vendor(user_id),
        invoice_number="",
        status="uploaded",
        image_path=image_path,
    )
    db.session.add(invoice)
    db.session.flush()

    # --- Gemini extraction ---
    try:
        extracted = extract_invoice(file_bytes, mime_type)
    except ExtractionError as e:
        invoice.status = "needs_review"
        db.session.commit()
        return jsonify({
            "invoice_id": invoice.id,
            "status": "needs_review",
            "error": str(e),
        }), 200

    # Update invoice header from extraction
    invoice.invoice_number = extracted.get("invoice_number") or ""
    invoice.invoice_date = extracted.get("invoice_date") or None
    invoice.total = extracted.get("total")

    # Try to match vendor by name if not provided
    if not vendor_id and extracted.get("vendor_name"):
        matched = Vendor.query.filter(
            Vendor.user_id == user_id,
            Vendor.name.ilike(f"%{extracted['vendor_name']}%"),
        ).first()
        if matched:
            invoice.vendor_id = matched.id

    # Insert lines
    lines = extracted.get("lines", [])
    for line in lines:
        db.session.add(InvoiceLine(
            invoice_id=invoice.id,
            line_type=line.get("line_type", "item"),
            item_code=line.get("item_code"),
            description=line.get("description"),
            quantity=line.get("quantity"),
            unit=line.get("unit"),
            unit_price=line.get("unit_price"),
            line_total=line.get("line_total"),
            handwritten_note=line.get("handwritten_note"),
        ))

    # Verify total
    total_ok = verify_total(lines, extracted.get("total"))
    invoice.status = "checked" if total_ok else "needs_review"

    db.session.commit()

    # --- Discrepancy checks + agent (Sub-Tasks 5 & 6) ---
    # Imported here to avoid circular imports; will be filled in by those sub-tasks
    discrepancies = []
    try:
        from invoices.discrepancy_checks import run_checks
        discrepancies = run_checks(invoice.id, user_id)
    except ImportError:
        pass  # Sub-Task 5 not yet implemented

    if discrepancies and invoice.status == "checked":
        try:
            from agent.runner import run_agent
            run_agent(invoice.id, user_id, discrepancies)
        except ImportError:
            pass  # Sub-Task 6 not yet implemented

    return jsonify({
        "invoice_id": invoice.id,
        "status": invoice.status,
        "invoice_number": invoice.invoice_number,
        "invoice_date": str(invoice.invoice_date) if invoice.invoice_date else None,
        "total": float(invoice.total) if invoice.total is not None else None,
        "line_count": len(lines),
        "discrepancy_count": len(discrepancies),
    }), 201


# ---------------------------------------------------------------------------
# GET /api/invoices
# ---------------------------------------------------------------------------

@invoices_bp.get("/")
def list_invoices():
    user_id = current_user_id()
    invoices = (
        Invoice.query
        .filter_by(user_id=user_id)
        .order_by(Invoice.uploaded_at.desc())
        .all()
    )
    return jsonify([_invoice_summary(inv) for inv in invoices]), 200


# ---------------------------------------------------------------------------
# GET /api/invoices/<id>
# ---------------------------------------------------------------------------

@invoices_bp.get("/<int:invoice_id>")
def get_invoice(invoice_id):
    user_id = current_user_id()
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=user_id).first_or_404()

    return jsonify({
        **_invoice_summary(invoice),
        "lines": [_line_dict(l) for l in invoice.lines],
        "discrepancies": [_disc_dict(d) for d in invoice.discrepancies],
        "pending_actions": [_action_dict(a) for a in invoice.pending_actions],
    }), 200


# ---------------------------------------------------------------------------
# GET /api/invoices/discrepancies  (all discrepancies for the user)
# ---------------------------------------------------------------------------

@invoices_bp.get("/discrepancies")
def list_discrepancies():
    from db import Discrepancy
    user_id = current_user_id()
    discs = (
        Discrepancy.query
        .filter_by(user_id=user_id)
        .order_by(Discrepancy.created_at.desc())
        .all()
    )
    return jsonify([_disc_dict(d) for d in discs]), 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_unknown_vendor(user_id: int) -> int:
    """Return the id of an 'Unknown Vendor' placeholder, creating it if needed."""
    vendor = Vendor.query.filter_by(user_id=user_id, name="Unknown Vendor").first()
    if not vendor:
        vendor = Vendor(user_id=user_id, name="Unknown Vendor")
        db.session.add(vendor)
        db.session.flush()
    return vendor.id


def _ext_from_mime(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "application/pdf": ".pdf",
    }.get(mime_type, "")


def _invoice_summary(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "vendor_id": inv.vendor_id,
        "vendor_name": inv.vendor.name if inv.vendor else None,
        "invoice_number": inv.invoice_number,
        "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
        "total": float(inv.total) if inv.total is not None else None,
        "status": inv.status,
        "uploaded_at": inv.uploaded_at.isoformat() if inv.uploaded_at else None,
    }


def _line_dict(line: InvoiceLine) -> dict:
    return {
        "id": line.id,
        "line_type": line.line_type,
        "item_code": line.item_code,
        "description": line.description,
        "quantity": float(line.quantity) if line.quantity is not None else None,
        "unit": line.unit,
        "unit_price": float(line.unit_price) if line.unit_price is not None else None,
        "line_total": float(line.line_total) if line.line_total is not None else None,
        "handwritten_note": line.handwritten_note,
    }


def _disc_dict(d) -> dict:
    return {
        "id": d.id,
        "type": d.type,
        "item_code": d.item_code,
        "amount": float(d.amount) if d.amount is not None else None,
        "status": d.status,
        "explanation": d.explanation,
    }


def _action_dict(a) -> dict:
    return {
        "id": a.id,
        "action_type": a.action_type,
        "details": a.details,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
