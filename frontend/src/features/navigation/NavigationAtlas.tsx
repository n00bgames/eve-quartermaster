import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import type { NavigationRoute } from "../../types/navigation";
import { AtlasCanvas } from "./AtlasCanvas";
import { MissionsPanel } from "./MissionsPanel";
import type { Activity, AtlasCatalog, AtlasDetail, RouteRequest } from "./atlasTypes";
import { activityValue, securityColor } from "./atlasTypes";
import "./atlas.css";

export function NavigationAtlas({onRoute,route}: {onRoute:(request:RouteRequest)=>void;route:NavigationRoute|null}) {
  const [catalog,setCatalog]=useState<AtlasCatalog|null>(null);const [error,setError]=useState("");
  const [tab,setTab]=useState("map");const [region,setRegion]=useState("known");const [overlay,setOverlay]=useState("security");
  const [selected,setSelected]=useState<number|null>(null);const [query,setQuery]=useState("");
  const [originName,setOriginName]=useState("Jita");const [destinationName,setDestinationName]=useState("");
  const [detail,setDetail]=useState<AtlasDetail|null>(null);const [detailError,setDetailError]=useState("");
  const [activity,setActivity]=useState<Activity|null>(null);const [activityError,setActivityError]=useState("");
  const [activityBusy,setActivityBusy]=useState(false);const [corpId,setCorpId]=useState<number|null>(null);
  const [reload,setReload]=useState(0);
  useEffect(()=>{let cancelled=false;setError("");void api<AtlasCatalog>("/navigation/atlas/catalog")
    .then(data=>{if(!cancelled)setCatalog(data);}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[reload]);
  useEffect(()=>{let cancelled=false;setActivityBusy(true);setActivityError("");void api<Activity>("/navigation/atlas/activity")
    .then(data=>{if(!cancelled)setActivity(data);}).catch(e=>{if(!cancelled)setActivityError(String(e));})
    .finally(()=>{if(!cancelled)setActivityBusy(false);});return()=>{cancelled=true;};},[reload]);
  useEffect(()=>{let cancelled=false;setDetail(null);setDetailError("");if(!selected)return;
    void api<AtlasDetail>(`/navigation/atlas/systems/${selected}`).then(data=>{if(!cancelled)setDetail(data);})
      .catch(e=>{if(!cancelled)setDetailError(String(e));});return()=>{cancelled=true;};},[selected]);
  const systems=catalog?.systems??[];
  const origin=systems.find(s=>s.name.toLowerCase()===originName.trim().toLowerCase())??null;
  const destination=systems.find(s=>s.name.toLowerCase()===destinationName.trim().toLowerCase())??null;
  const regions=useMemo(()=>[...new Map(systems.map(s=>[s.region_id,s.region_name])).entries()]
    .filter(([id])=>id!=null).sort((a,b)=>(a[1]??"").localeCompare(b[1]??"")),[catalog]);
  const matches=query.trim()?systems.filter(s=>s.name.toLowerCase().includes(query.trim().toLowerCase())).slice(0,12):[];
  const selectedSystem=systems.find(s=>s.system_id===selected);
  const wormhole=(selectedSystem?.region_id??0)>=11000000;
  function showMap(id:number){setSelected(id);setTab("map");setQuery("");
    const s=systems.find(s=>s.system_id===id);if(region!=="all"&&!(region==="known"&&(s?.region_id??Infinity)<11000000)&&String(s?.region_id)!==region)setRegion(s?.region_id?String(s.region_id):"all");}
  function plan(name:string){if(origin){setDestinationName(name);onRoute({origin:origin.name,destination:name,requestId:Date.now()});}}
  return <section className="panel stacked navigation-atlas">
    <div className="section-heading"><div><span className="atlas-eyebrow">EXPLORE / PLAN / EARN</span><h3>New Eden Atlas</h3></div>
      <button disabled={activityBusy} onClick={()=>setReload(r=>r+1)}>Refresh data</button></div>
    <div className="atlas-tabs" role="tablist" aria-label="Navigation atlas"><button role="tab" aria-selected={tab==="map"} onClick={()=>setTab("map")}>Star Map</button>
      <button role="tab" aria-selected={tab==="missions"} onClick={()=>setTab("missions")}>Missions & LP</button></div>
    {error&&<p role="alert" className="mini-alert">{error}</p>}
    {!catalog&&!error&&<p role="status">Loading the universe…</p>}
    {catalog&&systems.length===0&&<p className="notice">The star map needs imported SDE systems and stargates. Ask an administrator to import the map data.</p>}
    {catalog&&<><div className="atlas-fields atlas-route-fields">
      <label>Route origin<input list="atlas-system-names" value={originName} onChange={e=>setOriginName(e.target.value)} placeholder="Choose a system"/></label>
      <label>Destination<input list="atlas-system-names" value={destinationName} onChange={e=>setDestinationName(e.target.value)} placeholder="Choose a star or agent"/></label>
      <datalist id="atlas-system-names">{systems.map(s=><option key={s.system_id} value={s.name}/>)}</datalist>
      <button disabled={!origin||!destination} onClick={()=>plan(destination!.name)}>Open route planner</button>
      <span className="muted">{systems.length.toLocaleString()} systems · {catalog.agent_count.toLocaleString()} agents</span></div>
      {tab==="map"?<><div className="atlas-fields"><label>Find a system<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="System name"/></label>
        <label>Region<select value={region} onChange={e=>setRegion(e.target.value)}><option value="known">Known space</option><option value="all">All regions (including disconnected space)</option>{regions.map(([id,name])=><option key={id} value={String(id)}>{name}</option>)}</select></label>
        <label>Map layer<select value={overlay} onChange={e=>setOverlay(e.target.value)}><option value="security">Security status</option><option value="ship_kills">Ship kills / last reported hour</option><option value="pod_kills">Pod kills / last reported hour</option><option value="npc_kills">NPC kills / last reported hour</option><option value="ship_jumps">Jumps / last reported hour</option><option value="stations">NPC stations</option><option value="agents">Agents</option></select></label></div>
        {!!matches.length&&<div className="atlas-search-results">{matches.map(s=><button key={s.system_id} onClick={()=>showMap(s.system_id)}>{s.name} · {s.region_name}</button>)}</div>}
        {query&&matches.length===0&&<p>No matching system in the imported SDE.</p>}
        <div className="atlas-layout"><AtlasCanvas catalog={catalog} selected={selected} onSelect={showMap} region={region} overlay={overlay} activity={activity} routeIds={route?.systems.map(s=>s.system_id)??[]}/>
          <aside className="atlas-detail">{!selected&&<><h3>Select a system</h3><p>Inspect stations, agents and recent activity, then use it as a route endpoint.</p><p className="muted">Flat X/Z projection of the SDE universe. Wormholes and disconnected space have no permanent gate route.</p></>}
            {selected&&<><h3>{selectedSystem?.name??"System"} <span style={{color:securityColor(selectedSystem?.security_status)}}>{selectedSystem?.security_status?.toFixed(2)??"?"}</span></h3>
              <p>{selectedSystem?.region_name} · {selectedSystem?.constellation_name}</p>
              <div className="atlas-actions"><button onClick={()=>setOriginName(selectedSystem!.name)}>Set origin</button><button onClick={()=>setDestinationName(selectedSystem!.name)}>Set destination</button>
                <button disabled={!origin} onClick={()=>plan(selectedSystem!.name)}>Plan route here</button></div>
              <dl className="atlas-stats">{([ ["ship_kills","Ship kills"],["pod_kills","Pod kills"],["npc_kills","NPC kills"],["ship_jumps","Jumps"] ] as const).map(([field,label])=><div key={field}><dt>{label} / reported hour</dt><dd>{activityValue(activity,selected!,field,wormhole)?.toLocaleString()??"Unknown"}</dd></div>)}</dl>
              {detailError&&<p role="alert">{detailError}</p>}{!detail&&!detailError&&<p role="status">Loading system details…</p>}
              {detail&&<><div className="atlas-actions"><a href={detail.links.dotlan} target="_blank" rel="noreferrer">DOTLAN ↗</a><a href={detail.links.zkill} target="_blank" rel="noreferrer">zKillboard ↗</a></div>
                <h4>NPC stations · {detail.stations.length}</h4><div className="atlas-detail-list">{detail.stations.map(s=><article key={s.station_id}><strong>{s.name??`Station ${s.station_id}`}</strong><span>{s.corporation_name}</span>
                  {s.corporation_id&&<button onClick={()=>{setCorpId(s.corporation_id!);setTab("missions");}}>Browse LP rewards</button>}</article>)}{!detail.stations.length&&<p>No NPC stations in the SDE.</p>}</div>
                <h4>Agents · {detail.agents.length}</h4><div className="atlas-detail-list">{detail.agents.map(a=><article key={a.agent_id}><strong>{a.name}</strong><span>Level {a.level} · {a.division} · {a.corporation_name}</span><button onClick={()=>{setCorpId(a.corporation_id);setTab("missions");}}>Agents & LP store</button></article>)}{!detail.agents.length&&<p>No imported agents in this system.</p>}</div></>}
            </>}
          </aside></div>
        <div className="atlas-freshness">{activityError&&<p role="alert">{activityError}</p>}{activityBusy&&<span>Refreshing hourly activity…</span>}
          {activity&&(["kills","jumps"] as const).map(key=><span key={key}>{key==="kills"?"Kills":"Jumps"}: {activity[key].observed_at?`hour ending ${new Date(activity[key].observed_at!).toLocaleString()}`:"unavailable"}{activity[key].stale?" · STALE":""}{activity[key].error?` · ${activity[key].error}`:""}</span>)}
          <span>ESI snapshots, not live safety guarantees. Wormhole activity is unavailable. DOTLAN and zKillboard open separately.</span></div>
      </>:<MissionsPanel origin={origin} onMap={showMap} onRoute={plan} corporationId={corpId} onCorporation={setCorpId}/>}</>}
  </section>;
}
