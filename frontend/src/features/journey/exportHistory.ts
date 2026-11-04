import type {JourneyHistory,ShipSegment} from './types.ts';
import type {ExportCombat,CombatRow} from './exportModel.ts';
export type ExportHistoryPage={kind:'visits';history:JourneyHistory&{visit_offset:number};combat:ExportCombat;ship_cursor:string|null;combat_cursor:string|null;next_cursor:string|null;snapshot_at:string};
type Attachment={kind:'ships'|'combat';rows:(ShipSegment|CombatRow)[];total:number;available?:boolean;next_cursor:string|null};
type Fetcher=<T>(path:string,options?:RequestInit)=>Promise<T>;
export async function* journeyExportPages(fetcher:Fetcher,characterId:number,scope:'all'|'range',query:string,signal:AbortSignal){
 const base=`/journey/characters/${characterId}/export-history`;
 let path=`${base}?${scope==='all'?'scope=all':query+'&scope=range'}`,offset=0,snapshot:string|undefined;
 const seen=new Set<string>();
 while(true){
  if(signal.aborted)throw new DOMException('Export cancelled','AbortError');
  if(seen.has(path))throw new Error('The history cursor did not advance. Export stopped without skipping visits.');seen.add(path);
  const page=await fetcher<ExportHistoryPage>(path,{signal});
  if(page.kind!=='visits'||page.history.visit_offset!==offset||(snapshot&&snapshot!==page.snapshot_at))throw new Error('The journey snapshot changed. Start a new export; saved clips remain available.');
  snapshot=page.snapshot_at;
  const collect=async(kind:'ships'|'combat',cursor:string|null)=>{
   const rows:Attachment['rows']=[],visited=new Set<string>();
   while(cursor){
    if(visited.has(cursor))throw new Error('An export data cursor did not advance.');visited.add(cursor);
    const data=await fetcher<Attachment>(`${base}?cursor=${encodeURIComponent(cursor)}`,{signal});
    if(data.kind!==kind||(kind==='combat'&&data.available===false))throw new Error('Export data access changed. Saved clips remain available.');
    rows.push(...data.rows);cursor=data.next_cursor;
   }return rows;
  };
  const [ships,combat]=await Promise.all([collect('ships',page.ship_cursor),collect('combat',page.combat_cursor)]);
  page.history.ship_segments=page.history.ship_segments.concat(ships as ShipSegment[]);page.combat.rows=page.combat.rows.concat(combat as CombatRow[]);
  if(page.history.ship_segments.length!==page.history.ship_segment_count||page.combat.rows.length!==page.combat.total)throw new Error('Stored export records changed while loading. Export stopped; saved clips remain available.');
  page.history.ship_segments_truncated=false;page.combat.truncated=false;
  if(!page.history.visits.length){if(page.next_cursor)throw new Error('A journey page was missing visits.');return;}
  yield page;
  offset+=page.history.visits.length;
  if(!page.next_cursor)return;
  path=`${base}?cursor=${encodeURIComponent(page.next_cursor)}`;
 }
}
