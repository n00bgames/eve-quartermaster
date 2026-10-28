import { useEffect, useState } from "react";
import type { ApiClient, ScanReport } from "./types";
import { LocalScanResults } from "./LocalScanResults";
import "./localScan.css";

export function PublicLocalScanPage({api,token,onBack}:{api:ApiClient;token:string;onBack:()=>void}) {
  const [report,setReport]=useState<ScanReport|null>(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    let active=true;setReport(null);setError("");
    document.title="Local scan · EVE Quartermaster";
    const robots=document.createElement("meta");robots.name="robots";robots.content="noindex,nofollow,noarchive";document.head.appendChild(robots);
    const referrer=document.createElement("meta");referrer.name="referrer";referrer.content="no-referrer";document.head.appendChild(referrer);
    const refresh=()=>api<ScanReport>(`/local-scans/public/${encodeURIComponent(token)}`).then(r=>{if(active)setReport(r);}).catch(e=>{if(active){setReport(null);setError(e instanceof Error?e.message:"Report unavailable.");}});
    void refresh();
    // Revalidate live public access, including manual deletion, without retaining a cached report.
    const timer=window.setInterval(()=>void refresh(),60000);
    return()=>{active=false;window.clearInterval(timer);robots.remove();referrer.remove();};
  },[api,token]);
  const expired=report?.expires_at && Date.parse(report.expires_at)<=Date.now();
  return <main className="scan-public-shell"><header className="scan-public-brand"><button type="button" onClick={onBack}><img src="/eqm-logo.webp" alt=""/>EVE Quartermaster</button><span>Public local scan</span></header><div className="panel">{error || expired ? <><h1>Report unavailable</h1><p role="alert">{error||"This report has expired."}</p><button type="button" onClick={onBack}>Return to EQM</button></> : report ? <LocalScanResults key={report.token} report={report} api={api}/> : <p role="status">Loading local scan…</p>}</div></main>;
}
