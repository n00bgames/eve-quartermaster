import { useEffect, useMemo, useRef, useState } from "react";
import type { Activity, AtlasCatalog, AtlasSystem } from "./atlasTypes";
import { activityValue, securityColor } from "./atlasTypes";

type Point = { system: AtlasSystem; x: number; y: number };
export function AtlasCanvas({ catalog, selected, onSelect, region, overlay, activity, routeIds }: {
  catalog: AtlasCatalog; selected: number | null; onSelect: (id:number)=>void; region: string;
  overlay: string; activity: Activity | null; routeIds: number[];
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({ width: 900, height: 580 });
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [labels, setLabels] = useState(false);
  const [gates, setGates] = useState(true);
  const [hover, setHover] = useState<AtlasSystem | null>(null);
  const drag = useRef<{ x:number; y:number; moved:boolean } | null>(null);
  const points = useMemo(() => {
    const rows = catalog.systems.filter(s => (region === "all" || region === "known" && (s.region_id??Infinity)<11000000 || String(s.region_id) === region)
      && s.x != null && s.z != null && Number.isFinite(s.x) && Number.isFinite(s.z));
    if (!rows.length) return [];
    const xs = rows.map(s=>s.x!), zs = rows.map(s=>s.z!);
    const minX=Math.min(...xs), maxX=Math.max(...xs), minZ=Math.min(...zs), maxZ=Math.max(...zs);
    const scale=Math.min((size.width-70)/(maxX-minX || 1),(size.height-70)/(maxZ-minZ || 1));
    return rows.map(system=>({ system, x: size.width/2+(system.x!-(minX+maxX)/2)*scale,
      y:size.height/2-(system.z!-(minZ+maxZ)/2)*scale }));
  },[catalog,region,size]);
  const index = useMemo(()=>new Map(points.map(p=>[p.system.system_id,p])),[points]);
  useEffect(()=>{ setView({scale:1,x:0,y:0}); },[region]);
  useEffect(()=>{
    const el=canvas.current; if(!el)return;
    const observer=new ResizeObserver(([entry])=>setSize({width:Math.max(260,entry.contentRect.width),height:entry.contentRect.height}));
    observer.observe(el);return()=>observer.disconnect();
  },[]);
  useEffect(()=>{
    const el=canvas.current; if(!el)return;
    const zoom=(event:WheelEvent)=>{
      event.preventDefault();const rect=el.getBoundingClientRect();const x=event.clientX-rect.left,y=event.clientY-rect.top;
      setView(old=>{const scale=Math.max(.5,Math.min(80,old.scale*Math.exp(-event.deltaY*.0015)));const factor=scale/old.scale;
        return {scale,x:x-(x-old.x)*factor,y:y-(y-old.y)*factor};});
    };
    el.addEventListener("wheel",zoom,{passive:false});return()=>el.removeEventListener("wheel",zoom);
  },[]);
  useEffect(()=>{
    const el=canvas.current, ctx=el?.getContext("2d");if(!el||!ctx)return;
    const dpr=window.devicePixelRatio||1;el.width=size.width*dpr;el.height=size.height*dpr;
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle="#070e1b";ctx.fillRect(0,0,size.width,size.height);
    const project=(p:Point)=>[p.x*view.scale+view.x,p.y*view.scale+view.y];
    const line=(a:Point,b:Point)=>{const [x,y]=project(a),[u,v]=project(b);ctx.moveTo(x,y);ctx.lineTo(u,v);};
    if(gates){ctx.beginPath();ctx.strokeStyle="rgba(107,142,183,.2)";ctx.lineWidth=.65;
      for(const [a,b] of catalog.edges){const start=index.get(a),end=index.get(b);if(start&&end&&a<b)line(start,end);}ctx.stroke();}
    ctx.beginPath();ctx.strokeStyle="#7dd3fc";ctx.lineWidth=2;
    routeIds.slice(1).forEach((id,i)=>{const a=index.get(routeIds[i]),b=index.get(id);if(a&&b)line(a,b);});ctx.stroke();
    const regions=new Map<string,{x:number;y:number;n:number}>();
    for(const p of points){const [x,y]=project(p);if(x<0||y<0||x>size.width||y>size.height)continue;
      const s=p.system,active=s.system_id===selected;
      let count:number|null=0;
      if(overlay==="agents")count=s.agent_count;
      else if(overlay==="stations")count=s.station_count;
      else if(overlay!=="security")count=activityValue(activity,s.system_id,overlay as "ship_kills",(s.region_id??0)>=11000000);
      const r=active?6:overlay!=="security"&&count?Math.min(11,2+Math.log2(1+count)):Math.max(1.4,Math.min(3,view.scale*.9));
      ctx.beginPath();ctx.fillStyle=active?"#ffffff":overlay!=="security"?count===null?"#64748b":count>0?"#fbbf24":"#30435d":securityColor(s.security_status);
      ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
      if(active){ctx.strokeStyle="#7dd3fc";ctx.lineWidth=1.4;ctx.beginPath();ctx.arc(x,y,10,0,Math.PI*2);ctx.stroke();}
      if(active||labels&&view.scale>=2||view.scale>12){ctx.fillStyle=active?"#ffffff":"#becde0";ctx.font="11px system-ui";ctx.fillText(s.name,x+8,y-6);}
      const name=s.region_name||"Unknown region", aggregate=regions.get(name)||{x:0,y:0,n:0};aggregate.x+=x;aggregate.y+=y;aggregate.n++;regions.set(name,aggregate);
    }
    if(view.scale<4){ctx.fillStyle="rgba(210,222,239,.72)";ctx.font="12px system-ui";
      const occupied:{x:number;y:number;width:number}[]=[];
      for(const [name,p] of [...regions].sort((a,b)=>b[1].n-a[1].n)){
        const x=p.x/p.n,y=p.y/p.n,width=ctx.measureText(name).width;
        if(occupied.some(box=>Math.abs(box.y-y)<16&&x<box.x+box.width+6&&x+width+6>box.x))continue;
        occupied.push({x,y,width});ctx.fillText(name,x,y);
      }}
  },[points,index,catalog,size,view,selected,labels,gates,overlay,activity,routeIds]);
  function hit(clientX:number,clientY:number){const rect=canvas.current!.getBoundingClientRect(),x=clientX-rect.left,y=clientY-rect.top;
    let best:Point|null=null,distance=100;
    for(const p of points){const d=(p.x*view.scale+view.x-x)**2+(p.y*view.scale+view.y-y)**2;if(d<distance){distance=d;best=p;}}
    return best?.system??null;
  }
  return <div className="atlas-map">
    <div className="atlas-map-tools"><span>NEW EDEN / {points.length.toLocaleString()} systems</span>
      <label><input type="checkbox" checked={gates} onChange={e=>setGates(e.target.checked)}/> Gates</label>
      <label><input type="checkbox" checked={labels} onChange={e=>setLabels(e.target.checked)}/> Names</label>
      <button type="button" onClick={()=>setView({scale:1,x:0,y:0})}>Fit map</button>
      <button type="button" disabled={!selected||!index.has(selected)} onClick={()=>{const p=index.get(selected!)!;setView({scale:8,x:size.width/2-p.x*8,y:size.height/2-p.y*8});}}>Focus selected</button></div>
    <canvas ref={canvas} aria-label="New Eden star map. Select systems using the searchable system field or click a star. Drag to pan; scroll to zoom."
      onPointerDown={e=>{canvas.current?.setPointerCapture(e.pointerId);drag.current={x:e.clientX,y:e.clientY,moved:false};}}
      onPointerMove={e=>{if(drag.current){const dx=e.clientX-drag.current.x,dy=e.clientY-drag.current.y;
        if(Math.abs(dx)+Math.abs(dy)>2)drag.current.moved=true;
        setView(v=>({...v,x:v.x+dx,y:v.y+dy}));drag.current={...drag.current,x:e.clientX,y:e.clientY};}
        else setHover(hit(e.clientX,e.clientY));}}
      onPointerUp={e=>{if(drag.current&&!drag.current.moved){const s=hit(e.clientX,e.clientY);if(s)onSelect(s.system_id);}drag.current=null;}}
      onPointerCancel={()=>{drag.current=null;}} onPointerLeave={()=>setHover(null)}/>
    <div className="atlas-map-caption"><span>{hover?`${hover.name} · Security ${hover.security_status?.toFixed(2)??"unknown"} · ${hover.region_name}`:"Drag to pan · Scroll to zoom · Click a system"}</span>
      <span>{overlay==="security"?<><span style={{color:securityColor(1)}}>● Highsec </span><span style={{color:securityColor(.3)}}>● Lowsec </span><span style={{color:securityColor(-1)}}>● Nullsec</span></>:"Amber: activity / Grey: unknown"}</span></div>
  </div>;
}
