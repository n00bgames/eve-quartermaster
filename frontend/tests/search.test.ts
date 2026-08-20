import assert from "node:assert/strict";
import test from "node:test";

import { matchesSearchTerms, normalizedSearchTerms } from "../src/lib/search.ts";

test("normalizes whitespace-separated search terms", () => {
  assert.deepEqual(normalizedSearchTerms("  Heavy   Pulse  "), ["heavy", "pulse"]);
});

test("requires every term while allowing matches across fields", () => {
  const values = ["Heavy Pulse Laser II", "Steihl Lianul", "Dudreda"];
  assert.equal(matchesSearchTerms("pulse steihl", values), true);
  assert.equal(matchesSearchTerms("pulse jita", values), false);
});

test("matches numeric identifiers and treats an empty query as unfiltered", () => {
  assert.equal(matchesSearchTerms("12345", ["Hecate Blueprint", 12345]), true);
  assert.equal(matchesSearchTerms("", ["Hecate Blueprint"]), true);
});

