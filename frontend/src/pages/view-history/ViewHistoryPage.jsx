import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import { date, label, money, statusClass } from "../../utils/format.js";
import "./view-history.css";

const Status = ({ value }) => <span className={statusClass(value)}>{label(value)}</span>;

const TABS = [
  {
    key: "invoices",
    label: "Invoices",
    load: api.listInvoices,
    empty: "No invoices yet — attach one in Chat.",
    columns: [
      { head: "Invoice #", cell: (r) => <span className="vh-strong">{r.invoice_number || "—"}</span> },
      { head: "Vendor", cell: (r) => r.vendor_name || "—" },
      { head: "Invoice date", cell: (r) => <span className="vh-nowrap">{date(r.invoice_date)}</span> },
      { head: "Total", cell: (r) => money(r.total), num: true },
      { head: "Status", cell: (r) => <Status value={r.status} /> },
      { head: "Uploaded", cell: (r) => <span className="vh-nowrap">{date(r.uploaded_at)}</span> },
    ],
  },
  {
    key: "discrepancies",
    label: "Discrepancies",
    load: api.listDiscrepancies,
    empty: "No discrepancies found.",
    columns: [
      { head: "Type", cell: (r) => <span className="vh-strong vh-cap">{label(r.type)}</span> },
      { head: "Item", cell: (r) => <code>{r.item_code || "—"}</code> },
      { head: "Amount", cell: (r) => money(r.amount), num: true },
      { head: "Status", cell: (r) => <Status value={r.status} /> },
      { head: "Explanation", cell: (r) => <span className="vh-muted">{r.explanation || "—"}</span> },
    ],
  },
  {
    key: "actions",
    label: "Actions",
    load: api.listActions,
    empty: "No actions proposed yet.",
    columns: [
      { head: "Type", cell: (r) => <span className="vh-strong vh-cap">{label(r.action_type)}</span> },
      { head: "Summary", cell: (r) => <span className="vh-muted">{actionSummary(r)}</span> },
      { head: "Status", cell: (r) => <Status value={r.status} /> },
      { head: "Created", cell: (r) => <span className="vh-nowrap">{date(r.created_at)}</span> },
      { head: "Decided", cell: (r) => <span className="vh-nowrap">{date(r.decided_at)}</span> },
    ],
  },
  {
    key: "costs",
    label: "Agreed costs",
    load: api.listAgreedCosts,
    empty: "No agreed costs — import them under Upload history.",
    columns: [
      { head: "Item", cell: (r) => <code>{r.item_code}</code> },
      { head: "Description", cell: (r) => r.description || "—" },
      { head: "Vendor", cell: (r) => r.vendor_name || "—" },
      { head: "Unit", cell: (r) => (r.pack_size ? `${r.unit} of ${r.pack_size}` : r.unit || "—") },
      { head: "Cost", cell: (r) => money(r.cost), num: true },
      { head: "Updated", cell: (r) => <span className="vh-nowrap">{date(r.updated_at)}</span> },
    ],
  },
];

function actionSummary(a) {
  const d = a.details || {};
  switch (a.action_type) {
    case "dispute": return `${d.vendor_name ?? ""} · ${money(d.amount)} on ${d.items?.join(", ") ?? ""}`;
    case "cost_update": return `${d.item_code}: ${money(d.old_cost)} → ${money(d.new_cost)}`;
    case "hold_payment": return `${money(d.amount)} — ${d.reason ?? ""}`;
    case "question": return d.answer ? `${d.question} → ${d.answer}` : d.question;
    default: return "—";
  }
}

export default function ViewHistoryPage() {
  const [tabKey, setTabKey] = useState("invoices");
  const [state, setState] = useState({ key: null, rows: [], error: "" });
  const tab = TABS.find((t) => t.key === tabKey);
  const loading = state.key !== tabKey;

  useEffect(() => {
    let cancelled = false;
    tab.load()
      .then((rows) => { if (!cancelled) setState({ key: tab.key, rows, error: "" }); })
      .catch((e) => { if (!cancelled) setState({ key: tab.key, rows: [], error: e.message }); });
    return () => { cancelled = true; };
  }, [tab]);

  return (
    <div className="page">
      <div className="page-inner">
        <h1 className="page-title">History</h1>
        <p className="page-subtitle">Everything the checks and the agent have produced for your store.</p>

        <div className="vh-tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={t.key === tabKey}
              className={`vh-tab ${t.key === tabKey ? "is-active" : ""}`} onClick={() => setTabKey(t.key)}>
              {t.label}
              {state.key === t.key && !state.error && <span className="vh-count">{state.rows.length}</span>}
            </button>
          ))}
        </div>

        <div className="vh-card">
          {loading ? (
            <div className="vh-empty">Loading…</div>
          ) : state.error ? (
            <div className="vh-empty vh-error">{state.error}</div>
          ) : state.rows.length === 0 ? (
            <div className="vh-empty">{tab.empty}</div>
          ) : (
            <div className="vh-scroll">
              <table className="vh-table">
                <thead>
                  <tr>{tab.columns.map((c) => <th key={c.head} className={c.num ? "num" : ""}>{c.head}</th>)}</tr>
                </thead>
                <tbody>
                  {state.rows.map((r) => (
                    <tr key={r.id}>
                      {tab.columns.map((c) => <td key={c.head} className={c.num ? "num" : ""}>{c.cell(r)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
