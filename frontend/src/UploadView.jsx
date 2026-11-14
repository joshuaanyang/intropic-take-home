import { useState } from "react";
import { uploadTrades } from "./api.js";

export default function UploadView() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function submit(event) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setResult(null);
    const response = await uploadTrades(file);
    setResult(response.body ?? { outcome: "rejected", file_error: "The server returned no result." });
    setBusy(false);
  }

  return (
    <section>
      <h2>Upload trades</h2>
      <form onSubmit={submit} className="row">
        <input
          id="trade-file"
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => setFile(event.target.files[0] ?? null)}
        />
        <button type="submit" disabled={!file || busy}>
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>
      {result && <ImportResult result={result} />}
    </section>
  );
}

function ImportResult({ result }) {
  if (result.detail) {
    return <p className="banner bad">{String(result.detail)}</p>;
  }
  if (result.outcome === "imported") {
    return (
      <p className="banner good">
        <strong>Imported.</strong> {result.total_rows} rows in the file: {result.inserted_rows} inserted,{" "}
        {result.skipped_rows} skipped as exact duplicates.
      </p>
    );
  }
  return (
    <>
      <p className="banner bad">
        <strong>Rejected. Nothing was imported.</strong>{" "}
        {result.file_error
          ? result.file_error
          : `${result.total_rows} rows in the file: ${result.invalid_rows} invalid, ${result.aborted_rows} valid but not imported because the file failed.`}
      </p>
      {result.errors?.length > 0 && (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th className="num">Row</th>
                <th>Trade ID</th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {result.errors.map((error) => (
                <tr key={error.row}>
                  <td className="num">{error.row}</td>
                  <td>{error.trade_id}</td>
                  <td>{error.reasons.join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">Row numbers count the header as row 1.</p>
        </div>
      )}
    </>
  );
}
