// Single entry point for every backend call.
//
// When VITE_USE_MOCKS is not "false", requests are answered by the in-memory
// mock handlers in ./mock/handlers.js instead of hitting Flask. Response shapes
// mirror the real backend so flipping the flag is the only change needed once
// the endpoints exist.

import { handleMockRequest } from "./mock/handlers.js";

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

async function request(method, path, { json, formData } = {}) {
  if (USE_MOCKS) {
    const { status, data } = await handleMockRequest(method, path, { json, formData });
    if (status >= 400) throw new ApiError(data?.error || "Request failed", status, data);
    return data;
  }

  const init = { method, credentials: "include", headers: {} };
  if (json !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  } else if (formData) {
    init.body = formData; // browser sets the multipart boundary
  }

  let res;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach the server", 0);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(data?.error || `Request failed (${res.status})`, res.status, data);
  return data;
}

export const api = {
  // --- current store (real endpoint exists) ---
  me: () => request("GET", "/api/auth/me"),

  // --- invoices (real endpoints exist; mock adds agent_summary/agent_steps to upload) ---
  uploadInvoice: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("POST", "/api/invoices/upload", { formData: fd });
  },
  listInvoices: () => request("GET", "/api/invoices/"),
  getInvoice: (id) => request("GET", `/api/invoices/${id}`),
  listDiscrepancies: () => request("GET", "/api/invoices/discrepancies"),

  // --- actions (MOCK ONLY — Sub-Task 7 not built) ---
  listActions: () => request("GET", "/api/actions"),
  approveAction: (id, answer) =>
    request("POST", `/api/actions/${id}/approve`, { json: answer ? { answer } : {} }),
  rejectAction: (id) => request("POST", `/api/actions/${id}/reject`, { json: {} }),

  // --- history (MOCK ONLY) ---
  importHistory: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("POST", "/api/history/import", { formData: fd });
  },
  listAgreedCosts: () => request("GET", "/api/history/agreed-costs"),

  // --- chat (MOCK ONLY — agent Q&A, not designed in backend yet) ---
  // history: prior turns [{ role: "user" | "assistant", text }] so follow-ups have context
  chat: (message, history = []) => request("POST", "/api/agent/chat", { json: { message, history } }),
};
