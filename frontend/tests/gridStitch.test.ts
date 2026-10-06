import test from "node:test";
import assert from "node:assert/strict";
import { detectGridOverlap, fullGridCrop, pixelCrop, rowSignature, stitchLayout } from "../src/features/hypernet/gridStitch.ts";

function pixels(start: number, height: number, width = 128, repeat = 0, noise = 0) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const row = repeat ? (start + y) % repeat : start + y;
    let seed = Math.imul(row + 1, 2654435761) ^ Math.imul(x + 1, 1597334677);
    seed = Math.imul(seed ^ seed >>> 16, 2246822507);
    const value = ((seed ^ seed >>> 13) >>> 0) % 180 + 30;
    const p = (y * width + x) * 4;
    data[p] = data[p + 1] = data[p + 2] = value + (noise ? (x + y) % (noise * 2 + 1) - noise : 0); data[p + 3] = 255;
  }
  return { width, height, data };
}
test("detects overlapping scroll captures at native pixel offsets, including slight noise", () => {
  assert.equal(detectGridOverlap(rowSignature(pixels(0, 220)), rowSignature(pixels(147, 220))), 73);
  assert.equal(detectGridOverlap(rowSignature(pixels(0, 220)), rowSignature(pixels(147, 180, 128, 0, 2))), 73);
  assert.equal(detectGridOverlap(rowSignature(pixels(0, 220)), rowSignature(pixels(0, 220))), 220);
});
test("rejects generic repeated patterns, flat images, unrelated captures, and mismatched widths", () => {
  assert.equal(detectGridOverlap(rowSignature(pixels(0, 220, 128, 20)), rowSignature(pixels(140, 220, 128, 20))), null);
  const flat = { width: 128, height: 100, data: new Uint8ClampedArray(128 * 100 * 4) };
  assert.equal(detectGridOverlap(rowSignature(flat), rowSignature(flat)), null);
  assert.equal(detectGridOverlap(rowSignature(pixels(0, 100)), rowSignature(pixels(500, 100))), null);
  assert.equal(detectGridOverlap(rowSignature(pixels(0, 100)), rowSignature(pixels(50, 100, 129))), null);
});
test("composition appends only new source rows with no scaling or duplicated overlap", () => {
  assert.deepEqual(stitchLayout([{ width: 800, height: 600, overlap: null }, { width: 800, height: 600, overlap: 200 }, { width: 800, height: 300, overlap: 100 }]), {
    width: 800, height: 1200, placements: [{ sourceY: 0, y: 0, height: 600 }, { sourceY: 200, y: 600, height: 400 }, { sourceY: 100, y: 1000, height: 200 }],
  });
  assert.equal(stitchLayout([{ width: 100, height: 80, overlap: null }, { width: 100, height: 80, overlap: 80 }]).height, 80);
  assert.equal(stitchLayout([{ width: 100, height: 80, overlap: null }, { width: 100, height: 80, overlap: 0 }]).height, 160);
});
test("requires explicit decisions for uncertain joins and validates overlap and dimensions", () => {
  const first = { width: 800, height: 600, overlap: null };
  assert.throws(() => stitchLayout([]), /at least one/);
  assert.throws(() => stitchLayout([first, first]), /Set or detect/);
  for (const overlap of [-1, 601, 1.5, NaN]) assert.throws(() => stitchLayout([first, { ...first, overlap }]), /invalid overlap/);
  assert.throws(() => stitchLayout([first, { width: 801, height: 600, overlap: 100 }]), /same pixel width/);
  assert.throws(() => stitchLayout([{ width: 1, height: 32768, overlap: null }]), /exceeds/);
  assert.throws(() => stitchLayout([{ width: 4000, height: 16001, overlap: null }]), /exceeds/);
});
test("supports a 512-node grid in four columns without reducing source resolution", () => {
  const layout = stitchLayout(Array.from({ length: 32 }, (_, i) => ({ width: 1600, height: i === 31 ? 960 : 1080, overlap: i === 0 ? null : 480 })));
  assert.equal(layout.width, 1600); assert.equal(layout.height, 19560); assert.equal(layout.placements.length, 32);
});
test("percentage crops are clamped to source bounds and retain exact pixel dimensions", () => {
  assert.deepEqual(pixelCrop(1800, 1000, { x: 10, y: 20, width: 80, height: 70 }), { x: 180, y: 200, width: 1440, height: 700 });
  assert.deepEqual(pixelCrop(100, 100, { x: 80, y: 90, width: 100, height: 100 }), { x: 80, y: 90, width: 20, height: 10 });
  assert.deepEqual(pixelCrop(100, 100, fullGridCrop), { x: 0, y: 0, width: 100, height: 100 });
  assert.throws(() => pixelCrop(100, 100, { ...fullGridCrop, width: 0 }), /non-empty/);
  assert.throws(() => pixelCrop(100, 100, { ...fullGridCrop, x: NaN }), /non-empty/);
});
