import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ApiClient, Highlight, ReportMeta, ScanContext, ScanReport } from "./types";
import { LocalScanResults } from "./LocalScanResults";
import "./localScan.css";

type DeleteSpec = {tokens: string[]} | {from_at: string; to_at: string} | {all_in_scope: true};
type System = {system_id: number; name: string};
const errorText = (e: unknown) => e instanceof Error ? e.message : "Request failed.";
const retentionLabel: Record<string,string> = {"30m":"30 minutes","1h":"1 hour","2h":"2 hours","12h":"12 hours","24h":"24 hours","3days":"3 days","7days":"7 days","30days":"30 days","permanent":"Permanent"};

export function LocalScanPage({api}: {api: ApiClient}) {
  const [context,setContext] = useState<ScanContext | null>(null);
  const [text,setText] = useState("");
  const [retention,setRetention] = useState("24h");
  const [corp,setCorp] = useState("");
  const [systemText,setSystemText] = useState("");
  const [systems,setSystems] = useState<System[]>([]);
  const [system,setSystem] = useState<System | null>(null);
  const [report,setReport] = useState<ScanReport | null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [message,setMessage] = useState("");
  const [highlights,setHighlights] = useState<Highlight[]>([]);
  const [targetName,setTargetName] = useState("");
  const [targetKind,setTargetKind] = useState("corporation");
  const [highlightBusy,setHighlightBusy] = useState(false);
  const [history,setHistory] = useState<{reports:ReportMeta[]; total:number}>({reports:[],total:0});
  const [offset,setOffset] = useState(0);
  const [selected,setSelected] = useState<string[]>([]);
  const [from,setFrom] = useState("");
  const [to,setTo] = useState("");
  const [pending,setPending] = useState<{spec:DeleteSpec; message:string} | null>(null);
  const [deleting,setDeleting] = useState(false);
  const loadHistory = useCallback(async () => {
    setHistory(await api(`/local-scans/reports?offset=${offset}&limit=25`)); setSelected([]);
  },[api,offset]);
  useEffect(() => {
    let active = true;
    void Promise.all([api<ScanContext>("/local-scans/context"),api<Highlight[]>("/local-scans/highlights")])
      .then(([ctx,targets]) => {if(active){setContext(ctx);setHighlights(targets); if(ctx.corporations.length === 1) setCorp(String(ctx.corporations[0].id));}})
      .catch(e => {if(active)setError(errorText(e));});
    return () => {active=false;};
  },[api]);
  useEffect(() => {void loadHistory().catch(e=>setError(errorText(e)));},[loadHistory]);
  useEffect(() => {
    if (system || systemText.trim().length < 2) {setSystems([]);return;}
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void api<System[]>(`/navigation/systems?q=${encodeURIComponent(systemText.trim())}&limit=12`,{signal:controller.signal})
        .then(setSystems).catch(e=>{if(!controller.signal.aborted)setError(errorText(e));});
    },250);
    return () => {window.clearTimeout(timer);controller.abort();};
  },[api,systemText,system]);
  async function generate(e: FormEvent) {
    e.preventDefault();setBusy(true);setError("");setMessage("");
    try {
      const result = await api<ScanReport>("/local-scans",{method:"POST",body:JSON.stringify({text,retention,corporation_id:corp ? Number(corp) : null,system_id:system?.system_id ?? null})});
      setReport(result);setOffset(0);await loadHistory();
    } catch(e) {setError(errorText(e));} finally {setBusy(false);}
  }
  async function addHighlight(e:FormEvent) {
    e.preventDefault();setHighlightBusy(true);setError("");
    try {
      await api("/local-scans/highlights",{method:"POST",body:JSON.stringify({kind:targetKind,name:targetName})});
      setHighlights(await api<Highlight[]>("/local-scans/highlights"));setTargetName("");
    } catch(e) {setError(errorText(e));} finally {setHighlightBusy(false);}
  }
  async function removeHighlight(id:number) {
    setHighlightBusy(true);setError("");
    try {await api(`/local-scans/highlights/${id}`,{method:"DELETE"});setHighlights(rows=>rows.filter(r=>r.id !== id));}
    catch(e) {setError(errorText(e));}finally{setHighlightBusy(false);}
  }
  async function openReport(token:string) {
    setError("");
    try {setReport(await api<ScanReport>(`/local-scans/public/${encodeURIComponent(token)}`));}
    catch(e) {setError(errorText(e));}
  }
  async function dateDeletion() {
    if(!from || !to || from >= to){setError("Choose a start before the end of the UTC date range.");return;}
    const spec = {from_at:new Date(from+"Z").toISOString(),to_at:new Date(to+"Z").toISOString()};
    try {const result=await api<{total:number}>(`/local-scans/reports?limit=1&from_at=${encodeURIComponent(spec.from_at)}&to_at=${encodeURIComponent(spec.to_at)}`);
      setPending({spec,message:`Delete reports generated from ${from.replace('T',' ')} UTC (inclusive) to ${to.replace('T',' ')} UTC (exclusive) within ${context?.management_scope}? ${result.total} active reports currently match.`});
    }catch(e){setError(errorText(e));}
  }
  async function confirmDelete() {
    if(!pending)return;setDeleting(true);setError("");
    try {const result=await api<{deleted:number}>("/local-scans/reports/delete",{method:"POST",body:JSON.stringify(pending.spec)});
      setMessage(`Deleted ${result.deleted} report(s). Public links and PDF downloads are no longer available.`);setReport(null);setPending(null);setOffset(0);await loadHistory();
    }catch(e){setError(errorText(e));}finally{setDeleting(false);}
  }
  return <div className="local-scan-page">
    {error && <div className="alert" role="alert">{error}</div>}{message && <div className="notice" role="status">{message}</div>}
    <section className="panel scan-compose"><h3>New local scan</h3><p className="muted">Paste pilot names from local chat, one per line, or fleet clipboard rows with the pilot name first. Up to {context?.max_pilots.toLocaleString() ?? "2,000"} unique names.</p><form onSubmit={e=>void generate(e)}>
      <label>Pilot names<textarea aria-label="Pilot names" value={text} onChange={e=>setText(e.target.value)} rows={7} maxLength={150000} required placeholder="Paste local here, or enter a character name" /></label>
      <div className="scan-compose-options"><label>Keep public report<select aria-label="Report retention" value={retention} onChange={e=>setRetention(e.target.value)}>{(context?.retentions ?? Object.keys(retentionLabel)).map(r=><option key={r} value={r}>{retentionLabel[r]}</option>)}</select></label>
        <label>Report corporation<select value={corp} onChange={e=>setCorp(e.target.value)}><option value="">Personal report</option>{context?.corporations.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <div className="scan-system-search"><label>System (optional)<input aria-label="Scan system search" value={systemText} onChange={e=>{setSystemText(e.target.value);setSystem(null);}} placeholder="Search solar systems" autoComplete="off"/></label>{systems.length>0 && <ul className="scan-system-options">{systems.map(s=><li key={s.system_id}><button type="button" onClick={()=>{setSystem(s);setSystemText(s.name);setSystems([]);}}>{s.name}</button></li>)}</ul>}</div></div>
      {systemText && !system && <p className="muted">Choose a search result to link this report to a system.</p>}
      <p className="muted">Generating creates a public link containing pilot names, affiliations, your EQM account name, date, selected system, and marked organizations. Your corporation's directors can manage corporation-attributed reports.</p>
      <button type="submit" disabled={busy || !context?.can_generate || Boolean(systemText && !system)}>{busy ? "Resolving pilots and affiliations…" : "Generate public local scan"}</button>
      {context && !context.can_generate && <p className="muted">Your role can view saved reports but cannot generate them.</p>}
    </form></section>
    <details className="panel scan-highlight-editor"><summary>Highlighted organizations <span className="scan-count">{highlights.length}</span></summary><p className="muted">Saved to your account across sessions. Matches are marked red in new reports and PDFs. Existing snapshots keep their original markings.</p>
      <form className="scan-highlight-form" onSubmit={e=>void addHighlight(e)}><label>Type<select value={targetKind} onChange={e=>setTargetKind(e.target.value)}><option value="corporation">Corporation</option><option value="alliance">Alliance</option></select></label><label>Exact organization name<input value={targetName} onChange={e=>setTargetName(e.target.value)} maxLength={255} required /></label><button type="submit" disabled={highlightBusy || !context?.can_generate}>Add</button></form>
      <div className="scan-highlight-chips">{highlights.map(h=><span key={h.id} className="scan-highlight-chip"><span>{h.name} <small>({h.kind})</small></span><button type="button" aria-label={`Remove ${h.name}`} disabled={highlightBusy || !context?.can_generate} onClick={()=>void removeHighlight(h.id)}>×</button></span>)}</div>{highlights.length===0 && <p className="muted">No organizations marked yet.</p>}
    </details>
    {report && <div className="panel"><LocalScanResults key={report.token} report={report} api={api}/></div>}
    <section className="panel scan-history"><div className="scan-report-header"><h3>Saved local scans</h3><button type="button" onClick={()=>void loadHistory().catch(e=>setError(errorText(e)))}>Refresh reports</button></div><p className="muted">Manage {context?.management_scope ?? "your reports"}. {history.total} active reports. Expired reports are removed automatically.</p>
      {context?.can_generate && <><div className="scan-report-actions"><button type="button" disabled={selected.length===0 || deleting} onClick={()=>setPending({spec:{tokens:selected},message:`Delete ${selected.length} selected report(s) within ${context.management_scope}?`})}>Delete selected ({selected.length})</button><button type="button" disabled={history.total===0 || deleting} onClick={()=>setPending({spec:{all_in_scope:true},message:`Delete ALL reports within ${context.management_scope}? ${history.total} active reports currently match.`})}>Delete all in scope</button></div>
      <div className="scan-date-range"><label>Generated from (UTC, inclusive)<input type="datetime-local" value={from} onChange={e=>setFrom(e.target.value)}/></label><label>Generated before (UTC, exclusive)<input type="datetime-local" value={to} onChange={e=>setTo(e.target.value)}/></label><button type="button" disabled={deleting} onClick={()=>void dateDeletion()}>Delete date range</button></div></>}
      {pending && <div className="scan-delete-confirm" role="alertdialog" aria-label="Confirm report deletion"><p>{pending.message} This permanently removes the reports and their public links.</p><div className="scan-report-actions"><button type="button" disabled={deleting} onClick={()=>void confirmDelete()}>{deleting?"Deleting…":"Confirm deletion"}</button><button type="button" disabled={deleting} onClick={()=>setPending(null)}>Cancel</button></div></div>}
      <div className="scan-history-list">{history.reports.map(r=><div className="scan-history-row" key={r.token}><input type="checkbox" aria-label={`Select report ${r.token}`} checked={selected.includes(r.token)} disabled={!context?.can_generate} onChange={e=>setSelected(ids=>e.target.checked?[...ids,r.token]:ids.filter(t=>t!==r.token))}/><button type="button" className="scan-history-open" onClick={()=>void openReport(r.token)}><strong>{r.character_count} characters</strong><span>{r.account_name} · {new Date(r.created_at).toLocaleString()}</span><small>{r.expires_at?`Expires ${new Date(r.expires_at).toLocaleString()}`:"Permanent"}</small></button>{context?.can_generate && <button type="button" aria-label={`Delete report ${r.token}`} onClick={()=>setPending({spec:{tokens:[r.token]},message:`Delete this report by ${r.account_name} generated ${new Date(r.created_at).toLocaleString()}?`})}>Delete</button>}</div>)}</div>
      {history.total===0 && <p className="empty">No active reports in your scope.</p>}<div className="scan-report-actions"><button type="button" disabled={offset===0} onClick={()=>setOffset(n=>Math.max(0,n-25))}>Previous</button><span>{history.total ? `${offset+1}–${Math.min(offset+25,history.total)} of ${history.total}`:"0 reports"}</span><button type="button" disabled={offset+25>=history.total} onClick={()=>setOffset(n=>n+25)}>Next</button></div>
    </section>
  </div>;
}
