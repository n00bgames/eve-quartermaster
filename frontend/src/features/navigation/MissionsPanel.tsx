import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import type { Agent, AtlasSystem, Corporation, Loyalty, Offer } from "./atlasTypes";
import { lpCovered } from "./atlasTypes";

type Pilot = { token_id:number; character_id:number; name:string; has_lp_scope:boolean; sync_opt_out:boolean };
type StoreStation = { station_id:number; name:string; system_id:number; system_name:string; jumps:number|null };
type AgentResult = { agents:Agent[]; total:number; directory_count:number };
const n=(value:number)=>value.toLocaleString(undefined,{maximumFractionDigits:2});

export function MissionsPanel({origin,onMap,onRoute,corporationId,onCorporation}: {
  origin:AtlasSystem|null; onMap:(id:number)=>void; onRoute:(name:string)=>void;
  corporationId:number|null; onCorporation:(id:number|null)=>void;
}) {
  const [query,setQuery]=useState("");const [level,setLevel]=useState("");const [division,setDivision]=useState("");
  const [highsec,setHighsec]=useState(false);const [radius,setRadius]=useState("");const [offset,setOffset]=useState(0);
  const [agents,setAgents]=useState<AgentResult|null>(null);const [agentError,setAgentError]=useState("");
  const [corporations,setCorporations]=useState<Corporation[]>([]);const [pilots,setPilots]=useState<Pilot[]>([]);
  const [directoryError,setDirectoryError]=useState("");
  const [pilot,setPilot]=useState("");const [loyalty,setLoyalty]=useState<Loyalty|null>(null);
  const [lpError,setLpError]=useState("");const [lpLoading,setLpLoading]=useState(false);const [refresh,setRefresh]=useState(0);
  const [offers,setOffers]=useState<Offer[]|null>(null);const [offerError,setOfferError]=useState("");
  const [offerStamp,setOfferStamp]=useState("");const [offerQuery,setOfferQuery]=useState("");const [coveredOnly,setCoveredOnly]=useState(false);
  const [stations,setStations]=useState<StoreStation[]>([]);const [stationError,setStationError]=useState("");
  const [missionQuery,setMissionQuery]=useState("");
  useEffect(()=>{let cancelled=false;setDirectoryError("");
    void Promise.all([api<Corporation[]>("/navigation/atlas/corporations"),api<Pilot[]>("/navigation/atlas/characters")])
      .then(([corps,chars])=>{if(!cancelled){setCorporations(corps);setPilots(chars);}})
      .catch(e=>{if(!cancelled)setDirectoryError(String(e));});return()=>{cancelled=true;};
  },[refresh]);
  useEffect(()=>{setOffset(0);},[query,level,division,highsec,radius,corporationId,origin?.system_id]);
  useEffect(()=>{let cancelled=false;setAgents(null);setAgentError("");
    const timer=setTimeout(()=>{const params=new URLSearchParams({q:query,offset:String(offset),limit:"50",highsec_only:String(highsec)});
      if(level)params.set("level",level);if(division)params.set("division_id",division);
      if(corporationId)params.set("corporation_id",String(corporationId));
      if(origin){params.set("origin_id",String(origin.system_id));if(radius)params.set("max_jumps",radius);}
      void api<AgentResult>(`/navigation/atlas/agents?${params}`).then(data=>{if(!cancelled)setAgents(data);}).catch(e=>{if(!cancelled)setAgentError(String(e));});
    },250);return()=>{cancelled=true;clearTimeout(timer);};
  },[query,level,division,highsec,radius,corporationId,origin?.system_id,offset]);
  useEffect(()=>{let cancelled=false;setLoyalty(null);setLpError("");setLpLoading(false);if(!pilot)return;
    setLpLoading(true);void api<Loyalty>(`/navigation/atlas/characters/${pilot}/loyalty`)
      .then(data=>{if(!cancelled)setLoyalty(data);}).catch(e=>{if(!cancelled)setLpError(String(e));})
      .finally(()=>{if(!cancelled)setLpLoading(false);});return()=>{cancelled=true;};
  },[pilot,refresh]);
  useEffect(()=>{let cancelled=false;setOffers(null);setOfferError("");setOfferStamp("");if(!corporationId)return;
    void api<{data:Offer[];observed_at:string;stale:boolean;error:string|null}>(`/navigation/atlas/stores/${corporationId}/offers`)
      .then(data=>{if(!cancelled){setOffers(data.data);setOfferStamp(`${data.stale?"Stale snapshot":"ESI snapshot"} · ${data.observed_at?new Date(data.observed_at).toLocaleString():"timestamp unavailable"}`);if(data.error)setOfferError(data.error);}})
      .catch(e=>{if(!cancelled)setOfferError(String(e));});return()=>{cancelled=true;};
  },[corporationId,refresh]);
  useEffect(()=>{let cancelled=false;setStations([]);setStationError("");if(!corporationId)return;
    void api<StoreStation[]>(`/navigation/atlas/stores/${corporationId}/stations${origin?`?origin_id=${origin.system_id}`:""}`)
      .then(data=>{if(!cancelled)setStations(data);}).catch(e=>{if(!cancelled)setStationError(String(e));});return()=>{cancelled=true;};
  },[corporationId,origin?.system_id]);
  const balance=loyalty&&corporationId?(loyalty.balances.find(b=>b.corporation_id===corporationId)?.loyalty_points??0):null;
  useEffect(()=>{if(balance===null)setCoveredOnly(false);},[balance]);
  const filtered=useMemo(()=>offers?.filter(o=>(!coveredOnly||lpCovered(o,balance)===true)
    &&`${o.name} ${o.type_id} ${o.required_items.map(i=>i.name).join(" ")}`.toLowerCase().includes(offerQuery.toLowerCase()))??[],[offers,coveredOnly,balance,offerQuery]);
  const corps=useMemo(()=>{const all=new Map(corporations.map(c=>[c.corporation_id,c]));
    loyalty?.balances.forEach(b=>all.set(b.corporation_id,{corporation_id:b.corporation_id,name:b.corporation_name}));
    return [...all.values()].sort((a,b)=>a.name.localeCompare(b.name));},[corporations,loyalty]);
  return <div className="atlas-missions">
    <section className="atlas-widget"><h3>Agents & mission references</h3>
      <p className="muted">{origin?`Distances from ${origin.name} · shortest stargate paths`:"Choose an origin above to compare travel distances."} · Agent access still depends on in-game standings.</p>
      <div className="atlas-fields"><label>Agent, corporation or system<input value={query} onChange={e=>setQuery(e.target.value)}/></label>
        <label>Level<select value={level} onChange={e=>setLevel(e.target.value)}><option value="">All levels</option>{[1,2,3,4,5].map(l=><option key={l}>{l}</option>)}</select></label>
        <label>Division<select value={division} onChange={e=>setDivision(e.target.value)}><option value="">All divisions</option><option value="24">Security</option><option value="22">Distribution</option><option value="23">Mining</option><option value="18">Research</option></select></label>
        <label>Within jumps<input type="number" min="0" max="100" disabled={!origin} value={radius} onChange={e=>setRadius(e.target.value)}/></label>
        <label className="atlas-check"><input type="checkbox" checked={highsec} onChange={e=>setHighsec(e.target.checked)}/> Highsec agents only</label></div>
      <p className="muted">Highsec filters the agent’s location, not the path or mission destination.</p>
      {agentError&&<p role="alert" className="mini-alert">{agentError}</p>}
      {!agents&&!agentError&&<p role="status">Searching agents…</p>}
      {agents?.directory_count===0&&<p className="notice">No agent directory imported yet. An administrator can import the Agents section from the installed SDE.</p>}
      {agents&&agents.directory_count>0&&agents.total===0&&<p>No agents match these filters.</p>}
      <div className="atlas-agent-list">{agents?.agents.map(a=><article key={a.agent_id}>
        <div><strong>{a.name}</strong><span>Level {a.level} · {a.division}{a.is_locator?" · Locator":""}{a.agent_type_id!==2?` · Special agent (${a.agent_type_id})`:""}</span>
          <span>{a.corporation_name} · {a.system_name??"Location unavailable"} · {a.station_name??"In-space / unresolved location"}</span>
          <span>{a.security_status!=null?`Security ${a.security_status.toFixed(2)} · `:""}{origin?(a.jumps==null?"No known gate path":`${a.jumps} jumps`):""}</span></div>
        <div className="atlas-actions"><button disabled={!a.system_id} onClick={()=>onMap(a.system_id!)}>Show on map</button>
          <button disabled={!origin||!a.system_name||a.jumps==null} onClick={()=>onRoute(a.system_name!)}>Plan route</button>
          <button onClick={()=>onCorporation(a.corporation_id)}>LP store</button></div></article>)}</div>
      {agents&&agents.total>0&&<div className="atlas-actions"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous</button>
        <span>{offset+1}–{Math.min(offset+50,agents.total)} of {n(agents.total)}</span><button disabled={offset+50>=agents.total} onClick={()=>setOffset(offset+50)}>Next</button></div>}
      <div className="atlas-reference"><label>Mission name<input value={missionQuery} onChange={e=>setMissionQuery(e.target.value)} placeholder="e.g. The Blockade"/></label>
        <a href={`https://wiki.eveuniversity.org/index.php?title=Special:Search&search=${encodeURIComponent(missionQuery||"Missions")}`} target="_blank" rel="noreferrer">Search EVE University ↗</a>
        <a href="https://eve-survival.org/wikka.php?wakka=MissionReports" target="_blank" rel="noreferrer">EVE-Survival mission reports ↗</a>
        <p className="muted">Reference links; active mission journals and mission offers are not supplied here by ESI.</p></div>
    </section>
    <section className="atlas-widget"><h3>Loyalty points & rewards</h3>{directoryError&&<p role="alert">{directoryError}</p>}
      <div className="atlas-fields"><label>Linked pilot<select value={pilot} onChange={e=>setPilot(e.target.value)}><option value="">Browse public rewards</option>{pilots.map(p=><option key={p.token_id} value={p.token_id} disabled={!p.has_lp_scope||p.sync_opt_out}>{p.name}{!p.has_lp_scope?" — re-link for LP scope":p.sync_opt_out?" — sync disabled":""}</option>)}</select></label>
        <label>NPC corporation<select value={corporationId??""} onChange={e=>onCorporation(e.target.value?Number(e.target.value):null)}><option value="">Choose a corporation</option>{corps.map(c=><option key={c.corporation_id} value={c.corporation_id}>{c.name}</option>)}</select></label>
        <button onClick={()=>setRefresh(r=>r+1)} disabled={lpLoading}>Refresh</button></div>
      {lpError&&<p role="alert" className="mini-alert">{lpError}</p>}{lpLoading&&<p role="status">Loading this pilot’s LP…</p>}
      {loyalty&&<><p className="muted">LP checked {new Date(loyalty.checked_at).toLocaleString()} · ESI-cached balance</p>
        <div className="atlas-balances">{loyalty.balances.map(b=><button key={b.corporation_id} onClick={()=>onCorporation(b.corporation_id)}>{b.corporation_name}: {n(b.loyalty_points)} LP</button>)}{!loyalty.balances.length&&<p>No LP balances returned for this pilot.</p>}</div></>}
      {corporationId&&<><p className="atlas-lp-total">{balance===null?"LP balance unknown":`${n(balance)} LP available`}</p>
        <div className="atlas-fields"><label>Search rewards or required items<input value={offerQuery} onChange={e=>setOfferQuery(e.target.value)}/></label>
          <label className="atlas-check"><input type="checkbox" checked={coveredOnly} disabled={balance===null} onChange={e=>setCoveredOnly(e.target.checked)}/> LP covered only</label></div>
        <p className="muted">LP coverage only. ISK, required items, corporation access and any Analysis Kredits must be checked separately.</p>
        {offerError&&<p role="alert" className="mini-alert">{offerError}</p>}<small>{offerStamp}</small>
        {!offers&&!offerError&&<p role="status">Loading rewards…</p>}
        {offers&&<p>{filtered.length} matching rewards</p>}
        <div className="atlas-offers">{filtered.map(o=><article key={o.offer_id}><img src={`https://images.evetech.net/types/${o.type_id}/icon?size=64`} alt="" loading="lazy"/>
          <div><strong>{n(o.quantity)} × {o.name}</strong><span>{n(o.lp_cost)} LP · {n(o.isk_cost)} ISK{o.ak_cost?` · ${n(o.ak_cost)} Analysis Kredits`:""}</span>
            {o.required_items.length>0&&<span>Requires: {o.required_items.map(i=>`${n(i.quantity)} × ${i.name}`).join(", ")}</span>}
            <span className={lpCovered(o,balance)?"atlas-covered":"muted"}>{balance===null?"Select a pilot to check LP":lpCovered(o,balance)?"LP covered":`${n(Math.max(0,o.lp_cost-balance))} more LP needed`}</span></div></article>)}</div>
        <h4>Corporation stations</h4><p className="muted">Confirm the relevant LP store service in-game. Distances use shortest gate paths.</p>
        {stationError&&<p role="alert">{stationError}</p>}
        {!stationError&&!stations.length&&<p>No NPC stations found in the imported SDE.</p>}
        <div className="atlas-stations">{stations.map(s=><article key={s.station_id}><span>{s.name} {origin?`· ${s.jumps??"No gate path"}${s.jumps!=null?" jumps":""}`:""}</span>
          <div className="atlas-actions"><button onClick={()=>onMap(s.system_id)}>Map</button><button disabled={!origin||s.jumps==null} onClick={()=>onRoute(s.system_name)}>Route</button></div></article>)}</div></>}
    </section>
  </div>;
}
