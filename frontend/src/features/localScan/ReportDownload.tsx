import {useState} from "react";
const API_BASE=import.meta.env.VITE_API_BASE??"/api";
export function ReportDownload({path,filename,label="Export PDF"}:{path:string;filename:string;label?:string}) {
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 async function download(){setBusy(true);setError("");try{const token=localStorage.getItem("eq_access_token");const response=await fetch(`${API_BASE}${path}`,{credentials:"include",headers:token?{Authorization:`Bearer ${token}`}:{},signal:AbortSignal.timeout(120000)});if(!response.ok)throw new Error("Report download is unavailable. Check sign-in, access and expiry.");const url=URL.createObjectURL(await response.blob());const a=document.createElement("a");a.href=url;a.download=filename;a.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){setError(e instanceof Error?e.message:"Download failed.");}finally{setBusy(false);}}
 return <><button type="button" onClick={()=>void download()} disabled={busy}>{busy?"Downloading…":label}</button>{error&&<span role="alert">{error}</span>}</>;
}
