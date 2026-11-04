import {useEffect,useRef,useState} from 'react';
import {Download,Film} from 'lucide-react';
import {JourneyExportBatch} from './JourneyExportBatch';
import {api} from '../../lib/api';
import {APP_VERSION} from '../../version';
import type {JourneyHistory} from './types';
import {makeExportPlan,MAX_EXPORT_VISITS,type ExportCombat,type ExportMessage} from './exportModel';

type Result={url:string;format:'gif'|'mp4';name:string;duration:number;size:number};
function SingleJourneyExport({history,query}:{history:JourneyHistory;query:string}){
 const [first,setFirst]=useState(1),[last,setLast]=useState(Math.min(history.visits.length,MAX_EXPORT_VISITS)),[format,setFormat]=useState<'gif'|'mp4'>('mp4');
 const [busy,setBusy]=useState(false),[progress,setProgress]=useState(0),[error,setError]=useState(''),[notice,setNotice]=useState(''),[result,setResult]=useState<Result|null>(null);
 const active=useRef<{worker?:Worker;abort:AbortController}|null>(null),url=useRef<string|null>(null);
 const supported=typeof Worker!=='undefined'&&typeof OffscreenCanvas!=='undefined'&&typeof createImageBitmap!=='undefined';
 const invalidate=()=>{if(url.current)URL.revokeObjectURL(url.current);url.current=null;setResult(null);};
 useEffect(()=>()=>{active.current?.abort.abort();active.current?.worker?.terminate();active.current=null;if(url.current)URL.revokeObjectURL(url.current);},[]);
 function cancel(){active.current?.abort.abort();active.current?.worker?.terminate();active.current=null;setBusy(false);setProgress(0);setNotice('Export cancelled.');}
 async function start(){
  invalidate();setError('');setNotice('Loading existing combat records…');setProgress(0);setBusy(true);
  const task={abort:new AbortController(),worker:undefined as Worker|undefined};active.current=task;
  let bitmap:ImageBitmap|undefined;
  try{
   const combat=await api<ExportCombat>(`/journey/characters/${history.character.character_id}/export-combat?${query}`,{signal:task.abort.signal});
   if(active.current!==task)return;
   const plan=makeExportPlan(history,combat,first,last);
   const logo=await fetch('/eqm-logo.png',{signal:task.abort.signal});if(!logo.ok)throw new Error('Could not load the EQM export logo.');
   bitmap=await createImageBitmap(await logo.blob());
   if(active.current!==task){bitmap.close();return;}
   task.worker=new Worker(new URL('./export.worker.ts',import.meta.url),{type:'module'});
   const fail=(message:string)=>{if(active.current!==task)return;task.worker?.terminate();active.current=null;setBusy(false);setError(message);setNotice('');};
   task.worker.onerror=()=>fail('The export worker stopped. Try fewer visits or a different format.');
   const chosenFormat=format;
   task.worker.onmessage=(event:MessageEvent<ExportMessage>)=>{
    if(active.current!==task)return;const message=event.data;
    if(message.type==='error'){fail(message.message);return;}
    if(message.type==='progress'){setProgress(message.progress);return;}
    const blob=new Blob([message.buffer],{type:message.mime}),nextUrl=URL.createObjectURL(blob);url.current=nextUrl;
    const safe=history.character.name.replace(/[^a-z0-9_-]+/gi,'-');
    setResult({url:nextUrl,format:chosenFormat,name:`EQM-My-Journey-${safe}-${plan.exportedAt.slice(0,10)}.${chosenFormat}`,duration:plan.duration,size:blob.size});
    setProgress(1);setBusy(false);setNotice(`Ready · ${plan.visits.length} visits, ${plan.engagements.flat().length} imported combat records${plan.unmatched?` · Unmatched records excluded: ${plan.unmatched}`:''}.${!plan.combatAvailable?' Combat unavailable with current permissions; no engagement pauses.':''}`);
    task.worker?.terminate();active.current=null;
   };
   task.worker.postMessage({format,plan,logo:bitmap,version:APP_VERSION},[bitmap]);bitmap=undefined;
   setNotice(`Encoding ${plan.duration.toFixed(1)} seconds at 1920 × 1080. Keep this page open.${!combat.available?' Combat unavailable with current permissions; no engagement pauses.':''}`);
  }catch(e){bitmap?.close();task.worker?.terminate();if(active.current!==task)return;active.current=null;setBusy(false);setNotice('');setError(e instanceof Error?e.message:String(e));}
 }
 const valid=Number.isInteger(first)&&Number.isInteger(last)&&first>=1&&last>=first&&last<=history.visits.length&&last-first+1<=MAX_EXPORT_VISITS;
 return <section className="journey-export" aria-label="Journey movie export"><h4><Film size={18}/> Export your journey</h4>
 <p>1080p GIF or MP4 · one second per recorded visit, plus three seconds per page of kills and losses. Starts at 100%, follows your route close up, then returns to the whole journey.</p>
 <div className="journey-export-controls"><label>First visit<input type="number" min={1} max={history.visits.length} value={first} disabled={busy} onChange={e=>{invalidate();setFirst(Number(e.target.value));}}/></label><label>Last visit<input type="number" min={first} max={history.visits.length} value={last} disabled={busy} onChange={e=>{invalidate();setLast(Number(e.target.value));}}/></label><label>Export format<select value={format} disabled={busy} onChange={e=>{invalidate();setFormat(e.target.value as 'gif'|'mp4');}}><option value="mp4">MP4 · H.264 · 30 fps</option><option value="gif">Animated GIF · 10 fps</option></select></label>
 <button type="button" disabled={busy||!valid||!supported} onClick={()=>void start()}><Film size={16}/> Create {format.toUpperCase()}</button>{busy&&<button type="button" onClick={cancel}>Cancel export</button>}</div>
 {!supported&&<p role="alert">This browser cannot render exports. Open EQM in a current desktop Chrome or Edge browser.</p>}
 {!valid&&history.visits.length>0&&<p role="alert">Choose between 1 and {history.visits.length} loaded visits, up to {MAX_EXPORT_VISITS} per clip.</p>}
 <p className="muted">Selected character and UTC dates · {history.visits.length} loaded visits. Up to {MAX_EXPORT_VISITS} visits, ten minutes and 128 MiB per clip; use short ranges for GIF. Files are created on your device. Use a desktop browser to save them; Android’s embedded WebView does not support these downloads.</p>
 <p className="muted">Combat pauses use existing imported killmails involving this pilot, matched by system and visit time. Continuous visits extend to the next observation; gaps stop at the last confirmed sample. Unmatched records are excluded. Hulls are never inferred from killmails. Visit times and the export date are shown in UTC.</p>
 {(history.truncated||history.ship_segments_truncated)&&<p className="mini-alert">The loaded history is incomplete. Narrow the UTC dates for a complete export; missing hulls appear as Unknown hull.</p>}
 {busy&&<progress aria-label="Journey export progress" max={1} value={progress}/>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert" className="mini-alert">{error}</p>}
 {result&&<div className="journey-export-result">{result.format==='mp4'?<video aria-label="Journey export preview" src={result.url} controls preload="metadata"/>:<img src={result.url} alt="Animated journey export preview"/>}<a className="button" href={result.url} download={result.name}><Download size={16}/> Download {result.format.toUpperCase()} · {(result.size/1024/1024).toFixed(1)} MiB</a><small>{result.duration.toFixed(1)} seconds · 1920 × 1080 · includes private route and combat history</small></div>}
 </section>;
}

export function JourneyExport({history,query}:{history:JourneyHistory;query:string}){
 const [scope,setScope]=useState<'single'|'range'|'all'>('single');
 return <div className="journey-export-scope"><label>Journey export scope<select aria-label="Journey export scope" value={scope} onChange={e=>setScope(e.target.value as 'single'|'range'|'all')}><option value="single">Single clip · selected visits</option><option value="range">Segment selected dates · every visit</option><option value="all">Entire recorded journey · all dates</option></select></label>
 {scope==='single'?<SingleJourneyExport history={history} query={query}/>:<JourneyExportBatch key={scope} characterId={history.character.character_id} query={query} scope={scope}/>}</div>;
}
