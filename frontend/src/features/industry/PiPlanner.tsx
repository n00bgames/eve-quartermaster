import { useEffect, useRef, useState } from "react";
import { Download, Play, Plus, Save, Square, Upload } from "lucide-react";

import type { ApiClient, Costs, JobSummary, PlannerContext, PlanningJob, PlanningRequest, SavedScenario, Schedule, TemplateResult } from "./piPlannerTypes";
import { planetKinds } from "./piPlannerTypes";
import { addPlanets, buildSheet, defaultRequest, dependencyIds, hypotheticalPlanet, importScenario, removePlanet } from "./piPlannerState";
import { PiPlanResults, PiRecipeTools, PiScout, PiTemplateTools } from "./PiPlannerTools";
import "./piPlanner.css";

import { CommoditySelect, PiNumberField, downloadPi, plannerPath } from "./PiPlannerControls";

export function PiPlanner({ api }: { api: ApiClient }) {
  const [context, setContext] = useState<PlannerContext | null>(null);
  const [request, setRequest] = useState<PlanningRequest | null>(null);
  const [scenarios, setScenarios] = useState<SavedScenario[]>([]);
  const [saved, setSaved] = useState<{id: string; revision: number} | null>(null);
  const [job, setJob] = useState<PlanningJob | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("plan");
  const [planIndex, setPlanIndex] = useState(0);
  const [template, setTemplate] = useState<TemplateResult | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const running = job && ["queued", "pricing", "solving"].includes(job.status);
  const result = job?.result;
  const plan = result?.plans[planIndex];
  async function load() {
    const [value, savedRows, jobs] = await Promise.all([api<PlannerContext>(`${plannerPath}/context`), api<SavedScenario[]>(`${plannerPath}/scenarios`), api<JobSummary[]>(`${plannerPath}/jobs`)]);
    setContext(value); setRequest(r => r ?? defaultRequest(value)); setScenarios(savedRows); setRecentJobs(jobs);
  }
  useEffect(() => { void load().catch(e => setError(e.message)); }, []);
  useEffect(() => {
    if (!running || !job) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api<PlanningJob>(`${plannerPath}/jobs/${job.id}`, { signal: abort.signal });
        if (abort.signal.aborted) return;
        setJob(next);
        if (next.error) setError(next.error);
        if (!["queued", "pricing", "solving"].includes(next.status)) setRecentJobs(await api<JobSummary[]>(`${plannerPath}/jobs`));
        if (["queued", "pricing", "solving"].includes(next.status)) timer = setTimeout(poll, 1200);
      } catch (e) {
        if (!abort.signal.aborted) { setError(e instanceof Error ? e.message : "Cannot read planning job"); setJob(null); }
      }
    };
    timer = setTimeout(poll, 500);
    return () => { abort.abort(); clearTimeout(timer); };
  }, [job?.id, Boolean(running)]);
  async function action(fn: () => Promise<void>) {
    setError(null); setNotice(""); setBusy(true);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Planner request failed"); } finally { setBusy(false); }
  }
  const send = <T,>(path: string, body: unknown, method = "POST") => api<T>(`${plannerPath}${path}`, {method, body: JSON.stringify(body)});
  if (!context || !request) return <div className="pi-planner"><p role={error ? "alert" : "status"}>{error ?? "Loading PI planning data…"}</p><button type="button" onClick={() => void action(load)}>Retry</button></div>;
  const catalog = context.catalog;
  const update = (patch: Partial<PlanningRequest>) => setRequest({ ...request, ...patch });
  const chainIds = dependencyIds(catalog, request.products.map(p => p.type_id));
  const stale = !!result && JSON.stringify(result.request) !== JSON.stringify(request);
  async function save(copy: boolean) {
    if (!request) return;
    const value = await send<{id: string; revision: number}>(!copy && saved ? `/scenarios/${saved.id}` : "/scenarios", {request, revision: !copy && saved ? saved.revision : null}, !copy && saved ? "PUT" : "POST");
    setSaved(value); setScenarios(await api<SavedScenario[]>(`${plannerPath}/scenarios`)); setNotice("Scenario saved.");
  }
  async function importFile(file: File) {
    if (file.size > 250000) throw new Error("Scenario files are limited to 250 KB");
    const parsed = importScenario(await file.text());
    const validated = await send<PlanningRequest>("/validate", parsed);
    setRequest(validated); setSaved(null); setNotice("Scenario imported. Run it to fetch fresh ESI prices.");
  }
  return <div className="pi-planner">
    <div className="pi-toolbar">
      <div><h3>Plan your next PI operation</h3><p>Compare what to make, where to build, and what remains after inputs, customs and hauling.</p></div>
      <div className="button-row compact">
        <button type="button" disabled={busy} onClick={() => void action(() => save(false))}><Save size={15} />Save{saved ? " changes" : " scenario"}</button>
        {saved && <button type="button" disabled={busy} onClick={() => void action(() => save(true))}>Save a copy</button>}
        <button type="button" onClick={() => downloadPi("eqm-pi-scenario.json", request)}><Download size={15} />Export scenario</button>
        <button type="button" disabled={busy} onClick={() => fileInput.current?.click()}><Upload size={15} />Import</button>
        <input hidden type="file" accept=".json,application/json" ref={fileInput} aria-label="Import PI scenario" onChange={e => { const file = e.target.files?.[0]; if (file) void action(() => importFile(file)); e.target.value = ""; }} />
      </div>
    </div>
    <div className="pi-scenario-row">
      <label>Scenario name<input maxLength={120} value={request.name} onChange={e => update({name: e.target.value})} /></label>
      <label>Saved scenarios<select value={saved?.id ?? ""} onChange={e => { const row = scenarios.find(s => s.id === e.target.value); if (row) { setRequest(row.request); setSaved({id: row.id, revision: row.revision}); } else {setSaved(null); setRequest(defaultRequest(context));} }}><option value="">New scenario</option>{scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      {saved && <button type="button" disabled={busy} onClick={() => void action(async () => { await api(`${plannerPath}/scenarios/${saved.id}`, {method: "DELETE"}); setSaved(null); await load(); setNotice("Saved scenario deleted; the current draft remains open."); })}>Delete saved copy</button>}
      <small>Observed {new Date(context.as_of).toLocaleString()} · {context.baseline.colonies} existing colonies</small>
    </div>
    <details className="pi-card"><summary>Recent runs ({recentJobs.length})</summary><p className="pi-note">Open a previous result or reconnect to an unfinished run. The most recent 20 runs are retained.</p><div className="button-row compact"><button type="button" disabled={busy} onClick={() => void action(async () => setRecentJobs(await api<JobSummary[]>(`${plannerPath}/jobs`)))}>Refresh runs</button>{recentJobs.map(row => <button type="button" key={row.id} disabled={busy || !!running} onClick={() => void action(async () => {const next = await api<PlanningJob>(`${plannerPath}/jobs/${row.id}`); setJob(next); setRequest(next.request); setSaved(null); setPlanIndex(0); setTab("plan");})}>{row.name} · {row.status} · {new Date(row.created_at).toLocaleString()}</button>)}</div></details>
    {error && <div className="mini-alert" role="alert">{error}</div>}
    {notice && <p role="status" className="pi-notice">{notice}</p>}
    <nav className="pi-tabs" aria-label="PI planner tools">{[["plan", "Operation planner"], ["recipes", "Recipes & inventory"], ["scout", "Scout planets"], ["templates", "Templates"]].map(([id, name]) => <button type="button" key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{name}</button>)}</nav>
    {tab === "plan" && <>
      <form className="pi-config" onSubmit={e => { e.preventDefault(); void action(async () => { setPlanIndex(0); setJob(await send<PlanningJob>("/jobs", request)); }); }}>
        <section className="pi-card">
          <h4>Production goal</h4>
          <div className="pi-fields">
            <label>Optimize for<select value={request.objective} onChange={e => update({objective: e.target.value as PlanningRequest["objective"]})}><option value="profit">Profit after setup amortization</option><option value="output">Maximum output</option><option value="quota">Weekly quota</option><option value="mix">Combined weekly quotas</option><option value="compare">Compare products by profit</option></select></label>
            <label>Inputs<select aria-label="Inputs" value={request.sourcing} onChange={e => update({sourcing: e.target.value as PlanningRequest["sourcing"]})}><option value="auto">Compare sourcing strategies</option><option value="extract">Extract raw materials</option><option value="buy_raw">Buy P0</option><option value="buy_p1">Buy through P1</option><option value="buy_p2">Buy through P2</option><option value="buy_p3">Buy through P3</option></select></label>
            <label>ESI market hub<select value={request.hub} onChange={e => update({hub: e.target.value as PlanningRequest["hub"]})}>{["jita", "amarr", "hek", "dodixie", "rens"].map(h => <option value={h} key={h}>{h[0].toUpperCase() + h.slice(1)}</option>)}</select></label>
            <label>Sale method<select value={request.sale_mode} onChange={e => update({sale_mode: e.target.value as PlanningRequest["sale_mode"]})}><option value="immediate">Immediate · available station bids</option><option value="patient">Patient · lowest ask estimate</option></select></label>
          </div>
          {request.sale_mode === "patient" && <p className="pi-note">Patient prices assume your orders sell at the current lowest ask. Fill time and relisting costs are unknown.</p>}
          {request.products.map((p, i) => <div className="pi-inline" key={`${i}-${p.type_id}`}><CommoditySelect catalog={catalog} value={p.type_id} filter={id => !!catalog[id].recipe} label={`Product ${i + 1}`} onChange={id => update({products: request.products.map((t, j) => i === j ? {...t, type_id: id} : t)})} /><PiNumberField label={request.objective === "quota" || request.objective === "mix" ? "Units / week" : "Quantity to include in search"} value={p.quantity} min={1} max={1e9} onChange={q => update({products: request.products.map((t, j) => i === j ? {...t, quantity: q} : t)})} /><button type="button" aria-label={`Remove product ${i + 1}`} disabled={request.products.length === 1} onClick={() => update({products: request.products.filter((_, j) => i !== j)})}>Remove</button></div>)}
          <div className="button-row compact"><button type="button" disabled={request.products.length >= (request.objective === "mix" ? 8 : 83)} onClick={() => {const next = Object.values(catalog).find(c => c.recipe && !request.products.some(p => p.type_id === c.type_id)); if (next) update({products: [...request.products, {type_id: next.type_id, quantity: 1000}]});}}><Plus size={15} />Add product</button><button type="button" onClick={() => update({objective: "compare", products: Object.values(catalog).filter(c => c.recipe).map(c => ({type_id: c.type_id, quantity: 1000}))})}>Compare all products</button></div>
          <details><summary>Always purchase specific intermediates</summary><div className="pi-check-grid">{chainIds.filter(id => catalog[id].tier > 0 && !request.products.some(p => p.type_id === id)).map(id => <label key={id}><input type="checkbox" checked={request.buy_type_ids.includes(id)} onChange={e => update({buy_type_ids: e.target.checked ? [...request.buy_type_ids, id] : request.buy_type_ids.filter(t => t !== id)})} />{catalog[id].name}</label>)}</div></details>
        </section>
        <details className="pi-card" open><summary>Pilots & existing colonies</summary><p className="pi-note">Existing colonies reserve their slots. Selecting a replacement permits a proposal to rebuild that colony; nothing is changed in EVE.</p>
          {!context.pilots.length && <p>No visible characters. Link a character and sync PI and skills to plan an operation.</p>}
          {request.pilots.map((p, index) => { const pilot = context.pilots.find(c => c.character_id === p.character_id); if (!pilot) return <p key={p.character_id} className="mini-alert">Character {p.character_id} is no longer visible. Import a scenario with accessible pilots.</p>;
            const setPilot = (patch: Partial<typeof p>) => update({pilots: request.pilots.map((row, i) => i === index ? {...row, ...patch} : row)});
            return <details key={p.character_id} className="pi-pilot"><summary>{pilot.name} · CCU {pilot.ccu ?? "unknown"} · IC {pilot.ic ?? "unknown"} · {pilot.colonies.length} occupied</summary><div className="pi-fields"><label className="pi-check"><input type="checkbox" checked={p.enabled} onChange={e => setPilot({enabled: e.target.checked})} />Include pilot</label>{(["planned_ccu", "planned_ic"] as const).map(key => <label key={key}>{key === "planned_ccu" ? "Command Center Upgrades" : "Interplanetary Consolidation"}<select value={p[key] ?? "actual"} onChange={e => setPilot({[key]: e.target.value === "actual" ? null : Number(e.target.value)})}><option value="actual">Use synchronized active skill</option>{[0,1,2,3,4,5].map(v => <option key={v} value={v}>Planned level {v}</option>)}</select></label>)}</div><small>Skills synced: {pilot.skills_synced_at ? new Date(pilot.skills_synced_at).toLocaleString() : "not yet"}. Planned levels describe a future operation.</small>
              <h5>Allow replacement</h5><div className="pi-check-grid">{pilot.colonies.map(c => <label key={c.id}><input type="checkbox" checked={p.release_colony_ids.includes(c.id)} onChange={e => setPilot({release_colony_ids: e.target.checked ? [...p.release_colony_ids, c.id] : p.release_colony_ids.filter(id => id !== c.id)})} />{c.planet_name}</label>)}</div>
              <h5>Eligible planets</h5><div className="pi-check-grid">{request.planets.map(planet => <label key={planet.key}><input type="checkbox" checked={p.planet_keys.includes(planet.key)} onChange={e => setPilot({planet_keys: e.target.checked ? [...p.planet_keys, planet.key] : p.planet_keys.filter(k => k !== planet.key)})} />{planet.name}</label>)}</div>
            </details>;
          })}
        </details>
        <details className="pi-card"><summary>Candidate planets & extraction estimates ({request.planets.length})</summary><p className="pi-note">Add real planets from Scout planets, or model a hypothetical colony. Observed program yields are averages for that installed program; recheck them when changing duration.</p>
          <div className="button-row compact">{planetKinds.map(kind => <button type="button" key={kind} disabled={request.planets.length >= 60} onClick={() => setRequest(addPlanets(request, [hypotheticalPlanet(kind, crypto.randomUUID())]))}>+ {kind}</button>)}</div>
          {request.planets.map((planet, index) => { const setPlanet = (patch: Partial<typeof planet>) => update({planets: request.planets.map((row, i) => i === index ? {...row, ...patch} : row)}); const resources = Object.values(catalog).filter(c => c.planet_types.includes(planet.planet_type)); return <details className="pi-planet" key={planet.key}><summary>{planet.name} · {planet.planet_type} · {planet.planet_id ? `ID ${planet.planet_id}` : "hypothetical"}</summary><div className="pi-fields"><label>Planet name<input value={planet.name} maxLength={120} onChange={e => setPlanet({name: e.target.value})} /></label><PiNumberField label="Diameter (km)" value={planet.diameter_km} min={100} max={500000} onChange={v => setPlanet({diameter_km: v})} /><PiNumberField label="Security" value={planet.security} min={-1} max={1} onChange={v => setPlanet({security: v})} /><PiNumberField label="POCO owner tax (%)" value={planet.customs_percent} max={100} onChange={v => setPlanet({customs_percent: v})} /><PiNumberField label="NPC tax before CCE (%)" value={planet.npc_tax_percent} max={100} onChange={v => setPlanet({npc_tax_percent: v})} /></div>
            <h5>Average extraction per head for the chosen program</h5>{planet.yields.map((y, i) => <div className="pi-inline" key={i}><CommoditySelect catalog={catalog} value={y.type_id} filter={id => resources.some(r => r.type_id === id)} onChange={id => setPlanet({yields: planet.yields.map((r, j) => j === i ? {...r, type_id: id, source: "estimate"} : r)})} /><PiNumberField label="Raw units / head / hour" value={y.units_per_head_hour} min={.01} max={1e7} onChange={v => setPlanet({yields: planet.yields.map((r, j) => j === i ? {...r, units_per_head_hour: v, source: "estimate"} : r)})} /><label>Evidence<select value={y.source} onChange={e => setPlanet({yields: planet.yields.map((r, j) => j === i ? {...r, source: e.target.value as typeof y.source} : r)})}><option value="estimate">Estimate</option><option value="scan">Manual scan</option><option value="installed_program">Installed program</option></select></label><button type="button" onClick={() => setPlanet({yields: planet.yields.filter((_, j) => j !== i)})}>Remove yield</button></div>)}
            <div className="button-row compact"><button type="button" disabled={!resources.some(r => !planet.yields.some(y => y.type_id === r.type_id))} onClick={() => { const next = resources.find(r => !planet.yields.some(y => y.type_id === r.type_id)); if (next) setPlanet({yields: [...planet.yields, {type_id: next.type_id, units_per_head_hour: 1000, source: "estimate"}]}); }}>Add resource estimate</button><button type="button" onClick={() => setRequest(removePlanet(request, planet.key))}>Remove candidate</button></div>
          </details>; })}
        </details>
        <details className="pi-card"><summary>Schedule, hauling & costs</summary><div className="pi-fields">
          {([["visits_per_week", "Visits per week", 1, 168], ["minutes_per_visit", "Minutes per visit", 1, 1440], ["program_hours", "Extractor program (hours)", 1, 336], ["restart_minutes", "Restart delay (minutes)", 0, 1440], ["haul_capacity_m3", "Haul capacity per trip (m³)", 1, 1e9], ["max_trips_per_visit", "Maximum trips per visit", 1, 1000], ["link_length_km", "Assumed link length (km)", 1, 10000]] as [keyof Schedule, string, number, number][]).map(([key, label, min, max]) => <PiNumberField key={key} label={label} min={min} max={max} value={request.schedule[key]} onChange={v => update({schedule: {...request.schedule, [key]: v}})} />)}
          {([["sales_tax_percent", "Sales tax (%)", 100], ["broker_fee_percent", "Patient-sale broker fee (%)", 100], ["freight_isk_m3", "Freight ISK / m³", 1e12], ["weekly_overhead", "Fixed overhead ISK / week", 1e12], ["per_colony_weekly", "Overhead ISK / colony / week", 1e12], ["setup_budget", "Setup budget ISK", 1e12], ["additional_setup_per_colony", "Extra setup ISK / colony", 1e12], ["setup_amortization_weeks", "Amortize setup over weeks", 520]] as [keyof Costs, string, number][]).map(([key, label, max]) => <PiNumberField key={key} label={label} min={key === "setup_amortization_weeks" ? .1 : 0} max={max} value={request.costs[key]} onChange={v => update({costs: {...request.costs, [key]: v}})} />)}
          <PiNumberField label="Search time budget (seconds)" value={request.search_seconds} min={1} max={30} onChange={v => update({search_seconds: v})} />
        </div><p className="pi-note">Customs uses SDE taxable values, with half-rate imports and each planet's tax settings. Market tax is the effective rate you enter; prices come from ESI.</p></details>
        <div className="pi-run"><button className="primary" type="submit" disabled={busy || !!running || !request.products.length}><Play size={16} />Fetch ESI prices & calculate</button>{running && <button type="button" onClick={() => void action(async () => {await send(`/jobs/${job!.id}/cancel`, {}); setNotice("Cancellation requested.");})}><Square size={15} />Cancel</button>}<small>Proposals only. Nothing is bought, installed or changed in EVE.</small></div>
      </form>
      {job && <div className="pi-job" role="status"><strong>{job.progress.stage}</strong><progress max={1} value={job.progress.fraction} />{job.progress.evaluated != null && <small>{job.progress.evaluated} plans evaluated</small>}</div>}
      {result && <>
        {stale && <p className="pi-notice">These results use the last submitted scenario. Run again to apply your edits.</p>}
        <PiPlanResults result={result} catalog={catalog} selected={planIndex} onSelect={setPlanIndex} onTemplate={i => void action(async () => {setTemplate(await send<TemplateResult>("/templates/generate", {job_id: job!.id, plan_index: planIndex, colony_index: i})); setTab("templates");})} />
        <div className="button-row compact"><button type="button" disabled={!plan || plan.idle} onClick={() => plan && downloadPi("eqm-pi-build-sheet.csv", buildSheet(plan, catalog), "text/csv;charset=utf-8")}><Download size={15} />Build & shopping CSV</button><button type="button" onClick={() => void action(async () => downloadPi("eqm-pi-snapshot.json", await api(`${plannerPath}/jobs/${job!.id}/snapshot`)))}>Export reproducible snapshot</button><button type="button" disabled={!!running || busy} onClick={() => void action(async () => {setPlanIndex(0); setJob(await send<PlanningJob>(`/jobs/${job!.id}/replay`, {}));})}>Replay saved prices</button></div>
      </>}
    </>}
    {tab === "recipes" && <PiRecipeTools api={api} context={context} targets={request.products} buyTypeIds={request.buy_type_ids} />}
    {tab === "scout" && <PiScout api={api} catalog={catalog} rawIds={chainIds.filter(id => catalog[id].tier === 0)} onAdd={planets => {setRequest(addPlanets(request, planets)); setNotice("Scouted planets added to the scenario. Set taxes and extraction estimates before calculating.");}} />}
    {tab === "templates" && <PiTemplateTools api={api} value={template} onChange={setTemplate} catalog={catalog} />}
  </div>;
}
