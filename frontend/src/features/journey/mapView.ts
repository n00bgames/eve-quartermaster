export type MapPoint = {x: number; y: number};
export type MapView = MapPoint & {scale: number};
export const MIN_MAP_ZOOM = .5;
export const MAX_MAP_ZOOM = 80;
export const fittedView = (): MapView => ({scale: 1, x: 0, y: 0});

// Keep the world point under the cursor/fingers stationary while changing scale.
export function zoomView(view: MapView, factor: number, anchor: MapPoint): MapView {
  const scale = Math.max(MIN_MAP_ZOOM, Math.min(MAX_MAP_ZOOM, view.scale * factor));
  const ratio = scale / view.scale;
  return {scale, x: anchor.x - (anchor.x - view.x) * ratio, y: anchor.y - (anchor.y - view.y) * ratio};
}

export function panView(view: MapView, start: MapPoint, current: MapPoint): MapView {
  return {...view, x: view.x + current.x - start.x, y: view.y + current.y - start.y};
}

export function pinchView(view: MapView, start: MapPoint, startDistance: number, center: MapPoint, distance: number): MapView {
  return panView(zoomView(view, distance / Math.max(1, startDistance), start), start, center);
}

export function centeredView(view: MapView, at: MapPoint, size: {width: number; height: number}): MapView {
  return {...view, x: size.width / 2 - at.x * view.scale, y: size.height / 2 - at.y * view.scale};
}
