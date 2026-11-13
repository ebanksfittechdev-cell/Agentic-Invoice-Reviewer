import { useState } from "react";
import { api } from "../api/client.js";
import { CheckIcon, CopyIcon } from "./Icons.jsx";
import { money } from "../utils/format.js";
import "./ActionCard.css";

const TITLES = {
  dispute: "Dispute draft",
  cost_update: "Cost update",
  hold_payment: "Hold payment",
  question: "Question for you",
};

export default function ActionCard({ action: initial, onChange }) {
  const [action, setAction] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const d = action.details || {};
  const decided = action.status !== "pending";

  async function decide(kind, answer) {
    setBusy(true);
    setError("");
    try {
      const updated = kind === "approve"
        ? await api.approveAction(action.id, answer)
        : await api.rejectAction(action.id);
      const next = { ...action, ...updated, details: { ...action.details, ...updated.details, answer } };
      setAction(next);
      onChange?.(next);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(d.message || "");
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setError("Couldn't copy — select the text manually.");
    }
  }

  return (
    <div className={`action-card type-${action.action_type} status-${action.status}`}>
      <div className="action-card-head">
        <span className="action-card-title">{TITLES[action.action_type] || action.action_type}</span>
        {decided && (
          <span className={`badge ${action.status === "approved" ? "badge-success" : "badge-danger"}`}>
            {action.status}
          </span>
        )}
      </div>

      <div className="action-card-body">
        {action.action_type === "dispute" && (
          <>
            <p className="action-meta">
              {d.vendor_name} · {d.items?.join(", ")} · <strong>{money(d.amount)}</strong>
            </p>
            <pre className="action-email">{d.message}</pre>
          </>
        )}

        {action.action_type === "cost_update" && (
          <>
            <p className="action-meta">{d.item_code} · {d.description}</p>
            <div className="action-cost">
              <span className="action-cost-old">{money(d.old_cost)}</span>
              <span className="action-cost-arrow">→</span>
              <span className="action-cost-new">{money(d.new_cost)}</span>
            </div>
            {d.evidence && <p className="action-evidence">{d.evidence}</p>}
          </>
        )}

        {action.action_type === "hold_payment" && (
          <>
            <p className="action-amount">{money(d.amount)}</p>
            <p className="action-text">{d.reason}</p>
          </>
        )}

        {action.action_type === "question" && (
          <>
            <p className="action-text">{d.question}</p>
            {d.answer && <p className="action-meta">Your answer: <strong>{d.answer}</strong></p>}
          </>
        )}
      </div>

      {error && <p className="action-error">{error}</p>}

      {!decided && (
        <div className="action-card-foot">
          {action.action_type === "question" ? (
            (d.options?.length ? d.options : ["Yes", "No"]).map((opt, i) => (
              <button key={opt} className={`btn ${i === 0 ? "btn-primary" : ""}`} disabled={busy}
                onClick={() => decide("approve", opt)}>
                {opt}
              </button>
            ))
          ) : (
            <>
              <button className="btn btn-primary" disabled={busy} onClick={() => decide("approve")}>Approve</button>
              <button className="btn" disabled={busy} onClick={() => decide("reject")}>Reject</button>
            </>
          )}
        </div>
      )}

      {action.action_type === "dispute" && action.status === "approved" && (
        <div className="action-card-foot">
          <button className="btn" onClick={copy}>
            {copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
            {copied ? "Copied" : "Copy email text"}
          </button>
        </div>
      )}
    </div>
  );
}
