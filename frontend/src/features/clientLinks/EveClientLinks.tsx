import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from "react";
import {createPortal} from "react-dom";
import {api} from "../../lib/api";
import "./clientLinks.css";

type Target={kind?:"item"|"support";name?:string|null;type_id?:number|null;blueprint_id?:number|null;asset_id?:number|null};
type Character={token_id:number;name:string;can_open:boolean};
type Context={account:number|null;setAccount:(id:number|null)=>void;open:(target:Target)=>void};
const context=createContext<Context>({account:null,setAccount:()=>{},open:()=>{}});
export function useClientLinksAccount(id?:number){const {setAccount}=useContext(context);useEffect(()=>{setAccount(id??null);},[id,setAccount]);}
export function useEveClientLink(){return useContext(context);}
export function EveClientProvider({children}:{children:ReactNode}){
 const [account,setAccount]=useState<number|null>(null),[target,setTarget]=useState<Target|null>(null),[characters,setCharacters]=useState<Character[]>([]),[selected,setSelected]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const [preview,setPreview]=useState<{name:string;details:string;instance_link:boolean}|null>(null);
 const generation=useRef(0),locked=useRef(false),closeRef=useRef<HTMLButtonElement>(null),previousFocus=useRef<HTMLElement|null>(null);
 useEffect(()=>{if(target&&!busy)closeRef.current?.focus();},[target,busy]);
 const chosen=characters.find(c=>String(c.token_id)===selected);
 const open=(next:Target)=>{if(!account||locked.current)return;previousFocus.current=document.activeElement as HTMLElement;setTarget(next);setPreview(null);setError("");setNotice("");setCharacters([]);setSelected("");};
 useEffect(()=>{
  const contextLink=(event:MouseEvent|KeyboardEvent)=>{
   if(event instanceof KeyboardEvent && !(event.altKey&&event.key==="Enter"))return;
   const origin=event.target instanceof HTMLElement?event.target:null;
   const marked=origin?.closest<HTMLElement>("[data-eve-item]")??origin?.closest("button,a")?.querySelector<HTMLElement>("[data-eve-item]");
   if(!marked||!account)return;
   event.preventDefault();event.stopPropagation();
   try{open(JSON.parse(marked.dataset.eveItem??"{}"));}catch{/* Only explicit EQM item annotations participate. */}
  };
  document.addEventListener("contextmenu",contextLink);document.addEventListener("keydown",contextLink);
  return()=>{document.removeEventListener("contextmenu",contextLink);document.removeEventListener("keydown",contextLink);};
 },[account]);
 function close(){if(locked.current)return;generation.current++;setTarget(null);previousFocus.current?.focus();}
 useEffect(()=>{generation.current++;setTarget(null);setCharacters([]);setSelected("");setError("");setNotice("");},[account]);
 useEffect(()=>{if(!target)return;const version=++generation.current;setBusy(true);void Promise.all([api<{characters:Character[]}>("/client-links/characters"),api<{name:string;details:string;instance_link:boolean}>("/client-links/preview",{method:"POST",body:JSON.stringify(target)})]).then(([data,reference])=>{if(version!==generation.current)return;setPreview(reference);setCharacters(data.characters);setSelected(String(data.characters.find(c=>c.can_open)?.token_id??data.characters[0]?.token_id??""));}).catch(e=>{if(version===generation.current)setError(e.message);}).finally(()=>{if(version===generation.current)setBusy(false);});closeRef.current?.focus();return()=>{generation.current++;};},[target]);
 async function act(consent=false){if(!target||!chosen||locked.current)return;locked.current=true;setBusy(true);setError("");setNotice("");const version=generation.current;try{if(consent){const result=await api<{ready:boolean;url?:string;message?:string}>(`/client-links/characters/${chosen.token_id}/auth-url`);if(version!==generation.current)return;if(!result.ready||!result.url)throw new Error(result.message??"EVE SSO is unavailable.");window.location.assign(result.url);}else{const result=await api<{message:string;instance_link:boolean}>("/client-links/draft",{method:"POST",body:JSON.stringify({...target,token_id:chosen.token_id})});if(version===generation.current)setNotice(result.message+(result.instance_link?" The link refers to the specific owned item.":""));}}catch(e){if(version===generation.current)setError(e instanceof Error?e.message:"Could not open EVE.");}finally{locked.current=false;if(version===generation.current)setBusy(false);}}
 function trap(event:React.KeyboardEvent<HTMLElement>){if(event.key==="Escape"){event.preventDefault();close();}if(event.key==="Tab"){const nodes=Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button:not(:disabled),select:not(:disabled),a[href]"));const first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}}
 return <context.Provider value={{account,setAccount,open}}>{children}{target&&createPortal(<div className="modal-backdrop eve-client-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close();}}><section className="modal-window eve-client-dialog" role="dialog" aria-modal="true" aria-labelledby="eve-client-title" onKeyDown={trap}><header><h2 id="eve-client-title">{target.kind==="support"?"Steihl Lianul · in EVE":"Open item in EVE"}</h2><button ref={closeRef} type="button" disabled={busy} onClick={close} aria-label="Close in-game link">×</button></header>{preview&&<div className="eve-client-reference"><h3>{preview.name}</h3><p>{preview.details}</p>{preview.instance_link&&<small>Specific owned item link · current synced instance</small>}</div>}<p>Open a mail draft containing a clickable Show Info link. Keep your chosen character logged into EVE.</p><label>Open on character<select value={selected} onChange={e=>{setSelected(e.target.value);setNotice("");}} disabled={busy}>{!characters.length&&<option value="">{busy?"Loading characters…":"No linked characters"}</option>}{characters.map(c=><option key={c.token_id} value={c.token_id}>{c.name}{c.can_open?"":" · enable in-game windows"}</option>)}</select></label>{chosen&&!chosen.can_open&&<p>Enable in-game windows for this character through EVE SSO. Existing permitted grants are kept; this adds no private-data or mail-send permissions.</p>}{!busy&&!characters.length&&<p>Link your character through ESI Sync first.</p>}{error&&<p className="alert" role="alert">{error}</p>}{notice&&<p className="eve-client-success" role="status">{notice}</p>}<div className="button-row"><button type="button" disabled={busy||!chosen||!preview} onClick={()=>void act(!chosen?.can_open)}>{busy?"Working…":chosen&&!chosen.can_open?"Enable in-game windows":"Open draft in EVE"}</button><button type="button" disabled={busy} onClick={close}>Close</button></div><small>This never sends mail or transfers ISK. Close the draft after using its link.</small></section></div>,document.body)}</context.Provider>;
}
export function EveItemName({name,typeId,blueprintId,assetId,contextOnly=false,children}:{name?:string|null;typeId?:number|null;blueprintId?:number|null;assetId?:number|null;contextOnly?:boolean;children?:ReactNode}){
 const {account,open}=useEveClientLink();const label=children??name??"Unknown item";
 if(!account||!name)return <>{label}</>;
 const launch=()=>open({name,type_id:typeId||undefined,blueprint_id:blueprintId||undefined,asset_id:assetId||undefined});
 if(contextOnly)return <span className="eve-item-context" data-eve-item={JSON.stringify({name,type_id:typeId||undefined,blueprint_id:blueprintId||undefined,asset_id:assetId||undefined})} title="Right-click or Alt+Enter for an in-game Show Info link" onContextMenu={e=>{e.preventDefault();e.stopPropagation();launch();}}>{label}</span>;
 return <span className="eve-item-name">{label}<button type="button" className="eve-item-launch" title={`Open ${name} in EVE`} aria-label={`Open ${name} in EVE`} onClick={e=>{e.stopPropagation();launch();}}>↗</button></span>;
}
export function SupportCard(){const {open}=useEveClientLink();return <aside className="panel eqm-support-card" data-layout-id="overview-support"><div><h3>For capsuleers, by a capsuleer.</h3><p>EVE Quartermaster is, and always will be, free software—built by a 20-year veteran capsuleer and his wittle AI agent.</p><p>If EQM has earned a place in your Neocom, you’re welcome to yeet a little ISK to <button type="button" className="eqm-creator-link" onClick={()=>open({kind:"support"})}>Steihl Lianul</button> in game, with the reason <strong>EQM</strong>. Always appreciated, never expected.</p><small>Thank you, and fly dangerously! o7</small></div></aside>;}
