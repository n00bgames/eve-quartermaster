import {useEffect,useState} from 'react';
import {AnalyticsPane} from '../../components/AnalyticsPane';
import {api} from '../../lib/api';
import {InsightReport} from './InsightReport';
import {exportInsights,insightScope,viewUrl,type InsightOptions,type InsightReport as Report,type InsightScope,type SavedView,type ViewMeta} from './insightsModel';
import './insights.css';

type Props={query:string;defaultFleet?:boolean;onSystem?:(id:number)=>void};
export function JourneyInsights(props:Props){return <AnalyticsPane title="Hull and fleet insights" description="Full stored scope · private analysis and optional filtered snapshots" className="journey-analytics journey-insights" unmountOnClose><InsightControls {...props}/></AnalyticsPane>;}

function InsightControls({query,defaultFleet=false,onSystem}:Props){
 const [scope,setScope]=useState(()=>insightScope(query,defaultFleet)),[options,setOptions]=useState<InsightOptions|null>(null);
 const [search,setSearch]=useState(''),[data,setData]=useState<Report|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[refresh,setRefresh]=useState(0);
 const [title,setTitle]=useState('My Fleet summary'),[days,setDays]=useState(7),[saved,setSaved]=useState<SavedView|null>(null),[views,setViews]=useState<ViewMeta[]>([]),[busy,setBusy]=useState(false);
 const [combat,setCombat]=useState<{rows:{mail_id:number;side:string;time:string;pilot_id:number;hull_id:number|null;system_id:number}[];total:number}|null>(null);
 function update(changes:Partial<InsightScope>){setScope(old=>({...old,...changes,offset:changes.offset??0}));setSaved(null);setCombat(null);}
 useEffect(()=>{const dates=new URLSearchParams(query);setScope(old=>({...old,from_at:dates.get('from_at')??undefined,to_at:dates.get('to_at')??undefined,offset:0}));setSaved(null);},[query]);
 useEffect(()=>{const abort=new AbortController(),timer=window.setTimeout(()=>{
  void api<InsightOptions>(`/journey/insights/options?search=${encodeURIComponent(search)}`,{signal:abort.signal}).then(setOptions).catch(e=>{if(!abort.signal.aborted)setError(String(e.message??e));});
 },200);return()=>{clearTimeout(timer);abort.abort();};},[search]);
 const key=JSON.stringify(scope),valid=scope.cohort!=='selected'||scope.character_ids.length>0;
 useEffect(()=>{setData(null);if(!valid)return;const abort=new AbortController();setLoading(true);setError('');
  void api<Report>('/journey/insights/query',{method:'POST',body:key,signal:abort.signal}).then(value=>{if(!abort.signal.aborted)setData(value);})
   .catch(e=>{if(!abort.signal.aborted)setError(String(e.message??e));}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});return()=>abort.abort();
 },[key,valid,refresh]);
 async function loadViews(){const r=await api<{rows:ViewMeta[]}>('/journey/insights/views');setViews(r.rows);}
 useEffect(()=>{void loadViews().catch(e=>setError(String(e.message??e)));},[]);
 async function action(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 async function create(){const r=await api<SavedView>('/journey/insights/views',{method:'POST',body:JSON.stringify({title,days,scope})});setSaved(r);await loadViews();}
 async function change(view:ViewMeta,payload:object){const r=await api<ViewMeta>(`/journey/insights/views/${view.id}`,{method:'PATCH',body:JSON.stringify(payload)});setSaved(old=>old?.id===r.id?{...old,...r}:old);await loadViews();}
 const selected=scope.ship_type_id,system=scope.system_id;
 return <>
  <div className="journey-analytics-controls">
   <label>Insight pilot scope<select aria-label="Insight pilot scope" value={scope.cohort} onChange={e=>update({cohort:e.target.value as InsightScope['cohort'],character_ids:[]})}><option value="account">All my owned pilots</option><option value="fleet">Currently tracked My Fleet</option><option value="selected">Explicitly selected pilots</option></select></label>
   <label>Insight history<select value={scope.period} onChange={e=>update({period:e.target.value as 'all'|'range'})}><option value="all">All stored history</option><option value="range">Selected dates (UTC)</option></select></label>
   <label>Insight ranking<select aria-label="Insight ranking" value={scope.metric} onChange={e=>update({metric:e.target.value as InsightScope['metric']})}><option value="visits">Observed visits</option><option value="seconds">Confirmed observation span</option><option value="kills">Imported kills</option><option value="losses">Imported losses</option></select></label>
   <label>Groups per page<select value={scope.limit} onChange={e=>update({limit:Number(e.target.value)})}>{[10,25,50].map(n=><option key={n}>{n}</option>)}</select></label>
  </div>
  {scope.period==='range'&&<div className="journey-analytics-controls"><label>Insight from (UTC)<input type="date" value={scope.from_at?.slice(0,10)??''} onChange={e=>{if(e.target.value)update({from_at:e.target.value+'T00:00:00Z'});}}/></label><label>Insight through (UTC)<input type="date" value={scope.to_at?new Date(Date.parse(scope.to_at)-86400000).toISOString().slice(0,10):''} onChange={e=>{if(e.target.value)update({to_at:new Date(Date.parse(e.target.value+'T00:00:00Z')+86400000).toISOString()});}}/></label></div>}
  {scope.cohort==='selected'&&<fieldset><legend>Select owned pilots</legend><button type="button" onClick={()=>update({character_ids:options?.enabled_ids??[]})}>Use currently tracked pilots</button><div className="journey-insights-choices">{options?.pilots.map(p=><label key={p.id}><input type="checkbox" checked={scope.character_ids.includes(p.id)} onChange={e=>update({character_ids:e.target.checked?[...scope.character_ids,p.id]:scope.character_ids.filter(id=>id!==p.id)})}/>{p.name}</label>)}</div></fieldset>}
  <div className="journey-analytics-controls"><label>Search ship types<input placeholder="Hull name" value={search} onChange={e=>setSearch(e.target.value)}/></label>
   <label>Hull to analyze<select aria-label="Hull to analyze" value={selected??''} onChange={e=>update({ship_type_id:Number(e.target.value)||null})}><option value="">All hulls</option>{selected&&!options?.types.some(t=>t.type_id===selected)&&<option value={selected}>Selected hull {selected}</option>}{options?.types.map(t=><option key={t.type_id} value={t.type_id}>{t.name}</option>)}</select></label></div>
  {system&&<p>System filter: {system} <button onClick={()=>update({system_id:null})}>Clear system filter</button></p>}
  <details className="journey-insights-exclusions"><summary>Hull exclusions and public fields</summary>
   <p>Exclusions apply before every aggregate is calculated. Public snapshots always exclude unknown or unclassified hulls.</p>
   <div className="journey-insights-choices"><label><input type="checkbox" checked={scope.exclude_capitals} onChange={e=>update({exclude_capitals:e.target.checked})}/>Exclude all capital classes</label><label><input type="checkbox" checked={scope.exclude_supercapitals} onChange={e=>update({exclude_supercapitals:e.target.checked})}/>Exclude titans and supercarriers</label></div>
   <label>Exclude ship classes<select aria-label="Exclude ship classes" multiple value={scope.exclude_groups.map(String)} onChange={e=>update({exclude_groups:Array.from(e.target.selectedOptions,o=>Number(o.value))})}>{options?.groups.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></label>
   <label>Add an exact hull exclusion<select aria-label="Add hull exclusion" value="" onChange={e=>{const id=Number(e.target.value);if(id&&!scope.exclude_types.includes(id))update({exclude_types:[...scope.exclude_types,id]});}}><option value="">Choose from ship search results…</option>{options?.types.map(t=><option key={t.type_id} value={t.type_id}>{t.name}</option>)}</select></label>
   <div className="journey-insights-actions">{scope.exclude_types.map(id=><button key={id} onClick={()=>update({exclude_types:scope.exclude_types.filter(v=>v!==id)})}>Remove exclusion: {options?.types.find(t=>t.type_id===id)?.name??id}</button>)}</div>
   <label><input type="checkbox" checked={scope.show_systems} onChange={e=>update({show_systems:e.target.checked})}/>Publish system names and aggregate system rankings</label>
   <label><input type="checkbox" checked={scope.show_pilots} onChange={e=>update({show_pilots:e.target.checked})}/>Publish pilot names and aggregate pilot contributions</label>
   <p className="muted">Names are off by default. Raw journeys, exact visit times, positions, fittings and killmail links are never included in a public view.</p>
  </details>
  {error&&<p role="alert" className="mini-alert">{error}</p>}{!valid&&<p>Select at least one pilot.</p>}{loading&&<p role="status">Aggregating stored hull and fleet evidence…</p>}
  {data&&<><InsightReport report={data} onHull={id=>update({ship_type_id:id})} onSystem={id=>{update({system_id:id});onSystem?.(id);}} onPilot={id=>update({cohort:'selected',character_ids:[id]})}/>
   <div className="journey-insights-actions"><button disabled={scope.offset===0} onClick={()=>update({offset:Math.max(0,scope.offset-scope.limit)})}>Previous ranking page</button><button disabled={![data.hulls,data.systems,data.pilots].some(r=>r?.truncated)} onClick={()=>update({offset:scope.offset+scope.limit})}>Next ranking page</button><button onClick={()=>setRefresh(n=>n+1)}>Refresh private analysis</button>
    {(['csv','json'] as const).map(fmt=><button key={fmt} disabled={busy} onClick={()=>void action(()=>exportInsights(scope,fmt))}>Export all groups · {fmt.toUpperCase()}</button>)}
    {data.combat_available&&<button disabled={busy} onClick={()=>void action(async()=>setCombat(await api('/journey/insights/combat',{method:'POST',body:JSON.stringify(scope)})))}>Inspect imported combat</button>}
   </div>
   {combat&&<div><p>{combat.total} pilot/side records in scope · showing up to {scope.limit} at this page offset. Shared kills can repeat per pilot.</p><ul>{combat.rows.map((r,i)=><li key={`${r.mail_id}:${r.pilot_id}:${r.side}:${i}`}><a href={`https://zkillboard.com/kill/${r.mail_id}/`} target="_blank" rel="noreferrer">{r.side.toUpperCase()} · {r.time} · {data.cohort?.find(p=>p.id===r.pilot_id)?.name??'Selected pilot'}</a></li>)}</ul></div>}
   <fieldset><legend>Save a private view, then preview sharing</legend><p>Saving does not publish anything. Sharing requires reviewing the filtered snapshot below and explicitly publishing it. Future tracking or pilot changes do not update a snapshot.</p>
    <div className="journey-analytics-controls"><label>View title<input value={title} maxLength={120} onChange={e=>setTitle(e.target.value)}/></label><label>Expires after<select value={days} onChange={e=>setDays(Number(e.target.value))}>{[1,7,30,90].map(n=><option key={n} value={n}>{n} days</option>)}</select></label></div>
    <button disabled={busy||loading||scope.offset>0||!title.trim()} onClick={()=>void action(create)}>Save private view / preview sharing</button>{scope.offset>0&&<p>Return to the first ranking page before saving a share preview.</p>}
   </fieldset>
  </>}
  {saved&&<section className="journey-insights-preview" aria-label="Public sharing preview"><h4>{saved.title} · {saved.is_public?'Public snapshot':'Private · sharing preview'}</h4><p>This is exactly the aggregate report visitors would receive. Expires {new Date(saved.expires_at).toLocaleString()}.</p><InsightReport report={saved.report} publicView/>
   {!saved.is_public?<button disabled={busy} onClick={()=>void action(()=>change(saved,{is_public:true,preview_hash:saved.preview_hash}))}>Publish this reviewed snapshot</button>:<><a href={viewUrl(saved.share_path!)} target="_blank" rel="noreferrer">Open public view</a><button disabled={busy} onClick={()=>void action(()=>change(saved,{is_public:false}))}>Make private / revoke link</button></>}
  </section>}
  <details><summary>Saved private and public views ({views.length} most recent)</summary>{views.map(v=><div className="journey-insights-saved" key={v.id}><strong>{v.title}</strong><span>{v.is_public?'Public':'Private'} · expires {new Date(v.expires_at).toLocaleDateString()}</span><button disabled={busy} onClick={()=>void action(async()=>setSaved(await api(`/journey/insights/views/${v.id}`)))}>Review view</button>{v.is_public&&<><a href={viewUrl(v.share_path!)} target="_blank" rel="noreferrer">Public link</a><button disabled={busy} onClick={()=>void action(()=>change(v,{is_public:false}))}>Make private</button><button disabled={busy} onClick={()=>void action(()=>change(v,{rotate:true}))}>Rotate link</button></>}<button disabled={busy} onClick={()=>void action(async()=>{await api(`/journey/insights/views/${v.id}`,{method:'DELETE'});setSaved(old=>old?.id===v.id?null:old);await loadViews();})}>Delete view / revoke</button></div>)}</details>
 </>;
}
