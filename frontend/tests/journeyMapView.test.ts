import test from 'node:test';
import assert from 'node:assert/strict';
import {fittedView, panView, pinchView, zoomView} from '../src/features/journey/mapView.ts';

test('zoom keeps the cursor world point stationary after an existing pan', () => {
  const before = {scale: 2, x: -140, y: 35}, cursor = {x: 317, y: 128};
  const next = zoomView(before, 1.35, cursor);
  assert.equal((cursor.x - before.x) / before.scale, (cursor.x - next.x) / next.scale);
  assert.equal((cursor.y - before.y) / before.scale, (cursor.y - next.y) / next.scale);
});

test('zoom bounds preserve the anchor and avoid drift on repeated capped gestures', () => {
  const anchor = {x: 250, y: 150};
  const maximum = zoomView(fittedView(), 1000, anchor);
  assert.equal(maximum.scale, 80);
  assert.deepEqual(zoomView(maximum, 2, anchor), maximum);
  const minimum = zoomView(fittedView(), .00001, anchor);
  assert.equal(minimum.scale, .5);
  assert.deepEqual(zoomView(minimum, .5, anchor), minimum);
});

test('pan uses SVG viewport coordinates without multiplying movement by zoom', () => {
  assert.deepEqual(panView({scale: 8, x: -500, y: 200}, {x: 10, y: 30}, {x: 110, y: -20}), {scale: 8, x: -400, y: 150});
});

test('pinch zoom anchors its original midpoint and follows both fingers', () => {
  const start = {scale: 2, x: -50, y: -30};
  const next = pinchView(start, {x: 100, y: 100}, 100, {x: 120, y: 140}, 200);
  assert.deepEqual(next, {scale: 4, x: -180, y: -120});
  assert.equal((120 - next.x) / next.scale, (100 - start.x) / start.scale);
  assert.ok(Object.values(pinchView(start, {x: 0, y: 0}, 0, {x: 0, y: 0}, 1)).every(Number.isFinite));
});
