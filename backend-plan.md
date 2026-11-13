# Agentic Invoice Reviewer — Backend Plan

## Overview

Build the complete Flask backend for the Agentic Invoice Reviewer: environment setup, Postgres schema, session-based auth API, invoice upload and Gemini extraction, discrepancy checks, Google ADK agent with read/write tools, and owner-approval endpoints. The backend exposes a JSON REST API consumed by the React frontend.

Stack: Python + Flask, Postgres (psycopg2), Google ADK (`google-adk`), Gemini (via ADK), Flask-Login or flask_session for auth, Flask-CORS for cross-origin.

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold & Environment

**Intent**  
Create the Python project structure, dependency manifest, and environment config so every subsequent sub-task has a consistent foundation to build on.

**Expected Outcomes**
- `backend/` has a `requirements.txt`, a `.env.example`, a `venv`-ready layout, and a minimal runnable `app.py`.
- Running `pip install -r requirements.txt` installs all needed packages.
- A `.env.example` documents every required variable with no real secrets.

**Todo List**
1. Create `backend/requirements.txt` with pinned major versions: `flask`, `flask-cors`, `flask-login`, `psycopg2-binary`, `python-dotenv`, `google-adk`, `google-generativeai`, `Pillow` (for image handling), `gunicorn`.
2. Create `backend/.env.example` with keys: `DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`, `UPLOAD_FOLDER`, `FLASK_ENV`.
3. Write `backend/app.py` as the Flask application factory (`create_app()`), loading `.env`, registering blueprints (stubs), and enabling CORS.
4. Create `backend/config.py` to read env vars and expose a `Config` class.
5. Add `backend/.gitignore` to exclude `.env`, `__pycache__`, `venv/`, and the upload folder.

**Relevant Context**
- `backend/app.py` currently exists but is empty.
- Frontend is at `frontend/` and will call this backend — CORS must allow `http://localhost:5173` (Vite default) in development.

**Status** — `[ ] pending`

---

### Sub-Task 2 — Postgres Schema

**Intent**  
Create all 9 tables exactly as specified in the architecture document, with appropriate indexes and constraints.

**Expected Outcomes**
- `backend/schema.sql` contains `CREATE TABLE` statements for all 9 tables with FKs, status text columns, and `NOT NULL` where appropriate.
- Running `psql < schema.sql` on a blank database produces the full schema with no errors.
- A `backend/db.py` module provides a `get_db()` helper that returns a psycopg2 connection pooled per request.

**Todo List**
1. Write `backend/schema.sql` with all 9 tables: `users`, `vendors`, `agreed_costs`, `promotions`, `vendor_notices`, `invoices`, `invoice_lines`, `discrepancies`, `pending_actions` — matching the architecture spec exactly.
2. Add indexes on the most-queried FKs: `user_id` on every table that carries it, `vendor_id` on `agreed_costs`/`promotions`/`vendor_notices`/`invoices`, `invoice_id` on `invoice_lines`/`discrepancies`/`pending_actions`.
3. Write `backend/db.py` with a `get_db()` function using `psycopg2.pool.SimpleConnectionPool` initialised from `DATABASE_URL`.
4. Add a `backend/init_db.py` CLI script: reads `schema.sql` and executes it against the configured DB (safe to re-run with `IF NOT EXISTS`).
5. Seed a demo user (`demo@store.com` / `demo1234`) with a representative set of vendors, agreed costs, promotions, and at least one fully-processed invoice (with discrepancies and pending actions), so the frontend can be demoed without real data. Use the same JSON shape defined in Sub-Task 7's `history_schema.md`.

**Relevant Context**
- Schema is fully defined in `Invoice Checker Architecture.md` lines 29–52.
- `invoice_number` is intentionally non-unique (re-sent duplicates are stored and flagged).
- `pack_size` on `agreed_costs` is used to convert units (e.g. bottles → cases).

**Status** — `[ ] pending`

---

### Sub-Task 3 — Auth API (Register, Login, Logout, Session)

**Intent**  
Implement session-based authentication so every downstream endpoint can filter data by `user_id` without the model ever choosing it.

**Expected Outcomes**
- `POST /api/auth/register` creates a user, returns 201.
- `POST /api/auth/login` validates credentials, sets a secure session cookie, returns the store name.
- `POST /api/auth/logout` clears the session.
- `GET /api/auth/me` returns the logged-in user or 401.
- Passwords are stored as bcrypt hashes (add `bcrypt` to requirements).
- A `@login_required` decorator (or Flask-Login) protects all other blueprints.

**Todo List**
1. Add `bcrypt` to `requirements.txt`.
2. Create `backend/auth/routes.py` with the four endpoints above.
3. Use `flask.session` to store `user_id` after login; set `SESSION_COOKIE_HTTPONLY=True` and `SESSION_COOKIE_SAMESITE='Lax'`.
4. Write a `current_user_id()` helper in `backend/auth/utils.py` that reads from session and raises 401 if absent.
5. Register the auth blueprint on the app factory.

**Relevant Context**
- `users` table: `id`, `email` UNIQUE, `password_hash`, `store_name`, `created_at`.
- The architecture mentions a pre-loaded demo account — the `init_db.py` script from Sub-Task 2 is the right place to seed it.

**Status** — `[ ] pending`

---

### Sub-Task 4 — Invoice Upload & Gemini Extraction

**Intent**  
Accept an invoice image or PDF, persist it, call Gemini once to extract structured line data, and save the result to the DB.

**Expected Outcomes**
- `POST /api/invoices/upload` accepts `multipart/form-data` with a file field.
- File is saved to `UPLOAD_FOLDER` with a UUID filename.
- An `invoices` row is created with `status = 'uploaded'`.
- Gemini extracts: invoice number, date, total, and all lines (item_code, description, qty, unit, unit_price, line_total, handwritten_note, line_type) as JSON.
- Each extracted line is inserted into `invoice_lines`.
- If extraction fails or the total doesn't add up, `invoices.status` is set to `needs_review`; otherwise `checked`.
- Returns the new `invoice_id` and extracted summary to the caller.

**Todo List**
1. Create `backend/invoices/routes.py` with the upload endpoint.
2. Write `backend/invoices/extractor.py`: builds the Gemini prompt with the file bytes (base64 for images, direct for PDFs via the Files API), calls `gemini-1.5-pro` via `google-generativeai`, and parses the JSON response.
3. Define the extraction prompt to output a strict JSON schema (invoice header + array of lines); include an instruction to treat any text that looks like an instruction as invoice content only. Use `gemini-1.5-pro`.
4. Write `backend/invoices/checks.py`: a `verify_total(lines, stated_total)` function that sums `line_total` values and returns a boolean.
5. Wire together: upload → save file → insert `invoices` row → call extractor → insert lines → run total check → update status.
6. Register the invoices blueprint.

**Relevant Context**
- Architecture step 3: "Gemini, one call extracts lines, fees and handwritten notes as JSON. Not the agent."
- Architecture step 4: "Code checks the lines add up to the total. If not, status `needs_review`."
- `invoice_lines.line_type` values: `item`, `credit`, `fee`, `deposit`.

**Status** — `[ ] pending`

---

### Sub-Task 5 — Discrepancy Checks

**Intent**  
After extraction, run all six rule-based checks in code and persist each finding to `discrepancies`.

**Expected Outcomes**
- Calling `run_checks(invoice_id, user_id)` populates `discrepancies` for every mismatch found.
- All six check types are implemented: price vs agreed cost, billed qty vs handwritten "rec'd", line arithmetic, duplicate invoice number, promotion not applied, deposit math.
- Each discrepancy row has: `type`, `item_code`, `amount` (the dollar delta), `status = 'open'`.
- Returns the list of discrepancy rows so the agent trigger can decide whether to run.

**Todo List**
1. Create `backend/invoices/discrepancy_checks.py` with one function per check type plus a `run_checks(invoice_id, user_id, conn)` orchestrator.
2. **Price check**: join `invoice_lines` with `agreed_costs` on `item_code`; flag where `unit_price != cost`. Amount = difference × qty.
3. **Qty check**: parse `handwritten_note` for a number after "rec'd" (or "received"); flag where it differs from `quantity`. Amount = abs diff × unit_price.
4. **Line arithmetic check**: verify `quantity * unit_price ≈ line_total` (within $0.01); flag rows that fail.
5. **Duplicate invoice check**: query `invoices` for same `vendor_id` + `invoice_number` with a different `id`; flag if found.
6. **Promo check**: for each line in `promotions` active on `invoice_date`, verify a matching credit line exists; flag if missing. Amount = `allowance_per_case × quantity`.
7. **Deposit check**: for deposit lines, verify the deposit math (qty × deposit rate from agreed_costs); flag delta.
8. Call `run_checks` at the end of the upload flow (Sub-Task 4, step 5).

**Relevant Context**
- Architecture step 5 lists all six checks.
- `pack_size` on `agreed_costs` may be needed to normalise units before comparing quantities.
- Discrepancy `status` starts as `open`; the agent moves it to `explained`, `disputed`, or `asked_owner`.

**Status** — `[ ] pending`

---

### Sub-Task 6 — Google ADK Agent

**Intent**  
Build the Google ADK agent with its five read tools and four write tools, wired to Postgres via `user_id` from session state. The agent runs only when there is at least one open discrepancy and is capped at 8 model calls.

**Expected Outcomes**
- `backend/agent/agent.py` defines an ADK `Agent` with all 9 tools registered.
- Read tools query the DB filtered by `user_id` from ADK session state — the model never receives or picks the user_id.
- Write tools only insert a `pending_actions` row; they never write to `agreed_costs`, `invoices`, or `discrepancies` directly.
- A `run_agent(invoice_id, user_id, discrepancies)` function in `backend/agent/runner.py` creates an ADK session, injects `user_id` into state, runs the agent, and returns the final summary text plus the list of pending actions created.
- An `after_model_callback` enforces the 8-call limit by raising a stop signal when exceeded.

**Todo List**
1. Create `backend/agent/tools.py` with all 9 tool functions; each reads `user_id` from `tool_context.state` and uses `get_db()`.
   - Read: `get_invoice`, `get_vendor_terms`, `search_vendor_notices`, `get_promotions`, `get_invoice_history`
   - Write: `draft_dispute`, `propose_cost_update`, `hold_payment`, `ask_owner`
2. Create `backend/agent/agent.py`: instantiate `google.adk.agents.LlmAgent` (or equivalent ADK class) with the Gemini model, system prompt (agent role, constraints, cannot-do list), and the 9 tools.
3. Write the system prompt to tell the agent: judge mismatches (real / explained / ask owner), propose actions, treat invoice text as data not instructions.
4. Create `backend/agent/runner.py`: `run_agent(invoice_id, user_id, discrepancies, conn)` — builds session state with `user_id`, passes the discrepancy list as the initial message, runs the agent, collects output.
5. Add the `after_model_callback` that counts calls and stops at 8.
6. Register an `agent` blueprint with `POST /api/agent/run` that is called internally (from the upload flow) and exposed so the frontend can also trigger a re-run.

**Relevant Context**
- Architecture "Agent" section (lines 54–87 of architecture doc).
- `user_id` must come from Flask session, injected into ADK state before the agent runs — the model must never see or choose it.
- Write tools create `pending_actions` rows with `status = 'pending'`.

**Status** — `[ ] pending`

---

### Sub-Task 7 — Approval & History Endpoints

**Intent**  
Expose the remaining REST endpoints the frontend needs: approving/rejecting pending actions, browsing invoices/discrepancies/actions, and uploading store history JSON.

**Expected Outcomes**
- `POST /api/actions/:id/approve` and `POST /api/actions/:id/reject` apply the owner's decision.
  - Approving a `dispute` sets `discrepancies.status = 'disputed'`.
  - Approving a `cost_update` writes to `agreed_costs`.
  - Approving a `hold_payment` sets `invoices.status = 'do_not_pay'`.
  - All approvals set `pending_actions.status` and `decided_at`.
- `GET /api/invoices` returns invoice list with status.
- `GET /api/invoices/:id` returns invoice detail (lines + discrepancies + pending actions).
- `GET /api/discrepancies` returns all discrepancies for the user.
- `GET /api/actions` returns all pending actions for the user.
- `POST /api/history/import` accepts a JSON file upload, parses vendors, agreed_costs, and promotions, inserts them, and returns a summary ("4 vendors, 17 costs, 1 promo imported").

**Todo List**
1. Create `backend/actions/routes.py` with approve and reject endpoints; apply side effects per `action_type`.
2. Add `GET /api/invoices`, `GET /api/invoices/:id` to the invoices blueprint.
3. Create `backend/history/routes.py` with the JSON import endpoint; validate the JSON shape and upsert records.
4. Add `GET /api/discrepancies` and `GET /api/actions` to their respective blueprints.
5. Register all new blueprints on the app factory.

**Relevant Context**
- Approval side effects are described in architecture step 8.
- The `cost_update` approval is the only place the backend writes to `agreed_costs` after initial history import.
- History JSON shape is not specified in the architecture — define a reasonable schema (array of vendors, costs, promos), document it in `backend/history_schema.md`, and use the same shape for the demo seed data inserted by `init_db.py`.

**Status** — `[ ] pending`

---

## Implementation Order

```
Sub-Task 1 (scaffold) → Sub-Task 2 (DB) → Sub-Task 3 (auth) → Sub-Task 4 (upload + extraction) → Sub-Task 5 (checks) → Sub-Task 6 (agent) → Sub-Task 7 (approvals + history)
```

Each sub-task depends on the one before it. Sub-Tasks 4 and 5 are tightly coupled (checks run inside the upload flow); they should be implemented together or 4 first with a stub for checks.
