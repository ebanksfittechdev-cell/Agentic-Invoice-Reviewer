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

class User(db.Model):
    __tablename__ = "users"

    id:            Mapped[int]  = mapped_column(Integer, primary_key=True)
    email:         Mapped[str]  = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str]  = mapped_column(Text, nullable=False)
    store_name:    Mapped[str]  = mapped_column(Text, nullable=False)
    created_at:    Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendors:        Mapped[list["Vendor"]]        = relationship(back_populates="user", cascade="all, delete-orphan")
    invoices:       Mapped[list["Invoice"]]       = relationship(back_populates="user", cascade="all, delete-orphan")
    discrepancies:  Mapped[list["Discrepancy"]]   = relationship(back_populates="user", cascade="all, delete-orphan")
    pending_actions: Mapped[list["PendingAction"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Vendor(db.Model):
    __tablename__ = "vendors"

    id:         Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:    Mapped[int]        = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name:       Mapped[str]        = mapped_column(Text, nullable=False)
    account_no: Mapped[str | None] = mapped_column(Text)
    terms:      Mapped[str | None] = mapped_column(Text)

    user:          Mapped["User"]            = relationship(back_populates="vendors")
    agreed_costs:  Mapped[list["AgreedCost"]]  = relationship(back_populates="vendor", cascade="all, delete-orphan")
    promotions:    Mapped[list["Promotion"]]   = relationship(back_populates="vendor", cascade="all, delete-orphan")
    vendor_notices: Mapped[list["VendorNotice"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    invoices:      Mapped[list["Invoice"]]     = relationship(back_populates="vendor", cascade="all, delete-orphan")


class AgreedCost(db.Model):
    __tablename__ = "agreed_costs"

    id:          Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]        = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id:   Mapped[int]        = mapped_column(Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    item_code:   Mapped[str]        = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit:        Mapped[str | None] = mapped_column(Text)
    pack_size:   Mapped[int | None] = mapped_column(Integer)
    cost:        Mapped[float]      = mapped_column(Numeric(10, 2), nullable=False)
    updated_at:  Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendor: Mapped["Vendor"] = relationship(back_populates="agreed_costs")


class Promotion(db.Model):
    __tablename__ = "promotions"

    id:                 Mapped[int]   = mapped_column(Integer, primary_key=True)
    user_id:            Mapped[int]   = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id:          Mapped[int]   = mapped_column(Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    item_code:          Mapped[str]   = mapped_column(Text, nullable=False)
    description:        Mapped[str | None] = mapped_column(Text)
    allowance_per_case: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    start_date:         Mapped[Date]  = mapped_column(Date, nullable=False)
    end_date:           Mapped[Date]  = mapped_column(Date, nullable=False)

    vendor: Mapped["Vendor"] = relationship(back_populates="promotions")


class VendorNotice(db.Model):
    __tablename__ = "vendor_notices"

    id:          Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]        = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id:   Mapped[int]        = mapped_column(Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    notice_date: Mapped[Date]       = mapped_column(Date, nullable=False)
    subject:     Mapped[str | None] = mapped_column(Text)
    body:        Mapped[str | None] = mapped_column(Text)

    vendor: Mapped["Vendor"] = relationship(back_populates="vendor_notices")


class Invoice(db.Model):
    __tablename__ = "invoices"

    id:             Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:        Mapped[int]        = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id:      Mapped[int]        = mapped_column(Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    invoice_number: Mapped[str]        = mapped_column(Text, nullable=False)
    invoice_date:   Mapped[Date | None] = mapped_column(Date)
    total:          Mapped[float | None] = mapped_column(Numeric(10, 2))
    status:         Mapped[str]        = mapped_column(Text, nullable=False, default="uploaded")
    image_path:     Mapped[str | None] = mapped_column(Text)
    uploaded_at:    Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    user:            Mapped["User"]              = relationship(back_populates="invoices")
    vendor:          Mapped["Vendor"]            = relationship(back_populates="invoices")
    lines:           Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    discrepancies:   Mapped[list["Discrepancy"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    pending_actions: Mapped[list["PendingAction"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLine(db.Model):
    __tablename__ = "invoice_lines"

    id:               Mapped[int]        = mapped_column(Integer, primary_key=True)
    invoice_id:       Mapped[int]        = mapped_column(Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    line_type:        Mapped[str]        = mapped_column(Text, nullable=False, default="item")
    item_code:        Mapped[str | None] = mapped_column(Text)
    description:      Mapped[str | None] = mapped_column(Text)
    quantity:         Mapped[float | None] = mapped_column(Numeric)
    unit:             Mapped[str | None] = mapped_column(Text)
    unit_price:       Mapped[float | None] = mapped_column(Numeric(10, 2))
    line_total:       Mapped[float | None] = mapped_column(Numeric(10, 2))
    handwritten_note: Mapped[str | None] = mapped_column(Text)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")


class Discrepancy(db.Model):
    __tablename__ = "discrepancies"

    id:          Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]        = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    invoice_id:  Mapped[int]        = mapped_column(Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    type:        Mapped[str]        = mapped_column(Text, nullable=False)
    item_code:   Mapped[str | None] = mapped_column(Text)
    amount:      Mapped[float | None] = mapped_column(Numeric(10, 2))
    status:      Mapped[str]        = mapped_column(Text, nullable=False, default="open")
    explanation: Mapped[str | None] = mapped_column(Text)
    created_at:  Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    user:    Mapped["User"]    = relationship(back_populates="discrepancies")
    invoice: Mapped["Invoice"] = relationship(back_populates="discrepancies")


class PendingAction(db.Model):
    __tablename__ = "pending_actions"

    id:          Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int]        = mapped_column(Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    invoice_id:  Mapped[int]        = mapped_column(Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    action_type: Mapped[str]        = mapped_column(Text, nullable=False)
    details:     Mapped[dict | None] = mapped_column(JSONB)
    status:      Mapped[str]        = mapped_column(Text, nullable=False, default="pending")
    created_at:  Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at:  Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    user:    Mapped["User"]    = relationship(back_populates="pending_actions")
    invoice: Mapped["Invoice"] = relationship(back_populates="pending_actions")
