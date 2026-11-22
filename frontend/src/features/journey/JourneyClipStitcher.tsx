import {useEffect,useRef,useState} from 'react';
import {sortClips} from './clipOrder';

type Picker=(options:{suggestedName:string;types:{description:string;accept:Record<string,string[]>}[]})=>Promise<FileSystemFileHandle>;
export function JourneyClipStitcher(){
 const [files,setFiles]=useState<File[]>([]),[busy,setBusy]=useState(false),[progress,setProgress]=useState(0),[notice,setNotice]=useState(''),[error,setError]=useState('');
 const task=useRef<AbortController|null>(null),picker=(window as unknown as {showSaveFilePicker?:Picker}).showSaveFilePicker;
 useEffect(()=>()=>{task.current?.abort();},[]);
 function move(index:number,offset:number){setFiles(old=>{const next=old.slice();[next[index],next[index+offset]]=[next[index+offset],next[index]];return next;});setNotice('');}
 async function run(){
  const abort=new AbortController();task.current=abort;setBusy(true);setError('');setNotice('Choose a new output file, then the clips will be checked.');setProgress(0);
  try{
   const handle=await picker!.call(window,{suggestedName:`EQM-journey-combined-${new Date().toISOString().replace(/[:.]/g,'-')}.mp4`,types:[{description:'Combined Journey MP4',accept:{'video/mp4':['.mp4']}}]});
   const {validateClips,stitchClips}=await import('./clipStitch');
   setNotice('Checking every clip before writing…');await validateClips(files,abort.signal);
   if(abort.signal.aborted)throw new DOMException('Stitch cancelled','AbortError');
   const stream=await handle.createWritable();setNotice('Joining compressed packets directly to disk…');
   const seconds=await stitchClips(files,stream,abort.signal,(n,total)=>{setProgress(n/total);setNotice(`Joined ${n} / ${total} clips…`);});
   setNotice(`Saved ${handle.name} · ${files.length} clips · ${seconds.toFixed(1)} seconds. No frames were re-encoded.`);
  }catch(e){setNotice('');if(abort.signal.aborted||(e instanceof DOMException&&e.name==='AbortError'))setNotice('Stitch cancelled. Original clips are unchanged.');else setError(e instanceof Error?e.message:String(e));}
  finally{task.current=null;setBusy(false);}
 }
 return <details className="journey-export journey-stitcher"><summary>Combine Journey MP4 clips</summary>
  <p>Choose clips from one export run. Numbered parts sort automatically; review or adjust their order below. Compatible video and optional AAC music are joined directly to disk without re-encoding.</p>
  <input aria-label="Journey MP4 clips" type="file" accept="video/mp4,.mp4" multiple disabled={busy} onChange={e=>{setFiles(sortClips(Array.from(e.target.files??[])));setError('');setNotice('');}}/>
  <ol className="journey-stitch-list">{files.map((file,i)=><li key={`${i}:${file.name}`}>{file.name}<button aria-label={`Move ${file.name} earlier`} disabled={busy||i===0} onClick={()=>move(i,-1)}>↑</button><button aria-label={`Move ${file.name} later`} disabled={busy||i===files.length-1} onClick={()=>move(i,1)}>↓</button><button aria-label={`Remove ${file.name}`} disabled={busy} onClick={()=>setFiles(old=>old.filter((_,n)=>n!==i))}>Remove</button></li>)}</ol>
  <button disabled={busy||files.length<2||!picker} onClick={()=>void run()}>Save combined MP4</button>{busy&&<button onClick={()=>task.current?.abort()}>Cancel stitch</button>}
  {!picker&&<p>This needs a desktop Chrome or Edge browser with direct file saving. Your original individual downloads remain available.</p>}
  <p className="muted">No uploads. One input file is read at a time with small read/write caches; container indexes still use some memory. MP4 only; all clips must have matching codec settings and all use music or all be silent. Existing clip openings, closings and fades are kept.</p>
  {busy&&<progress aria-label="Journey stitch progress" max={1} value={progress}/>} {notice&&<p role="status">{notice}</p>}{error&&<p className="mini-alert" role="alert">{error}</p>}
 </details>;
}
