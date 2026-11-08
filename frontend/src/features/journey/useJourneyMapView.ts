import {useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type RefObject} from 'react';
import {centeredView, fittedView, panView, pinchView, zoomView, type MapPoint, type MapView} from './mapView';

type Pointer = MapPoint & {clientX: number; clientY: number};
type Gesture = {view: MapView; start: MapPoint; clientX: number; clientY: number; distance?: number};

export function useJourneyMapView(svg: RefObject<SVGSVGElement | null>, size: {width: number; height: number}, onSelect: (id: number) => void, followPoint: MapPoint | null = null) {
  const [view, setView] = useState<MapView>(fittedView);
  const [dragging, setDragging] = useState(false);
  const [following, setFollowing] = useState(false);
  const currentView = useRef(view);
  const pointers = useRef(new Map<number, Pointer>());
  const gesture = useRef<Gesture | null>(null);
  const moved = useRef(false);
  const candidate = useRef<number | null>(null);

  function update(next: MapView) {currentView.current = next; setView(next);}
  function point(clientX: number, clientY: number): MapPoint {
    const matrix = svg.current?.getScreenCTM();
    const transformed = matrix ? new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse()) : {x: 0, y: 0};
    return {x: transformed.x, y: transformed.y};
  }
  function rebase() {
    const [a, b] = [...pointers.current.values()];
    gesture.current = !a ? null : b
      ? {view: currentView.current, start: {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2}, distance: Math.hypot(b.x - a.x, b.y - a.y), clientX: a.clientX, clientY: a.clientY}
      : {view: currentView.current, start: a, clientX: a.clientX, clientY: a.clientY};
  }
  function fit() {setFollowing(false); update(fittedView()); rebase();}
  function zoom(factor: number) {
    setFollowing(false);
    update(zoomView(currentView.current, factor, {x: size.width / 2, y: size.height / 2}));
    rebase();
  }
  function focus(at: MapPoint) {
    setFollowing(false);
    update(centeredView({...currentView.current, scale: 8}, at, size));
    rebase();
  }

  function center() {
    setFollowing(false);
    if (followPoint) {update(centeredView(currentView.current, followPoint, size)); rebase();}
  }
  function toggleFollow() {
    if (following) {setFollowing(false); return;}
    if (!followPoint) return;
    update(centeredView({...currentView.current, scale: Math.max(8, currentView.current.scale)}, followPoint, size));
    rebase();
    setFollowing(true);
  }

  useEffect(() => {
    if (!following) {update(fittedView()); rebase();}
  }, [size.width, size.height]);
  // Coordinates also change when the projected history grows or the viewport resizes.
  useEffect(() => {
    if (following && followPoint) {update(centeredView(currentView.current, followPoint, size)); rebase();}
  }, [following, followPoint?.x, followPoint?.y, size.width, size.height]);
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      setFollowing(false);
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientHeight : 1);
      update(zoomView(currentView.current, Math.exp(-delta * .0015), point(event.clientX, event.clientY)));
      rebase();
    };
    // React's delegated wheel listener can be passive; the map must consume its own wheel gesture.
    element.addEventListener('wheel', wheel, {passive: false});
    return () => element.removeEventListener('wheel', wheel);
  }, [svg]);

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || pointers.current.size >= 2) return;
    event.preventDefault();
    const at = point(event.clientX, event.clientY);
    if (!pointers.current.size) {
      moved.current = false;
      const star = event.target instanceof Element ? event.target.closest('[data-journey-system]') : null;
      candidate.current = star ? Number(star.getAttribute('data-journey-system')) : null;
    } else {
      moved.current = true;
      candidate.current = null;
    }
    pointers.current.set(event.pointerId, {...at, clientX: event.clientX, clientY: event.clientY});
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
    rebase();
  }
  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!pointers.current.has(event.pointerId) || !gesture.current) return;
    if (event.pointerType === 'mouse' && !event.buttons) {finish(event, true); return;}
    const at = point(event.clientX, event.clientY);
    pointers.current.set(event.pointerId, {...at, clientX: event.clientX, clientY: event.clientY});
    const [a, b] = [...pointers.current.values()], start = gesture.current;
    if (b) {
      moved.current = true;
      setFollowing(false);
      update(pinchView(start.view, start.start, start.distance ?? 1, {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2}, Math.hypot(b.x - a.x, b.y - a.y)));
    } else {
      if (Math.hypot(event.clientX - start.clientX, event.clientY - start.clientY) > 4) moved.current = true;
      if (moved.current) {setFollowing(false); update(panView(start.view, start.start, at));}
    }
  }
  function finish(event: PointerEvent<SVGSVGElement>, cancelled = false) {
    if (!pointers.current.has(event.pointerId)) return;
    const start = gesture.current;
    const withinClick = start && Math.hypot(event.clientX - start.clientX, event.clientY - start.clientY) <= 4;
    const select = !cancelled && pointers.current.size === 1 && !moved.current && withinClick ? candidate.current : null;
    pointers.current.delete(event.pointerId);
    candidate.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    rebase();
    setDragging(pointers.current.size > 0);
    if (select !== null) onSelect(select);
  }
  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.target !== event.currentTarget) return;
    const shifts: Record<string, MapPoint> = {ArrowLeft: {x: 40, y: 0}, ArrowRight: {x: -40, y: 0}, ArrowUp: {x: 0, y: 40}, ArrowDown: {x: 0, y: -40}};
    if (shifts[event.key]) {event.preventDefault(); setFollowing(false); update(panView(currentView.current, {x: 0, y: 0}, shifts[event.key]));}
    else if (event.key === '+' || event.key === '=') {event.preventDefault(); zoom(1.35);}
    else if (event.key === '-') {event.preventDefault(); zoom(1 / 1.35);}
    else if (event.key === '0' || event.key === 'Home') {event.preventDefault(); fit();}
  }
  return {view, dragging, following, fit, zoom, focus, center, toggleFollow, handlers: {onPointerDown, onPointerMove, onPointerUp: (event: PointerEvent<SVGSVGElement>) => finish(event), onPointerCancel: (event: PointerEvent<SVGSVGElement>) => finish(event, true), onLostPointerCapture: (event: PointerEvent<SVGSVGElement>) => finish(event, true), onKeyDown}};
}
