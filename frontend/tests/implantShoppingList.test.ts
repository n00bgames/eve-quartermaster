import assert from "node:assert/strict";
import test from "node:test";

import { buildImplantShoppingList } from "../src/features/characters/implantShoppingList.ts";
import type { JumpCloneImplant } from "../src/types/jumpClones.ts";

function implant(name: string, typeId: number): JumpCloneImplant {
  return { name, type_id: typeId };
}

test("builds an appraisal-ready implant list", () => {
  const result = buildImplantShoppingList([
    implant("High-grade Ascendancy Omega", 1),
    implant("High-grade Ascendancy Alpha", 2),
  ]);

  assert.equal(result.text, "High-grade Ascendancy Alpha 1\nHigh-grade Ascendancy Omega 1");
  assert.equal(result.itemTypeCount, 2);
  assert.equal(result.implantCount, 2);
});

test("combines repeated implants across clones", () => {
  const result = buildImplantShoppingList([
    implant("Eifyr and Co. 'Rogue' Evasive Maneuvering EM-705", 1),
    implant("Eifyr and Co. 'Rogue' Evasive Maneuvering EM-705", 1),
  ]);

  assert.equal(result.text, "Eifyr and Co. 'Rogue' Evasive Maneuvering EM-705 2");
  assert.equal(result.itemTypeCount, 1);
  assert.equal(result.implantCount, 2);
});

test("ignores implants without a usable name", () => {
  const result = buildImplantShoppingList([implant("  ", 1)]);

  assert.equal(result.text, "");
  assert.equal(result.itemTypeCount, 0);
  assert.equal(result.implantCount, 0);
});