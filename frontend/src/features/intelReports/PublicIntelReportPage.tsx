import {useEffect,useState} from "react";
import type {ApiClient,Snapshot} from "./types";
import {IntelReportView,utc} from "./IntelReportView";
export function PublicIntelReportPage({api,token,onBack}:{api:ApiClient;token:string;onBack:()=>void}) {
 const [value,setValue]=useState<Snapshot|null>(null),[error,setError]=useState("");
 useEffect(()=>{let active=true,request=0;setValue(null);setError("");document.title="Intel Report · EVE Quartermaster";
  const robots=document.createElement("meta");robots.name="robots";robots.content="noindex,nofollow,noarchive";document.head.appendChild(robots);
  const referrer=document.createElement("meta");referrer.name="referrer";referrer.content="no-referrer";document.head.appendChild(referrer);
  async function load(){const current=++request;try{const result=await api<Snapshot>(`/intel-reports/public/${encodeURIComponent(token)}`);if(active&&current===request){setValue(result);setError("");}}catch(e){if(active&&current===request){setValue(null);setError(e instanceof Error?e.message:"Report unavailable");}}}
  void load();const timer=window.setInterval(()=>void load(),60000);
  return()=>{active=false;clearInterval(timer);robots.remove();referrer.remove();};
 },[api,token]);
 const expired=value?.expires_at&&Date.parse(value.expires_at)<=Date.now();
 return <main className="intel-report-public intel-page"><header className="panel"><button onClick={onBack}>EVE Quartermaster</button><h1>Intel Report</h1>{value&&!expired&&<p>Saved v{value.application_version} · {value.creator} · {utc(value.created_at)} · expires {value.expires_at?utc(value.expires_at):"when revoked"}. Public-data snapshot; no live queries or staff observations.</p>}</header>{error||expired?<section className="panel"><h2>Report unavailable</h2><p role="alert">{error||"This report has expired."}</p></section>:value?<IntelReportView report={value.report}/>:<p role="status">Loading Intel report…</p>}</main>;
}
