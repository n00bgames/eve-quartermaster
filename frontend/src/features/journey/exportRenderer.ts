import {ENGAGEMENT_PAGE_SIZE,exportFrame,hullAt,utcStamp,type ExportPlan} from './exportModel';

type Ctx=OffscreenCanvasRenderingContext2D;
const W=1920,H=1080,MX=50,MY=205,MW=1220,MH=650;
const ink='#e4f2fa',muted='#8dabbc',cyan='#55c8ef';
function text(c:Ctx,value:string,x:number,y:number,size=24,color=ink,max=1800){c.font=`${size}px sans-serif`;c.fillStyle=color;c.fillText(value,x,y,max);}
function panel(c:Ctx,x:number,y:number,w:number,h:number){c.fillStyle='#0d1b29';c.fillRect(x,y,w,h);c.strokeStyle='#294359';c.strokeRect(x,y,w,h);}
function ellipsis(c:Ctx,value:string,width:number){let out=value;while(out.length&&c.measureText(out+'…').width>width)out=out.slice(0,-1);return out===value?out:out+'…';}

export function renderExportFrame(c:Ctx,plan:ExportPlan,time:number,logo:ImageBitmap,version:string){
 const {phase,progress,camera}=exportFrame(plan,time),index=phase.index,visit=plan.visits[index],system=plan.history.systems.find(s=>s.system_id===visit.system_id);
 const overview=phase.kind==='overview'||phase.kind==='end';
 const rows=plan.engagements[index],page=phase.page??0,pageRows=rows.slice(page*ENGAGEMENT_PAGE_SIZE,(page+1)*ENGAGEMENT_PAGE_SIZE);
 const stamp=phase.kind==='engagement'?pageRows[0].time:phase.kind==='overview'||phase.kind==='zoom'?plan.clipStartAt??visit.first_seen_at:phase.kind==='end'||phase.kind==='outro'?plan.clipEndAt??visit.last_seen_at:new Date(Date.parse(visit.first_seen_at)+(Date.parse(visit.last_seen_at)-Date.parse(visit.first_seen_at))*progress).toISOString();
 const hull=hullAt(plan,index,stamp);
 c.fillStyle='#060e18';c.fillRect(0,0,W,H);
 // The supplied EQM banner is rendered intact; no remote images can taint the canvas.
 c.drawImage(logo,45,18,300,150);
 text(c,plan.partNumber?`MY JOURNEY · PART ${plan.partNumber}`:'MY JOURNEY',385,72,38);text(c,plan.history.character.name,385,112,25,muted,900);
 text(c,`EXPORTED ${utcStamp(plan.exportedAt)}`,1335,68,21,muted,540);
 text(c,`EVE QUARTERMASTER v${version}`,1335,107,19,muted);
 panel(c,MX,MY,MW,MH);
 c.save();c.beginPath();c.rect(MX+1,MY+1,MW-2,MH-2);c.clip();
 const screen=(p:{x:number;y:number})=>({x:MX+MW/2+(p.x-camera.x)*camera.scale,y:MY+MH/2+(p.y-camera.y)*camera.scale});
 const points=new Map(plan.points.map(p=>[p.system.system_id,p]));
 const reached=phase.kind==='overview'?0:phase.kind==='end'||phase.kind==='outro'?plan.visits.length-1:index;
 const route=(active:boolean)=>{
  for(let i=1;i<plan.visits.length;i++){
   if(active&&i>reached)break;
   const a=points.get(plan.visits[i-1].system_id),b=points.get(plan.visits[i].system_id);if(!a||!b)continue;
   const ap=screen(a),bp=screen(b);c.beginPath();c.moveTo(ap.x,ap.y);c.lineTo(bp.x,bp.y);c.strokeStyle=active?cyan:'#203447';c.lineWidth=active?3:2;c.setLineDash(plan.visits[i].gap_before?[8,10]:[]);c.stroke();
  }c.setLineDash([]);
 };route(false);route(true);
 for(const point of plan.points){const p=screen(point);if(p.x<MX-80||p.y<MY-40||p.x>MX+MW+80||p.y>MY+MH+40)continue;
  const current=point.system.system_id===visit.system_id&&!overview;
  c.beginPath();c.arc(p.x,p.y,current?11:5,0,Math.PI*2);c.fillStyle=current?'#ffffff':cyan;c.fill();
  if(current){c.beginPath();c.arc(p.x,p.y,20,0,Math.PI*2);c.strokeStyle=cyan;c.lineWidth=2;c.stroke();}
  // Labels and markers stay the same pixel size while the camera moves.
  c.font=`${current?26:20}px sans-serif`;const label=ellipsis(c,point.system.name,230),width=c.measureText(label).width;
  const labelX=Math.max(MX+10,Math.min(p.x+19,MX+MW-width-10)),labelY=Math.max(MY+30,Math.min(p.y-3,MY+MH-10));
  c.fillStyle='#060e18';c.fillRect(labelX-5,labelY-24,width+10,31);text(c,label,labelX,labelY,current?26:20,current?ink:muted);
 }
 c.restore();
 text(c,`${Math.round(camera.scale*100)}% · ${overview?'FULL JOURNEY':phase.kind==='engagement'?'ENGAGEMENT PAUSE':'OBSERVED ROUTE'}`,MX+20,MY+MH+40,20,muted);
 text(c,'Dashed links mark observation gaps. Lines do not imply a verified gate route.',MX+20,MY+MH+72,18,muted);
 panel(c,1310,MY,560,MH);
 text(c,overview?'JOURNEY OVERVIEW':phase.kind==='engagement'?'IMPORTED ENGAGEMENT':'SYSTEM VISIT',1340,249,20,cyan);
 text(c,system?.name??`System ${visit.system_id}`,1340,299,36,ink,500);
 text(c,plan.partNumber?`Journey visit ${plan.visitNumbers?.[index]}${plan.continued&&index===0?' · continued':''}`:`Visit ${index+1} of ${plan.visits.length}`,1340,340,22,muted);
 text(c,utcStamp(stamp),1340,385,22);
 text(c,'RECORDED SHIP TYPE',1340,428,17,muted);
 text(c,hull?.ship_name??'Unknown hull',1340,465,29,ink,500);
 const located=points.has(visit.system_id);
 if(!located)text(c,'Coordinates unavailable · camera held',1340,500,19,muted,500);
 if(phase.kind==='engagement'){
  const kills=rows.filter(r=>r.side==='kill').length,losses=rows.filter(r=>r.side==='loss').length;
  text(c,`KILLS: ${kills} / LOSSES: ${losses}`,1340,540,26);
  text(c,`Page ${page+1} / ${Math.ceil(rows.length/ENGAGEMENT_PAGE_SIZE)} · ${rows.length} imported records`,1340,573,18,muted);
  pageRows.forEach((r,i)=>{const y=607+i*40;text(c,r.side==='loss'?'LOSS':'KILL',1340,y,19,r.side==='loss'?'#ff7777':'#64e2ad');text(c,r.ship??'Unknown hull',1407,y,20,ink,420);text(c,utcStamp(r.time),1407,y+17,14,muted,420);});
 }else{
  text(c,overview?`${plan.visits.length} visits · ${plan.points.length} mapped systems`:'One second per recorded system visit',1340,550,22,muted,500);
  text(c,overview?'Whole journey at 100%':'Ship changes stay inside the same visit',1340,590,21,muted,500);
  if(rows.length&&!overview&&phase.kind!=='outro')text(c,`${rows.length} combat records · pause follows`,1340,633,22,cyan,500);
 }
 text(c,'Imported records only · selected pilot involvement',1340,848,17,muted,500);
 c.fillStyle='#21394a';c.fillRect(50,964,1820,5);c.fillStyle=cyan;c.fillRect(50,964,1820*Math.min(1,time/plan.duration),5);
 text(c,`${utcStamp(plan.clipStartAt??plan.visits[0].first_seen_at)}  →  ${utcStamp(plan.clipEndAt??plan.visits[plan.visits.length-1].last_seen_at)}`,50,1010,21,muted,1400);
 text(c,`${Math.min(plan.duration,time).toFixed(1)} / ${plan.duration.toFixed(1)} s`,1630,1010,21,muted,240);
 const note=!plan.combatAvailable?'Combat layer unavailable with current permissions.':plan.unmatched?`${plan.unmatched} imported records outside confirmed / continuous visits are not assigned.`:'Combat pauses show existing imports; missing records do not establish no engagement.';
 text(c,note,50,1045,18,muted);
}
