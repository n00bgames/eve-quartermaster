import test from "node:test";
import assert from "node:assert/strict";
import { matchesBlueprintTechnology } from "../src/features/industry/blueprintFilters.ts";
import type { Blueprint } from "../src/types/inventory.ts";
const bp = (tech: number | null, category: number | null) => ({ product_tech_level: tech, product_category_id: category } as Blueprint);
test("technology and product filters compose across ships, modules and subsystems", () => {
  assert(matchesBlueprintTechnology(bp(2, 6), "2", "ships"));
  assert(!matchesBlueprintTechnology(bp(3, 6), "2", "ships"));
  assert(!matchesBlueprintTechnology(bp(2, 7), "2", "ships"));
  assert(matchesBlueprintTechnology(bp(3, 32), "3", "modules"));
  assert(matchesBlueprintTechnology(bp(2, 7), "2", "modules"));
  assert(!matchesBlueprintTechnology(bp(2, 8), "2", "modules"));
});
test("unknown metadata stays visible in All and never guesses a technology or product", () => {
  assert(matchesBlueprintTechnology(bp(null, null), "all", "all"));
  assert(!matchesBlueprintTechnology(bp(null, 6), "2", "ships"));
  assert(!matchesBlueprintTechnology(bp(3, null), "3", "ships"));
  assert(matchesBlueprintTechnology(bp(1, 6), "all", "ships"));
});
