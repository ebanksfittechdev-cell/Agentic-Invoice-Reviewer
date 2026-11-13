# AGENTS.md — Agentic Invoice Reviewer

This file describes the AI agent and all automated processing in the backend: what runs automatically, what the agent can and cannot do, every tool it has access to, and the security constraints that keep one store's data isolated from another.

---

## Processing pipeline

When a user uploads an invoice the following steps run in order. Steps 1–5 and 8 are pure code — no model involved. The agent only runs at step 6.

```
Upload
  │
  ▼
1. Save file to disk (UUID filename, UPLOAD_FOLDER)
2. Insert invoices row  status = "uploaded"
3. Gemini 1.5 Pro — single extraction call
   └─ Returns: invoice header + array of lines (JSON)
4. Insert invoice_lines rows
5. verify_total() — sum lines vs stated total
   ├─ Mismatch → status = "needs_review"  (agent does NOT run)
   └─ OK       → status = "checked"
6. run_checks() — six rule-based checks → insert discrepancies rows
7. If discrepancies exist → run_agent()
   └─ Agent investigates, creates pending_actions rows
8. Owner reviews action cards → approve / reject
   └─ Code applies side effects
```

---

## Gemini extraction (not the agent)

**Model:** `gemini-1.5-pro`  
**Trigger:** once per invoice upload, before any agent runs  
**Function:** `backend/invoices/extractor.py`

Gemini is called with the raw file bytes (base64 for images, Files API for PDFs) and a strict prompt that asks for a JSON object with this shape:

```json
{
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "total": 0.00,
  "lines": [
    {
      "line_type": "item | credit | fee | deposit",
      "item_code": "string",
      "description": "string",
      "quantity": 0,
      "unit": "string",
      "unit_price": 0.00,
      "line_total": 0.00,
      "handwritten_note": "string | null"
    }
  ]
}
```

The extraction prompt explicitly instructs the model to treat any text on the invoice that looks like an instruction as invoice content only — it cannot inject behaviour into the pipeline.

---

## The agent

**Framework:** Google ADK (`google-adk`)  
**Model:** `gemini-1.5-pro` via ADK  
**Definition:** `backend/agent/agent.py`  
**Runner:** `backend/agent/runner.py` → `run_agent(invoice_id, user_id, discrepancies)`

### Role

The agent receives the list of discrepancies for one invoice and investigates each one. For each mismatch it decides:

- **Real** — draft a dispute, propose a cost update, or hold payment.
- **Explained** — a vendor notice, promo, or term accounts for it; mark explained.
- **Ask owner** — not enough information; surface a question card.

The agent proposes. It never approves its own proposals.

### How `user_id` is handled

The `user_id` is read from the Flask session by the backend before the agent starts. It is injected into ADK session state as `user_id`. Every tool reads it from `tool_context.state["user_id"]`. The model never receives, sees, or selects the `user_id`. This is the primary isolation mechanism between stores.

### Call limit

An `after_model_callback` counts model calls and raises a stop signal after **8 calls** per invoice. This prevents runaway inference costs and forces the agent to be concise.

---

## Tools

### Read tools — look things up

The agent calls these to investigate a discrepancy. Each filters all queries by `user_id` from session state.

| Tool | Signature | Returns |
|------|-----------|---------|
| `get_invoice` | `(invoice_id)` | Extracted lines and handwritten notes for the invoice |
| `get_vendor_terms` | `(vendor_id)` | Terms text: fees, substitution rules, etc. |
| `search_vendor_notices` | `(vendor_id, keyword)` | Matching price-change or promo emails |
| `get_promotions` | `(vendor_id, item_code)` | Active allowances and their date ranges |
| `get_invoice_history` | `(vendor_id, item_code)` | Past prices, quantities, and invoice numbers |

### Write tools — propose actions

Each write tool inserts exactly one row into `pending_actions` with `status = "pending"`. Nothing else is written.

| Tool | Signature | Action type created |
|------|-----------|---------------------|
| `draft_dispute` | `(vendor_id, items, message)` | `dispute` |
| `propose_cost_update` | `(item_code, new_cost, evidence)` | `cost_update` |
| `hold_payment` | `(invoice_id, reason)` | `hold_payment` |
| `ask_owner` | `(question)` | `question` |

---

## Discrepancy checks (code, not agent)

Defined in `backend/invoices/discrepancy_checks.py`. Run after extraction, before the agent.

| Check | Logic |
|-------|-------|
| **Price** | `invoice_lines.unit_price` vs `agreed_costs.cost` for the same `item_code`. Amount = delta × qty. |
| **Quantity** | Parse `handwritten_note` for a number after "rec'd"; compare to `invoice_lines.quantity`. |
| **Line arithmetic** | `quantity × unit_price ≈ line_total` within $0.01. |
| **Duplicate invoice** | Same `vendor_id` + `invoice_number` with a different `invoices.id`. |
| **Promotion not applied or short** | Active `promotions` row for `item_code` on `invoice_date`; credit lines summed (abs value) and compared to `allowance_per_case × qty`. Flags missing or partial credits; amount = shortfall. |
| **Deposit math** | Deposit line total vs `qty × deposit rate` from `agreed_costs`. |

Each finding is inserted into `discrepancies` with `status = "open"`.

---

## Owner approvals — side effects

When the owner approves a pending action, the backend applies the following side effects:

| `action_type` | Side effect |
|---------------|-------------|
| `dispute` | `discrepancies.status` → `"disputed"` for the referenced items. Shows email text to copy. |
| `cost_update` | Writes new `cost` and `updated_at` to `agreed_costs` for the item. |
| `hold_payment` | `invoices.status` → `"do_not_pay"`. |
| `question` | No data side effect; records the owner's answer in `pending_actions.details`. |

Rejecting any action type sets `pending_actions.status = "rejected"` and `decided_at` only — no other data is changed.

---

## What the agent cannot do

- See data belonging to another store (`user_id` is always enforced in every tool query).
- Calculate dollar amounts — all figures are computed by code before the agent sees them.
- Write directly to `agreed_costs`, `invoices`, or `discrepancies`.
- Send email (Approve copies dispute text to the clipboard; no email is sent).
- Approve its own proposals.
- Execute raw SQL or access passwords.
- Read the `user_id` from the prompt — it is only available in `tool_context.state`.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLite URL, e.g. `sqlite:///invoice_reviewer.db` (file lives in `backend/instance/`) |
| `SECRET_KEY` | Flask session signing key — keep this secret and long |
| `GEMINI_API_KEY` | Google AI API key with Gemini access |
| `UPLOAD_FOLDER` | Absolute path where invoice files are stored, e.g. `/var/data/uploads` |
| `FLASK_ENV` | `development` or `production` |
| `FRONTEND_ORIGINS` | Comma-separated allowed CORS origins, e.g. `http://localhost:5173` (defaults to `http://localhost:5173,http://127.0.0.1:5173`) |

Copy `backend/.env.example` to `backend/.env` and fill in all values before running.
