import {useState} from "react";
import {downloadApiFile} from "../../lib/api";

export function FullAssetExport({filters}: {filters:Record<string,string|null>}) {
  const [busy,setBusy]=useState<string|null>(null),[message,setMessage]=useState(""),[error,setError]=useState("");
  async function download(format:"csv"|"janice") {
    setBusy(format);setMessage("");setError("");
    const params=new URLSearchParams({format});
    Object.entries(filters).forEach(([key,value])=>{if(value!==null&&value!=="")params.set(key,value);});
    try{await downloadApiFile(`/quartermaster/assets-download?${params}`,`eqm-assets-${new Date().toISOString().slice(0,10)}.${format==="csv"?"csv":"txt"}`);setMessage("Download ready: all currently matching records, across every page.");}
    catch(e){setError(e instanceof Error?e.message:"Export failed");}finally{setBusy(null);}
  }
  return <section className="stacked"><strong>Full filtered downloads</strong><p className="muted">Export all matching records directly from the server. No need to load every page. Janice combines quantities by item name and omits owners and locations.</p>
    <div className="button-row compact"><button type="button" disabled={busy!==null} onClick={()=>void download("csv")}>{busy==="csv"?"Preparing CSV…":"Download full filtered CSV"}</button><button type="button" disabled={busy!==null} onClick={()=>void download("janice")}>{busy==="janice"?"Preparing Janice list…":"Download full Janice list"}</button></div>
    {message&&<p role="status" className="notice inline">{message}</p>}{error&&<p role="alert" className="mini-alert">{error}</p>}
  </section>;
}
