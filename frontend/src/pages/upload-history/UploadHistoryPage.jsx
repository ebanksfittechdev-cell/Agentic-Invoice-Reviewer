import { useRef, useState } from "react";
import { api } from "../../api/client.js";
import { CheckIcon, FileIcon, UploadIcon } from "../../components/Icons.jsx";
import "./upload-history.css";

const EXAMPLE = `{
  "vendors": [
    { "name": "Lakeshore Dairy", "account_no": "LD-4471", "terms": "Net 15. Deposits $2.77/crate." }
  ],
  "agreed_costs": [
    { "vendor": "Lakeshore Dairy", "item_code": "LD-1001", "description": "Whole Milk 1 gal",
      "unit": "case", "pack_size": 4, "cost": 14.20 }
  ],
  "promotions": [
    { "vendor": "Lakeshore Dairy", "item_code": "LD-2010", "allowance_per_case": 1.50,
      "start_date": "2026-11-01", "end_date": "2026-11-30" }
  ]
}`;

export default function UploadHistoryPage() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);

  function choose(f) {
    setResult(null);
    setError("");
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".json")) {
      setError("Please choose a .json file.");
      return;
    }
    setFile(f);
  }

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      setResult(await api.importHistory(file));
      setFile(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="page-inner uh">
        <h1 className="page-title">Upload history</h1>
        <p className="page-subtitle">
          Import your store's vendors, agreed costs, and promotions from one JSON file. The agent checks invoices against these records.
        </p>

        <div
          className={`uh-drop ${dragging ? "is-dragging" : ""}`}
          onClick={() => input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files?.[0]); }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.current?.click(); } }}
        >
          <input ref={input} type="file" accept=".json,application/json" hidden
            onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
          <span className="uh-drop-icon">{file ? <FileIcon size={22} /> : <UploadIcon size={22} />}</span>
          {file ? (
            <>
              <strong>{file.name}</strong>
              <span>{(file.size / 1024).toFixed(1)} KB · click to choose a different file</span>
            </>
          ) : (
            <>
              <strong>Drop a JSON file here, or click to browse</strong>
              <span>vendors · agreed_costs · promotions</span>
            </>
          )}
        </div>

        <div className="uh-actions">
          <button className="btn btn-primary" disabled={!file || busy} onClick={upload}>
            {busy ? "Importing…" : "Import"}
          </button>
          {error && <span className="uh-error">{error}</span>}
        </div>

        {result && (
          <div className="uh-result">
            <span className="uh-result-icon"><CheckIcon size={18} /></span>
            <div>
              <strong>{result.message}</strong>
              <div className="uh-stats">
                <span><b>{result.vendors}</b> vendors</span>
                <span><b>{result.agreed_costs}</b> agreed costs</span>
                <span><b>{result.promotions}</b> promotions</span>
              </div>
            </div>
          </div>
        )}

        <details className="uh-example">
          <summary>Expected file format</summary>
          <pre>{EXAMPLE}</pre>
        </details>
      </div>
    </div>
  );
}
