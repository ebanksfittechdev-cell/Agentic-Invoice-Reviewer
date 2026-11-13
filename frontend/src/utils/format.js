const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (n) => (n == null ? "—" : usd.format(n));

export const date = (s) =>
  s ? new Date(s.length === 10 ? `${s}T00:00:00` : s).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—";

export const label = (s) => (s ? s.replaceAll("_", " ") : "—");

// Status → badge colour, covering invoice / discrepancy / action statuses.
const STATUS_TONE = {
  checked: "success", approved: "success", explained: "success",
  needs_review: "warning", pending: "warning", open: "warning", uploaded: "info",
  do_not_pay: "danger", disputed: "danger", rejected: "danger",
};
export const statusClass = (s) => (STATUS_TONE[s] ? `badge badge-${STATUS_TONE[s]}` : "badge");
