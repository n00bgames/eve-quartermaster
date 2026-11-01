import {useEffect,useMemo,useRef,useState} from 'react';
import type {Context,JourneySystem,Visit} from './types';
import {projectSystems,visitCounts} from './replay';
import {securityColor} from '../navigation/atlasTypes';

export function JourneyMap({systems,visits,selected,onSelect,context}:{systems:JourneySystem[];visits:Visit[];selected:number|null;onSelect:(id:number)=>void;context:Context|null}){
 const svg=useRef<SVGSVGElement>(null);const [size,setSize]=useState({width:1000,height:560});
 useEffect(()=>{const element=svg.current;if(!element)return;const observer=new ResizeObserver(([entry])=>setSize({width:Math.max(260,entry.contentRect.width),height:Math.max(220,entry.contentRect.height)}));observer.observe(element);return()=>observer.disconnect();},[]);
 useEffect(()=>setView({scale:1,x:0,y:0}),[size.width,size.height]);
 const [view,setView]=useState({scale:1,x:0,y:0});
 const drag=useRef<{x:number;y:number;startX:number;startY:number;moved:boolean}|null>(null);
 const points=useMemo(()=>projectSystems(systems,size.width,size.height),[systems,size]);const index=new Map(points.map(p=>[p.system.system_id,p]));
 const counts=visitCounts(visits),current=visits[visits.length-1]?.system_id;
 const pairs=new Map<string,{a:number;b:number;gap:boolean}>();
 for(let i=1;i<visits.length;i++){const a=visits[i-1].system_id,b=visits[i].system_id;if(a!==b)pairs.set(`${Math.min(a,b)}:${Math.max(a,b)}:${visits[i].gap_before}`,{a,b,gap:visits[i].gap_before});}
 function zoom(factor:number){setView(v=>{const scale=Math.max(.5,Math.min(10,v.scale*factor));return {scale,x:size.width/2-(size.width/2-v.x)*scale/v.scale,y:size.height/2-(size.height/2-v.y)*scale/v.scale};});}
 return <div className="journey-map-wrap"><div className="journey-map-tools"><span>NEW EDEN / PERSONAL FLIGHT LOG</span><div><button type="button" aria-label="Zoom journey map in" onClick={()=>zoom(1.35)}>+</button><button type="button" aria-label="Zoom journey map out" onClick={()=>zoom(1/1.35)}>−</button><button type="button" onClick={()=>setView({scale:1,x:0,y:0})}>Fit journey</button></div></div>
 <svg ref={svg} className="journey-map" viewBox={`0 0 ${size.width} ${size.height}`} role="group" aria-label="Private journey map, select a visited system" onPointerDown={e=>{drag.current={x:e.clientX,y:e.clientY,startX:view.x,startY:view.y,moved:false};if(e.target===e.currentTarget)e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{const d=drag.current;if(!d||!e.buttons)return;const r=e.currentTarget.getBoundingClientRect();if(Math.abs(e.clientX-d.x)+Math.abs(e.clientY-d.y)>4)d.moved=true;if(d.moved)setView(v=>({...v,x:d.startX+(e.clientX-d.x)*size.width/r.width,y:d.startY+(e.clientY-d.y)*size.height/r.height}));}} onPointerUp={()=>{if(drag.current&&!drag.current.moved)drag.current=null;}}>
 <defs><pattern id="journey-grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M 50 0 L 0 0 0 50" fill="none" stroke="#152b3c" strokeWidth=".6"/></pattern><radialGradient id="journey-nebula"><stop stopColor="#18384b"/><stop offset="1" stopColor="#07111e"/></radialGradient></defs>
 <rect width={size.width} height={size.height} fill="url(#journey-nebula)" pointerEvents="none"/><rect width={size.width} height={size.height} fill="url(#journey-grid)" pointerEvents="none"/>
 <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
 {[...pairs.values()].map(({a,b,gap})=>{const p=index.get(a),q=index.get(b);return p&&q?<line key={`${a}:${b}:${gap}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} className={gap?'journey-link journey-gap':'journey-link'} vectorEffect="non-scaling-stroke"/>:null;})}
 {points.filter(p=>counts.has(p.system.system_id)).map(p=>{const s=p.system,n=counts.get(s.system_id)??0,combat=context?.combat.systems[String(s.system_id)],assets=context?.assets.systems[String(s.system_id)];return <g key={s.system_id} transform={`translate(${p.x} ${p.y})`} role="button" tabIndex={0} aria-label={`${s.name}: ${n} observed visits`} onClick={e=>{e.stopPropagation();if(drag.current?.moved){drag.current=null;return;}onSelect(s.system_id);}} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(s.system_id);}}} className="journey-star">
 {s.system_id===current&&<circle r="19" className="journey-current" vectorEffect="non-scaling-stroke"/>}{s.system_id===selected&&<circle r="24" fill="none" stroke="#f0c35d" vectorEffect="non-scaling-stroke"/>}
 <circle r={Math.min(13,5+Math.log2(n+1)*2)} fill={securityColor(s.security)} stroke="#e0f6ff" strokeWidth=".7" vectorEffect="non-scaling-stroke"/>
 <text x={p.x>size.width-125?-19:19} textAnchor={p.x>size.width-125?'end':'start'} y="-10" className="journey-star-name">{s.name}</text>{(size.width>550||s.system_id===current||s.system_id===selected)&&<text x={p.x>size.width-125?-19:19} textAnchor={p.x>size.width-125?'end':'start'} y="8" className="journey-star-count">{n} visit{n===1?'':'s'}{combat&&combat.kills+combat.losses?` · ${combat.kills}K/${combat.losses}L`:''}{assets?.quantity?` · ${assets.quantity.toLocaleString()} items`:''}</text>}
 <title>{s.name} · {s.region??'Unknown region'} · {n} observations</title></g>;})}</g>
 {!points.length&&<text x={size.width/2} y={size.height/2} textAnchor="middle" fill="#b2c4d5">{systems.length?'SDE coordinates unavailable — use the visit log below':'Your journey begins with the first online location sample'}</text>}
 </svg><div className="journey-map-legend"><span>● Current replay position</span><span>Lines = observed system changes, not verified gate paths</span><span>Dashed = collection gap; intermediate systems unknown</span><span>X/Z projection · drag to pan</span></div></div>;
}
