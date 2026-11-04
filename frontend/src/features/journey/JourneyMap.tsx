import {useEffect, useMemo, useRef, useState} from 'react';
import type {Context, JourneySystem, Visit} from './types';
import {projectSystems, visitCounts} from './replay';
import {securityColor} from '../navigation/atlasTypes';
import {useJourneyMapView} from './useJourneyMapView';

export function JourneyMap({systems, visits, selected, onSelect, context}: {systems: JourneySystem[]; visits: Visit[]; selected: number | null; onSelect: (id: number) => void; context: Context | null}) {
  const svg = useRef<SVGSVGElement>(null);
  const [size, setSize] = useState({width: 1000, height: 560});
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setSize({width: Math.max(260, entry.contentRect.width), height: Math.max(220, entry.contentRect.height)}));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const {view, dragging, fit, zoom, focus, handlers} = useJourneyMapView(svg, size, onSelect);
  const points = useMemo(() => projectSystems(systems, size.width, size.height), [systems, size]);
  const index = useMemo(() => new Map(points.map(p => [p.system.system_id, p])), [points]);
  const counts = useMemo(() => visitCounts(visits), [visits]);
  const current = visits[visits.length - 1]?.system_id;
  const pairs = useMemo(() => {
    const links = new Map<string, {a: number; b: number; gap: boolean}>();
    for (let i = 1; i < visits.length; i++) {
      const a = visits[i - 1].system_id, b = visits[i].system_id;
      if (a !== b) links.set(`${Math.min(a, b)}:${Math.max(a, b)}:${visits[i].gap_before}`, {a, b, gap: visits[i].gap_before});
    }
    return [...links.values()];
  }, [visits]);
  const selectedPoint = selected === null ? null : index.get(selected);
  return <div className="journey-map-wrap">
    <div className="journey-map-tools"><span>NEW EDEN / PERSONAL FLIGHT LOG</span><div>
      <button type="button" aria-label="Zoom journey map in" onClick={() => zoom(1.35)}>+</button>
      <output className="journey-map-zoom" aria-label="Journey map zoom">{Math.round(view.scale * 100)}%</output>
      <button type="button" aria-label="Zoom journey map out" onClick={() => zoom(1 / 1.35)}>−</button>
      <button type="button" onClick={fit}>Fit journey</button>
      <button type="button" disabled={!selectedPoint} onClick={() => {if (selectedPoint) focus(selectedPoint);}}>Focus selected</button>
    </div></div>
    <svg ref={svg} className={`journey-map${dragging ? ' is-dragging' : ''}`} viewBox={`0 0 ${size.width} ${size.height}`} role="group" tabIndex={0}
      aria-label="Private journey map. Drag to pan; scroll or pinch to zoom. Arrow keys pan, plus and minus zoom, Home fits the journey. Select a visited system for context." {...handlers}>
      <defs><pattern id="journey-grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M 50 0 L 0 0 0 50" fill="none" stroke="#152b3c" strokeWidth=".6"/></pattern><radialGradient id="journey-nebula"><stop stopColor="#18384b"/><stop offset="1" stopColor="#07111e"/></radialGradient></defs>
      <rect width={size.width} height={size.height} fill="url(#journey-nebula)" pointerEvents="none"/><rect width={size.width} height={size.height} fill="url(#journey-grid)" pointerEvents="none"/>
      <g data-journey-viewport="" transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
        {pairs.map(({a, b, gap}) => {
          const p = index.get(a), q = index.get(b);
          return p && q ? <line key={`${a}:${b}:${gap}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} className={gap ? 'journey-link journey-gap' : 'journey-link'} vectorEffect="non-scaling-stroke"/> : null;
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
              <text x={left ? -19 : 19} textAnchor={left ? 'end' : 'start'} y="-10" className="journey-star-name">{s.name}</text>
              {(size.width > 550 || s.system_id === current || s.system_id === selected) && <text x={left ? -19 : 19} textAnchor={left ? 'end' : 'start'} y="8" className="journey-star-count">{n} visit{n === 1 ? '' : 's'}{combat && combat.kills + combat.losses ? ` · ${combat.kills}K/${combat.losses}L` : ''}{assets?.quantity ? ` · ${assets.quantity.toLocaleString()} items` : ''}</text>}
              <title>{s.name} · {s.region ?? 'Unknown region'} · {n} observations</title>
            </g>
          </g>;
        })}
      </g>
      {!points.length && <text x={size.width / 2} y={size.height / 2} textAnchor="middle" fill="#b2c4d5">{systems.length ? 'SDE coordinates unavailable — use the visit log below' : 'Your journey begins with the first online location sample'}</text>}
    </svg>
    <div className="journey-map-legend"><span>● Current replay position</span><span>Lines = observed system changes, not verified gate paths</span><span>Dashed = collection gap; intermediate systems unknown</span><span>X/Z projection · drag to pan · scroll or pinch to zoom</span></div>
  </div>;
}
