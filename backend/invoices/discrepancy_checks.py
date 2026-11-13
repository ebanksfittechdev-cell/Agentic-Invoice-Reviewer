"""
discrepancy_checks.py — six rule-based checks run after extraction.

All checks are pure code — no model involved.
Each finding is inserted into `discrepancies` with status = "open".
Returns the list of Discrepancy ORM objects created.
"""

import re
from decimal import Decimal, ROUND_HALF_UP

from db import db, Invoice, InvoiceLine, AgreedCost, Promotion, Discrepancy


def run_checks(invoice_id: int, user_id: int) -> list[Discrepancy]:
    """Run all six checks and return the discrepancies created."""
    invoice = Invoice.query.filter_by(id=invoice_id, user_id=user_id).first()
    if not invoice:
        return []

    lines = invoice.lines
    found: list[Discrepancy] = []

    found += _check_prices(invoice, lines, user_id)
    found += _check_quantities(invoice, lines, user_id)
    found += _check_line_arithmetic(invoice, lines, user_id)
    found += _check_duplicate_invoice(invoice, user_id)
    found += _check_promotions(invoice, lines, user_id)
    found += _check_deposits(invoice, lines, user_id)

    if found:
        db.session.add_all(found)
        db.session.commit()

    return found


# ---------------------------------------------------------------------------
# 1. Price check — invoice unit_price vs agreed cost
# ---------------------------------------------------------------------------

def _check_prices(invoice: Invoice, lines: list[InvoiceLine], user_id: int) -> list[Discrepancy]:
    results = []
    for line in lines:
        if not line.item_code or line.unit_price is None:
            continue
        agreed = AgreedCost.query.filter_by(
            user_id=user_id,
            vendor_id=invoice.vendor_id,
            item_code=line.item_code,
        ).first()
        if not agreed:
            continue
        delta = _dec(line.unit_price) - _dec(agreed.cost)
        if abs(delta) > Decimal("0.01"):
            amount = (delta * _dec(line.quantity or 1)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            results.append(Discrepancy(
                user_id=user_id,
                invoice_id=invoice.id,
                type="price",
                item_code=line.item_code,
                amount=float(amount),
                status="open",
            ))
    return results


# ---------------------------------------------------------------------------
# 2. Quantity check — billed qty vs handwritten "rec'd"
# ---------------------------------------------------------------------------

_RECD_RE = re.compile(r"rec(?:eived|'d|d)[^\d]*(\d+(?:\.\d+)?)", re.IGNORECASE)

def _check_quantities(invoice: Invoice, lines: list[InvoiceLine], user_id: int) -> list[Discrepancy]:
    results = []
    for line in lines:
        if not line.handwritten_note or line.quantity is None:
            continue
        match = _RECD_RE.search(line.handwritten_note)
        if not match:
            continue
        recd = Decimal(match.group(1))
        billed = _dec(line.quantity)
        if abs(recd - billed) > Decimal("0.01"):
            unit_price = _dec(line.unit_price or 0)
            amount = (abs(recd - billed) * unit_price).quantize(Decimal("0.01"), ROUND_HALF_UP)
            results.append(Discrepancy(
                user_id=user_id,
                invoice_id=invoice.id,
                type="quantity",
                item_code=line.item_code,
                amount=float(amount),
                status="open",
            ))
    return results


# ---------------------------------------------------------------------------
# 3. Line arithmetic check — quantity × unit_price ≈ line_total
# ---------------------------------------------------------------------------

def _check_line_arithmetic(invoice: Invoice, lines: list[InvoiceLine], user_id: int) -> list[Discrepancy]:
    results = []
    for line in lines:
        if line.quantity is None or line.unit_price is None or line.line_total is None:
            continue
        expected = (_dec(line.quantity) * _dec(line.unit_price)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        actual = _dec(line.line_total)
        if abs(expected - actual) > Decimal("0.01"):
            results.append(Discrepancy(
                user_id=user_id,
                invoice_id=invoice.id,
                type="line_arithmetic",
                item_code=line.item_code,
                amount=float(abs(expected - actual)),
                status="open",
            ))
    return results


# ---------------------------------------------------------------------------
# 4. Duplicate invoice check
# ---------------------------------------------------------------------------

def _check_duplicate_invoice(invoice: Invoice, user_id: int) -> list[Discrepancy]:
    if not invoice.invoice_number:
        return []
    duplicate = Invoice.query.filter(
        Invoice.user_id == user_id,
        Invoice.vendor_id == invoice.vendor_id,
        Invoice.invoice_number == invoice.invoice_number,
        Invoice.id != invoice.id,
    ).first()
    if duplicate:
        return [Discrepancy(
            user_id=user_id,
            invoice_id=invoice.id,
            type="duplicate_invoice",
            item_code=None,
            amount=float(invoice.total or 0),
            status="open",
        )]
    return []


# ---------------------------------------------------------------------------
# 5. Promotion not applied — active promo with no matching credit line
# ---------------------------------------------------------------------------

def _check_promotions(invoice: Invoice, lines: list[InvoiceLine], user_id: int) -> list[Discrepancy]:
    if not invoice.invoice_date:
        return []

    active_promos = Promotion.query.filter(
        Promotion.user_id == user_id,
        Promotion.vendor_id == invoice.vendor_id,
        Promotion.start_date <= invoice.invoice_date,
        Promotion.end_date >= invoice.invoice_date,
    ).all()

    # Build set of item_codes that have a credit line on this invoice
    credit_item_codes = {
        l.item_code for l in lines
        if l.line_type == "credit" and l.item_code
    }

    results = []
    for promo in active_promos:
        if promo.item_code in credit_item_codes:
            continue  # credit already present
        # Find quantity billed for this item
        qty = sum(
            _dec(l.quantity or 0)
            for l in lines
            if l.item_code == promo.item_code and l.line_type == "item"
        )
        if qty == 0:
            continue  # item not on this invoice
        amount = (_dec(promo.allowance_per_case) * qty).quantize(Decimal("0.01"), ROUND_HALF_UP)
        results.append(Discrepancy(
            user_id=user_id,
            invoice_id=invoice.id,
            type="promotion",
            item_code=promo.item_code,
            amount=float(amount),
            status="open",
        ))
    return results


# ---------------------------------------------------------------------------
# 6. Deposit math check
# ---------------------------------------------------------------------------

def _check_deposits(invoice: Invoice, lines: list[InvoiceLine], user_id: int) -> list[Discrepancy]:
    results = []
    deposit_lines = [l for l in lines if l.line_type == "deposit"]
    for line in deposit_lines:
        if line.item_code is None or line.line_total is None or line.quantity is None:
            continue
        agreed = AgreedCost.query.filter_by(
            user_id=user_id,
            vendor_id=invoice.vendor_id,
            item_code=line.item_code,
        ).first()
        if not agreed:
            continue
        expected = (_dec(line.quantity) * _dec(agreed.cost)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        actual = _dec(line.line_total)
        if abs(expected - actual) > Decimal("0.01"):
            results.append(Discrepancy(
                user_id=user_id,
                invoice_id=invoice.id,
                type="deposit",
                item_code=line.item_code,
                amount=float(abs(expected - actual)),
                status="open",
            ))
    return results


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _dec(value) -> Decimal:
    return Decimal(str(value))
