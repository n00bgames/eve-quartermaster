import {useEffect,useRef,useState} from 'react';
import {api} from '../../lib/api';
import {APP_VERSION} from '../../version';
import {journeyExportPages} from './exportHistory';
import {exportTimeline,segmentTimeline,planTimelineClip,splitTimeline,MAX_EXPORT_VISITS,type ExportPlan,type ExportMessage,type TimelineUnit} from './exportModel';

type Writable={write(data:Blob|string):Promise<void>;close():Promise<void>;abort?():Promise<void>};
type Directory={getFileHandle(name:string,options:{create:boolean}):Promise<{createWritable():Promise<Writable>}>};
type Task={abort:AbortController;worker?:Worker;resume?:()=>void;pending?:ClipRecord};
type ClipRecord={part:number;filename:string;bytes:number;seconds:number;first_visit:number;last_visit:number;starts_with:string;ends_with:string;events:number};
function last<T>(rows:T[]):T{return rows[rows.length-1];}
const eventKey=(unit:TimelineUnit,offset:number)=>`${offset+unit.visitIndex+1}:${unit.kind}${unit.kind==='engagement'?`:${unit.page!+1}`:''}`;

function encode(plan:ExportPlan,format:'gif'|'mp4',logo:Blob,task:Task,progress:(n:number)=>void):Promise<{buffer:ArrayBuffer;mime:string}>{
 return new Promise((resolve,reject)=>{
  let bitmap:ImageBitmap|undefined;
  const stop=()=>{task.worker?.terminate();reject(new DOMException('Export cancelled','AbortError'));};
  task.abort.signal.addEventListener('abort',stop,{once:true});
  const done=()=>{task.abort.signal.removeEventListener('abort',stop);task.worker?.terminate();task.worker=undefined;};
  void (async()=>{
   try{
    bitmap=await createImageBitmap(logo);if(task.abort.signal.aborted)throw new DOMException('Export cancelled','AbortError');
    const worker=new Worker(new URL('./export.worker.ts',import.meta.url),{type:'module'});task.worker=worker;
    worker.onerror=()=>{done();reject(new Error('The export worker stopped. Try a different format.'));};
    worker.onmessage=(e:MessageEvent<ExportMessage>)=>{const data=e.data;if(data.type==='progress'){progress(data.progress);return;}done();if(data.type==='error')reject(Object.assign(new Error(data.message),{code:data.code}));else resolve(data);};
    worker.postMessage({format,plan,logo:bitmap,version:APP_VERSION},[bitmap]);bitmap=undefined;
   }catch(error){bitmap?.close();done();reject(error);}
  })();
 });
}

export function JourneyExportBatch({characterId,query,scope}:{characterId:number;query:string;scope:'all'|'range'}){
 const [format,setFormat]=useState<'gif'|'mp4'>('mp4'),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState(''),[progress,setProgress]=useState(0),[saved,setSaved]=useState<ClipRecord[]>([]);
 const [ready,setReady]=useState<{url:string;record:ClipRecord;downloaded:boolean}|null>(null),[indexUrl,setIndexUrl]=useState<string|null>(null);
 const active=useRef<Task|null>(null),url=useRef<string|null>(null),index=useRef<string|null>(null);
 const picker=(window as unknown as {showDirectoryPicker?:(options:{mode:'readwrite'})=>Promise<Directory>}).showDirectoryPicker;
 const supported=typeof Worker!=='undefined'&&typeof OffscreenCanvas!=='undefined'&&typeof createImageBitmap!=='undefined';
 const release=()=>{if(url.current)URL.revokeObjectURL(url.current);url.current=null;setReady(null);};
 useEffect(()=>()=>{active.current?.abort.abort();active.current?.worker?.terminate();active.current?.resume?.();active.current=null;if(url.current)URL.revokeObjectURL(url.current);if(index.current)URL.revokeObjectURL(index.current);},[]);
 function cancel(){const task=active.current;task?.abort.abort();task?.worker?.terminate();task?.resume?.();release();setNotice('Stopping export. Saved clips remain in your chosen folder or downloads.');}
 async function run(toFolder:boolean){
  release();if(index.current)URL.revokeObjectURL(index.current);index.current=null;setIndexUrl(null);setSaved([]);setError('');setProgress(0);setBusy(true);
  const task:Task={abort:new AbortController()};active.current=task;
  const records:ClipRecord[]=[],exportedAt=new Date().toISOString(),jobId=exportedAt.replace(/[:.]/g,'-')+'-'+crypto.randomUUID().slice(0,8);
  let folder:Directory|undefined,baseName=`EQM-My-Journey-${jobId}`,snapshotAt='',total=0,completed=0,status='running',combatUnavailable=false,unmatched=0;
  const exportIndex=()=>JSON.stringify({application_version:APP_VERSION,exported_at:exportedAt,snapshot_at:snapshotAt,character_id:characterId,scope,query:scope==='range'?query:undefined,format,status,total_visits:total,completed_visit_events:completed,combat_unavailable:combatUnavailable,unmatched_combat_records:unmatched,clips:records,pending_clip:task.pending},null,2);
  const write=async(name:string,data:Blob|string)=>{const file=await folder!.getFileHandle(name,{create:true}),stream=await file.createWritable();try{await stream.write(data);await stream.close();}catch(reason){try{await stream.abort?.();}catch{}throw reason;}};
  try{
   if(toFolder){setNotice('Choose a folder for the numbered clips.');folder=await picker!.call(window,{mode:'readwrite'});}
   if(task.abort.signal.aborted)return;
   const response=await fetch('/eqm-logo.png',{signal:task.abort.signal});if(!response.ok)throw new Error('Could not load the EQM logo.');const logo=await response.blob();
   for await(const page of journeyExportPages(api,characterId,scope,query,task.abort.signal)){
    total=page.history.window_visits;
    if(!snapshotAt)baseName=`EQM-My-Journey-${page.history.character.name.replace(/[^a-z0-9_-]+/gi,'-')}-${jobId}`;
    snapshotAt=page.snapshot_at;
    const timeline=exportTimeline(page.history,page.combat),queue=segmentTimeline(timeline.units);
    combatUnavailable ||= !page.combat.available;unmatched+=timeline.unmatched;
    while(queue.length){
     if(task.abort.signal.aborted)throw new DOMException('Export cancelled','AbortError');
     const units=queue.shift()!,part=records.length+1,plan=planTimelineClip(timeline,units,exportedAt,part);
     setNotice(`Creating part ${part} · journey visits ${plan.visitNumbers![0]}–${last(plan.visitNumbers!)} · ${completed} of ${total} visit events saved${page.combat.available?'':' · Combat unavailable; travel only'}.`);
     setProgress(0);
     let encoded:{buffer:ArrayBuffer;mime:string};
     try{encoded=await encode(plan,format,logo,task,p=>{if(active.current===task)setProgress(p);});}
     catch(reason){if((reason as {code?:string})?.code==='size_limit'){const [a,b]=splitTimeline(units);queue.unshift(a,b);continue;}throw reason;}
     if(active.current===task)setProgress(1);
     const filename=`${baseName}-part-${String(part).padStart(4,'0')}.${format}`,blob=new Blob([encoded.buffer],{type:encoded.mime});
     const record:ClipRecord={part,filename,bytes:blob.size,seconds:plan.duration,first_visit:plan.visitNumbers![0],last_visit:last(plan.visitNumbers!)!,starts_with:eventKey(units[0],page.history.visit_offset),ends_with:eventKey(last(units),page.history.visit_offset),events:units.length};
     task.pending=record;
     if(folder)await write(filename,blob);
     else{
      const nextUrl=URL.createObjectURL(blob);url.current=nextUrl;
      if(active.current===task){setReady({url:nextUrl,record,downloaded:false});setNotice(`Part ${part} is ready. Download it, then continue; the next clip starts at the next timeline event.`);}
      await new Promise<void>(resolve=>{task.resume=resolve;});task.resume=undefined;
      if(task.abort.signal.aborted)throw new DOMException('Export cancelled','AbortError');release();
     }
     records.push(record);task.pending=undefined;completed+=units.filter(u=>u.kind==='visit').length;
     if(active.current===task)setSaved([...records]);
     if(folder)await write(`${baseName}-index.json`,exportIndex());
    }
   }
   if(task.abort.signal.aborted)throw new DOMException('Export cancelled','AbortError');
   if(completed!==total)throw new Error('The export did not cover every visit. Saved clips remain available.');
   status='complete';
   if(active.current===task){setProgress(1);setNotice(total?`Export complete · ${completed} visits in ${records.length} clips. Every timeline event was exported in order.${combatUnavailable?' Combat was unavailable for some pages; those clips contain travel only.':''}${unmatched?` Unmatched combat records excluded: ${unmatched}.`:''}`:'No recorded visits in this export scope.');}
  }catch(reason){
   status=task.abort.signal.aborted||(reason instanceof DOMException&&reason.name==='AbortError')?'cancelled':'failed';
   if(active.current===task){if(status==='cancelled')setNotice('Export cancelled. Saved clips are preserved.');else{setError(reason instanceof Error?reason.message:String(reason));setNotice('Export stopped. Already saved clips are preserved.');}}
  }finally{
   if(folder&&snapshotAt){try{await write(`${baseName}-index.json`,exportIndex());}catch{if(active.current===task)setError(old=>(old?old+' ':'')+'The export index could not be saved. Saved clips remain available.');}}
   if(active.current===task){const next=URL.createObjectURL(new Blob([exportIndex()],{type:'application/json'}));index.current=next;setIndexUrl(next);setBusy(false);active.current=null;}
  }
 }
 return <section className="journey-export" aria-label="Segmented journey export"><h4>Export {scope==='all'?'entire recorded journey':'selected dates'} as numbered clips</h4>
 <p>Clips continue at the next visit or engagement page. Up to {MAX_EXPORT_VISITS} visits, ten minutes and 128 MiB each. A long engagement continues in the next part; file-size splits happen automatically.</p>
 <p className="muted">{scope==='all'?'All recorded dates for this character, including visits beyond the map’s loaded history.':'Every visit in the selected UTC dates, including pages beyond the loaded replay.'} 1080p · one second per visit · three seconds per engagement page. Each clip includes the map opening/closing, EQM branding, export date and part number.</p>
 <div className="journey-export-controls"><label>Segment format<select value={format} disabled={busy} onChange={e=>setFormat(e.target.value as 'gif'|'mp4')}><option value="mp4">MP4 · H.264 · 30 fps</option><option value="gif">GIF · 10 fps</option></select></label>
 {picker&&<button disabled={busy||!supported} onClick={()=>void run(true)}>Export clips to folder</button>}<button disabled={busy||!supported} onClick={()=>void run(false)}>Export clips for download</button>{busy&&<button onClick={cancel}>Cancel segmented export</button>}</div>
 <p className="muted">Folder export saves all parts automatically. Individual downloads pause after each clip until you save it and continue. Keep this page open. Saved clips are preserved if you cancel; an index records each part’s timeline boundaries. Desktop browser saving is required; Android WebView downloads are unsupported.</p>
 {!supported&&<p role="alert">This browser cannot render exports. Use a current desktop Chrome or Edge browser.</p>}
 {busy&&<progress aria-label="Segment export progress" max={1} value={progress}/>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert" className="mini-alert">{error}</p>}
 {ready&&<div className="journey-export-result"><strong>Part {ready.record.part} · visits {ready.record.first_visit}–{ready.record.last_visit} · {ready.record.seconds.toFixed(1)} seconds</strong>{format==='mp4'?<video src={ready.url} controls preload="metadata" aria-label="Segmented journey preview"/>:<img src={ready.url} alt="Segmented journey GIF preview"/>}<a href={ready.url} download={ready.record.filename} onClick={()=>setReady(old=>old?{...old,downloaded:true}:old)}>Download part {ready.record.part} · {(ready.record.bytes/1024/1024).toFixed(1)} MiB</a><button disabled={!ready.downloaded} onClick={()=>active.current?.resume?.()}>Continue after saving</button></div>}
 {!!saved.length&&<p>{saved.length} clips saved · last saved through journey visit {last(saved).last_visit}. {indexUrl&&<a href={indexUrl} download="EQM-journey-export-index.json">Download export index</a>}</p>}
 </section>;
}
