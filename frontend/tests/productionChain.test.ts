import test from "node:test";
import assert from "node:assert/strict";
import { productionChain } from "../src/features/industry/productionChain.ts";
const material = (type_id: number) => ({ type_id, name: `Material ${type_id}`, quantity: 1, volume: 1 });
const recipe = (id: number, output: number, inputs: number[]) => ({ id, name: `Recipe ${id}`, cycle_time: 3600, output: material(output), inputs: inputs.map(material) });
const recipes = [recipe(1,10,[1]),recipe(2,20,[10]),recipe(3,30,[20]),recipe(4,31,[20]),recipe(5,40,[30,31,10])];
test("P4 fed from P2 deduplicates shared feed and preserves direct P1", () => {
  const result = productionChain(recipes, recipes[4], 2);
  assert.equal(result.tier,4);
  assert.deepEqual(result.inputs.map(i=>i.type_id),[10,20]);
  assert.equal(result.stages.length,3);
});
test("lower feed tiers expand additional stages, direct mode stays compatible", () => {
  assert.deepEqual(productionChain(recipes,recipes[4],0).inputs.map(i=>i.type_id),[1]);
  assert.equal(productionChain(recipes,recipes[4],0).stages.length,5);
  assert.deepEqual(productionChain(recipes,recipes[4],null).inputs.map(i=>i.type_id),[30,31,10]);
});
test("cyclic catalogs fail explicitly", () => {
  assert.throws(()=>productionChain([recipe(1,10,[20]),recipe(2,20,[10])],recipe(1,10,[20]),0),/cycle/);
});
