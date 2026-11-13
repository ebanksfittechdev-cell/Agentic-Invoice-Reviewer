import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client.js";
import { useAuth } from "../../auth/AuthContext.jsx";
import ActionCard from "../../components/ActionCard.jsx";
import { ChevronIcon, CloseIcon, FileIcon, LogoMark, PaperclipIcon, SendIcon } from "../../components/Icons.jsx";
import { money } from "../../utils/format.js";
import "./chat.css";

const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,application/pdf";
const SUGGESTIONS = [
  "How much did Lakeshore overcharge us this month?",
  "What's waiting for my approval?",
  "What can you check on an invoice?",
];

let msgSeq = 0;
const newId = () => `m${++msgSeq}`;

export default function ChatPage() {
  const { messages, setMessages } = useOutletContext();
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef(null);
  const textarea = useRef(null);
  const scroller = useRef(null);

  // Keep the newest message in view.
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Auto-grow the composer.
  useEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const push = (msg) => setMessages((m) => [...m, { id: newId(), ...msg }]);
  const replace = (id, msg) => setMessages((m) => m.map((x) => (x.id === id ? { id, ...msg } : x)));
  const updateAction = (msgId, next) =>
    setMessages((m) => m.map((x) =>
      x.id === msgId ? { ...x, actions: x.actions.map((a) => (a.id === next.id ? next : a)) } : x));

  async function send(override) {
    const body = (override ?? text).trim();
    if (busy || (!body && !file)) return;

    const attached = file;
    push({ role: "user", text: body, fileName: attached?.name });
    setText("");
    setFile(null);
    setBusy(true);

    const pendingId = newId();
    setMessages((m) => [...m, { id: pendingId, role: "assistant", pending: true,
      pendingLabel: attached ? "Reading invoice and checking against your records…" : "Thinking…" }]);

    try {
      if (attached) {
        const result = await api.uploadInvoice(attached);
        const detail = await api.getInvoice(result.invoice_id);
        replace(pendingId, { role: "assistant", ...invoiceReply(result, detail) });
      } else {
        const res = await api.chat(body);
        replace(pendingId, { role: "assistant", text: res.reply, steps: res.steps });
      }
    } catch (e) {
      replace(pendingId, { role: "assistant", error: true, text: e.message || "Something went wrong." });
    } finally {
      setBusy(false);
      textarea.current?.focus();
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function pickFile(f) {
    if (f && ACCEPT.split(",").includes(f.type)) setFile(f);
  }

  const dragProps = {
    onDragOver: (e) => { e.preventDefault(); setDragging(true); },
    onDragLeave: (e) => { if (e.currentTarget === e.target) setDragging(false); },
    onDrop: (e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files?.[0]); },
  };

  const empty = messages.length === 0;
  const storeName = user?.store_name || "there";

  return (
    <div className={`chat ${empty ? "is-empty" : ""}`} {...dragProps}>
      {dragging && <div className="chat-drop">Drop invoice to review</div>}

      <div className="chat-scroll" ref={scroller}>
        {empty ? (
          <div className="chat-hero">
            <span className="chat-hero-logo"><LogoMark size={26} /></span>
            <h1>Hi {storeName}, what are we checking today?</h1>
            <p>Attach an invoice photo or PDF and I'll compare it against your agreed costs, promotions, and history.</p>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((m) => (
              <Message key={m.id} msg={m} onActionChange={(next) => updateAction(m.id, next)} />
            ))}
          </div>
        )}
      </div>

      <div className="chat-composer-wrap">
        <form className="chat-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          {file && (
            <div className="chat-attachment">
              <FileIcon size={16} />
              <span className="chat-attachment-name">{file.name}</span>
              <button type="button" className="chat-attachment-remove" onClick={() => setFile(null)} aria-label="Remove attachment">
                <CloseIcon size={14} />
              </button>
            </div>
          )}
          <div className="chat-composer-row">
            <button type="button" className="chat-icon-btn" onClick={() => fileInput.current?.click()}
              aria-label="Attach invoice" title="Attach invoice (image or PDF)" disabled={busy}>
              <PaperclipIcon size={19} />
            </button>
            <input ref={fileInput} type="file" accept={ACCEPT} hidden
              onChange={(e) => { pickFile(e.target.files?.[0]); e.target.value = ""; }} />
            <textarea ref={textarea} rows={1} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKeyDown}
              placeholder={file ? "Add a note (optional)…" : "Ask about your invoices, or attach one to review…"}
              aria-label="Message" />
            <button type="submit" className="chat-send" disabled={busy || (!text.trim() && !file)} aria-label="Send">
              <SendIcon size={18} />
            </button>
          </div>
        </form>

        {empty && (
          <div className="chat-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chat-suggestion" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        <p className="chat-footnote">The agent only proposes actions — nothing changes until you approve it.</p>
      </div>
    </div>
  );
}

function invoiceReply(result, detail) {
  const header = {
    vendor: detail.vendor_name,
    number: result.invoice_number,
    total: result.total,
    lines: result.line_count,
    discrepancies: result.discrepancy_count,
    status: result.status,
  };
  if (result.status === "needs_review") {
    return {
      invoice: header,
      text: result.error
        ? `I couldn't read this invoice cleanly (${result.error}). It's been marked for manual review.`
        : "The line items don't add up to the stated total, so I've marked this invoice for manual review instead of checking it.",
    };
  }
  const pending = (detail.pending_actions || []).filter((a) => a.status === "pending");
  return {
    invoice: header,
    text: result.agent_summary
      || (result.discrepancy_count
        ? `Found ${result.discrepancy_count} discrepanc${result.discrepancy_count === 1 ? "y" : "ies"}.`
        : "Everything matches your records — no discrepancies found."),
    steps: result.agent_steps,
    actions: pending,
  };
}

function Message({ msg, onActionChange }) {
  const [showSteps, setShowSteps] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="msg-user-bubble">
          {msg.fileName && (
            <div className="msg-file"><FileIcon size={15} /> {msg.fileName}</div>
          )}
          {msg.text && <p>{msg.text}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="msg msg-assistant">
      <span className="msg-avatar"><LogoMark size={16} /></span>
      <div className="msg-body">
        {msg.pending ? (
          <div className="msg-pending">
            <span className="typing"><i /><i /><i /></span>
            <span>{msg.pendingLabel}</span>
          </div>
        ) : (
          <>
            {msg.invoice && (
              <div className="msg-invoice">
                <span className="msg-invoice-title">{msg.invoice.vendor || "Unknown vendor"} · #{msg.invoice.number || "—"}</span>
                <span>{money(msg.invoice.total)}</span>
                <span>{msg.invoice.lines} lines</span>
                <span>{msg.invoice.discrepancies} flagged</span>
              </div>
            )}
            <p className={`msg-text ${msg.error ? "is-error" : ""}`}>{msg.text}</p>

            {msg.steps?.length > 0 && (
              <div className="msg-steps">
                <button className={`msg-steps-toggle ${showSteps ? "is-open" : ""}`} onClick={() => setShowSteps((s) => !s)}>
                  <ChevronIcon size={14} /> {showSteps ? "Hide steps" : "Show steps"}
                </button>
                {showSteps && (
                  <ol>{msg.steps.map((s, i) => <li key={i}><code>{s}</code></li>)}</ol>
                )}
              </div>
            )}

            {msg.actions?.length > 0 && (
              <div className="msg-actions">
                {msg.actions.map((a) => <ActionCard key={a.id} action={a} onChange={onActionChange} />)}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
