import {useEffect,useState} from "react";
import {ExternalLink,ShieldCheck} from "lucide-react";
import type {Affiliation,ApiClient,Badge,IntelReport} from "./types";
const link=(kind:string,id:number)=>`https://zkillboard.com/${kind}/${id}/`;
export function IntelIdentityHeader({report,api,badges}:{report:IntelReport;api:ApiClient;badges:Badge[]}){
 const [resolved,setResolved]=useState<{key:string;rows:Affiliation[]}|null>(null),[failed,setFailed]=useState(false);
 const subject=report.subject,profile=subject.public_data.esi?.data;
 const identityKey=`${subject.id}:${profile?.corporation_id??""}:${profile?.alliance_id??""}`;
 useEffect(()=>{setResolved(null);setFailed(false);if(subject.kind!=="character")return;
  let active=true;const controller=new AbortController();
  void api<Affiliation[]>(`/intel/subjects/${subject.id}/affiliations`,{signal:controller.signal}).then(rows=>{if(active)setResolved({key:identityKey,rows});}).catch(()=>{if(active)setFailed(true);});
  return()=>{active=false;controller.abort();};
 },[api,identityKey]);
 const affiliations=resolved?.key===identityKey?resolved.rows:report.affiliations??[];
 return <div className="intel-identity"><img alt={`${subject.name} ${subject.kind==="character"?"portrait":"logo"}`} src={subject.kind==="character"?`https://images.evetech.net/characters/${subject.eve_id}/portrait?size=128`:`https://images.evetech.net/${subject.kind==="corporation"?"corporations":"alliances"}/${subject.eve_id}/logo?size=128`}/>
 <div><span className="intel-kind">{subject.kind} · {subject.eve_id}</span><h2>{subject.name}</h2>
 {subject.kind==="character"&&<div className="intel-affiliations">{affiliations.map(row=><a key={row.kind} className="intel-affiliation" href={link(row.kind,row.eve_id)} target="_blank" rel="noreferrer" title={`Open ${row.name} on zKillboard`}>
 <img alt={`${row.name} logo`} width={40} height={40} src={`https://images.evetech.net/${row.kind==="corporation"?"corporations":"alliances"}/${row.eve_id}/logo?size=64`}/><span><small>{row.kind}</small><strong>{row.name}</strong><span className="intel-affiliation-tag">{row.ticker?`[${row.ticker}]`:"Tag unavailable"}</span></span><ExternalLink size={12}/></a>)}
 {!profile?.corporation_id&&<small>Corporation unavailable</small>}{!profile?.alliance_id&&<small>{subject.public_data.esi?.state==="available"?"No alliance":"Alliance unavailable"}</small>}
 {(failed||affiliations.some(row=>row.stale))&&<small className="intel-affiliation-notice">Public affiliation details may be stale or unavailable.</small>}</div>}
 <div className="intel-badges">{badges.map(badge=><span key={badge.label} title={`${badge.meaning}. ${badge.source==="zkill-rule"?"EQM applies the documented zKill rule; ":""}zKill rolling ${badge.window_days}-day window; fetched ${subject.public_data.zkill?.fetched_at??"unknown"}`}><ShieldCheck size={13}/>{badge.label}{badge.level?` ${badge.level}`:""}{badge.count!==undefined?` (${badge.count})`:""}</span>)}{report.summary.smartbomb.frequent&&<span title={report.definitions.smartbomb} className="intel-local-tag">EQM · FREQUENT SMARTBOMBER</span>}</div></div>
 <a className="intel-source-link" href={link(subject.kind,subject.eve_id)} target="_blank" rel="noreferrer">zKill <ExternalLink size={14}/></a></div>;
}
