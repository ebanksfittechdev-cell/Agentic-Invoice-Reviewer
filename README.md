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
│   ├── app.py                  # Flask application factory
│   ├── config.py               # Config class from env vars
│   ├── db.py                   # Postgres connection pool
│   ├── schema.sql              # All 9 table definitions
│   ├── init_db.py              # Create schema + seed demo data
│   ├── history_schema.md       # JSON format for store record imports
│   ├── requirements.txt
│   ├── .env.example
│   ├── auth/
│   │   ├── routes.py           # Register, login, logout, /me
│   │   └── utils.py            # current_user_id() helper
│   ├── invoices/
│   │   ├── routes.py           # Upload, list, detail endpoints
│   │   ├── extractor.py        # Gemini 1.5 Pro extraction call
│   │   ├── checks.py           # verify_total()
│   │   └── discrepancy_checks.py  # Six rule-based checks
│   ├── agent/
│   │   ├── agent.py            # Google ADK LlmAgent definition
│   │   ├── tools.py            # 5 read tools + 4 write tools
│   │   └── runner.py           # run_agent() — session, state, callback
│   ├── actions/
│   │   └── routes.py           # Approve / reject pending actions
│   └── history/
│       └── routes.py           # JSON store-records import
└── frontend/
    └── src/
        ├── App.jsx
        └── login page/
```

---

## Getting started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- A Google Cloud project with the Gemini API enabled
- Node 20+ (for the frontend)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, GEMINI_API_KEY

python init_db.py          # creates tables + seeds demo account
flask run                  # starts on http://localhost:5000
```

Demo account: `demo@store.com` / `demo1234` — pre-loaded with vendors, costs, and invoice history.

### Frontend

```bash
cd frontend
npm install
npm run dev                # starts on http://localhost:5173
```

The Vite dev server proxies `/api` requests to the backend. By default it targets
`http://127.0.0.1:5000` (IPv4). To point at a different backend, copy
`frontend/.env.example` to `frontend/.env` and set `VITE_API_PROXY`.

#### Troubleshooting: "connection refused" from the frontend

- Start the backend (`flask run`) before the frontend, and confirm it responds:
  `curl http://127.0.0.1:5000/api/auth/me` should return `401`, not a connection error.
- If the browser and backend are on the same machine, no extra config is needed.
  The proxy uses `127.0.0.1`, not `localhost`, because on many systems
  `localhost` resolves to IPv6 (`::1`) while Flask listens only on IPv4.
- If the backend runs on another machine, start it with
  `flask run --host=0.0.0.0` and set `VITE_API_PROXY=http://<backend-ip>:5000`
  in `frontend/.env`.
- If the frontend runs on a non-default origin/port, set `FRONTEND_ORIGINS`
  (comma-separated) in `backend/.env` for CORS.

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
| GET | `/api/invoices` | List invoices with status |
| GET | `/api/invoices/:id` | Invoice detail (lines, discrepancies, actions) |
| GET | `/api/invoices/discrepancies` | All discrepancies for the store |
| GET | `/api/actions` | All pending actions for the store |
| POST | `/api/actions/:id/approve` | Approve a pending action |
| POST | `/api/actions/:id/reject` | Reject a pending action |
| POST | `/api/history/import` | Import store records JSON |

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
