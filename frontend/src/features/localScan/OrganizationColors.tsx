import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { Highlight } from "./types";
import { SCAN_COLORS, colorStyle, normalizeColor } from "./highlights";
import type { OrganizationTarget, SaveColor, ScanColor } from "./highlights";

export function ColorOptions() {
  return <>{Object.entries(SCAN_COLORS).map(([key,c])=><option key={key} value={key}>{c.label}</option>)}</>;
}
export function OrganizationColors({highlights,onSave,busy,disabled}: {highlights:Highlight[];onSave:SaveColor;busy:boolean;disabled:boolean}) {
  const [name,setName]=useState("");
  const [kind,setKind]=useState<OrganizationTarget["kind"]>("corporation");
  const [color,setColor]=useState<ScanColor>("red");
  async function add(e:FormEvent) {e.preventDefault();try {await onSave({kind,name},color);setName("");} catch {/* Parent shows the request error. */}}
  return <><p className="muted">Saved to your account across sessions. Use a Color button in the results or add an exact name here. Corporation colors override alliance colors. Your current view updates immediately; new reports and PDFs save the colors. Existing public snapshots keep their original markings.</p>
    <form className="scan-highlight-form" onSubmit={e=>void add(e)}><label>Type<select value={kind} onChange={e=>setKind(e.target.value as OrganizationTarget["kind"])}><option value="corporation">Corporation</option><option value="alliance">Alliance</option></select></label><label>Exact organization name<input value={name} onChange={e=>setName(e.target.value)} required maxLength={255}/></label><label>Color<select aria-label="New organization color" value={color} onChange={e=>setColor(e.target.value as ScanColor)}><ColorOptions/></select></label><button disabled={busy||disabled}>Save color</button></form>
    <div className="scan-highlight-chips">{highlights.map(h=><div className="scan-highlight-chip scan-marked" style={colorStyle(normalizeColor(h.color))} key={h.id}><span>{h.name} <small>({h.kind})</small></span><select aria-label={`Color for ${h.name}`} value={normalizeColor(h.color)} disabled={busy||disabled} onChange={e=>void onSave(h,e.target.value as ScanColor).catch(()=>undefined)}><ColorOptions/></select><button type="button" aria-label={`Remove ${h.name}`} disabled={busy||disabled} onClick={()=>void onSave(h,null).catch(()=>undefined)}>×</button></div>)}</div>{highlights.length===0&&<p className="muted">No organizations colored yet.</p>}
  </>;
}

export function OrganizationColorDialog({target,highlights,onSave,onClose}: {target:OrganizationTarget;highlights:Highlight[];onSave:SaveColor;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const existing=highlights.find(h=>h.kind===target.kind&&h.eve_id===target.eve_id);
  const [color,setColor]=useState<ScanColor>(normalizeColor(existing?.color));
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  useEffect(()=>{const node=dialog.current;const previous=document.activeElement;node?.showModal();return()=>{node?.close();if(previous instanceof HTMLElement&&previous.isConnected)previous.focus();};},[]);
  async function save(value:ScanColor|null) {setBusy(true);setError("");try {await onSave(target,value);onClose();} catch(e){setError(e instanceof Error?e.message:"Could not save color.");}finally{setBusy(false);}}
  return <dialog ref={dialog} className="scan-color-dialog" aria-labelledby="scan-color-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}><h3 id="scan-color-title">Color {target.name}</h3><p>Save this {target.kind} to your account. Corporation colors override alliance colors.</p><form onSubmit={e=>{e.preventDefault();void save(color);}}><label>Organization color<select autoFocus aria-label="Organization color" disabled={busy} value={color} onChange={e=>setColor(e.target.value as ScanColor)}><ColorOptions/></select></label><p className="scan-color-preview" style={colorStyle(color)}><span aria-hidden="true">● </span>{SCAN_COLORS[color].label}</p>{error&&<p role="alert">{error}</p>}<div className="scan-report-actions"><button type="submit" disabled={busy}>{busy?"Saving…":"Save color"}</button>{existing&&<button type="button" disabled={busy} onClick={()=>void save(null)}>Remove override</button>}<button type="button" disabled={busy} onClick={onClose}>Cancel</button></div></form></dialog>;
}
