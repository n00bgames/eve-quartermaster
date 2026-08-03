import assert from "node:assert/strict";
import test from "node:test";

import { bonusValueText, groupBonusProfiles } from "../src/features/characters/skillDogmaPresentation.ts";

test("formats per-level and effective percentage bonuses", () => {
  const bonus = { value: -5, unit_id: 105, text: "reduction to CPU need" };
  assert.equal(bonusValueText(bonus), "5%");
  assert.equal(bonusValueText(bonus, 5), "25%");
});

test("groups affected types that share an identical bonus profile", () => {
  const profiles = groupBonusProfiles([
    { affected_type_id: 1, affected_type_name: "Raven", group_name: "Battleship", bonuses: [{ value: 5, unit_id: 105, text: "bonus to launcher rate of fire" }] },
    { affected_type_id: 2, affected_type_name: "Raven State Issue", group_name: "Battleship", bonuses: [{ value: 5, unit_id: 105, text: "bonus to launcher rate of fire" }] },
    { affected_type_id: 3, affected_type_name: "Rokh", group_name: "Battleship", bonuses: [{ value: 10, unit_id: 105, text: "bonus to hybrid turret optimal range" }] },
  ]);
  assert.equal(profiles.length, 2);
  assert.deepEqual(profiles[0].names, ["Raven", "Raven State Issue"]);
  assert.deepEqual(profiles[1].names, ["Rokh"]);
});
