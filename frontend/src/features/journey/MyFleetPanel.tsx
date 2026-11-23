import {JourneyInsights} from './JourneyInsights';
import {useEffect,useMemo,useState} from 'react';
import {Pause,Play} from 'lucide-react';
import {api} from '../../lib/api';
import type {Settings,JourneyHistory} from './types';
import {mapConcurrent,mergeFleet} from './fleetModel';
import {fleetPositions} from './fleetGeometry';
import {journeySteps} from './shipTimeline';
import {JourneyMap} from './JourneyMap';
import {JourneyHull} from './JourneyHull';
import {JourneyExport} from './JourneyExport';

const stamp=(s:string)=>new Date(s).toISOString().replace('T',' ').slice(0,19)+' UTC';
export function MyFleetPanel({settings,query,refresh}:{settings:Settings|null;query:string;refresh:number}){
 const pilots=settings?.characters.filter(c=>c.enabled)??[],pilotKey=pilots.map(c=>c.character_id).sort((a,b)=>a-b).join(',');
 const [histories,setHistories]=useState<JourneyHistory[]>([]),[errors,setErrors]=useState<string[]>([]),[loading,setLoading]=useState(true);
 const [cursor,setCursor]=useState<number|null>(null),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[selected,setSelected]=useState<number|null>(null);
 const [followRequest,setFollowRequest]=useState(0);
 useEffect(()=>{
  setHistories([]);setErrors([]);setCursor(null);setPlaying(false);setSelected(null);setLoading(true);
  if(!pilotKey){setLoading(false);return;}
  let stopped=false,timer:number;const abort=new AbortController();
  async function load(){
   const results=await mapConcurrent(pilots,async pilot=>{
    try{return {history:await api<JourneyHistory>(`/journey/characters/${pilot.character_id}/history?${query}`,{signal:abort.signal}),error:''};}
    catch(e){return {history:null,error:`${pilot.name}: ${e instanceof Error?e.message:String(e)}`};}
   });
   if(stopped)return;
   setHistories(results.flatMap(r=>r.history?[r.history]:[]));setErrors(results.filter(r=>r.error).map(r=>r.error));setLoading(false);
   timer=window.setTimeout(()=>void load(),document.hidden?60000:15000);
  }
  void load();return()=>{stopped=true;abort.abort();window.clearTimeout(timer);};
 },[pilotKey,query,refresh]);
 const history=useMemo(()=>histories.length?mergeFleet(histories):null,[histories]);
 const steps=useMemo(()=>history?journeySteps(history.visits,history.ship_segments).sort((a,b)=>Date.parse(a.at)-Date.parse(b.at)||history.fleet!.owners[history.visits[a.visitIndex].id]-history.fleet!.owners[history.visits[b.visitIndex].id]||a.key.localeCompare(b.key)):[],[history]);
 const step=steps[cursor??steps.length-1],at=cursor===null?Infinity:step?Date.parse(step.at):-Infinity;
 const visible=useMemo(()=>history?{...history,visits:history.visits.filter(v=>Date.parse(v.first_seen_at)<=at)}:null,[history,at]);
 const positions=visible?fleetPositions(visible,at):[],active=history&&step?history.fleet!.pilots.find(p=>p.character_id===history.fleet!.owners[history.visits[step.visitIndex].id]):null;
 useEffect(()=>{if(cursor!==null&&cursor>=steps.length)setCursor(Math.max(0,steps.length-1));},[steps.length,cursor]);
 useEffect(()=>{if(!playing||!steps.length)return;const timer=window.setInterval(()=>setCursor(old=>{const next=(old??-1)+1;if(next>=steps.length-1){setPlaying(false);return steps.length-1;}return next;}),1000/speed);return()=>window.clearInterval(timer);},[playing,speed,steps.length]);
 return <section className="journey-fleet" aria-label="My Fleet"><h4>My Fleet · {pilots.length} tracked pilots</h4>
  <p className="muted">Private recorded positions for your enabled Journey pilots. Replay switches focus to the next pilot’s observation in UTC timestamp order. Positions are last observed, not a live tactical feed; gaps and sampling delays still apply.</p>
  <JourneyInsights query={query} defaultFleet onSystem={setSelected}/>
  {loading&&<p role="status">Loading fleet histories…</p>}{!pilots.length&&<p>Enable Journey tracking for your linked pilots above to populate My Fleet. No pilot is enrolled automatically.</p>}
  {errors.map(error=><p className="mini-alert" role="alert" key={error}>{error}</p>)}
  {history&&<>
   <div className="journey-metrics"><div><strong>{histories.length} / {pilots.length}</strong><span>Pilot histories available</span></div><div><strong>{history.visits.length.toLocaleString()}</strong><span>Loaded fleet visits</span></div><div><strong>{history.systems.length}</strong><span>Mapped / recorded systems</span></div><div><strong>{steps.length.toLocaleString()}</strong><span>Observation / hull steps</span></div></div>
   {history.truncated&&<p className="mini-alert" role="alert">The fleet replay shows at most 2,000 loaded visits and may omit later history. Narrow the dates or use segmented export, which reads every pilot’s complete paged history.</p>}
   {history.ship_segments_truncated&&<p className="mini-alert">Some loaded hull history is incomplete. Missing hull observations stay unknown.</p>}
   <div className="journey-replay"><button disabled={!steps.length} onClick={()=>{if(!playing){if(cursor===null||cursor>=steps.length-1)setCursor(0);setFollowRequest(n=>n+1);}setPlaying(v=>!v);}}>{playing?<Pause size={15}/>:<Play size={15}/>} {playing?'Pause fleet replay':'Replay fleet'}</button><button onClick={()=>{setPlaying(false);setCursor(null);}}>Latest / live fleet view</button><label>Replay speed<select aria-label="Fleet replay speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}>{[.5,1,2,4].map(n=><option key={n} value={n}>{n} steps / second</option>)}</select></label><span>{cursor===null?'Latest recorded fleet positions':`Fleet step ${cursor+1} / ${steps.length}`} · {step?stamp(cursor===null?step.last_at:step.at):'No observations'}</span></div>
   <label className="journey-scrubber">Fleet timeline<input aria-label="Fleet timeline" type="range" min={0} max={Math.max(0,steps.length-1)} disabled={!steps.length} value={cursor??Math.max(0,steps.length-1)} onChange={e=>{setPlaying(false);setCursor(Number(e.target.value));}}/></label>
   <div className="journey-current-hull"><span>Camera focus: {active?.name??'No pilot observed'}</span><JourneyHull typeId={step?.ship?.ship_type_id} name={step?.ship?.ship_name}/><small>{history.systems.find(s=>s.system_id===step?.system_id)?.name??'No recorded system'}</small></div>
   {visible&&<JourneyMap key={'map:'+pilotKey+query} systems={history.systems} visits={visible.visits} selected={selected} onSelect={setSelected} context={null} fleet={{history:visible,positions,focusSystem:step?.system_id,activePilot:active?.character_id,followRequest}}/>}
   <div className="journey-fleet-roster">{history.fleet!.pilots.map(p=>{const position=positions.find(v=>v.pilot_id===p.character_id),system=history.systems.find(s=>s.system_id===position?.visit.system_id);return <div key={p.character_id} data-fleet-pilot={p.character_id}><span className="journey-fleet-dot" style={{background:p.color}}/><strong>{p.name}</strong><span>{system?.name??(position?`System ${position.visit.system_id}`:'Not yet observed')}</span><small>{position?`Last confirmed ${stamp(Date.parse(position.visit.last_seen_at)<=at?position.visit.last_seen_at:position.visit.first_seen_at)}`:'No position at this replay point'}</small><JourneyHull typeId={position?.ship?.ship_type_id} name={position?.ship?.ship_name}/></div>;})}</div>
   <JourneyExport key={'export:'+pilotKey+query} history={history} query={query} fleet={pilots} fleetHistories={histories} incomplete={errors.length>0}/>
   <p className="muted">Different colors identify pilots; paths only connect observations from the same pilot. Co-located markers are offset for readability, not separate in-system coordinates. Missing SDE coordinates remain in the roster. Paused pilots are excluded from My Fleet; their individual history remains available.</p>
  </>}
 </section>;
}
