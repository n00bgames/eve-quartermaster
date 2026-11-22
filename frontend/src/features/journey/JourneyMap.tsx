import {useEffect, useMemo, useRef, useState} from 'react';
import {fleetLinks} from './fleetGeometry';
import type {JourneyHistory,FleetPosition} from './types';
import type {Context, JourneySystem, Visit} from './types';
import {projectSystems, visitCounts} from './replay';
import {securityColor} from '../navigation/atlasTypes';
import {useJourneyMapView} from './useJourneyMapView';

export function JourneyMap({systems, visits, selected, onSelect, context, fleet}: {fleet?:{history:JourneyHistory;positions:FleetPosition[];focusSystem?:number;activePilot?:number;followRequest?:number};systems: JourneySystem[]; visits: Visit[]; selected: number | null; onSelect: (id: number) => void; context: Context | null}) {
  const svg = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({width: 1000, height: 560});
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setSize({width: Math.max(260, entry.contentRect.width), height: Math.max(220, entry.contentRect.height)}));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const points = useMemo(() => projectSystems(systems, size.width, size.height), [systems, size]);
  const index = useMemo(() => new Map(points.map(p => [p.system.system_id, p])), [points]);
  const counts = useMemo(() => visitCounts(visits), [visits]);
  const current = fleet?.focusSystem ?? visits[visits.length - 1]?.system_id;
  const currentPoint = current === undefined ? null : index.get(current) ?? null;
  const {view, dragging, following, fit, zoom, focus, center, toggleFollow, handlers} = useJourneyMapView(svg, size, onSelect, currentPoint);
  useEffect(()=>{if(fleet?.followRequest&&!following)toggleFollow();},[fleet?.followRequest]);
  const pairs = useMemo(() => {
    if(fleet)return fleetLinks(visits,fleet.history.fleet!.owners,fleet.history.fleet!.seeds);
    const links = new Map<string, {a: number; b: number; gap: boolean;pilot_id?:number}>();
    for (let i = 1; i < visits.length; i++) {
      const a = visits[i - 1].system_id, b = visits[i].system_id;
      if (a !== b) links.set(`${Math.min(a, b)}:${Math.max(a, b)}:${visits[i].gap_before}`, {a, b, gap: visits[i].gap_before});
    }
    return [...links.values()];
  }, [visits, fleet]);
  const selectedPoint = selected === null ? null : index.get(selected);
  return <div className="journey-map-wrap">
    <div className="journey-map-tools"><span>NEW EDEN / {fleet?'MY FLEET':'PERSONAL FLIGHT LOG'}</span><div>
      <button type="button" aria-label="Zoom journey map in" onClick={() => zoom(1.35)}>+</button>
      <output className="journey-map-zoom" aria-label="Journey map zoom">{Math.round(view.scale * 100)}%</output>
      <button type="button" aria-label="Zoom journey map out" onClick={() => zoom(1 / 1.35)}>−</button>
      <button type="button" aria-pressed={following} disabled={!currentPoint && !following} onClick={toggleFollow}
        title="Zoom to and follow the current replay or latest recorded position">Zoom-and-Follow</button>
      <button type="button" disabled={!currentPoint} onClick={center} title="Center the current position without changing zoom">Center</button>
      <button type="button" onClick={fit}>Fit journey</button>
      <button type="button" disabled={!selectedPoint} onClick={() => {if (selectedPoint) focus(selectedPoint);}}>Focus selected</button>
    </div></div>
    <svg ref={svg} className={`journey-map${dragging ? ' is-dragging' : ''}`} viewBox={`0 0 ${size.width} ${size.height}`} role="group" tabIndex={0}
      aria-label="Private journey map. Drag to pan; scroll or pinch to zoom. Arrow keys pan, plus and minus zoom, Home fits the journey. Select a visited system for context." {...handlers}>
      <defs><pattern id="journey-grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M 50 0 L 0 0 0 50" fill="none" stroke="#152b3c" strokeWidth=".6"/></pattern><radialGradient id="journey-nebula"><stop stopColor="#18384b"/><stop offset="1" stopColor="#07111e"/></radialGradient></defs>
      <rect width={size.width} height={size.height} fill="url(#journey-nebula)" pointerEvents="none"/><rect width={size.width} height={size.height} fill="url(#journey-grid)" pointerEvents="none"/>
      <g data-journey-viewport="" transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
        {pairs.map(({a, b, gap, pilot_id},i) => {
          const p = index.get(a), q = index.get(b);
          return p && q ? <line key={`${pilot_id??''}:${a}:${b}:${gap}:${i}`} style={fleet?{stroke:fleet.history.fleet!.pilots.find(p=>p.character_id===pilot_id)?.color}:undefined} x1={p.x} y1={p.y} x2={q.x} y2={q.y} className={gap ? 'journey-link journey-gap' : 'journey-link'} vectorEffect="non-scaling-stroke"/> : null;
        })}
        {points.filter(p => counts.has(p.system.system_id)).map(p => {
          const s = p.system, n = counts.get(s.system_id) ?? 0;
          const combat = context?.combat.systems[String(s.system_id)], assets = context?.assets.systems[String(s.system_id)];
          const left = p.x * view.scale + view.x > size.width - 150;
          return <g key={s.system_id} transform={`translate(${p.x} ${p.y})`} data-journey-system={s.system_id} role="button" tabIndex={0}
            aria-label={`${s.name}: ${n} observed visits`} onClick={event => {if (event.detail === 0) onSelect(s.system_id);}}
            onKeyDown={event => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); onSelect(s.system_id);}}} className="journey-star">
            <g transform={`scale(${1 / view.scale})`}>
              {s.system_id === current && <circle r="19" className="journey-current" vectorEffect="non-scaling-stroke"/>}
              {s.system_id === selected && <circle r="24" fill="none" stroke="#f0c35d" vectorEffect="non-scaling-stroke"/>}
              <circle r={Math.min(13, 5 + Math.log2(n + 1) * 2)} fill={securityColor(s.security)} stroke="#e0f6ff" strokeWidth=".7" vectorEffect="non-scaling-stroke"/>
              {(!fleet||size.width>550||s.system_id===current||s.system_id===selected||fleet.positions.some(v=>v.visit.system_id===s.system_id))&&<text x={left ? -19 : 19} textAnchor={left ? 'end' : 'start'} y="-10" className="journey-star-name">{s.name}</text>}
              {(size.width > 550 || s.system_id === current || s.system_id === selected) && <text x={left ? -19 : 19} textAnchor={left ? 'end' : 'start'} y="8" className="journey-star-count">{n} visit{n === 1 ? '' : 's'}{combat && combat.kills + combat.losses ? ` · ${combat.kills}K/${combat.losses}L` : ''}{assets?.quantity ? ` · ${assets.quantity.toLocaleString()} items` : ''}</text>}
              <title>{s.name} · {s.region ?? 'Unknown region'} · {n} observations</title>
            </g>
          </g>;
        })}
        {fleet?.positions.map(position=>{
          const p=index.get(position.visit.system_id),pilot=fleet.history.fleet!.pilots.find(v=>v.character_id===position.pilot_id);
          if(!p||!pilot)return null;
          const group=fleet.positions.filter(v=>v.visit.system_id===position.visit.system_id),slot=group.findIndex(v=>v.pilot_id===position.pilot_id),offset=(slot-(group.length-1)/2)*Math.min(20,80/group.length);
          const left=p.x*view.scale+view.x+offset>size.width-140;
          return <g key={`pilot:${pilot.character_id}`} data-fleet-marker={pilot.character_id} transform={`translate(${p.x} ${p.y})`} pointerEvents="none"><g transform={`scale(${1/view.scale}) translate(${offset} 25)`}>
            <path d="M 0 -7 L 7 0 L 0 7 L -7 0 Z" fill={pilot.color} stroke={pilot.character_id===fleet.activePilot?'#fff':'#07111e'} strokeWidth="2"/>
            <text x={left?-10:10} textAnchor={left?'end':'start'} y={16+Math.min(slot,4)*15} fill={pilot.color} fontSize="11" paintOrder="stroke" stroke="#07111e" strokeWidth="3">{slot<4?(pilot.name.length>22?pilot.name.slice(0,20)+'…':pilot.name):slot===4?`+${group.length-4} pilots`:''}</text>
            <title>{pilot.name}: last observed in {p.system.name}</title>
          </g></g>;
        })}
      </g>
      {!points.length && <text x={size.width / 2} y={size.height / 2} textAnchor="middle" fill="#b2c4d5">{systems.length ? 'SDE coordinates unavailable — use the visit log below' : 'Your journey begins with the first online location sample'}</text>}
    </svg>
    <div className="journey-map-legend"><span>● Current replay position</span><span role="status">{following ? currentPoint ? 'Following current position' : 'Following paused: current system coordinates unavailable' : 'Free map view'}</span><span>Lines = observed system changes, not verified gate paths</span><span>Dashed = collection gap; intermediate systems unknown</span><span>X/Z projection · drag to pan · scroll or pinch to zoom</span></div>
  </div>;
}
