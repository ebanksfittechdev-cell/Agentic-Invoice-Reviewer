// Seed data for the mock API. Shapes match backend/invoices/routes.py helpers
// (_invoice_summary, _line_dict, _disc_dict, _action_dict) and schema.sql.

export const DEMO_USER = {
  user_id: 1,
  email: "demo@store.com",
  store_name: "Corner Market",
  created_at: "2026-09-01T14:00:00+00:00",
};

export const vendors = [
  { id: 1, name: "Lakeshore Dairy" },
  { id: 2, name: "Northfield Produce" },
  { id: 3, name: "Summit Beverage Co." },
];

export const agreedCosts = [
  { id: 1, vendor_id: 1, item_code: "LD-1001", description: "Whole Milk 1 gal", unit: "case", pack_size: 4, cost: 14.2, updated_at: "2026-10-01T12:00:00+00:00" },
  { id: 2, vendor_id: 1, item_code: "LD-1002", description: "2% Milk 1 gal", unit: "case", pack_size: 4, cost: 13.8, updated_at: "2026-10-01T12:00:00+00:00" },
  { id: 3, vendor_id: 1, item_code: "LD-2010", description: "Greek Yogurt 32oz", unit: "case", pack_size: 6, cost: 21.5, updated_at: "2026-09-15T12:00:00+00:00" },
  { id: 4, vendor_id: 2, item_code: "NP-300", description: "Gala Apples 40lb", unit: "case", pack_size: 1, cost: 38.0, updated_at: "2026-10-20T12:00:00+00:00" },
  { id: 5, vendor_id: 2, item_code: "NP-410", description: "Romaine Hearts 12ct", unit: "case", pack_size: 12, cost: 24.75, updated_at: "2026-10-20T12:00:00+00:00" },
  { id: 6, vendor_id: 3, item_code: "SB-55", description: "Sparkling Water 12oz 24pk", unit: "case", pack_size: 24, cost: 9.6, updated_at: "2026-08-30T12:00:00+00:00" },
];

export const invoices = [
  { id: 101, vendor_id: 1, invoice_number: "LD-88412", invoice_date: "2026-11-03", total: 612.4, status: "checked", uploaded_at: "2026-11-04T15:22:00+00:00" },
  { id: 102, vendor_id: 2, invoice_number: "NP-20931", invoice_date: "2026-11-05", total: 438.25, status: "do_not_pay", uploaded_at: "2026-11-06T10:05:00+00:00" },
  { id: 103, vendor_id: 3, invoice_number: "SB-7710", invoice_date: "2026-11-08", total: 230.4, status: "needs_review", uploaded_at: "2026-11-09T09:41:00+00:00" },
];

export const invoiceLines = {
  101: [
    { id: 1, line_type: "item", item_code: "LD-1001", description: "Whole Milk 1 gal", quantity: 20, unit: "case", unit_price: 14.95, line_total: 299.0, handwritten_note: null },
    { id: 2, line_type: "item", item_code: "LD-2010", description: "Greek Yogurt 32oz", quantity: 12, unit: "case", unit_price: 21.5, line_total: 258.0, handwritten_note: "rec'd 10" },
    { id: 3, line_type: "deposit", item_code: "DEP", description: "Crate deposit", quantity: 20, unit: "ea", unit_price: 2.77, line_total: 55.4, handwritten_note: null },
  ],
  102: [
    { id: 4, line_type: "item", item_code: "NP-300", description: "Gala Apples 40lb", quantity: 6, unit: "case", unit_price: 38.0, line_total: 228.0, handwritten_note: null },
    { id: 5, line_type: "item", item_code: "NP-410", description: "Romaine Hearts 12ct", quantity: 8, unit: "case", unit_price: 26.28, line_total: 210.25, handwritten_note: null },
  ],
  103: [],
};

export const discrepancies = [
  { id: 1, invoice_id: 101, type: "price", item_code: "LD-1001", amount: 15.0, status: "open", explanation: null, created_at: "2026-11-04T15:22:30+00:00" },
  { id: 2, invoice_id: 101, type: "quantity", item_code: "LD-2010", amount: 43.0, status: "open", explanation: null, created_at: "2026-11-04T15:22:30+00:00" },
  { id: 3, invoice_id: 102, type: "price", item_code: "NP-410", amount: 12.24, status: "explained", explanation: "Vendor notice 2026-10-28: romaine up 6% due to supply.", created_at: "2026-11-06T10:05:20+00:00" },
];

export const pendingActions = [
  {
    id: 1, invoice_id: 101, action_type: "dispute", status: "pending", created_at: "2026-11-04T15:23:10+00:00",
    details: {
      vendor_name: "Lakeshore Dairy",
      items: ["LD-1001", "LD-2010"],
      amount: 58.0,
      message:
        "Hi Lakeshore team,\n\nOn invoice LD-88412 (Nov 3) we found two issues:\n• LD-1001 Whole Milk billed at $14.95/case vs our agreed $14.20 — 20 cases, $15.00 over.\n• LD-2010 Greek Yogurt billed for 12 cases, 10 received — $43.00 over.\n\nPlease issue a credit for $58.00.\n\nThanks,\nCorner Market",
    },
  },
  {
    id: 2, invoice_id: 102, action_type: "cost_update", status: "approved", created_at: "2026-11-06T10:06:00+00:00",
    details: { item_code: "NP-410", description: "Romaine Hearts 12ct", old_cost: 24.75, new_cost: 26.28, evidence: "Vendor notice 2026-10-28: \"Romaine pricing increases 6% effective Nov 1.\"" },
  },
];
