import {useEffect,useState} from 'react';
import {api} from '../../lib/api';
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
import {InsightReport} from './InsightReport';
import type {InsightReport as Report} from './insightsModel';

export function PublicJourneyView({token,onBack}:{token:string;onBack:()=>void}){
 const [data,setData]=useState<{title:string;report:Report;expires_at:string}|null>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;const abort=new AbortController();
  async function refresh(){try{const value=await api<{title:string;report:Report;expires_at:string}>(`/journey-views/${encodeURIComponent(token)}`,{signal:abort.signal});if(active){setData(value);setError('');}}catch(e){if(active){setData(null);setError(e instanceof Error?e.message:String(e));}}}
  void refresh();const timer=window.setInterval(()=>void refresh(),30000),visible=()=>{if(!document.hidden)void refresh();};document.addEventListener('visibilitychange',visible);
  return()=>{active=false;abort.abort();clearInterval(timer);document.removeEventListener('visibilitychange',visible);};
 },[token]);
 const expired=data&&Date.parse(data.expires_at)<=Date.now();
 return <main className="journey-public-view"><header><button onClick={onBack}>EVE Quartermaster</button><span>Shared Journey aggregates</span></header>
  <section className="panel journey-analytics">{error||expired?<><h1>Shared view unavailable</h1><p role="alert">{error||'This view has expired.'}</p></>:data?<><h1>{data.title}</h1><p>Published snapshot · expires {new Date(data.expires_at).toLocaleString()}</p><InsightReport report={data.report} publicView/><div className="journey-insights-actions">{(['json','csv'] as const).map(fmt=><a key={fmt} href={`${API_BASE}/journey-views/${encodeURIComponent(token)}/export/${fmt}`} rel="noreferrer">Download shared {fmt.toUpperCase()}</a>)}</div></>:<p role="status">Loading shared snapshot…</p>}</section>
 </main>;
}
