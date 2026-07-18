import { BarChart3, Database, Download, Gauge, Pickaxe, RefreshCw, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { CharacterSyncJob, MiningLedgerEntry, MiningLedgerPayload } from "../../types/mining";
import { MiningBarChart, MiningEfficiencyRanking, MiningTimeline } from "./MiningCharts";
import { MiningOperations } from "./MiningOperations";
import "./mining.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type SortKey = "date" | "character" | "ore" | "quantity" | "residue" | "volume" | "value" | "system";

const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const isk = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 });

export function MiningLedgerPage({ api }: { api: ApiClient }) {
  const [data, setData] = useState<MiningLedgerPayload | null>(null);
  const [characterId, setCharacterId] = useState("");
  const [systemId, setSystemId] = useState("");
  const [operationId, setOperationId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [syncJob, setSyncJob] = useState<CharacterSyncJob | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortAsc, setSortAsc] = useState(false);

  function queryPath(nextPage = page) {
    const params = new URLSearchParams({ page: String(nextPage), page_size: "100" });
    if (characterId) params.set("character_id", characterId);
    if (systemId) params.set("system_id", systemId);
    if (operationId) params.set("operation_id", operationId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return `/mining-ledger?${params}`;
  }

  async function load(nextPage = page) {
    setError(null);
    setData(await api<MiningLedgerPayload>(queryPath(nextPage)));
    setPage(nextPage);
  }

  async function syncAll() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      let job = await api<CharacterSyncJob>("/esi/sync/characters/all?sync_kind=mining", { method: "POST", body: "{}" });
      setSyncJob(job);
      while (job.status === "queued" || job.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        job = await api<CharacterSyncJob>(`/esi/sync/characters/all/${job.job_id}`);
        setSyncJob(job);
      }
      await load(1);
      if (job.failed_count) setError(job.errors.join(" · "));
      else setMessage(`Mining history synced for ${job.success_count} characters. Stored history outside ESI's rolling window was retained.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Mining sync failed");
    } finally {
      setBusy(false);
    }
  }

  async function importLedger(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ row_count: number; imported: number; updated: number; character_name: string }>("/mining-ledger/import", { method: "POST", body: JSON.stringify({ character_id: Number(form.get("character_id")), operation_id: form.get("operation_id") || null, text: form.get("text") }) });
      setMessage(`Loaded ${result.row_count} rows for ${result.character_name}: ${result.imported} new, ${result.updated} updated.`);
      formElement.reset();
      setShowImport(false);
      await load(1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Mining ledger import failed");
    } finally {
      setBusy(false);
    }
  }

  async function clearSelectedCharacter() {
    const character = data?.characters.find((row) => String(row.character_id) === characterId);
    if (!character || !window.confirm(`Clear all mining ledger history for ${character.name}? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api<{ character_name: string; deleted_count: number }>(`/mining-ledger/characters/${character.character_id}`, { method: "DELETE" });
      setMessage(`Cleared ${result.deleted_count} mining ledger rows for ${result.character_name}.`);
      await load(1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to clear mining ledger history");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(1).catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load mining ledger")); }, []);

  const entries = useMemo(() => [...(data?.entries ?? [])].sort((left, right) => {
    const values: Record<SortKey, [(row: MiningLedgerEntry) => string | number, boolean]> = {
      date: [(row) => Date.parse(row.timestamp ?? row.date), true], character: [(row) => row.character_name, false], ore: [(row) => row.ore_type, false],
      quantity: [(row) => row.quantity, true], residue: [(row) => row.residue_quantity, true], volume: [(row) => row.volume, true], value: [(row) => row.estimated_price, true], system: [(row) => row.solar_system, false],
    };
    const [selector, numeric] = values[sortKey];
    const a = selector(left); const b = selector(right);
    const result = numeric ? Number(a) - Number(b) : String(a).localeCompare(String(b), undefined, { numeric: true });
    return sortAsc ? result : -result;
  }), [data?.entries, sortKey, sortAsc]);

  const totals = data?.analytics.totals;
  const pageCount = Math.max(1, Math.ceil((data?.entry_count ?? 0) / (data?.page_size ?? 100)));
  const syncPercent = syncJob?.total_count ? Math.round(syncJob.processed_count / syncJob.total_count * 100) : 0;
  const valueRanking = [...(data?.analytics.by_character ?? [])].sort((a, b) => b.estimated_price - a.estimated_price);

  function sortHeader(key: SortKey, label: string) {
    return <button type="button" className="sort-header" onClick={() => { if (sortKey === key) setSortAsc((value) => !value); else { setSortKey(key); setSortAsc(false); } }}>{label}<span>{sortKey === key ? (sortAsc ? "^" : "v") : ""}</span></button>;
  }

  return <section className="panel stacked mining-ledger-page">
    <div className="section-heading"><div><h3>Mining Ledger</h3><p>Persistent per-character extraction history, residue loss, named operations, and mining performance analytics.</p></div><div className="button-row compact"><button type="button" onClick={() => setShowImport((value) => !value)}><Upload size={16} />Import detailed ledger</button><button type="button" disabled={busy || !data?.characters.some((row) => row.can_sync)} onClick={() => void syncAll()}><Download size={16} />{busy ? "Working" : "Sync all mining"}</button><button type="button" disabled={busy} onClick={() => void load()}><RefreshCw size={16} />Refresh</button></div></div>
    <div className="mining-data-note"><Database size={17} /><span>EQM keeps each dated row as history. ESI supplies recovered quantity, system, and ore type; detailed imports add residue and exported valuation.</span></div>
    {message && <div className="notice inline">{message}</div>}{error && <div className="mini-alert">{error}</div>}
    {syncJob && <div className={syncJob.failed_count ? "research-sync-status has-errors" : "research-sync-status"}><div><strong>{syncJob.processed_count} / {syncJob.total_count}</strong><span>{syncJob.current_character_name ? `Syncing ${syncJob.current_character_name}` : `Mining sync ${syncJob.status}`}</span></div><progress max={100} value={syncPercent} /><small>{syncJob.success_count} synced · {syncJob.failed_count} failed · {syncJob.skipped_count} skipped</small></div>}
    {showImport && <form className="mining-import-form" onSubmit={(event) => void importLedger(event)}><div className="form-grid"><label>Character<select name="character_id" required defaultValue=""><option value="" disabled>Select character</option>{data?.characters.filter((row) => !row.sync_opt_out).map((row) => <option value={row.character_id} key={row.character_id}>{row.name}</option>)}</select></label><label>Mining operation<select name="operation_id" defaultValue=""><option value="">No named operation</option>{data?.operations.map((row) => <option value={row.id} key={row.id}>{row.name}</option>)}</select></label></div><label>Mining ledger export<textarea name="text" required rows={8} placeholder="Paste tab-separated or CSV ledger data, including the header row." /></label><div className="button-row compact"><button type="submit" disabled={busy}><Upload size={16} />Import rows</button></div></form>}
    <div className="mining-filter-bar"><label>Character<select value={characterId} onChange={(event) => setCharacterId(event.target.value)}><option value="">All characters</option>{data?.characters.map((row) => <option key={row.character_id} value={row.character_id}>{row.name}</option>)}</select></label><label>System<select value={systemId} onChange={(event) => setSystemId(event.target.value)}><option value="">All systems</option>{data?.systems.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label>Operation<select value={operationId} onChange={(event) => setOperationId(event.target.value)}><option value="">All history</option>{data?.operations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label><label>From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label>To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label><div className="button-row compact mining-filter-actions"><button type="button" onClick={() => void load(1)}>Apply</button><button type="button" className="danger" disabled={busy || !characterId} onClick={() => void clearSelectedCharacter()} title={characterId ? "Clear this character's complete mining ledger" : "Select a character to clear its ledger"}><Trash2 size={15} />Clear selected</button></div></div>
    <div className="status-grid mining-summary-grid"><article><Pickaxe size={19} /><span>Recovered</span><strong>{number.format(totals?.volume ?? 0)} m3</strong></article><article><BarChart3 size={19} /><span>Gross extraction</span><strong>{number.format(totals?.gross_volume ?? 0)} m3</strong></article><article className="residue-stat"><span>Residue loss</span><strong>{number.format(totals?.residue_volume ?? 0)} m3</strong></article><article><span>Net value</span><strong>{isk.format(totals?.estimated_price ?? 0)} ISK</strong></article><article><Gauge size={19} /><span>Measured efficiency</span><strong>{totals?.efficiency == null ? "Not reported" : `${totals.efficiency}%`}</strong><small>{totals?.efficiency == null ? "Import residue data to measure" : `${number.format(totals.measured_volume)} m3 measured`}</small></article></div>
    <div className="mining-chart-grid"><MiningTimeline rows={data?.analytics.by_day ?? []} /><MiningBarChart title="Ore composition" subtitle="Recovered volume by ore" rows={data?.analytics.by_ore ?? []} value={(row) => row.volume} format={(value) => `${number.format(value)} m3`} /><MiningBarChart title="Most mined" subtitle="Recovered volume by character" rows={data?.analytics.by_character ?? []} value={(row) => row.volume} format={(value) => `${number.format(value)} m3`} /><MiningBarChart title="Largest gross extraction" subtitle="Recovered plus residue volume by character" rows={data?.analytics.by_character ?? []} value={(row) => row.gross_volume} format={(value) => `${number.format(value)} m3`} /><MiningBarChart title="Highest net value" subtitle="Estimated recovered ISK by character" rows={valueRanking} value={(row) => row.estimated_price} format={(value) => `${isk.format(value)} ISK`} /><MiningEfficiencyRanking rows={data?.analytics.by_character ?? []} /><MiningBarChart title="System extraction" subtitle="Gross volume by solar system" rows={data?.analytics.by_system ?? []} value={(row) => row.gross_volume} format={(value) => `${number.format(value)} m3`} /></div>
    {data && <MiningOperations api={api} characters={data.characters} systems={data.systems} operations={data.operations} onChanged={() => load(1)} />}
    <div className="section-heading"><div><h4>Ledger history</h4><p>{whole.format(data?.entry_count ?? 0)} persistent rows match the current filters.</p></div><div className="button-row compact"><button type="button" disabled={page <= 1} onClick={() => void load(page - 1)}>Previous</button><span>Page {page} / {pageCount}</span><button type="button" disabled={page >= pageCount} onClick={() => void load(page + 1)}>Next</button></div></div>
    <div className="table-wrap mining-table-wrap"><table className="mining-table"><thead><tr><th>{sortHeader("date", "Date")}</th><th>{sortHeader("character", "Character")}</th><th>{sortHeader("ore", "Ore")}</th><th>{sortHeader("quantity", "Recovered")}</th><th>{sortHeader("residue", "Residue")}</th><th>{sortHeader("volume", "Volume")}</th><th>{sortHeader("value", "Net value")}</th><th>{sortHeader("system", "System")}</th><th>Operation</th></tr></thead><tbody>{entries.map((row) => <tr key={row.id}><td>{row.date}<span>{row.source.toUpperCase()}</span></td><td>{row.character_name}</td><td><strong>{row.ore_type}</strong><span>Type {row.ore_type_id}</span></td><td>{whole.format(row.quantity)}</td><td>{row.has_residue_data ? whole.format(row.residue_quantity) : <span className="unmeasured">Not reported</span>}</td><td>{number.format(row.volume)} m3<span>{row.has_residue_data && row.residue_volume > 0 ? `${number.format(row.residue_volume)} m3 lost` : ""}</span></td><td>{whole.format(row.estimated_price)} ISK<span>{row.estimated_residue_price > 0 ? `${whole.format(row.estimated_residue_price)} ISK lost` : ""}</span></td><td>{row.solar_system}<span>{row.solar_system_id}</span></td><td>{row.operation_name ?? "Unassigned"}</td></tr>)}{data && entries.length === 0 && <tr><td colSpan={9}>No mining ledger rows match these filters.</td></tr>}</tbody></table></div>
  </section>;
}
