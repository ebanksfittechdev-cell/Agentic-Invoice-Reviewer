git@github.com:ebanksfittechdev-cell/Agentic-Invoice-Reviewer.git# Invoice Checker Architecture

Nov 12, 2026 · @Ethan Adragna

A web app for independent grocers: code checks supplier invoices against the store's records, an agent decides which mismatches are real, and the owner approves disputes and cost updates. Stack: React, Flask, Postgres, Google ADK with Gemini.

## What it does

The model reads, code calculates, the agent judges, the owner decides.

1. User attaches an invoice image or PDF in chat.
2. Code saves the file and creates an `invoices` row (status `uploaded`).
3. Gemini, one call extracts lines, fees and handwritten notes as JSON. Not the agent.
4. Code checks the lines add up to the total. If not, status `needs_review`.
5. Code runs the checks and saves each mismatch to `discrepancies`:
   - price vs agreed cost
   - billed qty vs handwritten "rec'd"
   - line arithmetic
   - duplicate invoice number
   - promotion not applied
   - deposit math
6. Agent runs only if there is at least one mismatch. It investigates each one, decides real / explained / ask owner, and creates pending actions.
7. Chat shows the agent's summary plus one card per pending action, with Approve / Reject.
8. Code applies approvals: dispute marked ready, cost file updated, or payment held.

The same chat answers questions such as "How much did Lakeshore overcharge us this month?" using the agent's read tools.

## Database (Postgres, 9 tables)

One account = one store. Every table except `users` and the line tables carries `user_id`, and every query filters by it.

- **users**: `id` SERIAL PK · `email` TEXT UNIQUE · `password_hash` TEXT · `store_name` TEXT · `created_at` TIMESTAMPTZ
- **vendors**: `id` SERIAL PK · `user_id` INT FK · `name` TEXT · `account_no` TEXT · `terms` TEXT
- **agreed_costs**: `id` SERIAL PK · `user_id` INT FK · `vendor_id` INT FK · `item_code` TEXT · `description` TEXT · `unit` TEXT · `pack_size` INT · `cost` NUMERIC(10,2) · `updated_at` TIMESTAMPTZ
- **promotions**: `id` SERIAL PK · `user_id` INT FK · `vendor_id` INT FK · `item_code` TEXT · `description` TEXT · `allowance_per_case` NUMERIC(10,2) · `start_date` DATE · `end_date` DATE
- **vendor_notices**: `id` SERIAL PK · `user_id` INT FK · `vendor_id` INT FK · `notice_date` DATE · `subject` TEXT · `body` TEXT
- **invoices**: `id` SERIAL PK · `user_id` INT FK · `vendor_id` INT FK · `invoice_number` TEXT · `invoice_date` DATE · `total` NUMERIC(10,2) · `status` TEXT · `image_path` TEXT · `uploaded_at` TIMESTAMPTZ
- **invoice_lines**: `id` SERIAL PK · `invoice_id` INT FK · `line_type` TEXT · `item_code` TEXT · `description` TEXT · `quantity` NUMERIC · `unit` TEXT · `unit_price` NUMERIC(10,2) · `line_total` NUMERIC(10,2) · `handwritten_note` TEXT
- **discrepancies**: `id` SERIAL PK · `user_id` INT FK · `invoice_id` INT FK · `type` TEXT · `item_code` TEXT · `amount` NUMERIC(10,2) · `status` TEXT · `explanation` TEXT · `created_at` TIMESTAMPTZ
- **pending_actions**: `id` SERIAL PK · `user_id` INT FK · `invoice_id` INT FK · `action_type` TEXT · `details` JSONB · `status` TEXT · `created_at` TIMESTAMPTZ · `decided_at` TIMESTAMPTZ

### Status values

```text
invoices.status: uploaded · checked · needs_review · do_not_pay
invoice_lines.line_type: item · credit · fee · deposit
discrepancies.status: open · explained · disputed · asked_owner
pending_actions.action_type: dispute · cost_update · hold_payment · question
pending_actions.status: pending · approved · rejected
```

`invoice_number` is not unique on purpose, so a re-sent invoice can be stored and flagged as a duplicate. `pack_size` lets code convert 192 bottles into 8 cases of 24.

## Agent

The agent judges and proposes. It never calculates, and it never changes anything without the owner's approval.

Input: the list of mismatches for one invoice. The `user_id` is set in session state by the backend, never chosen by the model.

### Read tools (look things up)

- `get_invoice(invoice_id)`: the extracted lines and handwritten notes
- `get_vendor_terms(vendor_id)`: terms text, such as fees and substitution rules
- `search_vendor_notices(vendor_id, keyword)`: price-change and promo emails
- `get_promotions(vendor_id, item_code)`: agreed discounts and dates
- `get_invoice_history(vendor_id, item_code)`: past prices, quantities, invoice numbers

### Write tools (each only creates a `pending_actions` row)

- `draft_dispute(vendor_id, items, message)`
- `propose_cost_update(item_code, new_cost, evidence)`
- `hold_payment(invoice_id, reason)`
- `ask_owner(question)`

### Cannot

- See another store's data: every tool filters by the `user_id` in state
- Calculate dollar amounts: code computes every figure first
- Write to `agreed_costs`, `invoices` or `discrepancies` directly
- Send email or approve its own actions
- Run raw SQL or see passwords

### Limits

- Runs only when there is at least one mismatch
- At most 8 model calls per invoice, enforced by a callback
- Invoice text is treated as data: instructions written on an invoice are ignored

## Frontend (React)

Six screens. After login, everything lives inside a dashboard with a left sidebar: Chat · Upload history · View history · Log out.

| Screen | Shows | User can |
| --- | --- | --- |
| Login | Email and password form | Sign in; the demo account comes pre-loaded with history |
| Register | Store name, email, password | Create a new account, which starts empty |
| Chat (default) | Messages, agent summary, one card per pending action, a collapsible "Show steps" trace | Attach an invoice image or PDF, ask questions, Approve or Reject each card |
| Upload history | One file input and an import summary ("4 vendors, 17 costs, 1 promo imported") | Upload one JSON file of store records |
| View history | Tables: invoices with status, discrepancies, actions with status, agreed costs | Browse only |
| Log out | Button at the bottom of the sidebar | Ends the session, returns to Login |

Action cards in chat: dispute draft (email text plus Copy), cost update (old → new, with evidence), hold payment (amount and reason), owner question (two answer buttons).

## Left out on purpose

Each cut is mentioned in the pitch as the roadmap, not built.

- Onboarding and account settings
- Saved chat history: agent sessions are in memory, but all results are saved in Postgres
- Purchase orders and a receiving screen: the handwritten "rec'd" on the photo is the receiving record
- Sending real email: Approve marks a dispute "ready" and shows text to copy
- Email, point-of-sale and vendor-portal integrations
- Weekly vendor pattern reports
- Editing extracted lines: a failed extraction is marked `needs_review`
- Separate CSV imports: history is one JSON file
- Multiple users per store, roles, password reset

Assumed, change if needed: history upload as one JSON file, and extraction failures marked `needs_review` rather than corrected in the UI.
