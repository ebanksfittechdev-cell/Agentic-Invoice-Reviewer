from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    BigInteger, Date, DateTime, Integer, Numeric, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

from sqlalchemy.dialects.postgresql import JSONB
 

 
 
class User(db.Model):
    __tablename__ = "users"
 
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    store_name = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
 
    vendors = db.relationship("Vendor", backref="user", lazy=True, cascade="all, delete-orphan")
    # Read-only shortcut: users -> vendors -> invoices
    invoices = db.relationship("Invoice", secondary="vendors", viewonly=True)
 
 
class Vendor(db.Model):
    __tablename__ = "vendors"
 
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.Text, nullable=False)
    account_no = db.Column(db.Text)
    terms = db.Column(db.Text)
 
    agreed_costs = db.relationship("AgreedCost", backref="vendor", lazy=True, cascade="all, delete-orphan")
    promotions = db.relationship("Promotion", backref="vendor", lazy=True, cascade="all, delete-orphan")
    vendor_notices = db.relationship("VendorNotice", backref="vendor", lazy=True, cascade="all, delete-orphan")
    invoices = db.relationship("Invoice", backref="vendor", lazy=True, cascade="all, delete-orphan")
 
 
class AgreedCost(db.Model):
    __tablename__ = "agreed_costs"
    __table_args__ = (db.UniqueConstraint("vendor_id", "item_code"),)
 
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    item_code = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.Text)
    pack_size = db.Column(db.Integer)
    cost = db.Column(db.Numeric(10, 2), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )
 
 
class Promotion(db.Model):
    __tablename__ = "promotions"
 
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    item_code = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    allowance_per_case = db.Column(db.Numeric(10, 2), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
 
 
class VendorNotice(db.Model):
    __tablename__ = "vendor_notices"
 
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    notice_date = db.Column(db.Date, nullable=False)
    subject = db.Column(db.Text)
    body = db.Column(db.Text)
 
 
class Invoice(db.Model):
    __tablename__ = "invoices"
    __table_args__ = (db.UniqueConstraint("vendor_id", "invoice_number"),)
 
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    invoice_number = db.Column(db.Text, nullable=False)
    invoice_date = db.Column(db.Date)
    total = db.Column(db.Numeric(10, 2))
    status = db.Column(db.Text, nullable=False, default="uploaded")
    image_path = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
 
    lines = db.relationship("InvoiceLine", backref="invoice", lazy=True, cascade="all, delete-orphan")
    discrepancies = db.relationship("Discrepancy", backref="invoice", lazy=True, cascade="all, delete-orphan")
    pending_actions = db.relationship("PendingAction", backref="invoice", lazy=True, cascade="all, delete-orphan")
 
 
class InvoiceLine(db.Model):
    __tablename__ = "invoice_lines"
 
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    line_type = db.Column(db.Text, nullable=False, default="item")
    item_code = db.Column(db.Text)
    description = db.Column(db.Text)
    quantity = db.Column(db.Numeric)
    unit = db.Column(db.Text)
    unit_price = db.Column(db.Numeric(10, 2))
    line_total = db.Column(db.Numeric(10, 2))
    handwritten_note = db.Column(db.Text)
 
 
class Discrepancy(db.Model):
    __tablename__ = "discrepancies"
 
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    type = db.Column(db.Text, nullable=False)
    item_code = db.Column(db.Text)
    amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.Text, nullable=False, default="open")
    explanation = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
 
 
class PendingAction(db.Model):
    __tablename__ = "pending_actions"
 
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    action_type = db.Column(db.Text, nullable=False)
    details = db.Column(JSONB)
    status = db.Column(db.Text, nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    decided_at = db.Column(db.DateTime(timezone=True))
