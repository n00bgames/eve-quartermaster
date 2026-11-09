import {useEffect,useState,type Dispatch,type SetStateAction} from "react";
import {api} from "../../lib/api";
import {JourneyAnalytics} from "../journey/JourneyAnalytics";
import type {Settings} from "../journey/types";

/** Journey stays account-private, independently of the platform corporation scope. */
export function JourneyAnalyticsSection(){
  const [character,setCharacter]=useState(0),[from,setFrom]=useState(()=>new Date(Date.now()-7*86400000).toISOString().slice(0,10));
  const [to,setTo]=useState(()=>new Date().toISOString().slice(0,10));
  const query=new URLSearchParams({from_at:`${from}T00:00:00Z`,to_at:new Date(new Date(`${to}T00:00:00Z`).getTime()+86400000).toISOString()}).toString();
  return <JourneyAnalytics id="analytics-journey" character={character} query={query} refresh={0} onSelectCharacter={setCharacter}>
    <JourneyFilters character={character} choose={setCharacter} from={from} to={to} setFrom={setFrom} setTo={setTo}/>
  </JourneyAnalytics>;
}

function JourneyFilters({character,choose,from,to,setFrom,setTo}:{character:number;choose:Dispatch<SetStateAction<number>>;from:string;to:string;setFrom:(value:string)=>void;setTo:(value:string)=>void}){
  const [settings,setSettings]=useState<Settings|null>(null),[error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();
    void api<Settings>("/journey/settings",{signal:controller.signal}).then(result=>{if(controller.signal.aborted)return;setSettings(result);choose(current=>result.characters.some(row=>row.character_id===current)?current:result.characters[0]?.character_id??0);})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"Unable to read your Journey pilots.");});
    return ()=>controller.abort();
  },[]);
  return <><div className="journey-analytics-controls">
    <label>Journey pilot<select aria-label="Analytics Journey pilot" value={character||""} onChange={event=>choose(Number(event.target.value))}><option value="" disabled>Choose a linked pilot</option>{settings?.characters.map(row=><option key={row.character_id} value={row.character_id}>{row.name}</option>)}</select></label>
    <label>From (UTC)<input aria-label="Journey analytics from (UTC)" type="date" value={from} onChange={event=>{if(event.target.value)setFrom(event.target.value);}}/></label>
    <label>Through (UTC)<input aria-label="Journey analytics through (UTC)" type="date" value={to} onChange={event=>{if(event.target.value)setTo(event.target.value);}}/></label>
  </div><p className="muted">These UTC dates apply when History scope is Selected dates. Journey analytics includes only your account’s pilots, independently of the platform scope.</p>
    {error&&<p role="alert" className="mini-alert">{error}</p>}{settings&&!settings.characters.length&&<p>No linked Journey pilots yet.</p>}</>;
}
