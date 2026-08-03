import type { PointerEvent, WheelEvent } from "react";
import { useRef, useState } from "react";

import { eveSecurityLabel } from "../../lib/evePresentation";
import type { NavigationSystem, OperationalMapAlternateNode, OperationalMapContext, OperationalMapGate, OperationalMapRouteNode, OperationalMapSystem } from "../../types/navigation";
type CoordinateAxis = "x" | "y" | "z";



function coordinateValue(system: NavigationSystem, axis: CoordinateAxis): number | null {

  const value = system[axis];

  return typeof value === "number" ? value : null;

}



function bestRouteMapAxes(systems: NavigationSystem[]): [CoordinateAxis, CoordinateAxis] {

  const axes: CoordinateAxis[] = ["x", "y", "z"];

  const spans = axes.map((axis) => {

    const values = systems.map((system) => coordinateValue(system, axis)).filter((value): value is number => value !== null);

    return { axis, span: values.length > 1 ? Math.max(...values) - Math.min(...values) : 0 };

  }).sort((left, right) => right.span - left.span);

  return [spans[0]?.axis ?? "x", spans[1]?.axis ?? "z"];

}



export function OperationalMap({ title, subtitle, badge, routeSystems, alternateSystems = [], mapContext, selectedKey, onSelectRouteSystem, onSelectAlternateSystem }: { title: string; subtitle: string; badge?: string; routeSystems: OperationalMapRouteNode[]; alternateSystems?: OperationalMapAlternateNode[]; mapContext?: OperationalMapContext; selectedKey?: string | null; onSelectRouteSystem?: (selectedKey: string | null) => void; onSelectAlternateSystem?: (alternateKey: string) => void }) {

  const width = 1000;

  const height = 560;

  const minZoom = 0.65;

  const maxZoom = 4;

  const svgRef = useRef<SVGSVGElement | null>(null);

  const [zoom, setZoom] = useState(1);

  const [pan, setPan] = useState({ x: 0, y: 0 });

  const [dragStart, setDragStart] = useState<{ pointerId: number; x: number; y: number; panX: number; panY: number } | null>(null);



  if (routeSystems.length < 2 || routeSystems.some((system) => system.x == null || system.y == null || system.z == null)) {

    return <section className="operational-map-panel"><h4>{title}</h4><p className="empty">System coordinates are missing. Re-import the SDE map data to render the operational map.</p></section>;

  }



  const routeIds = new Set(routeSystems.map((system) => system.system_id));

  const alternateIds = new Set(alternateSystems.map((system) => system.system_id));

  const systemById = new Map<number, OperationalMapSystem>();

  for (const system of mapContext?.systems ?? []) {

    if (system.x != null && system.y != null && system.z != null) {

      systemById.set(system.system_id, system);

    }

  }

  for (const system of routeSystems) {

    systemById.set(system.system_id, { ...system, on_route: true });

  }

  for (const system of alternateSystems) {

    if (system.x != null && system.y != null && system.z != null && !routeIds.has(system.system_id)) {

      systemById.set(system.system_id, system);

    }

  }



  const mapSystems = Array.from(systemById.values());

  const [horizontalAxis, verticalAxis] = bestRouteMapAxes(mapSystems);

  const rawPoints = mapSystems.map((system) => ({

    system,

    horizontal: coordinateValue(system, horizontalAxis) ?? 0,

    vertical: coordinateValue(system, verticalAxis) ?? 0,

  }));

  const minHorizontal = Math.min(...rawPoints.map((point) => point.horizontal));

  const maxHorizontal = Math.max(...rawPoints.map((point) => point.horizontal));

  const minVertical = Math.min(...rawPoints.map((point) => point.vertical));

  const maxVertical = Math.max(...rawPoints.map((point) => point.vertical));

  const padding = 72;

  const horizontalSpan = maxHorizontal - minHorizontal || 1;

  const verticalSpan = maxVertical - minVertical || 1;

  const points = rawPoints.map((point) => ({

    ...point,

    x: padding + ((point.horizontal - minHorizontal) / horizontalSpan) * (width - padding * 2),

    y: height - padding - ((point.vertical - minVertical) / verticalSpan) * (height - padding * 2),

  }));

  const pointBySystemId = new Map(points.map((point) => [point.system.system_id, point]));

  const routePoints = routeSystems.map((system, index) => ({ point: pointBySystemId.get(system.system_id), routeSystem: system, index })).filter((entry): entry is { point: (typeof points)[number]; routeSystem: OperationalMapRouteNode; index: number } => Boolean(entry.point));

  const pathData = routePoints.map((entry, index) => `${index === 0 ? "M" : "L"} ${entry.point.x.toFixed(2)} ${entry.point.y.toFixed(2)}`).join(" ");

  const gateLines = (mapContext?.stargates ?? []).map((gate) => ({ gate, from: pointBySystemId.get(gate.from_system_id), to: pointBySystemId.get(gate.to_system_id) })).filter((entry): entry is { gate: OperationalMapGate; from: (typeof points)[number]; to: (typeof points)[number] } => Boolean(entry.from && entry.to));

  const alternatePoints = alternateSystems.map((system) => ({ point: pointBySystemId.get(system.system_id), alternateSystem: system })).filter((entry): entry is { point: (typeof points)[number]; alternateSystem: OperationalMapAlternateNode } => Boolean(entry.point));

  const alternateLines = alternatePoints.map((entry) => ({ ...entry, from: pointBySystemId.get(entry.alternateSystem.from_system_id) })).filter((entry): entry is (typeof alternatePoints)[number] & { from: (typeof points)[number] } => Boolean(entry.from));

  const contextPoints = points.filter((point) => !routeIds.has(point.system.system_id) && !alternateIds.has(point.system.system_id));

  const hopCount = mapContext?.gate_hops ?? 0;

  const hopLabel = hopCount === 1 ? "1 gate hop" : `${hopCount} gate hops`;

  const labelStride = zoom < 1.15 ? Math.max(1, Math.ceil(routePoints.length / 9)) : zoom < 1.8 ? Math.max(1, Math.ceil(routePoints.length / 16)) : 1;

  const detailLabels = zoom >= 1.35 || routePoints.length <= 12;

  const segmentLabels = zoom >= 1.75 || routePoints.length <= 10;



  function selectRouteNode(key?: string | null) {

    if (!key || !onSelectRouteSystem) return;

    onSelectRouteSystem(selectedKey === key ? null : key);

  }



  function clampMapZoom(value: number) {

    return Math.max(minZoom, Math.min(maxZoom, value));

  }



  function svgPoint(clientX: number, clientY: number) {

    const rect = svgRef.current?.getBoundingClientRect();

    if (!rect) return { x: width / 2, y: height / 2 };

    return { x: ((clientX - rect.left) / rect.width) * width, y: ((clientY - rect.top) / rect.height) * height };

  }



  function zoomTo(nextZoom: number, focal = { x: width / 2, y: height / 2 }) {

    setZoom((currentZoom) => {

      const clamped = clampMapZoom(nextZoom);

      const ratio = clamped / currentZoom;

      setPan((currentPan) => ({ x: focal.x - (focal.x - currentPan.x) * ratio, y: focal.y - (focal.y - currentPan.y) * ratio }));

      return clamped;

    });

  }



  function resetViewport() {

    setZoom(1);

    setPan({ x: 0, y: 0 });

  }



  function handleWheel(event: WheelEvent<SVGSVGElement>) {

    event.preventDefault();

    const focal = svgPoint(event.clientX, event.clientY);

    zoomTo(zoom * (event.deltaY < 0 ? 1.16 : 0.86), focal);

  }



  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {

    if (event.button !== 0) return;

    event.currentTarget.setPointerCapture(event.pointerId);

    setDragStart({ pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y });

  }



  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {

    if (!dragStart || dragStart.pointerId !== event.pointerId) return;

    const rect = svgRef.current?.getBoundingClientRect();

    if (!rect) return;

    const dx = ((event.clientX - dragStart.x) / rect.width) * width;

    const dy = ((event.clientY - dragStart.y) / rect.height) * height;

    setPan({ x: dragStart.panX + dx, y: dragStart.panY + dy });

  }



  function handlePointerEnd(event: PointerEvent<SVGSVGElement>) {

    if (dragStart?.pointerId === event.pointerId) setDragStart(null);

  }



  return <section className="operational-map-panel"><div className="section-heading compact"><div><h4>{title}</h4><p>{subtitle} · {contextPoints.length.toLocaleString()} context systems · {alternatePoints.length.toLocaleString()} alternates · {hopLabel}{mapContext?.truncated ? " · clipped for performance" : ""}</p></div><div className="operational-map-actions"><span className="version-badge">{Math.round(zoom * 100)}%</span>{badge && <span className="version-badge">{badge}</span>}<button type="button" onClick={() => zoomTo(zoom * 0.8)}>-</button><button type="button" onClick={resetViewport}>Fit</button><button type="button" onClick={() => zoomTo(zoom * 1.25)}>+</button></div></div><svg ref={svgRef} className={`operational-route-map ${dragStart ? "dragging" : ""}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title} onWheel={handleWheel} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerEnd} onPointerCancel={handlePointerEnd}><defs><radialGradient id="operational-map-glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stopColor="#4fb3c7" stopOpacity="0.45" /><stop offset="100%" stopColor="#4fb3c7" stopOpacity="0" /></radialGradient></defs><rect className="operational-map-bg" x="0" y="0" width={width} height={height} rx="12" /><g transform={`translate(${pan.x.toFixed(2)} ${pan.y.toFixed(2)}) scale(${zoom.toFixed(3)})`}>{gateLines.map(({ gate, from, to }) => <line key={`${gate.from_system_id}-${gate.to_system_id}`} className="operational-map-gate-line" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />)}{contextPoints.map((point) => { const security = point.system.security_band ?? "unknown"; return <g key={point.system.system_id} className={`operational-map-context-node ${security}`}><circle cx={point.x} cy={point.y} r={zoom >= 1.8 ? 3.8 : 4.5} /><title>{point.system.name} · {eveSecurityLabel(point.system.security_status)}</title></g>; })}{alternateLines.map(({ alternateSystem, point, from }) => <line key={`alternate-line-${alternateSystem.alternate_key}`} className={`operational-map-alternate-line ${alternateSystem.selected ? "selected" : ""}`} x1={from.x} y1={from.y} x2={point.x} y2={point.y} />)}<path className="operational-route-line" d={pathData} />{alternatePoints.map(({ alternateSystem, point }) => { const security = point.system.security_band ?? "unknown"; return <g key={`alternate-${alternateSystem.alternate_key}`} role="button" tabIndex={0} className={`operational-map-alternate-node ${alternateSystem.selected ? "selected" : ""} ${security}`} onClick={() => onSelectAlternateSystem?.(alternateSystem.alternate_key)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectAlternateSystem?.(alternateSystem.alternate_key); } }}><rect x={point.x - (alternateSystem.selected ? 7 : 5)} y={point.y - (alternateSystem.selected ? 7 : 5)} width={alternateSystem.selected ? 14 : 10} height={alternateSystem.selected ? 14 : 10} transform={`rotate(45 ${point.x} ${point.y})`} /><title>{alternateSystem.label} · {alternateSystem.meta ?? eveSecurityLabel(point.system.security_status)}</title>{(alternateSystem.selected || zoom >= 1.65) && <text x={point.x + 12} y={point.y - 8}>{alternateSystem.label}</text>}</g>; })}{routePoints.slice(1).map((entry, index) => { const previous = routePoints[index]; return <g key={`label-${entry.routeSystem.system_id}`} className="operational-map-segment-label"><line x1={previous.point.x} y1={previous.point.y} x2={entry.point.x} y2={entry.point.y} />{segmentLabels && entry.routeSystem.segment_label && <text x={(previous.point.x + entry.point.x) / 2} y={(previous.point.y + entry.point.y) / 2 - 8}>{entry.routeSystem.segment_label}</text>}</g>; })}{routePoints.map((entry) => { const selected = Boolean(entry.routeSystem.selected_key && selectedKey === entry.routeSystem.selected_key); const security = entry.point.system.security_band ?? "unknown"; const showLabel = selected || entry.index === 0 || entry.index === routePoints.length - 1 || entry.index % labelStride === 0; return <g key={entry.point.system.system_id} role="button" tabIndex={0} className={`operational-map-route-node ${selected ? "selected" : ""} ${showLabel ? "labeled" : "compact"} ${security}`} onClick={() => selectRouteNode(entry.routeSystem.selected_key)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectRouteNode(entry.routeSystem.selected_key); } }}><circle className="operational-map-node-glow" cx={entry.point.x} cy={entry.point.y} r={selected ? 22 : 15} /><circle cx={entry.point.x} cy={entry.point.y} r={selected ? 8 : 6.5} />{showLabel && <text x={entry.point.x + 12} y={entry.point.y - 10}>{entry.routeSystem.label}</text>}{showLabel && detailLabels && <text className="operational-map-node-meta" x={entry.point.x + 12} y={entry.point.y + 8}>{entry.routeSystem.meta ?? eveSecurityLabel(entry.point.system.security_status)}</text>}</g>; })}</g></svg><div className="operational-map-legend"><span><i className="security-dot security-10" /> Highsec</span><span><i className="security-dot security-03" /> Lowsec</span><span><i className="security-dot security-00" /> Nullsec</span><span><i className="operational-map-legend-line" /> Stargates</span><span><i className="operational-map-legend-alternate" /> Alternate cyno</span><span>Wheel to zoom, drag to pan. Labels reveal as you zoom in.</span></div></section>;

}

