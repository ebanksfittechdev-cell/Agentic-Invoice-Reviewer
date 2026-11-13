# Backend Progress Report — Branch `arodgers`

**To:** Big Pickle  
**From:** Aaron  
**Date:** 2026-11-13  
**Branch:** `arodgers` (ahead of `main`)

---

## What's been built

The Flask backend is fully scaffolded and the code-driven part of the invoice pipeline (upload → extraction → checks) works end to end. The agent stage (Sub-Task 6) is not built yet. Here's what exists and what still needs to be done.

---

## Completed sub-tasks

### 1. Project scaffold & environment
- `requirements.txt` with all pinned deps (`flask`, `flask-sqlalchemy`, `sqlalchemy`, `psycopg2-binary`, `google-genai`, `google-adk`, `bcrypt`, `gunicorn`, `Pillow`)
- `dev-requirements.txt` for test tooling (`pytest>=8.0,<10`)
- `.env.example` documenting all five required env vars
- `config.py` Config class; normalises `DATABASE_URL` to `postgresql+psycopg2://` for SQLAlchemy 2
- `app.py` — `create_app(config_overrides=None)` factory with CORS, blueprints, and SQLAlchemy init
- Root `.gitignore` covering Python, Node, env files, uploads, editors, and OS artefacts

### 2. Postgres schema + demo seed
- `schema.sql` — legacy DDL for all 9 tables with FKs, indexes, and `IF NOT EXISTS`; currently unused because `init_db.py` builds the schema with `db.create_all()`
- `db.py` — SQLAlchemy `db` instance + all 9 ORM models with typed columns and relationships
- `init_db.py` — `db.create_all()` + seeds `demo@store.com / demo1234` with:
  - 2 vendors (Lakeshore Beverages, Summit Foods)
  - 8 agreed costs, 1 active promotion, 1 vendor notice
  - 1 fully-processed invoice with 5 lines, 2 open discrepancies, 2 pending actions

### 3. Auth API
Endpoints: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`

- Passwords bcrypt-hashed
- `user_id` stored in Flask session on login/register
- `current_user_id()` helper used by all protected routes
- Tested manually — all 6 curl cases pass

### 4. Invoice upload + Gemini extraction
- `POST /api/invoices/upload` — accepts JPEG, PNG, WebP, GIF, PDF
- Saves file with UUID filename, creates `invoices` row
- Calls Gemini 1.5 Pro once via `google-genai` SDK to extract: invoice number, date, total, all line items + handwritten notes
- Prompt is injection-resistant (treats on-invoice text as data only)
- `verify_total()` checks line sum vs stated total (`Decimal`, $0.01 tolerance); sets `status = needs_review` on mismatch
- `GET /api/invoices/` and `GET /api/invoices/:id` also implemented

### 5. Six discrepancy checks
`backend/invoices/discrepancy_checks.py` — pure code, no model involved:

| Check | Logic |
|-------|-------|
| price | `unit_price` vs `agreed_costs.cost`; signed amount (+ = overcharge, − = undercharge) |
| quantity | Parses `handwritten_note` for `rec'd N`; flags billed vs received diff |
| line_arithmetic | `qty × unit_price ≈ line_total` within $0.01 |
| duplicate_invoice | Same `vendor_id` + `invoice_number`, different `id` |
| promotion | Active promo on `invoice_date`; flags missing or partial credit (amount = shortfall); credit `line_total` normalised with `abs()` to handle both sign conventions |
| deposit | `qty × agreed deposit rate` vs billed `line_total` |

Also: `GET /api/invoices/discrepancies` — returns all discrepancies for the logged-in store.

---

## Review flags addressed

A round of code review found five flags. All are fixed and committed:

| # | Severity | Flag | Fix |
|---|----------|------|-----|
| 1 | HIGH | Silent `ImportError` swallow hiding real errors | Narrowed to `ModuleNotFoundError` with `exc.name` check; re-raises everything else with `logging.exception` |
| 2 | MED | README documented wrong path (`/api/discrepancies`) | Fixed to `/api/invoices/discrepancies` |
| 3 | MED | Partial promo credit silently passed | Now compares total credit amount vs `allowance × qty`; flags shortfall |
| 4 | LOW | Price check direction undocumented | Both over/undercharges flagged; amount is signed; decision documented in code |
| 5 | HIGH | Tests ran against real Postgres dev DB (dropped all 9 tables) | Root cause: `config.update()` after `db.init_app()` was ignored. Fixed: overrides now applied before `db.init_app()`. Added mandatory SQLite engine guard (`assert drivername == 'sqlite'`) that aborts loudly before any `create_all()`. DB restored. |

---

## Test suite

**Run command:** `python -m pytest tests/test_discrepancy_checks.py -v`  
**Result: 22 passed, 0 failed (4.99s), re-verified locally**  
**Engine:** `sqlite:///:memory:` — Postgres was not touched (row counts identical before/after)  
**Warning:** one harmless `DeprecationWarning` from `google-genai`'s `types.py` (not project code)

Coverage: all six checks (price, quantity, line_arithmetic, duplicate_invoice, promotion, deposit) plus user-scoping on `/api/invoices/discrepancies` and unauthenticated 401.

To run:
```bash
cd backend
source venv/bin/activate
python -m pytest tests/test_discrepancy_checks.py -v
```

---

## Current state of Postgres dev DB

All 9 tables present, demo data intact:

| Table | Rows |
|-------|------|
| users | 1 |
| vendors | 2 |
| agreed_costs | 8 |
| promotions | 1 |
| vendor_notices | 1 |
| invoices | 1 |
| invoice_lines | 5 |
| discrepancies | 2 |
| pending_actions | 2 |

**Data-loss caveat:** this is demo data only. The Flag 5 wipe destroyed the temporary `pickle@store.com` and `test@store.com` accounts created during manual auth testing. `init_db.py` restores only `demo@store.com / demo1234`; the other accounts must be re-registered if needed.

---

## Commit log (branch `arodgers`)

```
bd6a693  docs: add progress report for Big Pickle
a4ad461  fix: safe test isolation, credit sign normalisation, dev-requirements
d64bdf9  fix: address five review flags on discrepancy checks
7d759b5  chore: ignore cookies.txt test artifact
0c4f4b8  feat(checks): six discrepancy checks + GET /api/invoices/discrepancies
08d107d  feat(invoices): upload endpoint, Gemini 1.5 Pro extraction, verify_total
4d599a2  refactor: migrate from psycopg2 to SQLAlchemy ORM
a699ec3  feat(auth): register, login, logout, /me endpoints with bcrypt + session
9de5ea4  chore: add root .gitignore
51b8d73  feat: scaffold backend — schema, DB pool, blueprint stubs, demo seed
```

---

## What's next

| Sub-task | Status |
|----------|--------|
| Sub-Task 6 — Google ADK agent (5 read tools + 4 write tools, 8-call limit) | **Not started** |
| Sub-Task 7 — Approval & history endpoints (`approve`, `reject`, `GET /api/actions`, JSON import) | **Not started** |

The upload flow already has stub hooks for both — `run_checks()` is wired in and working; `run_agent()` will drop in without touching the upload route once Sub-Task 6 is done.

---

## How to get set up

```bash
git checkout arodgers
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, GEMINI_API_KEY
python init_db.py      # creates tables + seeds demo@store.com / demo1234
flask run              # http://localhost:5000
```
