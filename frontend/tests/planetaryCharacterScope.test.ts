import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import { scopePlanetaryCharacters } from "../src/features/industry/planetaryCharacterScope.ts";
import type { PlanetaryIndustryPayload } from "../src/types/planetaryIndustry.ts";

test("PI groups keep report and export payloads consistent with selected pilots", () => {
  const fixture = JSON.parse(fs.readFileSync(new URL("./fixtures/planetary-shortage-input.v1.json", import.meta.url), "utf8")) as PlanetaryIndustryPayload;
  const sample = fixture.colonies[0];
  fixture.characters = [1, 2, 3].map(id => ({ id, name: `Pilot ${id}` }));
  fixture.colonies = [1, 2, 3].map(id => ({ ...sample, character_id: id, summary: { ...sample.summary, stored_volume: id * 100 } }));
  fixture.sync_tokens = [1, 2, 3].map(id => ({ token_id: id, character_id: id, character_eve_id: id, character_name: `Pilot ${id}`, has_scope: true, can_sync: true }));
  fixture.character_scopes = [
    { id: "mine", name: "My Characters Only", character_ids: [1] },
    { id: "corp", name: "My Corp Pilots", character_ids: [1, 2] },
    { id: "all", name: "All Characters", character_ids: [1, 2, 3] },
  ];
  assert.equal(scopePlanetaryCharacters(fixture, "mine").summary.stored_volume, 100);
  const corp = scopePlanetaryCharacters(fixture, "corp");
  assert.equal(corp.summary.colonies, 2);
  assert.deepEqual(corp.characters.map(row => row.id), [1, 2]);
  assert.deepEqual(corp.sync_tokens.map(row => row.character_id), [1, 2]);
  assert.equal(scopePlanetaryCharacters(fixture, "all").summary.stored_volume, 600);
  assert.equal(scopePlanetaryCharacters(fixture, "2").summary.stored_volume, 200);
  assert.equal(scopePlanetaryCharacters(fixture, "999").colonies.length, 0);
  fixture.character_scopes = fixture.character_scopes.slice(0, 1);
  assert.equal(scopePlanetaryCharacters(fixture, "all").colonies.length, 0);
  assert.equal(fixture.colonies.length, 3);
});
