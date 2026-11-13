# Agentic Invoice Reviewer

A web app for independent grocers: code checks supplier invoices against the store's records, an agent decides which mismatches are real, and the owner approves disputes and cost updates.

**Stack:** React · Flask · Postgres · Google ADK · Gemini 1.5 Pro

---

## What it does

> The model reads, code calculates, the agent judges, the owner decides.

1. User attaches an invoice image or PDF in chat.
2. Code saves the file and creates an `invoices` row (status `uploaded`).
3. Gemini (one call) extracts lines, fees, and handwritten notes as JSON — not the agent.
4. Code checks the lines add up to the total. If not, status → `needs_review`.
5. Code runs six checks and saves each mismatch to `discrepancies`:
   - Price vs agreed cost
   - Billed qty vs handwritten "rec'd"
   - Line arithmetic
   - Duplicate invoice number
   - Promotion not applied
   - Deposit math
6. The agent runs only if there is at least one mismatch. It investigates each one, decides real / explained / ask owner, and creates pending actions.
7. Chat shows the agent's summary plus one card per pending action, with Approve / Reject.
8. Code applies approvals: dispute marked ready, cost file updated, or payment held.

The same chat answers questions such as "How much did Lakeshore overcharge us this month?" using the agent's read tools.

---

## Project structure

```
Agentic-Invoice-Reviewer/
├── backend/
│   ├── app.py                     # Flask application factory
│   ├── config.py                  # Config class from env vars
│   ├── db.py                      # SQLAlchemy db instance + all 9 ORM models
│   ├── schema.sql                 # All 9 table definitions (reference)
│   ├── init_db.py                 # Create schema + seed demo data
│   ├── history_schema.md          # JSON format for store record imports
│   ├── requirements.txt
│   ├── dev-requirements.txt       # pytest (test dependencies)
│   ├── .env.example
│   ├── auth/
│   │   ├── routes.py              # Register, login, logout, /me
│   │   └── utils.py               # current_user_id() helper
│   ├── invoices/
│   │   ├── routes.py              # Upload, list, detail, discrepancies
│   │   ├── extractor.py           # Gemini 1.5 Pro extraction call
│   │   ├── checks.py              # verify_total()
│   │   └── discrepancy_checks.py  # Six rule-based checks
│   ├── agent/
│   │   ├── agent.py               # Google ADK LlmAgent definition
│   │   ├── tools.py               # 5 read tools + 4 write tools
│   │   └── runner.py              # run_agent() — session, state, 8-call limit
│   ├── actions/
│   │   └── routes.py              # List, approve, reject pending actions
│   ├── history/
│   │   └── routes.py              # JSON store-records import
│   └── tests/                     # 93 tests, in-memory SQLite
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_upload.py
│       ├── test_checks.py
│       ├── test_discrepancy_checks.py
│       ├── test_agent_tools.py
│       ├── test_actions.py
│       └── test_history.py
└── frontend/
    ├── vite.config.js             # /api proxy to the backend
    ├── .env.example               # VITE_API_PROXY
    └── src/
        ├── App.jsx
        └── login page/
            ├── login.jsx          # Login + register forms
            └── login.css
```

---

## Getting started from a fresh clone

These steps take a blank machine to a running app at `http://localhost:5173`.
You need **two terminals**: one for the Flask API, one for Vite.

### 0. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Git | any recent | |
| Python | 3.11+ | `python3 --version` |
| PostgreSQL | 14+ | server and client |
| Node.js | 20+ | includes `npm` |
| Gemini API key | — | https://aistudio.google.com/app/apikey |

On Debian/Ubuntu, also install the venv package:

```bash
sudo apt install -y python3-venv
```

Install Node 20+ from your distro or NodeSource if `node --version` is missing
or too old.

### 1. Clone the repository

```bash
git clone https://github.com/ebanksfittechdev-cell/Agentic-Invoice-Reviewer.git
cd Agentic-Invoice-Reviewer

# Active development branch:
git switch arodgers
```

### 2. Install and start PostgreSQL

Fedora / RHEL:

```bash
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
```

Debian / Ubuntu:

```bash
sudo apt update
sudo apt install -y postgresql
sudo systemctl enable --now postgresql
```

Create the role and database used by the example `.env`:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER invoice_user WITH PASSWORD 'invoice_pass';
CREATE DATABASE invoice_reviewer OWNER invoice_user;
SQL
```

If the role/database already exist, skip this. To reset the password:

```bash
sudo -u postgres psql -c "ALTER USER invoice_user WITH PASSWORD 'invoice_pass';"
```

Verify the connection:

```bash
psql "postgresql://invoice_user:invoice_pass@localhost:5432/invoice_reviewer" -c "SELECT 1;"
```

### 3. Backend (Flask API) — terminal 1

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
```

Edit `backend/.env`:

```env
DATABASE_URL=postgresql://invoice_user:invoice_pass@localhost:5432/invoice_reviewer
SECRET_KEY=<output of the command below>
GEMINI_API_KEY=<your Gemini API key>
UPLOAD_FOLDER=/tmp/invoice_uploads
FLASK_ENV=development
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Generate `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Create the schema and demo data:

```bash
mkdir -p /tmp/invoice_uploads
python init_db.py
```

Expected output on a fresh database:

```
Schema applied.
Demo account seeded: demo@store.com / demo1234
```

If the demo user already exists, it prints `already exists — skipping seed`.

Start the API:

```bash
flask run
# http://127.0.0.1:5000
```

Leave this terminal running. To reach the API from another machine, use:

```bash
flask run --host=0.0.0.0 --port=5000
```

Sanity check (new terminal):

```bash
curl -i http://127.0.0.1:5000/api/auth/me   # HTTP/1.1 401 (expected logged out)
```

### 4. Frontend (React + Vite) — terminal 2

From the repo root:

```bash
cd frontend
npm install
cp .env.example .env      # optional for a local backend
npm run dev
# http://localhost:5173
```

`frontend/.env` defaults to:

```env
VITE_API_PROXY=http://127.0.0.1:5000
```

The Vite dev server proxies `/api` requests to that URL, so the browser only
talks to `http://localhost:5173` and CORS is not involved.

### 5. Log in

Open http://localhost:5173 and use the demo account:

- Email: `demo@store.com`
- Password: `demo1234`

Registration also works; on success it returns to the Log In tab. A successful
login shows an alert: `Logged in as <store name>`.

### 6. Run the tests

```bash
cd backend
source venv/bin/activate
pip install -r dev-requirements.txt
python -m pytest -q        # 93 tests
```

The suite uses an in-memory SQLite database and never touches Postgres. A guard
aborts the run if the bound engine is not SQLite.

### 7. Frontend and backend on different machines

On the **backend machine**:

```bash
flask run --host=0.0.0.0 --port=5000
hostname -I                       # note the LAN IP
# open the firewall if needed, e.g. sudo ufw allow 5000/tcp
```

On the **frontend machine**:

```bash
cd frontend
cp .env.example .env
# set VITE_API_PROXY=http://<backend-lan-ip>:5000
npm run dev -- --host 0.0.0.0
```

Verify from the frontend machine:

```bash
curl http://<backend-lan-ip>:5000/api/auth/me   # 401 = reachable
curl http://localhost:5173/api/auth/me          # 401 = proxy working
```

### 8. Stopping the servers

Press `Ctrl+C` in each terminal. If you started them in the background, stop the
processes listening on ports 5000 and 5173.

### Troubleshooting

- **"Connection refused" from the frontend**: the backend isn't running or the
  proxy target is wrong. `curl http://127.0.0.1:5000/api/auth/me` should return
  401. The proxy uses `127.0.0.1`, not `localhost`, because `localhost` often
  resolves to IPv6 (`::1`) while Flask listens only on IPv4.
- **`psql: FATAL: password authentication failed`**: re-check `DATABASE_URL` and
  the role/password from step 2.
- **`init_db.py` cannot connect**: Postgres isn't running
  (`sudo systemctl status postgresql`) or the database doesn't exist.
- **CORS errors**: only relevant when the browser calls the API directly. Add the
  frontend origin to `FRONTEND_ORIGINS` in `backend/.env`.
- **Upload returns `needs_review`**: `GEMINI_API_KEY` is missing/invalid or
  extraction failed; the invoice is saved for manual review.
- **Port already in use**: stop the old process or use
  `flask run --port=5001` (and update `VITE_API_PROXY` to match).
- **`localhost:5173` unreachable from another machine**: start Vite with
  `npm run dev -- --host 0.0.0.0`.

---

## API overview

All endpoints require a session cookie (set at login) except `/api/auth/register` and `/api/auth/login`.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, sets session cookie |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/auth/me` | Current user info |
| POST | `/api/invoices/upload` | Upload invoice image or PDF |
| GET | `/api/invoices/` | List invoices with status |
| GET | `/api/invoices/:id` | Invoice detail (lines, discrepancies, actions) |
| GET | `/api/invoices/discrepancies` | All discrepancies for the store |
| GET | `/api/actions/` | All pending actions for the store |
| POST | `/api/actions/:id/approve` | Approve — applies side-effect per action type |
| POST | `/api/actions/:id/reject` | Reject — sets decided_at only, no data change |
| POST | `/api/history/import` | Upsert vendors, costs, promos, notices from JSON |

See `backend/history_schema.md` for the JSON import format.

---

## Database

Postgres, 9 tables. One account = one store. Every table except `users` and `invoice_lines` carries `user_id`, and every query filters by it.

| Table | Purpose |
|-------|---------|
| `users` | Store accounts |
| `vendors` | Supplier records |
| `agreed_costs` | Contracted prices per item |
| `promotions` | Active allowances and their date ranges |
| `vendor_notices` | Price-change and promo emails |
| `invoices` | One row per uploaded invoice |
| `invoice_lines` | Extracted line items |
| `discrepancies` | Mismatches found by the checks |
| `pending_actions` | Agent proposals awaiting owner decision |

**Status values:**

```
invoices.status:          uploaded · checked · needs_review · do_not_pay
invoice_lines.line_type:  item · credit · fee · deposit
discrepancies.status:     open · explained · disputed · asked_owner
pending_actions.status:   pending · approved · rejected
```

---

## Frontend screens

> Current status: only Login and Register are implemented. A successful login
> shows an alert; registration returns to the Log In tab. The remaining screens
> are planned.

| Screen | Description |
|--------|-------------|
| Login | Email + password; demo account pre-loaded |
| Register | Store name, email, password |
| Chat | Attach invoice, view agent summary, approve/reject action cards |
| Upload history | Import store records JSON |
| View history | Browse invoices, discrepancies, actions, agreed costs |
| Log out | Sidebar button, returns to Login |

---

## Intentionally left out (roadmap)

- Onboarding and account settings
- Saved chat history (sessions are in-memory; results persist in Postgres)
- Purchase orders and receiving screen
- Sending real email (Approve copies dispute text)
- Email, POS, and vendor-portal integrations
- Weekly vendor pattern reports
- Editing extracted lines in the UI
- Multiple users per store, roles, password reset
