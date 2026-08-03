import assert from "node:assert/strict";
import test from "node:test";

import { droppedReplotWaypoints, orderedReplotConstraints } from "../src/features/navigation/jumpReplot.ts";
import type { JumpFreighterRoute } from "../src/types/navigation.ts";

const route = {
  requested_waypoints: [{ system_id: 3, name: "Gusandall" }],
  jumps: [
    { jump_index: 1, to_system: { system_id: 2, name: "Bundindus" } },
    { jump_index: 2, to_system: { system_id: 3, name: "Gusandall" } },
  ],
} as JumpFreighterRoute;

test("selected alternate is inserted before the next required cyno", () => {
  assert.deepEqual(orderedReplotConstraints(route, 1, "Illamur"), [
    { name: "Illamur", selectedAlternate: true },
    { name: "Gusandall", selectedAlternate: false },
  ]);
});

test("dropped waypoint reporting names only constraints that could not be retained", () => {
  const retained = new Set<string>();
  assert.deepEqual(droppedReplotWaypoints(route, retained), ["Gusandall"]);
  assert.deepEqual(orderedReplotConstraints(route, 1, "Illamur", retained).map((row) => row.name), ["Illamur"]);
});