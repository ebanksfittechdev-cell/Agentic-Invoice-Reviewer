// In-memory fake backend. Routes marked REAL exist in Flask today and are
// mocked here only so the UI runs without a database; routes marked FAKE are
// guesses at endpoints from backend-plan.md / the architecture doc and do not
// exist yet.

import * as seed from "./data.js";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// Mutable copies so approve/reject/upload persist for the page lifetime.
const db = {
  users: [{ ...seed.DEMO_USER }],
  vendors: structuredClone(seed.vendors),
  agreedCosts: structuredClone(seed.agreedCosts),
  invoices: structuredClone(seed.invoices),
  lines: structuredClone(seed.invoiceLines),
  discrepancies: structuredClone(seed.discrepancies),
  actions: structuredClone(seed.pendingActions),
};
let nextId = 1000;

// No login screen — every request acts as the demo store.
const currentUser = () => db.users[0];

const ok = (data, status = 200) => ({ status, data });
const err = (error, status) => ({ status, data: { error } });

const vendorName = (id) => db.vendors.find((v) => v.id === id)?.name ?? null;
const invoiceSummary = (inv) => ({
  id: inv.id, vendor_id: inv.vendor_id, vendor_name: vendorName(inv.vendor_id),
  invoice_number: inv.invoice_number, invoice_date: inv.invoice_date, total: inv.total,
  status: inv.status, uploaded_at: inv.uploaded_at,
});
const discDict = ({ id, type, item_code, amount, status, explanation }) =>
  ({ id, type, item_code, amount, status, explanation });
const actionDict = ({ id, invoice_id, action_type, details, status, created_at, decided_at }) =>
  ({ id, invoice_id, action_type, details, status, created_at, decided_at: decided_at ?? null });

// ---------------------------------------------------------------------------
// Route table: [method, regex, handler(match, body, user)]
// ---------------------------------------------------------------------------
const routes = [
  // REAL ------------------------------------------------------------------
  ["GET", /^\/api\/auth\/me$/, (_, __, user) => {
    const { user_id, email, store_name, created_at } = user;
    return ok({ user_id, email, store_name, created_at });
  }],

  ["GET", /^\/api\/invoices\/?$/, () =>
    ok([...db.invoices].sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at)).map(invoiceSummary))],
  ["GET", /^\/api\/invoices\/discrepancies$/, () =>
    ok([...db.discrepancies].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(discDict))],
  ["GET", /^\/api\/invoices\/(\d+)$/, ([, id]) => {
    const inv = db.invoices.find((i) => i.id === Number(id));
    if (!inv) return err("Not found", 404);
    return ok({
      ...invoiceSummary(inv),
      lines: db.lines[inv.id] || [],
      discrepancies: db.discrepancies.filter((d) => d.invoice_id === inv.id).map(discDict),
      pending_actions: db.actions.filter((a) => a.invoice_id === inv.id).map(actionDict),
    });
  }],
  ["POST", /^\/api\/invoices\/upload$/, async (_, { formData }) => {
    const file = formData?.get("file");
    if (!file) return err("No file attached", 400);
    await delay(1400); // pretend Gemini + agent are working
    return ok(fakeProcessedInvoice(file), 201);
  }],

  // FAKE ------------------------------------------------------------------
  ["GET", /^\/api\/actions\/?$/, () =>
    ok([...db.actions].sort((a, b) => b.created_at.localeCompare(a.created_at)).map(actionDict))],
  ["POST", /^\/api\/actions\/(\d+)\/(approve|reject)$/, ([, id, decision], { json }) => {
    const action = db.actions.find((a) => a.id === Number(id));
    if (!action) return err("Not found", 404);
    if (action.status !== "pending") return err(`Action already ${action.status}`, 409);
    action.status = decision === "approve" ? "approved" : "rejected";
    action.decided_at = new Date().toISOString();
    if (decision === "approve") applySideEffects(action, json?.answer);
    return ok(actionDict(action));
  }],

  ["POST", /^\/api\/history\/import$/, async (_, { formData }) => {
    const file = formData?.get("file");
    if (!file) return err("No file attached", 400);
    let parsed;
    try { parsed = JSON.parse(await file.text()); } catch { return err("File is not valid JSON", 400); }
    const count = (k) => (Array.isArray(parsed?.[k]) ? parsed[k].length : 0);
    const summary = { vendors: count("vendors"), agreed_costs: count("agreed_costs"), promotions: count("promotions") };
    if (!summary.vendors && !summary.agreed_costs && !summary.promotions)
      return err("Expected top-level arrays: vendors, agreed_costs, promotions", 422);
    await delay(700);
    return ok({
      ...summary,
      message: `${summary.vendors} vendors, ${summary.agreed_costs} costs, ${summary.promotions} promo${summary.promotions === 1 ? "" : "s"} imported`,
    });
  }],
  ["GET", /^\/api\/history\/agreed-costs$/, () =>
    ok(db.agreedCosts.map((c) => ({ ...c, vendor_name: vendorName(c.vendor_id) })))],

  ["POST", /^\/api\/agent\/chat$/, async (_, { json }) => {
    await delay(900);
    return ok(fakeChatReply(json?.message || ""));
  }],
];

export async function handleMockRequest(method, path, body) {
  await delay(250);
  const user = currentUser();
  for (const [m, re, handler] of routes) {
    const match = path.match(re);
    if (m === method && match) {
      return handler(match, body, user);
    }
  }
  return err(`Mock route not found: ${method} ${path}`, 404);
}

// ---------------------------------------------------------------------------
// Fake behaviour
// ---------------------------------------------------------------------------

function applySideEffects(action, answer) {
  // Mirrors the table in AGENTS.md "Owner approvals — side effects".
  if (action.action_type === "dispute") {
    db.discrepancies
      .filter((d) => d.invoice_id === action.invoice_id && action.details.items?.includes(d.item_code))
      .forEach((d) => { d.status = "disputed"; });
  } else if (action.action_type === "cost_update") {
    const cost = db.agreedCosts.find((c) => c.item_code === action.details.item_code);
    if (cost) { cost.cost = action.details.new_cost; cost.updated_at = new Date().toISOString(); }
  } else if (action.action_type === "hold_payment") {
    const inv = db.invoices.find((i) => i.id === action.invoice_id);
    if (inv) inv.status = "do_not_pay";
  } else if (action.action_type === "question") {
    action.details = { ...action.details, answer };
  }
}

function fakeProcessedInvoice(file) {
  const id = nextId++;
  const now = new Date().toISOString();
  const invoiceNumber = `LD-${88000 + (id % 1000)}`;
  const inv = { id, vendor_id: 1, invoice_number: invoiceNumber, invoice_date: now.slice(0, 10), total: 487.6, status: "checked", uploaded_at: now };
  db.invoices.push(inv);
  db.lines[id] = [
    { id: id * 10 + 1, line_type: "item", item_code: "LD-1002", description: "2% Milk 1 gal", quantity: 18, unit: "case", unit_price: 14.6, line_total: 262.8, handwritten_note: null },
    { id: id * 10 + 2, line_type: "item", item_code: "LD-2010", description: "Greek Yogurt 32oz", quantity: 8, unit: "case", unit_price: 21.5, line_total: 172.0, handwritten_note: null },
    { id: id * 10 + 3, line_type: "deposit", item_code: "DEP", description: "Crate deposit", quantity: 18, unit: "ea", unit_price: 2.93, line_total: 52.8, handwritten_note: null },
  ];
  db.discrepancies.push(
    { id: id * 10 + 1, invoice_id: id, type: "price", item_code: "LD-1002", amount: 14.4, status: "open", explanation: null, created_at: now },
    { id: id * 10 + 2, invoice_id: id, type: "promotion", item_code: "LD-2010", amount: 12.0, status: "open", explanation: null, created_at: now },
  );
  db.actions.push(
    {
      id: id * 10 + 1, invoice_id: id, action_type: "dispute", status: "pending", created_at: now,
      details: {
        vendor_name: "Lakeshore Dairy", items: ["LD-1002", "LD-2010"], amount: 26.4,
        message: `Hi Lakeshore team,\n\nOn invoice ${invoiceNumber} we found:\n• LD-1002 2% Milk billed at $14.60/case vs agreed $13.80 — 18 cases, $14.40 over.\n• LD-2010 Greek Yogurt: the $1.50/case November allowance was not applied — $12.00.\n\nPlease issue a credit for $26.40.\n\nThanks,\nCorner Market`,
      },
    },
    {
      id: id * 10 + 2, invoice_id: id, action_type: "hold_payment", status: "pending", created_at: now,
      details: { amount: 487.6, reason: "Hold until Lakeshore confirms the $26.40 credit." },
    },
    {
      id: id * 10 + 3, invoice_id: id, action_type: "question", status: "pending", created_at: now,
      details: { question: "Lakeshore's notice from Oct 30 mentions a fuel surcharge \"starting soon\". Should future surcharges be accepted?", options: ["Accept surcharges", "Flag every time"] },
    },
  );

  return {
    invoice_id: id,
    status: inv.status,
    invoice_number: inv.invoice_number,
    invoice_date: inv.invoice_date,
    total: inv.total,
    line_count: db.lines[id].length,
    discrepancy_count: 2,
    // Not returned by the real upload route yet — proposed for the agent step.
    file_name: file.name,
    agent_summary:
      "I checked 3 lines against your agreed costs and active promotions. Two mismatches look real: 2% milk is billed $0.80/case above your agreed price, and the November yogurt allowance wasn't applied. Together that's $26.40. I drafted a dispute and suggest holding payment until the credit arrives.",
    agent_steps: [
      "get_invoice(invoice_id) → 3 lines, no handwritten notes",
      "search_vendor_notices(Lakeshore Dairy, \"price\") → no notice covering LD-1002",
      "get_promotions(Lakeshore Dairy, LD-2010) → $1.50/case, Nov 1–30",
      "get_invoice_history(Lakeshore Dairy, LD-1002) → last 4 invoices at $13.80",
      "draft_dispute(…) · hold_payment(…) · ask_owner(…)",
    ],
  };
}

function fakeChatReply(message) {
  const m = message.toLowerCase();
  const open = db.discrepancies.filter((d) => d.status === "open" || d.status === "disputed");
  const total = open.reduce((s, d) => s + (d.amount || 0), 0);

  if (/overcharg|owe|credit|how much/.test(m)) {
    return {
      reply: `Across ${new Set(open.map((d) => d.invoice_id)).size} invoices, open or disputed discrepancies total $${total.toFixed(2)}. The largest is a $43.00 quantity shortfall on Greek Yogurt (invoice LD-88412).`,
      steps: ["get_invoice_history(Lakeshore Dairy, *)", "sum(discrepancies.amount where status in open, disputed)"],
    };
  }
  if (/pending|approve|action/.test(m)) {
    const pending = db.actions.filter((a) => a.status === "pending");
    return {
      reply: pending.length
        ? `You have ${pending.length} action${pending.length === 1 ? "" : "s"} waiting for approval. Open View history → Actions to see them all.`
        : "Nothing is waiting on you right now.",
      steps: [],
    };
  }
  return {
    reply: "I can review an invoice if you attach a photo or PDF, or answer questions like \"How much did Lakeshore overcharge us this month?\"",
    steps: [],
  };
}
