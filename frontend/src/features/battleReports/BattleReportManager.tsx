import {useEffect, useState} from "react";
import type {BattleReportContext, BattleReportShare} from "../../types/battleReports";
import {ReportDownload} from "../localScan/ReportDownload";
import {PublicBattleReportPage} from "./PublicBattleReportPage";
import {BattleReportSearch,emptyBattleSearch,type BattleSearch} from "./BattleReportSearch";
import "./battleReportManager.css";

type ApiClient = <T>(path:string, options?:RequestInit)=>Promise<T>;
type DeleteSelection = Partial<BattleSearch>&{ids?:number[];from_at?:string;to_at?:string;all_in_scope?:boolean;scope:"own"|"managed";corporation_id?:number;created_before?:string};
type Preview = {count:number;selection:DeleteSelection};
const pageSize=25;
const when=(value?:string|null)=>value?new Date(value).toLocaleString():"Permanent";

export function BattleReportManager({api,context,revision}:{api:ApiClient;context:BattleReportContext;revision:number}) {
  const [draft,setDraft]=useState<BattleSearch>({...emptyBattleSearch});
  const [search,setSearch]=useState<BattleSearch>({...emptyBattleSearch});
  const [scope,setScope]=useState<"own"|"managed">("own");
  const [corporation,setCorporation]=useState("");
  const [from,setFrom]=useState("");
  const [to,setTo]=useState("");
  const [offset,setOffset]=useState(0);
  const [reload,setReload]=useState(0);
  const [data,setData]=useState<{reports:BattleReportShare[];total:number}>({reports:[],total:0});
  const [selected,setSelected]=useState<number[]>([]);
  const [preview,setPreview]=useState<Preview|null>(null);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [opened,setOpened]=useState<number|null>(null);
  const pendingDetails=JSON.stringify(draft)!==JSON.stringify(search);
  const dateError=Boolean(from||to)&&(!from||!to||new Date(from)>=new Date(to));

  useEffect(()=>{setOffset(0);setSelected([]);setPreview(null);},[scope,corporation,from,to,revision,search]);
  useEffect(()=>{
    let active=true;
    setSelected([]);setPreview(null);setError("");setLoading(true);
    if(dateError){setData({reports:[],total:0});setLoading(false);return;}
    const params=new URLSearchParams({scope,offset:String(offset),limit:String(pageSize)});
    const controller=new AbortController();
    for(const [key,value] of Object.entries(search)){if(value!==undefined&&value!=="")params.set(key,String(value));}
    if(corporation)params.set("corporation_id",corporation);
    if(from&&to){params.set("from_at",new Date(from).toISOString());params.set("to_at",new Date(to).toISOString());}
    void api<typeof data>(`/battle-reports/reports?${params}`,{signal:controller.signal}).then(next=>{if(active){setData(next);if(offset&&offset>=next.total)setOffset(Math.max(0,Math.floor((next.total-1)/pageSize)*pageSize));}})
      .catch(e=>{if(active){setData({reports:[],total:0});setError(e instanceof Error?e.message:"Could not load saved reports");}})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;controller.abort();};
  },[scope,corporation,from,to,offset,revision,reload,api,dateError,search]);

  useEffect(()=>{setPreview(null);setSelected([]);},[draft]);

  async function review(mode:"selected"|"range"|"all",ids=selected){
    if(pendingDetails){setError("Apply or clear your pending battle details before reviewing deletion.");return;}
    setBusy(true);setError("");setNotice("");setPreview(null);
    const choice:DeleteSelection={...search,scope,...(corporation?{corporation_id:Number(corporation)}:{})};
    if(mode==="selected")choice.ids=ids;
    else if(mode==="range"){choice.from_at=new Date(from).toISOString();choice.to_at=new Date(to).toISOString();}
    else choice.all_in_scope=true;
    try{setPreview(await api<Preview>("/battle-reports/reports/delete-preview",{method:"POST",body:JSON.stringify(choice)}));}
    catch(e){setError(e instanceof Error?e.message:"Could not review deletion");}
    finally{setBusy(false);}
  }
  async function remove(){
    if(!preview)return;
    setBusy(true);setError("");
    try{const result=await api<{deleted:number}>("/battle-reports/reports/delete",{method:"POST",body:JSON.stringify(preview.selection)});
      setNotice(`${result.deleted} saved report${result.deleted===1?"":"s"} deleted. Their links and exports are unavailable.`);
      setPreview(null);setSelected([]);setReload(n=>n+1);
    }catch(e){setError(e instanceof Error?e.message:"Could not delete reports");setPreview(null);}
    finally{setBusy(false);}
  }
  function toggle(id:number){setPreview(null);setSelected(ids=>ids.includes(id)?ids.filter(x=>x!==id):[...ids,id]);}

  if(opened!==null)return <section className="battle-saved-view"><PublicBattleReportPage api={api} shareToken="" savedId={opened} onBack={()=>setOpened(null)}/></section>;
  return <section className="panel battle-report-manager" aria-label="Saved Battle Report management">
    <div><h3>Saved Battle Reports</h3><p>Manage {context.management_scope??"your reports"}. Private reports remain creator-only.</p></div>
    <fieldset disabled={busy} className="battle-management-filters">
      <label>Report scope<select value={scope} onChange={e=>setScope(e.target.value as typeof scope)}><option value="own">My reports</option>{context.can_manage_others&&<option value="managed">All reports I can manage</option>}</select></label>
      <label>Attributed corporation<select value={corporation} onChange={e=>setCorporation(e.target.value)}><option value="">All corporations / unattributed</option>{context.corporations?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Generated from (local time)<input type="datetime-local" value={from} onChange={e=>setFrom(e.target.value)}/></label>
      <label>Generated before (local time)<input type="datetime-local" value={to} onChange={e=>setTo(e.target.value)}/></label>
      <button type="button" onClick={()=>{setFrom("");setTo("");setCorporation("");setDraft({...emptyBattleSearch});setSearch({...emptyBattleSearch});setReload(n=>n+1);}}>Clear filters / refresh</button>
    </fieldset>
    <BattleReportSearch api={api} value={draft} setValue={setDraft} disabled={busy} onSearch={()=>{setSearch({...draft});setOffset(0);}} onClear={()=>{setDraft({...emptyBattleSearch});setSearch({...emptyBattleSearch});setOffset(0);}}/>
    {pendingDetails&&<p role="status">Battle details changed. Click Search saved reports to apply them.</p>}
    {dateError&&<p role="alert">Choose both dates, with the start before the end. The end is exclusive.</p>}
    {error&&<p role="alert" className="alert">{error}</p>}
    {notice&&<p role="status">{notice}</p>}
    <p aria-live="polite">{loading?"Loading saved reports…":`${data.total} active saved reports match. Expired and revoked reports are excluded.`}</p>
    <div className="battle-management-table"><table><thead><tr>
      <th><input type="checkbox" aria-label="Select reports on this page" disabled={busy||loading||pendingDetails||!data.reports.length} checked={data.reports.length>0&&data.reports.every(r=>selected.includes(r.id))} onChange={e=>{setSelected(e.target.checked?data.reports.map(r=>r.id):[]);setPreview(null);}}/></th>
      <th>Battle / creator</th><th>Access</th><th>Generated / expires</th><th>Actions</th>
    </tr></thead><tbody>{data.reports.map(row=><tr key={row.id}>
      <td><input type="checkbox" aria-label={`Select report ${row.id}`} disabled={busy||loading||pendingDetails} checked={selected.includes(row.id)} onChange={()=>toggle(row.id)}/></td>
      <td><strong>{row.selected_character_name}</strong><small>By {row.creator_name} · #{row.id}</small>{row.battle_summary&&<div className="battle-result-summary"><strong>{row.battle_summary.systems.join(", ")||"System unresolved"}</strong><small>Battle (local): {row.battle_summary.battle_start?when(row.battle_summary.battle_start):"Unavailable"}</small><small>My Side: {row.battle_summary.my_pilots} · Hostile Side: {row.battle_summary.hostile_pilots} recorded pilots</small><small>{row.battle_summary.side==="my"?"My Side":"Hostile Side"} hulls: {row.battle_summary.side_hulls.join(", ")||"No resolved hulls"}{row.battle_summary.side_hull_types>8?` +${row.battle_summary.side_hull_types-8} more`:""}</small></div>}</td>
      <td>{row.is_private?"Private":"Public"}<small>{row.is_owner?"Yours":"Within management scope"}</small></td>
      <td>{when(row.created_at)}<small>Expires: {when(row.expires_at)}</small></td>
      <td><div className="battle-management-actions"><button type="button" disabled={busy} onClick={()=>setOpened(row.id)}>Open</button><ReportDownload path={`/battle-reports/shares/${row.id}/pdf`} filename="eqm-battle-report.pdf"/>
        {row.share_url&&<button type="button" onClick={()=>void navigator.clipboard.writeText(row.share_url!).then(()=>setNotice("Public link copied.")).catch(()=>setError("Clipboard unavailable."))}>Copy link</button>}
        <button type="button" disabled={busy||loading||pendingDetails} onClick={()=>void review("selected",[row.id])}>Delete</button></div></td>
    </tr>)}</tbody></table></div>
    <div className="battle-management-actions">
      <button type="button" disabled={busy||loading||pendingDetails||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-pageSize))}>Previous page</button>
      <span>{data.total?`${offset+1}–${Math.min(offset+pageSize,data.total)} of ${data.total}`:"No saved reports"}</span>
      <button type="button" disabled={busy||loading||pendingDetails||offset+pageSize>=data.total} onClick={()=>setOffset(n=>n+pageSize)}>Next page</button>
    </div>
    <div className="battle-management-actions">
      <button type="button" disabled={busy||loading||pendingDetails||!selected.length} onClick={()=>void review("selected")}>Review deletion of {selected.length} selected</button>
      <button type="button" disabled={busy||loading||pendingDetails||!from||!to||dateError||!data.total} onClick={()=>void review("range")}>Review deletion for date range</button>
      <button type="button" disabled={busy||loading||pendingDetails||dateError||Boolean(from||to)||!data.total} onClick={()=>void review("all")}>Review deletion of all in scope</button>
    </div>
    {preview&&<div className="battle-delete-review" role="region" aria-label="Review report deletion"><strong>Delete {preview.count} saved report{preview.count===1?"":"s"}?</strong>
      <p>{preview.selection.ids?.length?"Only the selected reports":"All matching reports across every page"} within your current permissions and all applied search filters. Public links and PDF exports will stop working. This cannot be undone. Reports created after this review are excluded.</p>
      <div className="battle-management-actions"><button type="button" className="danger-action" disabled={busy||!preview.count} onClick={()=>void remove()}>{busy?"Deleting…":"Confirm deletion"}</button><button type="button" disabled={busy} onClick={()=>setPreview(null)}>Cancel</button></div>
    </div>}
  </section>;
}
