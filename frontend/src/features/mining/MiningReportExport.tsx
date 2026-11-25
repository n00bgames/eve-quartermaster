import { Download } from "lucide-react";
import { useState } from "react";
import type { MiningLedgerPayload } from "../../types/mining";
import { buildMiningReport, buildMiningReportExport, type MiningReportScope } from "./miningReport";

export function MiningReportExport({ data, scope, loadedAt, loading, pending, failed }: {
  data: MiningLedgerPayload | null;
  scope: MiningReportScope;
  loadedAt: string | null;
  loading: boolean;
  pending: boolean;
  failed: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const disabled = !data || !loadedAt || loading || pending || failed;
  function download(format: "csv" | "json") {
    if (disabled || !data || !loadedAt) return;
    try {
      setError(null);
      const file = buildMiningReportExport(buildMiningReport(data, scope, loadedAt), format);
      const url = URL.createObjectURL(new Blob([file.text], { type: file.mime }));
      const link = document.createElement("a");
      link.href = url;
      link.download = file.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Mining Report export failed.");
    }
  }
  return <section className="mining-report" aria-label="Mining Report">
    <div><h4>Mining Report</h4>
      <p>Export totals and every day, ore, character and system breakdown for the applied filters, across all ledger pages.</p>
      {data?.analytics.hourly && <small>Single-day reports also include hourly record-time buckets and totals with no recorded hour.</small>}
      <small>{scope.date_from || "All recorded history"} → {scope.date_to || "Latest recorded day"} · UTC dates, both ends inclusive · {data?.entry_count ?? 0} matching ledger rows</small>
      <small>Stored ISK estimates; efficiency covers imported residue measurements only. Unmeasured efficiency stays blank in CSV and null in JSON.</small>
      {(pending || loading || failed) && <p role="status">{loading ? "Loading the selected period…" : pending ? "Filters changed. Select Apply to update the report." : "Refresh successfully before exporting this report."}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
    <div className="button-row compact"><button type="button" disabled={disabled} onClick={() => download("csv")}><Download size={16} />Export Mining CSV</button><button type="button" disabled={disabled} onClick={() => download("json")}><Download size={16} />Export Mining JSON</button></div>
  </section>;
}
