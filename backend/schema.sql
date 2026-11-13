-- Agentic Invoice Reviewer — SQLite schema (reference)
-- The ORM models in db.py are canonical; init_db.py creates the real database.
-- Safe to re-run: all tables use IF NOT EXISTS

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    store_name    TEXT NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vendors (
    id         INTEGER PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    account_no TEXT,
    terms      TEXT
);
CREATE INDEX IF NOT EXISTS idx_vendors_user_id ON vendors(user_id);

CREATE TABLE IF NOT EXISTS agreed_costs (
    id          INTEGER PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vendor_id   INT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    item_code   TEXT NOT NULL,
    description TEXT,
    unit        TEXT,
    pack_size   INT,
    cost        NUMERIC(10,2) NOT NULL,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agreed_costs_user_id   ON agreed_costs(user_id);
CREATE INDEX IF NOT EXISTS idx_agreed_costs_vendor_id ON agreed_costs(vendor_id);

CREATE TABLE IF NOT EXISTS promotions (
    id                 INTEGER PRIMARY KEY,
    user_id            INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vendor_id          INT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    item_code          TEXT NOT NULL,
    description        TEXT,
    allowance_per_case NUMERIC(10,2) NOT NULL,
    start_date         DATE NOT NULL,
    end_date           DATE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promotions_user_id   ON promotions(user_id);
CREATE INDEX IF NOT EXISTS idx_promotions_vendor_id ON promotions(vendor_id);

CREATE TABLE IF NOT EXISTS vendor_notices (
    id          INTEGER PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vendor_id   INT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    notice_date DATE NOT NULL,
    subject     TEXT,
    body        TEXT
);
CREATE INDEX IF NOT EXISTS idx_vendor_notices_user_id   ON vendor_notices(user_id);
CREATE INDEX IF NOT EXISTS idx_vendor_notices_vendor_id ON vendor_notices(vendor_id);

CREATE TABLE IF NOT EXISTS invoices (
    id             INTEGER PRIMARY KEY,
    user_id        INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vendor_id      INT NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    invoice_date   DATE,
    total          NUMERIC(10,2),
    status         TEXT NOT NULL DEFAULT 'uploaded',
    image_path     TEXT,
    uploaded_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_invoices_user_id   ON invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_vendor_id ON invoices(vendor_id);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id              INTEGER PRIMARY KEY,
    invoice_id      INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_type       TEXT NOT NULL DEFAULT 'item',
    item_code       TEXT,
    description     TEXT,
    quantity        NUMERIC,
    unit            TEXT,
    unit_price      NUMERIC(10,2),
    line_total      NUMERIC(10,2),
    handwritten_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_invoice_lines_invoice_id ON invoice_lines(invoice_id);

CREATE TABLE IF NOT EXISTS discrepancies (
    id          INTEGER PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invoice_id  INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    item_code   TEXT,
    amount      NUMERIC(10,2),
    status      TEXT NOT NULL DEFAULT 'open',
    explanation TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_discrepancies_user_id    ON discrepancies(user_id);
CREATE INDEX IF NOT EXISTS idx_discrepancies_invoice_id ON discrepancies(invoice_id);

CREATE TABLE IF NOT EXISTS pending_actions (
    id          INTEGER PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invoice_id  INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    details     TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at  DATETIME
);
CREATE INDEX IF NOT EXISTS idx_pending_actions_user_id    ON pending_actions(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_actions_invoice_id ON pending_actions(invoice_id);
