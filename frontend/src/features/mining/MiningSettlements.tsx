import { AlertTriangle, Calculator, CheckCircle2, ClipboardCopy, DollarSign, Edit3, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { MiningCharacter, MiningOperation } from "../../types/mining";
import type {
  MiningCompensationMethod, MiningContributionBasis, MiningDeductionMethod, MiningReserveMethod, MiningSettlementMode,
  MiningSettlement, SettlementAppraisal, SettlementDeduction, SettlementOptionsPayload,
  SettlementOutput, SettlementParticipant, SettlementPreview,
} from "../../types/miningSettlement";
import { miningSettlementDiscordReport } from "./miningSettlementReport";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Draft = {
  id?: number; name: string; sourceType: "operation" | "range"; operationId: string;
  rangeStart: string; rangeEnd: string; contributionBasis: MiningContributionBasis;
  settlementMode: MiningSettlementMode; priceSource: string; outputs: SettlementOutput[]; refiningPilotName: string;
  refiningPilotCharacterId: string; refiningLocation: string; statedRefinePercent: string;
  reserveMethod: MiningReserveMethod; reserveValue: string; deductions: SettlementDeduction[];
  participants: SettlementParticipant[]; notes: string;
};

const isk = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });
const whole = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const roles = ["Miner", "Booster", "Security", "Scout", "Logistics", "Hauler", "Refiner", "Fleet Commander", "Coordinator", "Other"];
const deductionTypes = ["refining_cost", "refining_tax", "hauling", "fuel", "compression", "broker_fee", "sales_fee", "other"];
const basisLabels: Record<MiningContributionBasis, string> = {
  estimated_raw_value: "Estimated raw ore value", volume: "Recovered volume",
  quantity: "Raw quantity", manual: "Equal starting shares",
};

function emptyOutput(): SettlementOutput {
  return { type_id: 0, type_name: "", quantity: 0, unit_price: 0, price_source: "manual", price_overridden: false };
}
function emptyDeduction(): SettlementDeduction {
  return { deduction_type: "refining_cost", description: "Refining cost", calculation_method: "flat_isk", value: 0 };
}
function emptyParticipant(): SettlementParticipant {
  return { display_name: "", role: "Booster", source: "manual", compensation_method: "shares", compensation_value: 1, share_weight_overridden: true, notes: "" };
}
function freshDraft(): Draft {
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 86400000);
  return {
    name: "", sourceType: "operation", operationId: "", rangeStart: weekAgo.toISOString().slice(0, 10),
    rangeEnd: now.toISOString().slice(0, 10), contributionBasis: "estimated_raw_value", settlementMode: "isk",
    priceSource: "jita_split", outputs: [emptyOutput()], refiningPilotName: "",
    refiningPilotCharacterId: "", refiningLocation: "", statedRefinePercent: "",
    reserveMethod: "none", reserveValue: "0", deductions: [], participants: [], notes: "",
  };
}
function fromSettlement(row: MiningSettlement): Draft {
  return {
    id: row.id, name: row.name, sourceType: row.source_type,
    operationId: row.operation_id ? String(row.operation_id) : "",
    rangeStart: (row.range_start ?? row.source_filter.range_start ?? "").slice(0, 16),
    rangeEnd: (row.range_end ?? row.source_filter.range_end ?? "").slice(0, 16),
    contributionBasis: row.contribution_basis, settlementMode: row.settlement_mode, priceSource: row.price_source,
    outputs: row.outputs.map((output) => ({
      ...output,
      stated_refine_percent:
        output.stated_refine_percent == null
          ? null
          : output.stated_refine_percent * 100,
    })),
    refiningPilotName: row.refining_pilot_name ?? "",
    refiningPilotCharacterId: row.refining_pilot_character_id ? String(row.refining_pilot_character_id) : "",
    refiningLocation: row.refining_location ?? "",
    statedRefinePercent: row.stated_refine_percent == null ? "" : String(row.stated_refine_percent * 100),
    reserveMethod: row.reserve.method,
    reserveValue: String(row.reserve.normalized_percentage != null ? row.reserve.normalized_percentage * 100 : row.reserve.entered_value),
    deductions: row.deductions.map((item) => ({ ...item, value: item.normalized_percentage != null ? item.normalized_percentage * 100 : item.entered_value })),
    participants: row.participants.map((item) => ({ ...item, compensation_value: item.compensation_method === "fixed_percentage" ? (item.fixed_percentage ?? 0) * 100 : item.share_weight ?? 0 })),
    notes: row.notes ?? "",
  };
}
function requestPayload(draft: Draft) {
  return {
    name: draft.name,
    source: draft.sourceType === "operation"
      ? { type: "operation", operation_id: Number(draft.operationId) }
      : { type: "range", range_start: draft.rangeStart, range_end: draft.rangeEnd },
    contribution_basis: draft.contributionBasis, settlement_mode: draft.settlementMode,
    price_source: draft.priceSource, outputs: draft.outputs,
    refining_pilot_name: draft.refiningPilotName,
    refining_pilot_character_id: draft.refiningPilotCharacterId ? Number(draft.refiningPilotCharacterId) : null,
    refining_location: draft.refiningLocation, stated_refine_percent: draft.statedRefinePercent,
    reserve: { method: draft.reserveMethod, value: draft.reserveValue },
    deductions: draft.deductions.map((row) => ({ ...row, value: row.value ?? row.entered_value ?? 0 })),
    participants: draft.participants.map((row) => ({
      character_id: row.character_id, display_name: row.display_name, role: row.role, source: row.source,
      compensation_method: row.compensation_method,
      compensation_value: row.compensation_value ?? (row.compensation_method === "fixed_percentage" ? (row.fixed_percentage ?? 0) * 100 : row.share_weight ?? 0),
      share_weight_overridden: row.source === "ledger" ? row.share_weight_overridden : row.compensation_method === "shares",
      notes: row.notes,
    })),
    notes: draft.notes,
  };
}
function formatPercent(value?: number | null) {
  return number.format((value ?? 0) * 100) + "%";
}

export function MiningSettlements({ api, characters, operations }: {
  api: ApiClient; characters: MiningCharacter[]; operations: MiningOperation[];
}) {
  const [options, setOptions] = useState<SettlementOptionsPayload | null>(null);
  const [draft, setDraft] = useState<Draft>(freshDraft);
  const [preview, setPreview] = useState<SettlementPreview | null>(null);
  const [priceHub, setPriceHub] = useState("jita");
  const [priceSide, setPriceSide] = useState<"buy" | "split" | "sell">("split");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadOptions() {
    setOptions(await api<SettlementOptionsPayload>("/mining-ledger/settlements"));
  }
  useEffect(() => { void loadOptions().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load mining settlements")); }, []);

  function patch(value: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...value }));
    setPreview(null);
  }
  function updateOutput(index: number, value: Partial<SettlementOutput>) {
    patch({ outputs: draft.outputs.map((row, rowIndex) => rowIndex === index ? { ...row, ...value } : row) });
  }
  function updateDeduction(index: number, value: Partial<SettlementDeduction>) {
    patch({ deductions: draft.deductions.map((row, rowIndex) => rowIndex === index ? { ...row, ...value } : row) });
  }
  function updateParticipant(index: number, value: Partial<SettlementParticipant>) {
    patch({ participants: draft.participants.map((row, rowIndex) => rowIndex === index ? { ...row, ...value } : row) });
  }

  async function calculate(): Promise<SettlementPreview | null> {
    setBusy(true); setError(null); setMessage(null);
    try {
      const result = await api<SettlementPreview>("/mining-ledger/settlements/preview", { method: "POST", body: JSON.stringify(requestPayload(draft)) });
      setPreview(result);
      setDraft((current) => ({
        ...current,
        participants: result.participants.map((row) => ({
          ...row,
          compensation_value: row.compensation_method === "fixed_percentage" ? (row.fixed_percentage ?? 0) * 100 : row.share_weight ?? 0,
        })),
      }));
      return result;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to calculate settlement");
      return null;
    } finally { setBusy(false); }
  }

  async function priceOutputs() {
    setBusy(true); setError(null);
    try {
      const result = await api<SettlementAppraisal>("/mining-ledger/settlements/appraise", { method: "POST", body: JSON.stringify({ outputs: draft.outputs, hubs: [priceHub] }) });
      const prices = new Map(result.items.map((item) => [item.type_id, item.hubs[priceHub]?.[priceSide] ?? 0]));
      patch({
        priceSource: priceHub + "_" + priceSide,
        outputs: draft.outputs.map((row) => ({ ...row, unit_price: prices.get(row.type_id) ?? row.unit_price, price_source: priceHub + "_" + priceSide, price_overridden: false })),
      });
      const hub = options?.price_sources.find((row) => row.key === priceHub)?.label ?? priceHub;
      setMessage("Loaded " + priceSide + " prices from " + hub + ".");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to price refined output");
    } finally { setBusy(false); }
  }

  async function saveDraft() {
    const result = await calculate();
    if (!result) return;
    setBusy(true);
    try {
      const path = draft.id ? "/mining-ledger/settlements/" + draft.id : "/mining-ledger/settlements";
      const saved = await api<MiningSettlement>(path, { method: draft.id ? "PUT" : "POST", body: JSON.stringify(requestPayload(draft)) });
      setDraft(fromSettlement(saved)); setPreview(null); setMessage("Saved " + saved.name + " as a draft.");
      await loadOptions();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save settlement draft");
    } finally { setBusy(false); }
  }

  async function finalize(row: MiningSettlement) {
    if (!window.confirm("Finalize " + row.name + "? Finalized settlements are immutable historical snapshots.")) return;
    setBusy(true); setError(null);
    try {
      await api("/mining-ledger/settlements/" + row.id + "/finalize", { method: "POST", body: "{}" });
      setMessage(row.name + " finalized.");
      if (draft.id === row.id) { setDraft(freshDraft()); setPreview(null); }
      await loadOptions();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to finalize settlement");
    } finally { setBusy(false); }
  }

  async function removeDraft(row: MiningSettlement) {
    if (!window.confirm("Delete draft " + row.name + "?")) return;
    setBusy(true);
    try {
      await api("/mining-ledger/settlements/" + row.id, { method: "DELETE" });
      if (draft.id === row.id) setDraft(freshDraft());
      await loadOptions();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete settlement draft");
    } finally { setBusy(false); }
  }

  async function copyReport(row: MiningSettlement | SettlementPreview, name: string, status?: string) {
    try {
      await navigator.clipboard.writeText(miningSettlementDiscordReport(row, name, status));
      setMessage("Copied a Discord-ready settlement report.");
      setError(null);
    } catch {
      setError("Unable to copy the settlement report to the clipboard.");
    }
  }

  const outputTotal = useMemo(() => draft.outputs.reduce((total, row) => total + row.quantity * row.unit_price, 0), [draft.outputs]);
  const selectedTypes = new Set(draft.outputs.map((row) => row.type_id).filter(Boolean));

  return <section className="mining-settlements">
    <div className="section-heading">
      <div><h4>Mining Op Settlement</h4><p>Turn actual refined output and ledger contributions into auditable ISK or mineral shares.</p></div>
      <button type="button" onClick={() => setOpen((value) => !value)}><Calculator size={16} />{open ? "Close calculator" : "Open split calculator"}</button>
    </div>
    {error && <div className="mini-alert">{error}</div>}{message && <div className="notice inline">{message}</div>}
    {open && <div className="settlement-editor">
      <SettlementSource draft={draft} operations={operations} patch={patch} />
      <section className="settlement-step">
        <StepHeader number="2" title="Enter actual refined output" description="These quantities are authoritative. Reported refine percentages are analytics metadata only." />
        <div className="settlement-price-controls">
          <label>Trade hub<select value={priceHub} onChange={(event) => setPriceHub(event.target.value)}>{options?.price_sources.filter((row) => row.available && !row.key.startsWith("npc")).map((row) => <option value={row.key} key={row.key}>{row.label}</option>)}</select></label>
          <label>Price<select value={priceSide} onChange={(event) => setPriceSide(event.target.value as typeof priceSide)}><option value="buy">Best buy</option><option value="split">Market split</option><option value="sell">Lowest sell</option></select></label>
          <button type="button" disabled={busy} onClick={() => void priceOutputs()}><DollarSign size={15} />Price minerals</button>
          <strong>{isk.format(outputTotal)} ISK entered</strong>
        </div>
        <div className="settlement-repeat-list">
          {draft.outputs.map((row, index) => <div className="settlement-output-row" key={String(row.type_id) + "-" + index}>
            <label>Mineral<select value={row.type_id || ""} onChange={(event) => { const typeId = Number(event.target.value); const mineral = options?.minerals.find((item) => item.type_id === typeId); updateOutput(index, { type_id: typeId, type_name: mineral?.name ?? "" }); }}><option value="">Select mineral</option>{options?.minerals.map((mineral) => <option key={mineral.type_id} value={mineral.type_id} disabled={selectedTypes.has(mineral.type_id) && mineral.type_id !== row.type_id}>{mineral.name}</option>)}</select></label>
            <label>Type ID<input value={row.type_id || ""} readOnly /></label>
            <label>Quantity<input type="number" min="0" step="1" value={row.quantity || ""} onChange={(event) => updateOutput(index, { quantity: Number(event.target.value) || 0 })} /></label>
            <label>Unit price<input type="number" min="0" step=".0001" value={row.unit_price || ""} onChange={(event) => updateOutput(index, { unit_price: Number(event.target.value) || 0, price_overridden: true, price_source: "manual" })} /></label>
            <label>Reported refine %<input type="number" min="0" max="100" step=".01" value={row.stated_refine_percent ?? ""} onChange={(event) => updateOutput(index, { stated_refine_percent: event.target.value === "" ? null : Number(event.target.value) })} /></label>
            <span className="settlement-row-total">{isk.format(row.quantity * row.unit_price)} ISK</span>
            <button type="button" className="danger compact-icon-button" title="Remove mineral" onClick={() => patch({ outputs: draft.outputs.filter((_, rowIndex) => rowIndex !== index) })}><Trash2 size={15} /></button>
          </div>)}
          <button type="button" className="settlement-add-row" onClick={() => patch({ outputs: [...draft.outputs, emptyOutput()] })}><Plus size={15} />Add mineral</button>
        </div>
      </section>
      <RefiningAndExpenses draft={draft} characters={characters} patch={patch} updateDeduction={updateDeduction} />
      <Participants draft={draft} characters={characters} patch={patch} updateParticipant={updateParticipant} />
      <section className="settlement-step">
        <StepHeader number="5" title="Preview and reconcile" description="The backend recalculates every value. Nothing is trusted from browser totals." />
        <label>Settlement notes<textarea rows={3} value={draft.notes} onChange={(event) => patch({ notes: event.target.value })} placeholder="Refining arrangement, hauling details, payout notes..." /></label>
        <div className="button-row"><button type="button" disabled={busy} onClick={() => void calculate()}><RefreshCw size={15} />Recalculate</button><button type="button" disabled={busy} onClick={() => void saveDraft()}><Save size={15} />{draft.id ? "Update draft" : "Save draft"}</button><button type="button" onClick={() => { setDraft(freshDraft()); setPreview(null); }}><Plus size={15} />New settlement</button></div>
        {preview && <SettlementPreviewView preview={preview} onCopy={() => void copyReport(preview, draft.name, "Preview")} />}
      </section>
    </div>}
    <SettlementHistory rows={options?.settlements ?? []} busy={busy} onEdit={(row) => { setDraft(fromSettlement(row)); setPreview(null); setOpen(true); }} onFinalize={finalize} onDelete={removeDraft} onCopy={(row) => void copyReport(row, row.name, row.status)} />
  </section>;
}

function StepHeader({ number: step, title, description }: { number: string; title: string; description: string }) {
  return <header><span>{step}</span><div><h5>{title}</h5><p>{description}</p></div></header>;
}

function SettlementSource({ draft, operations, patch }: { draft: Draft; operations: MiningOperation[]; patch: (value: Partial<Draft>) => void }) {
  return <section className="settlement-step">
    <StepHeader number="1" title="Choose the mining activity" description="Saved operations and date ranges use persistent Mining Ledger history." />
    <div className="form-grid settlement-source-grid">
      <label>Settlement name<input value={draft.name} onChange={(event) => patch({ name: event.target.value })} placeholder="Hahda replenishment op" /></label>
      <label>Source<select value={draft.sourceType} onChange={(event) => patch({ sourceType: event.target.value as Draft["sourceType"] })}><option value="operation">Saved mining operation</option><option value="range">Date or time range</option></select></label>
      {draft.sourceType === "operation"
        ? <label>Operation<select value={draft.operationId} onChange={(event) => patch({ operationId: event.target.value })}><option value="">Select operation</option>{operations.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        : <><label>From<input type="datetime-local" value={draft.rangeStart} onChange={(event) => patch({ rangeStart: event.target.value })} /></label><label>To<input type="datetime-local" value={draft.rangeEnd} onChange={(event) => patch({ rangeEnd: event.target.value })} /></label></>}
      <label>Contribution basis<select value={draft.contributionBasis} onChange={(event) => patch({ contributionBasis: event.target.value as MiningContributionBasis })}>{Object.entries(basisLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Payout method<select value={draft.settlementMode} onChange={(event) => patch({ settlementMode: event.target.value as MiningSettlementMode })}><option value="isk">ISK shares</option><option value="minerals">Mineral shares</option></select></label>
    </div>
  </section>;
}

function RefiningAndExpenses({ draft, characters, patch, updateDeduction }: {
  draft: Draft; characters: MiningCharacter[]; patch: (value: Partial<Draft>) => void;
  updateDeduction: (index: number, value: Partial<SettlementDeduction>) => void;
}) {
  return <section className="settlement-step">
    <StepHeader number="3" title="Record refining details and expenses" description="Link the refiner when possible, or keep a plain-text pilot for outside help." />
    <div className="form-grid settlement-refiner-grid">
      <label>Linked EQM refiner<select value={draft.refiningPilotCharacterId} onChange={(event) => { const selected = characters.find((row) => String(row.character_id) === event.target.value); patch({ refiningPilotCharacterId: event.target.value, refiningPilotName: selected?.name ?? draft.refiningPilotName }); }}><option value="">Unlinked or outside pilot</option>{characters.map((row) => <option key={row.character_id} value={row.character_id}>{row.name}</option>)}</select></label>
      <label>Refining pilot<input value={draft.refiningPilotName} onChange={(event) => patch({ refiningPilotName: event.target.value })} /></label>
      <label>Location or structure<input value={draft.refiningLocation} onChange={(event) => patch({ refiningLocation: event.target.value })} placeholder="Station, structure, or system" /></label>
      <label>Stated total refine %<input type="number" min="0" max="100" step=".01" value={draft.statedRefinePercent} onChange={(event) => patch({ statedRefinePercent: event.target.value })} /></label>
    </div>
    <div className="settlement-reserve-grid">
      <label>Operation reserve<select value={draft.reserveMethod} onChange={(event) => patch({ reserveMethod: event.target.value as MiningReserveMethod })}><option value="none">No reserve</option><option value="percentage">Percent of gross value</option><option value="output_percentage">Percent of output value</option><option value="flat_isk">Flat ISK amount</option></select></label>
      <label>{draft.reserveMethod === "flat_isk" ? "Reserve ISK" : "Reserve %"}<input type="number" min="0" step=".01" disabled={draft.reserveMethod === "none"} value={draft.reserveValue} onChange={(event) => patch({ reserveValue: event.target.value })} /></label>
      <small>Enter either 10 or 0.10 for 10%. The preview shows EQM's interpretation.</small>
    </div>
    <div className="settlement-repeat-list">
      {draft.deductions.map((row, index) => <div className="settlement-deduction-row" key={index}>
        <label>Expense<select value={row.deduction_type} onChange={(event) => updateDeduction(index, { deduction_type: event.target.value })}>{deductionTypes.map((type) => <option key={type} value={type}>{type.replace(/_/g, " ")}</option>)}</select></label>
        <label>Description<input value={row.description} onChange={(event) => updateDeduction(index, { description: event.target.value })} /></label>
        <label>Method<select value={row.calculation_method} onChange={(event) => updateDeduction(index, { calculation_method: event.target.value as MiningDeductionMethod })}><option value="flat_isk">Flat ISK</option><option value="percentage">Percent of gross</option></select></label>
        <label>Value<input type="number" min="0" step=".01" value={row.value ?? 0} onChange={(event) => updateDeduction(index, { value: Number(event.target.value) || 0 })} /></label>
        <button type="button" className="danger compact-icon-button" title="Remove expense" onClick={() => patch({ deductions: draft.deductions.filter((_, rowIndex) => rowIndex !== index) })}><Trash2 size={15} /></button>
      </div>)}
      <button type="button" className="settlement-add-row" onClick={() => patch({ deductions: [...draft.deductions, emptyDeduction()] })}><Plus size={15} />Add expense</button>
    </div>
  </section>;
}

function Participants({ draft, characters, patch, updateParticipant }: {
  draft: Draft; characters: MiningCharacter[]; patch: (value: Partial<Draft>) => void;
  updateParticipant: (index: number, value: Partial<SettlementParticipant>) => void;
}) {
  return <section className="settlement-step">
    <StepHeader number="4" title="Assign pilots and compensation" description="Preview once to load miners. Add outside support pilots by name, with fixed percentages or relative shares." />
    <div className="settlement-repeat-list">
      {draft.participants.map((row, index) => <div className="settlement-participant-row" key={row.source + "-" + String(row.character_id ?? index) + "-" + index}>
        {row.source === "ledger" ? <label>Pilot<input value={row.display_name} readOnly /></label> : <>
          <label>Linked character<select value={row.character_id ?? ""} onChange={(event) => { const selected = characters.find((item) => String(item.character_id) === event.target.value); updateParticipant(index, { character_id: selected?.character_id ?? null, display_name: selected?.name ?? row.display_name, source: selected ? "linked_character" : "manual" }); }}><option value="">Outside pilot</option>{characters.map((character) => <option value={character.character_id} key={character.character_id}>{character.name}</option>)}</select></label>
          <label>Display name<input value={row.display_name} onChange={(event) => updateParticipant(index, { display_name: event.target.value })} /></label>
        </>}
        <label>Role<select value={roles.includes(row.role) ? row.role : "Other"} onChange={(event) => updateParticipant(index, { role: event.target.value })}>{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
        <label>Compensation<select value={row.compensation_method} onChange={(event) => updateParticipant(index, { compensation_method: event.target.value as MiningCompensationMethod, compensation_value: event.target.value === "fixed_percentage" ? 0 : 1, share_weight_overridden: row.source !== "ledger" })}><option value="shares">Relative shares</option><option value="fixed_percentage">Fixed %</option></select></label>
        <label>{row.compensation_method === "fixed_percentage" ? "Fixed %" : "Share weight"}<input type="number" min="0" step=".01" value={row.compensation_value ?? 0} onChange={(event) => updateParticipant(index, { compensation_value: Number(event.target.value) || 0, share_weight_overridden: row.source === "ledger" && row.compensation_method === "shares" })} /></label>
        <label>Notes<input value={row.notes ?? ""} onChange={(event) => updateParticipant(index, { notes: event.target.value })} /></label>
        {row.source !== "ledger" && <button type="button" className="danger compact-icon-button" title="Remove pilot" onClick={() => patch({ participants: draft.participants.filter((_, rowIndex) => rowIndex !== index) })}><Trash2 size={15} /></button>}
      </div>)}
      <button type="button" className="settlement-add-row" onClick={() => patch({ participants: [...draft.participants, emptyParticipant()] })}><Plus size={15} />Add support pilot</button>
    </div>
  </section>;
}

function SettlementPreviewView({ preview, onCopy }: { preview: SettlementPreview; onCopy: () => void }) {
  return <div className="settlement-preview">
    <div className="settlement-preview-actions"><span>{preview.settlement_mode === "minerals" ? "Mineral-share settlement" : "ISK-share settlement"}</span><button type="button" onClick={onCopy}><ClipboardCopy size={14} />Copy Discord report</button></div>
    {preview.warnings.length > 0 && <div className="settlement-warnings"><AlertTriangle size={17} /><div>{preview.warnings.map((warning) => <span key={warning}>{warning}</span>)}</div></div>}
    <div className="settlement-reconciliation">
      <div><span>Gross refined value</span><strong>{isk.format(preview.gross_value)} ISK</strong></div>
      <div><span>Operation reserve {preview.reserve_normalized_percentage != null ? "(" + formatPercent(preview.reserve_normalized_percentage) + ")" : ""}</span><strong>-{isk.format(preview.reserve_value)} ISK</strong></div>
      <div><span>Other expenses</span><strong>-{isk.format(preview.deduction_total)} ISK</strong></div>
      <div className="total"><span>Distributable value</span><strong>{isk.format(preview.distributable_value)} ISK</strong></div>
      <div><span>Fixed payouts</span><strong>{isk.format(preview.fixed_payout_total)} ISK</strong></div>
      <div><span>Share pool</span><strong>{isk.format(preview.share_pool_value)} ISK</strong></div>
      <div><span>Participant payouts</span><strong>{isk.format(preview.participant_payout_total)} ISK</strong></div>
      <div className={Math.abs(preview.unallocated_remainder) > .01 ? "difference bad" : "difference"}><span>Reconciliation difference</span><strong>{isk.format(preview.unallocated_remainder)} ISK</strong></div>
    </div>
    <div className="table-wrap"><table className="settlement-payout-table"><thead><tr><th>Pilot</th><th>Role / source</th><th>Contribution</th><th>Compensation</th><th>Payout ratio</th><th>Final payout</th></tr></thead><tbody>{preview.participants.map((row, index) => <tr key={row.display_name + "-" + index}><td>{row.display_name}</td><td>{row.role}<span>{row.source.replace("_", " ")}</span></td><td>{isk.format(row.contribution_value ?? 0)} ISK<span>{formatPercent(row.contribution_percentage)}</span></td><td>{row.compensation_method === "fixed_percentage" ? formatPercent(row.fixed_percentage) + " fixed" : number.format(row.share_weight ?? 0) + " shares"}</td><td>{formatPercent(row.payout_ratio)}</td><td>{preview.settlement_mode === "minerals" ? <div className="settlement-mineral-basket">{(row.mineral_payouts ?? []).map((mineral) => <span key={mineral.type_id}>{mineral.type_name} <strong>{whole.format(mineral.quantity)}</strong></span>)}</div> : <strong>{isk.format(row.payout_isk ?? 0)} ISK</strong>}</td></tr>)}</tbody></table></div>
  </div>;
}

function SettlementHistory({ rows, busy, onEdit, onFinalize, onDelete, onCopy }: {
  rows: MiningSettlement[]; busy: boolean; onEdit: (row: MiningSettlement) => void;
  onFinalize: (row: MiningSettlement) => Promise<void>; onDelete: (row: MiningSettlement) => Promise<void>;
  onCopy: (row: MiningSettlement) => void;
}) {
  return <div className="settlement-history">
    <div className="section-heading"><div><h5>Settlement history</h5><p>Finalized rows are immutable snapshots; drafts remain editable.</p></div></div>
    <div className="table-wrap"><table><thead><tr><th>Settlement</th><th>Scope</th><th>Status</th><th>Gross</th><th>Distributed</th><th>Created by</th><th>Actions</th></tr></thead><tbody>
      {rows.map((row) => <tr key={row.id}><td><strong>{row.name}</strong><span>{row.source_entry_count} ledger rows · {row.participants.length} pilots</span></td><td>{row.operation_name ?? (row.range_start && row.range_end ? new Date(row.range_start).toLocaleDateString() + " - " + new Date(row.range_end).toLocaleDateString() : row.source_type)}</td><td><span className={"settlement-status " + row.status}>{row.status === "finalized" ? <CheckCircle2 size={13} /> : <Edit3 size={13} />}{row.status}</span><span>{row.settlement_mode === "minerals" ? "Minerals" : "ISK"}</span></td><td>{isk.format(row.gross_value)} ISK</td><td>{row.settlement_mode === "minerals" ? "Mineral shares" : isk.format(row.participant_payout_total) + " ISK"}</td><td>{row.created_by}<span>{row.created_at ? new Date(row.created_at).toLocaleString() : ""}</span></td><td><div className="button-row compact"><button type="button" disabled={busy} onClick={() => onCopy(row)}><ClipboardCopy size={14} />Report</button>{row.status === "draft" && <><button type="button" disabled={busy} onClick={() => onEdit(row)}><Edit3 size={14} />Edit</button><button type="button" disabled={busy} onClick={() => void onFinalize(row)}><CheckCircle2 size={14} />Finalize</button><button type="button" className="danger compact-icon-button" title="Delete draft" disabled={busy} onClick={() => void onDelete(row)}><Trash2 size={14} /></button></>}</div></td></tr>)}
      {rows.length === 0 && <tr><td colSpan={7}>No mining settlements saved yet.</td></tr>}
    </tbody></table></div>
  </div>;
}
