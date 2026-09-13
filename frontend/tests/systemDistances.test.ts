import assert from "node:assert/strict";
import test from "node:test";
import { AU_METRES, distanceAU, roughWarpSeconds, formatDistance } from "../src/features/navigation/systemDistances.ts";
import type { SystemObject } from "../src/features/navigation/systemDistances.ts";
const object = (x: number, y: number, z: number): SystemObject => ({object_id: "1", name: "test", kind: "planet", source: "sde", position: {x,y,z}});
test("three-dimensional distance in AU, symmetric and translation invariant", () => {
  assert.equal(distanceAU(object(0,0,0), object(3*AU_METRES,4*AU_METRES,0)), 5);
  assert.equal(distanceAU(object(3*AU_METRES,4*AU_METRES,0), object(0,0,0)), 5);
  assert.equal(distanceAU(object(AU_METRES,AU_METRES,AU_METRES), object(4*AU_METRES,5*AU_METRES,AU_METRES)), 5);
});
test("unavailable coordinates never become an apparent zero-distance warp", () => {
  assert.equal(distanceAU(undefined, object(0,0,0)), null);
  assert.equal(distanceAU({...object(0,0,0), position: null}, object(0,0,0)), null);
  assert.equal(distanceAU(object(NaN,0,0), object(0,0,0)), null);
});
test("reference time includes only constant-speed travel plus align", () => {
  assert.equal(roughWarpSeconds(30,"3","10"),20);
  assert.equal(roughWarpSeconds(30,"3","0"),10);
  assert.equal(roughWarpSeconds(0,"3","10"),0);
});
test("invalid and empty inputs suppress the estimate", () => {
  for (const [speed,align] of [["0","10"],["-1","0"],["3","-1"],["","10"],["3",""],["Infinity","0"],["abc","0"]]) assert.equal(roughWarpSeconds(30,speed,align),null);
  assert.equal(roughWarpSeconds(null,"3","10"),null);
  assert.equal(roughWarpSeconds(100,"1e-320","10"),null);
});
test("nearby objects do not round to a misleading zero", () => {
  assert.equal(formatDistance(1e-8),"<0.000001 AU");
  assert.equal(formatDistance(null),"Position unavailable");
});
