import { CheckCircle2, ClipboardList, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { formatMarketIsk } from "../../lib/market";
import type { ManufacturingActivityFlag, ManufacturingAppraisal, ManufacturingCategory, ManufacturingJob, ManufacturingJobStatus, ManufacturingLineItem, ManufacturingOutputDisposition, ManufacturingPayload } from "../../types/manufacturing";
import type { MarketHub, MarketItemQuote } from "../../types/market";

type ManufacturingPageProps = {
  api: <T>(path: string, options?: RequestInit) => Promise<T>;
  formatDateTime: (value?: string | null) => string;
};

type DraftJob = {
  name: string;
  output_type_name: string;
  output_quantity: number;
  activity_flags: ManufacturingActivityFlag[];
  research_runs: string;
  me_start: string;
  me_target: string;
  te_start: string;
  te_target: string;
  copy_runs: string;
  invention_runs: string;
  invention_successes: string;
  status: ManufacturingJobStatus;
  output_disposition: ManufacturingOutputDisposition;
  output_sale_price: string;
  output_sale_notes: string;
  cost_to_run: string;
  time_to_run: string;
  date_started: string;
  time_started: string;
  notes: string;
};

const FALLBACK_CATEGORIES: ManufacturingCategory[] = [
  { key: "blueprint", label: "BPC/BPO" },
  { key: "decryptor", label: "Decryptors" },
  { key: "datacore", label: "Datacores" },
  { key: "component", label: "Components" },
  { key: "mineral", label: "Minerals" },
  { key: "pi", label: "PI Materials" },
  { key: "ship", label: "Ships Required" },
  { key: "item", label: "Items Required" },
  { key: "reaction", label: "Reaction Materials" },
  { key: "fee", label: "Fees" },
  { key: "other", label: "Other" },
];

const emptyJob: DraftJob = {
  name: "",
  output_type_name: "",
  output_quantity: 1,
  activity_flags: ["manufacturing"],
  research_runs: "",
  me_start: "",
  me_target: "",
  te_start: "",
  te_target: "",
  copy_runs: "",
  invention_runs: "",
  invention_successes: "",
  status: "draft",
  output_disposition: "pending",
  output_sale_price: "",
  output_sale_notes: "",
  cost_to_run: "",
  time_to_run: "",
  date_started: "",
  time_started: "",
  notes: "",
};

const ACTIVITY_OPTIONS: { key: ManufacturingActivityFlag; label: string }[] = [
  { key: "manufacturing", label: "Manufacturing" },
  { key: "me", label: "ME research" },
  { key: "te", label: "TE research" },
  { key: "invention", label: "Invention" },
  { key: "copy", label: "Copy" },
  { key: "reaction", label: "Reaction" },
];

const DECRYPTOR_OPTIONS = [
  "Accelerant Decryptor",
  "Attainment Decryptor",
  "Augmentation Decryptor",
  "Optimized Attainment Decryptor",
  "Optimized Augmentation Decryptor",
  "Parity Decryptor",
  "Process Decryptor",
  "Symmetry Decryptor",
];
function newLine(category: string): ManufacturingLineItem {
  return { category, item_name: "", quantity: 1, unit_price: null, price_paid: null, notes: "" };
}

function lineKey(line: ManufacturingLineItem, index: number) {
  return `${line.id ?? "draft"}-${line.category}-${index}`;
}

function categoryLabel(categories: ManufacturingCategory[], key: string) {
  return categories.find((category) => category.key === key)?.label ?? key;
}

function inputValue(value?: number | null) {
  return value == null ? "" : String(value);
}

function parseOptionalNumber(value: string): number | null {
  const clean = value.trim();
  if (!clean) return null;
  const next = Number(clean);
  return Number.isFinite(next) ? next : null;
}

function parseOptionalInteger(value: string): number | null {
  const clean = value.trim();
  if (!clean) return null;
  const next = Number(clean);
  return Number.isFinite(next) ? Math.trunc(next) : null;
}

function parseDurationMs(value?: string | null): number | null {
  if (!value) return null;
  const clean = value.trim().toLowerCase();
  if (!clean) return null;

  const colon = clean.match(/^(?:(\d+):)?(\d{1,2}):(\d{1,2})$/);
  if (colon) {
    const hours = Number(colon[1] ?? 0);
    const minutes = Number(colon[2] ?? 0);
    const seconds = Number(colon[3] ?? 0);
    return ((hours * 60 + minutes) * 60 + seconds) * 1000;
  }

  let totalMs = 0;
  const tokenPattern = /(\d+(?:\.\d+)?)\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)/g;
  let match: RegExpExecArray | null;
  while ((match = tokenPattern.exec(clean)) !== null) {
    const amount = Number(match[1]);
    const unit = match[2];
    if (unit.startsWith("d")) totalMs += amount * 86400000;
    else if (unit.startsWith("h")) totalMs += amount * 3600000;
    else if (unit.startsWith("m")) totalMs += amount * 60000;
    else totalMs += amount * 1000;
  }
  if (totalMs > 0) return totalMs;

  const plainHours = Number(clean);
  return Number.isFinite(plainHours) && plainHours > 0 ? plainHours * 3600000 : null;
}

function jobStartMs(job: Pick<ManufacturingJob, "date_started" | "time_started"> | DraftJob): number | null {
  if (!job.date_started || !job.time_started) return null;
  const dateText = `${job.date_started}T${job.time_started}`;
  const start = new Date(dateText).getTime();
  return Number.isFinite(start) ? start : null;
}

function jobEndMs(job: Pick<ManufacturingJob, "date_started" | "time_started" | "time_to_run"> | DraftJob): number | null {
  const start = jobStartMs(job);
  const duration = parseDurationMs(job.time_to_run);
  return start != null && duration != null ? start + duration : null;
}

function formatCountdown(ms: number): string {
  const abs = Math.abs(ms);
  const days = Math.floor(abs / 86400000);
  const hours = Math.floor((abs % 86400000) / 3600000);
  const minutes = Math.floor((abs % 3600000) / 60000);
  const seconds = Math.floor((abs % 60000) / 1000);
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function jobCountdownText(job: Pick<ManufacturingJob, "date_started" | "time_started" | "time_to_run" | "status"> | (DraftJob & { status?: ManufacturingJobStatus }), now: number): string {
  if (job.status === "completed") return "Completed";
  const end = jobEndMs(job);
  if (end == null) return job.date_started && job.time_to_run && !job.time_started ? "Missing start time" : "No timer";
  const remaining = end - now;
  return remaining > 0 ? `${formatCountdown(remaining)} remaining` : `Due ${formatCountdown(remaining)} ago`;
}


function dateInputValue(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function timeInputValue(value: Date): string {
  return `${String(value.getHours()).padStart(2, "0")}:${String(value.getMinutes()).padStart(2, "0")}`;
}

function applyStatusDefaults(draft: DraftJob, status: ManufacturingJobStatus, forceTime = false): DraftJob {
  if (status !== "running") return { ...draft, status };
  const now = new Date();
  return {
    ...draft,
    status,
    date_started: draft.date_started || dateInputValue(now),
    time_started: forceTime ? timeInputValue(now) : (draft.time_started || timeInputValue(now)),
  };
}
function statusLabel(status?: ManufacturingJobStatus | null): string {
  if (status === "completed") return "Completed";
  if (status === "running") return "Running";
  return "Draft";
}

function activityLabel(flag: ManufacturingActivityFlag): string {
  return ACTIVITY_OPTIONS.find((activity) => activity.key === flag)?.label ?? flag;
}
function outputDispositionLabel(disposition?: ManufacturingOutputDisposition | null): string {
  if (disposition === "sold") return "Sold";
  if (disposition === "kept") return "Kept";
  return "Pending";
}
function quoteForLine(result: ManufacturingAppraisal | null, line: ManufacturingLineItem): MarketItemQuote | null {
  if (!result) return null;
  const name = (line.type_name ?? line.item_name).toLowerCase();
  return result.items.find((item) => (item.type_name ?? item.name).toLowerCase() === name || item.input.toLowerCase() === name) ?? null;
}

function LineEditor({
  categories,
  line,
  index,
  onChange,
  onRemove,
}: {
  categories: ManufacturingCategory[];
  line: ManufacturingLineItem;
  index: number;
  onChange: (index: number, patch: Partial<ManufacturingLineItem>) => void;
  onRemove: (index: number) => void;
}) {
  const isDecryptor = line.category === "decryptor";
  const decryptorOptions = DECRYPTOR_OPTIONS.includes(line.item_name) || !line.item_name ? DECRYPTOR_OPTIONS : [line.item_name, ...DECRYPTOR_OPTIONS];
  return <div className="manufacturing-line-row">
    <label>Category<select value={line.category} onChange={(event) => onChange(index, { category: event.target.value })}>{categories.map((category) => <option key={category.key} value={category.key}>{category.label}</option>)}</select></label>
    {isDecryptor ? <label>Item<select value={line.item_name} onChange={(event) => onChange(index, { item_name: event.target.value })}><option value="">Select decryptor</option>{decryptorOptions.map((name) => <option key={name} value={name}>{name}</option>)}</select></label> : <label>Item<input value={line.item_name} onChange={(event) => onChange(index, { item_name: event.target.value })} placeholder="Raven Navy Issue, Tritanium, Core Temperature Regulator..." /></label>}
    <label>Qty<input type="number" min="0" step="0.0001" value={inputValue(line.quantity)} onChange={(event) => onChange(index, { quantity: Number(event.target.value) || 0 })} /></label>
    <label>Current Price<input type="number" min="0" step="0.01" value={inputValue(line.unit_price)} onChange={(event) => onChange(index, { unit_price: parseOptionalNumber(event.target.value) })} /></label>
    <label>Price Paid<input type="number" min="0" step="0.01" value={inputValue(line.price_paid)} onChange={(event) => onChange(index, { price_paid: parseOptionalNumber(event.target.value) })} /></label>
    <button type="button" className="danger compact-icon-button" onClick={() => onRemove(index)} title="Remove line"><Trash2 size={16} /></button>
  </div>;
}

function OutputPricePanel({ result }: { result: ManufacturingAppraisal | null }) {
  if (!result) return <p className="empty">Price the final product to compare major-hub buy and sell opportunities.</p>;
  const quote = result.items[0];
  if (!quote || !quote.matched) return <p className="empty">No market match found for the final product.</p>;

  const hubRows = result.hubs.map((hub) => ({ hub, quote: quote.hubs[hub.key] }));
  const bestBuy = Math.max(...hubRows.map((row) => row.quote?.buy ?? 0));
  const sellPrices = hubRows.map((row) => row.quote?.sell ?? 0).filter((price) => price > 0);
  const bestSell = sellPrices.length ? Math.min(...sellPrices) : 0;

  return <div className="manufacturing-output-prices">
    {hubRows.map(({ hub, quote: hubQuote }) => {
      const buy = hubQuote?.buy ?? null;
      const sell = hubQuote?.sell ?? null;
      const isBestBuy = buy != null && buy > 0 && buy === bestBuy;
      const isBestSell = sell != null && sell > 0 && sell === bestSell;
      return <article key={hub.key}>
        <strong>{hub.label}</strong>
        <span className={isBestBuy ? "best-buy" : ""}>Buy {formatMarketIsk(buy)} <small>{formatMarketIsk(hubQuote?.buy_total ?? null)} total</small></span>
        <span className={isBestSell ? "best-sell" : ""}>Sell {formatMarketIsk(sell)} <small>{formatMarketIsk(hubQuote?.sell_total ?? null)} total</small></span>
      </article>;
    })}
  </div>;
}

function HubPriceMatrix({ result, lines }: { result: ManufacturingAppraisal | null; lines: ManufacturingLineItem[] }) {
  if (!result) return <p className="empty">Price this build to see buy, sell, and split estimates across the selected trade hubs.</p>;

  const priceableLines = lines.filter((line) => line.item_name.trim());
  if (priceableLines.length === 0) return <p className="empty">No line items to price yet.</p>;

  return <div className="table-wrap manufacturing-price-wrap">
    <table className="manufacturing-price-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Qty</th>
          {result.hubs.map((hub) => <th key={hub.key}>{hub.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {priceableLines.map((line, index) => {
          const quote = quoteForLine(result, line);
          return <tr key={lineKey(line, index)}>
            <td><strong>{line.item_name}</strong><small>{categoryLabel(FALLBACK_CATEGORIES, line.category)}{quote && !quote.matched ? " · unresolved" : ""}</small></td>
            <td>{line.quantity.toLocaleString()}</td>
            {result.hubs.map((hub) => {
              const hubQuote = quote?.hubs?.[hub.key];
              return <td key={hub.key}>
                <span className="manufacturing-price-cell"><b>{formatMarketIsk(hubQuote?.sell)}</b><small>buy {formatMarketIsk(hubQuote?.buy)}</small><small>split {formatMarketIsk(hubQuote?.split)}</small></span>
              </td>;
            })}
          </tr>;
        })}
      </tbody>
    </table>
  </div>;
}

function JobLedger({ jobs, selectedId, now, onSelect, onDelete, onSetStatus, formatDateTime }: { jobs: ManufacturingJob[]; selectedId?: number | null; now: number; onSelect: (job: ManufacturingJob) => void; onDelete: (job: ManufacturingJob) => void; onSetStatus: (job: ManufacturingJob, status: ManufacturingJobStatus) => void; formatDateTime: (value?: string | null) => string }) {
  if (jobs.length === 0) return <p className="empty">No manufacturing jobs saved yet.</p>;

  return <div className="manufacturing-ledger-list">
    {jobs.map((job) => <article key={job.id} className={selectedId === job.id ? "active" : ""}>
      <button type="button" onClick={() => onSelect(job)}>
        <strong>{job.name}</strong>
        <span>{job.output_quantity.toLocaleString()} x {job.output_type_name ?? job.output_type_id ?? "output"}</span>
        <small>Added by {job.created_by_display_name ?? "Unknown user"} · {formatDateTime(job.created_at)} · {job.items.length} row{job.items.length === 1 ? "" : "s"}</small>
        <small>{(job.activity_flags?.length ? job.activity_flags : ["manufacturing"]).map((flag) => activityLabel(flag as ManufacturingActivityFlag)).join(" · ")}</small>
        <small><span className={`manufacturing-status-badge status-${job.status}`}>{statusLabel(job.status)}</span> <span className={`manufacturing-status-badge output-${job.output_disposition}`}>{outputDispositionLabel(job.output_disposition)}</span></small>
        <small>{jobCountdownText(job, now)}</small>
      </button>
      <div className="manufacturing-ledger-actions">
        {job.status !== "completed" && <button type="button" className="compact-icon-button" onClick={() => onSetStatus(job, "completed")} title="Mark completed"><CheckCircle2 size={15} /></button>}
        <button type="button" className="danger compact-icon-button" onClick={() => onDelete(job)} title="Delete job"><Trash2 size={15} /></button>
      </div>
    </article>)}
  </div>;
}

export function ManufacturingPage({ api, formatDateTime }: ManufacturingPageProps) {
  const [categories, setCategories] = useState<ManufacturingCategory[]>(FALLBACK_CATEGORIES);
  const [jobs, setJobs] = useState<ManufacturingJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<ManufacturingJob | null>(null);
  const [draft, setDraft] = useState<DraftJob>(emptyJob);
  const [lines, setLines] = useState<ManufacturingLineItem[]>([newLine("blueprint"), newLine("decryptor"), newLine("datacore"), newLine("component"), newLine("mineral"), newLine("pi"), newLine("ship"), newLine("item"), newLine("reaction")]);
  const [appraisal, setAppraisal] = useState<ManufacturingAppraisal | null>(null);
  const [outputAppraisal, setOutputAppraisal] = useState<ManufacturingAppraisal | null>(null);
  const [busy, setBusy] = useState(false);
  const [pricing, setPricing] = useState(false);
  const [outputPricing, setOutputPricing] = useState(false);
  const [outcomeSaving, setOutcomeSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  async function load() {
    const payload = await api<ManufacturingPayload>("/manufacturing/jobs");
    setCategories(payload.categories.length ? payload.categories : FALLBACK_CATEGORIES);
    setJobs(payload.jobs);
  }

  useEffect(() => { void load().catch((err) => setError(err instanceof Error ? err.message : "Unable to load manufacturing ledger.")); }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const enteredTotal = useMemo(() => {
    const itemTotal = lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.unit_price) || 0), 0);
    return itemTotal + (parseOptionalNumber(draft.cost_to_run) ?? 0);
  }, [draft.cost_to_run, lines]);

  const paidTotal = useMemo(() => {
    const itemTotal = lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.price_paid) || 0), 0);
    return itemTotal + (parseOptionalNumber(draft.cost_to_run) ?? 0);
  }, [draft.cost_to_run, lines]);

  const savingsTotal = enteredTotal - paidTotal;

  function toggleActivity(flag: ManufacturingActivityFlag, enabled: boolean) {
    setDraft((current) => {
      const nextFlags = enabled ? [...new Set([...current.activity_flags, flag])] : current.activity_flags.filter((value) => value !== flag);
      return { ...current, activity_flags: nextFlags.length ? nextFlags : ["manufacturing"] };
    });
  }

  function updateLine(index: number, patch: Partial<ManufacturingLineItem>) {
    setLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, ...patch } : line));
  }

  function removeLine(index: number) {
    setLines((current) => current.filter((_, lineIndex) => lineIndex !== index));
  }

  function addLine(category: string) {
    setLines((current) => [...current, newLine(category)]);
  }

  function loadJob(job: ManufacturingJob) {
    setSelectedJob(job);
    setDraft({
      name: job.name,
      output_type_name: job.output_type_name ?? "",
      output_quantity: job.output_quantity,
      activity_flags: job.activity_flags?.length ? job.activity_flags : ["manufacturing"],
      research_runs: inputValue(job.research_runs),
      me_start: inputValue(job.me_start),
      me_target: inputValue(job.me_target),
      te_start: inputValue(job.te_start),
      te_target: inputValue(job.te_target),
      copy_runs: inputValue(job.copy_runs),
      invention_runs: inputValue(job.invention_runs),
      invention_successes: inputValue(job.invention_successes),
      status: job.status,
      output_disposition: job.output_disposition ?? "pending",
      output_sale_price: inputValue(job.output_sale_price),
      output_sale_notes: job.output_sale_notes ?? "",
      cost_to_run: inputValue(job.cost_to_run),
      time_to_run: job.time_to_run ?? "",
      date_started: job.date_started ?? "",
      time_started: job.time_started ?? "",
      notes: job.notes ?? "",
    });
    setLines(job.items.length ? job.items.map((item) => ({ ...item })) : [newLine("blueprint")]);
    setAppraisal(null);
    setOutputAppraisal(null);
    setMessage(`Loaded ${job.name}.`);
  }

  function resetDraft() {
    setSelectedJob(null);
    setDraft(emptyJob);
    setLines([newLine("blueprint"), newLine("decryptor"), newLine("datacore"), newLine("component"), newLine("mineral"), newLine("pi"), newLine("ship"), newLine("item"), newLine("reaction")]);
    setAppraisal(null);
    setOutputAppraisal(null);
    setMessage(null);
    setError(null);
  }

  async function priceOutput() {
    const outputName = draft.output_type_name.trim() || draft.name.trim();
    if (!outputName) {
      setError("Enter an output item before pricing the final product.");
      return;
    }
    setOutputPricing(true);
    setError(null);
    try {
      setOutputAppraisal(await api<ManufacturingAppraisal>("/manufacturing/appraise", { method: "POST", body: JSON.stringify({ items: [{ item_name: outputName, quantity: draft.output_quantity || 1 }] }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Final product price check failed.");
    } finally {
      setOutputPricing(false);
    }
  }

  async function priceLines() {
    setPricing(true);
    setError(null);
    try {
      setAppraisal(await api<ManufacturingAppraisal>("/manufacturing/appraise", { method: "POST", body: JSON.stringify({ items: lines }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manufacturing price check failed.");
    } finally {
      setPricing(false);
    }
  }

  async function saveJob(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const jobDraft = draft.status === "running" ? applyStatusDefaults(draft, "running", true) : draft;
      setDraft(jobDraft);
      const saved = await api<ManufacturingJob>("/manufacturing/jobs", {
        method: "POST",
        body: JSON.stringify({
          ...jobDraft,
          cost_to_run: parseOptionalNumber(jobDraft.cost_to_run),
          status: jobDraft.status,
          output_disposition: jobDraft.output_disposition,
          output_sale_price: parseOptionalNumber(jobDraft.output_sale_price),
          output_sale_notes: jobDraft.output_sale_notes,
          research_runs: parseOptionalInteger(jobDraft.research_runs),
          me_start: parseOptionalInteger(jobDraft.me_start),
          me_target: parseOptionalInteger(jobDraft.me_target),
          te_start: parseOptionalInteger(jobDraft.te_start),
          te_target: parseOptionalInteger(jobDraft.te_target),
          copy_runs: parseOptionalInteger(jobDraft.copy_runs),
          invention_runs: parseOptionalInteger(jobDraft.invention_runs),
          invention_successes: parseOptionalInteger(jobDraft.invention_successes),
          items: lines.filter((line) => line.item_name.trim() && Number(line.quantity) > 0),
        }),
      });
      setMessage(`${saved.name} saved to manufacturing history.`);
      await load();
      loadJob(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save manufacturing job.");
    } finally {
      setBusy(false);
    }
  }


  async function updateOutcome() {
    if (!selectedJob) return;
    setOutcomeSaving(true);
    setError(null);
    try {
      const updated = await api<ManufacturingJob>(`/manufacturing/jobs/${selectedJob.id}`, { method: "PATCH", body: JSON.stringify({ output_disposition: draft.output_disposition, output_sale_price: parseOptionalNumber(draft.output_sale_price), output_sale_notes: draft.output_sale_notes }) });
      setJobs((current) => current.map((row) => row.id === updated.id ? updated : row));
      loadJob(updated);
      setMessage(`${updated.name} output marked ${outputDispositionLabel(updated.output_disposition).toLowerCase()}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update output outcome.");
    } finally {
      setOutcomeSaving(false);
    }
  }

  async function setJobStatus(job: ManufacturingJob, status: ManufacturingJobStatus) {
    setError(null);
    try {
      const updated = await api<ManufacturingJob>(`/manufacturing/jobs/${job.id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      setJobs((current) => current.map((row) => row.id === updated.id ? updated : row));
      if (selectedJob?.id === updated.id) loadJob(updated);
      setMessage(`${updated.name} marked ${statusLabel(updated.status).toLowerCase()}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update manufacturing job.");
    }
  }
  async function deleteJob(job: ManufacturingJob) {
    if (!window.confirm(`Delete manufacturing job ${job.name}?`)) return;
    setError(null);
    try {
      await api(`/manufacturing/jobs/${job.id}`, { method: "DELETE" });
      if (selectedJob?.id === job.id) resetDraft();
      await load();
      setMessage(`${job.name} deleted.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete manufacturing job.");
    }
  }

  const categoryGroups = categories.map((category) => ({ category, rows: lines.filter((line) => line.category === category.key) }));
  const pricedHubs: MarketHub[] = appraisal?.hubs ?? [];
  const outputPricedHubs: MarketHub[] = outputAppraisal?.hubs ?? [];
  const salePrice = parseOptionalNumber(draft.output_sale_price);
  const realizedMargin = salePrice != null ? salePrice - paidTotal : null;

  return <section className="panel stacked manufacturing-page">
    <div className="section-heading">
      <div>
        <h3>Manufacturing</h3>
        <p>Record build inputs, fees, timers, and hub pricing so production history can feed analytics later.</p>
      </div>
      <div className="button-row compact">
        <button type="button" onClick={() => void load()}><RefreshCw size={16} /> Refresh</button>
        <button type="button" onClick={resetDraft}><Plus size={16} /> New build</button>
      </div>
    </div>

    {message && <div className="notice inline">{message}</div>}
    {error && <div className="mini-alert">{error}</div>}

    <div className="manufacturing-layout">
      <aside className="panel manufacturing-ledger">
        <h4>Ledger</h4>
        <JobLedger jobs={jobs} selectedId={selectedJob?.id} now={now} onSelect={loadJob} onDelete={(job) => void deleteJob(job)} onSetStatus={(job, status) => void setJobStatus(job, status)} formatDateTime={formatDateTime} />
      </aside>

      <form className="manufacturing-workspace" onSubmit={(event) => void saveJob(event)}>
        <section className="manufacturing-summary-card">
          <div className="manufacturing-title-row">
            <label>Build name<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="Deimos, Raven Navy Issue, Core Temperature Regulators..." required /></label>
            <label>Output item<input value={draft.output_type_name} onChange={(event) => setDraft({ ...draft, output_type_name: event.target.value })} placeholder="Optional SDE item name" /></label>
            <label>Output qty<input type="number" min="1" value={draft.output_quantity} onChange={(event) => setDraft({ ...draft, output_quantity: Number(event.target.value) || 1 })} /></label>
            <label>Status<select value={draft.status} onChange={(event) => setDraft((current) => applyStatusDefaults(current, event.target.value as ManufacturingJobStatus))}><option value="draft">Draft</option><option value="running">Running</option><option value="completed">Completed</option></select></label>
          </div>
          <div className="manufacturing-activity-selector">
            {ACTIVITY_OPTIONS.map((activity) => <label key={activity.key} className="check"><input type="checkbox" checked={draft.activity_flags.includes(activity.key)} onChange={(event) => toggleActivity(activity.key, event.target.checked)} /> {activity.label}</label>)}
          </div>
          {(draft.activity_flags.includes("me") || draft.activity_flags.includes("te") || draft.activity_flags.includes("copy") || draft.activity_flags.includes("invention")) && <div className="manufacturing-title-row manufacturing-research-row">
            {(draft.activity_flags.includes("me") || draft.activity_flags.includes("te")) && <label>Research runs<input type="number" min="0" value={draft.research_runs} onChange={(event) => setDraft({ ...draft, research_runs: event.target.value })} placeholder="Runs" /></label>}
            {draft.activity_flags.includes("me") && <><label>ME from<input type="number" min="0" max="10" value={draft.me_start} onChange={(event) => setDraft({ ...draft, me_start: event.target.value })} /></label><label>ME target<input type="number" min="0" max="10" value={draft.me_target} onChange={(event) => setDraft({ ...draft, me_target: event.target.value })} /></label></>}
            {draft.activity_flags.includes("te") && <><label>TE from<input type="number" min="0" max="20" value={draft.te_start} onChange={(event) => setDraft({ ...draft, te_start: event.target.value })} /></label><label>TE target<input type="number" min="0" max="20" value={draft.te_target} onChange={(event) => setDraft({ ...draft, te_target: event.target.value })} /></label></>}
            {draft.activity_flags.includes("copy") && <label>Copy runs<input type="number" min="0" value={draft.copy_runs} onChange={(event) => setDraft({ ...draft, copy_runs: event.target.value })} placeholder="BPC runs" /></label>}
            {draft.activity_flags.includes("invention") && <><label>Invention attempts<input type="number" min="0" value={draft.invention_runs} onChange={(event) => setDraft({ ...draft, invention_runs: event.target.value })} /></label><label>Invention successes<input type="number" min="0" value={draft.invention_successes} onChange={(event) => setDraft({ ...draft, invention_successes: event.target.value })} /></label></>}
          </div>}
          <div className="manufacturing-title-row">
            <label>Cost to run<input type="number" min="0" step="0.01" value={draft.cost_to_run} onChange={(event) => setDraft({ ...draft, cost_to_run: event.target.value })} placeholder="Installation fee" /></label>
            <label>Time to run<input value={draft.time_to_run} onChange={(event) => setDraft({ ...draft, time_to_run: event.target.value })} placeholder="2d18h40m" /></label>
            <label>Date started<input type="date" value={draft.date_started} onChange={(event) => setDraft({ ...draft, date_started: event.target.value })} /></label>
            <label>Time started<input type="time" value={draft.time_started} onChange={(event) => setDraft({ ...draft, time_started: event.target.value })} /></label>
          </div>
          <div className="manufacturing-title-row manufacturing-output-row">
            <label>Output result<select value={draft.output_disposition} onChange={(event) => setDraft({ ...draft, output_disposition: event.target.value as ManufacturingOutputDisposition })}><option value="pending">Pending</option><option value="sold">Sold</option><option value="kept">Kept</option></select></label>
            <label>Sale price (total)<input type="number" min="0" step="0.01" value={draft.output_sale_price} onChange={(event) => setDraft({ ...draft, output_sale_price: event.target.value })} placeholder="Actual ISK received" /></label>
            <label>Outcome notes<input value={draft.output_sale_notes} onChange={(event) => setDraft({ ...draft, output_sale_notes: event.target.value })} placeholder="Buyer, destination, kept for doctrine, etc." /></label>
          </div>
          <label>Notes<textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} placeholder="Facility, input location, build reason, hull batch, or market assumptions." /></label>
          <div className="manufacturing-total-strip">
            <article><span>Current value</span><strong>{formatMarketIsk(enteredTotal)}</strong></article>
            <article><span>Price paid</span><strong>{formatMarketIsk(paidTotal)}</strong></article>
            <article><span>Savings / margin</span><strong>{formatMarketIsk(savingsTotal)}</strong></article>
            <article><span>Sale margin</span><strong>{realizedMargin == null ? "n/a" : formatMarketIsk(realizedMargin)}</strong></article>
            <article><span>Line items</span><strong>{lines.filter((line) => line.item_name.trim()).length.toLocaleString()}</strong></article>
            <article><span>Priced hubs</span><strong>{pricedHubs.length.toLocaleString()}</strong></article>
            <article><span>Output hubs</span><strong>{outputPricedHubs.length.toLocaleString()}</strong></article>
            <article><span>Timer</span><strong>{jobCountdownText(draft, now)}</strong></article>
          </div>
        </section>

        <section className="manufacturing-prices manufacturing-output-market">
          <div className="section-heading compact">
            <div><h4>Final Product Market</h4><p>Highlights the strongest instant-buy and lowest sell listing across major hubs.</p></div>
            <div className="button-row compact">
              <button type="button" onClick={() => void priceOutput()} disabled={outputPricing || !(draft.output_type_name.trim() || draft.name.trim())}><ClipboardList size={16} /> {outputPricing ? "Pricing" : "Price output"}</button>
              {selectedJob && <button type="button" onClick={() => void updateOutcome()} disabled={outcomeSaving}><Save size={16} /> {outcomeSaving ? "Updating" : "Update outcome"}</button>}
            </div>
          </div>
          <OutputPricePanel result={outputAppraisal} />
        </section>

        <section className="manufacturing-line-editor">
          <div className="section-heading compact">
            <div><h4>Build Inputs</h4><p>Add as many rows as needed per category.</p></div>
            <div className="button-row compact">
              <button type="button" onClick={() => void priceLines()} disabled={pricing || lines.every((line) => !line.item_name.trim())}><ClipboardList size={16} /> {pricing ? "Pricing" : "Price hubs"}</button>
              <button type="submit" disabled={busy}><Save size={16} /> {busy ? "Saving" : "Save ledger"}</button>
            </div>
          </div>
          {categoryGroups.map(({ category, rows }) => <div key={category.key} className="manufacturing-category-block">
            <div className="manufacturing-category-heading">
              <strong>{category.label}</strong>
              <button type="button" onClick={() => addLine(category.key)}><Plus size={15} /> Add</button>
            </div>
            <div className="manufacturing-line-list">
              {rows.map((line) => {
                const index = lines.indexOf(line);
                return <LineEditor key={lineKey(line, index)} categories={categories} line={line} index={index} onChange={updateLine} onRemove={removeLine} />;
              })}
              {rows.length === 0 && <span className="muted">No {category.label.toLowerCase()} rows yet.</span>}
            </div>
          </div>)}
        </section>

        <section className="manufacturing-prices">
          <div className="section-heading compact"><div><h4>Hub Prices</h4><p>Uses the major trade hubs from the Market page.</p></div></div>
          <HubPriceMatrix result={appraisal} lines={lines} />
        </section>
      </form>
    </div>
  </section>;
}

