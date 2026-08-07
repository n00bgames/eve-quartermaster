import assert from "node:assert/strict";
import test from "node:test";

import { adaptiveDateTicks, chartDomain, compactChartValue } from "../src/lib/chartScale.ts";

test("wallet domains preserve detail and add peak headroom", () => {
  const domain = chartDomain([2_800_000_000, 3_800_000_000]);
  assert.ok(domain.low > 0, "absolute wallet charts should not be forced to zero");
  assert.ok(domain.low <= 2_800_000_000);
  assert.ok(domain.high >= 3_850_000_000, "the peak should have at least five percent of the visible span as headroom");
  assert.deepEqual(domain.ticks.slice(1).map((tick, index) => tick - domain.ticks[index]), domain.ticks.slice(1).map(() => 250_000_000));
});

test("rebased movement charts retain zero context", () => {
  const domain = chartDomain([120_000_000, 340_000_000], true);
  assert.equal(domain.low, 0);
});

test("date labels become less dense as the selected period grows", () => {
  const start = Date.parse("2026-01-01T00:00:00Z");
  const end = Date.parse("2026-12-31T00:00:00Z");
  assert.equal(adaptiveDateTicks(start, start + 6 * 86_400_000, 7).length, 7);
  assert.ok(adaptiveDateTicks(start, start + 29 * 86_400_000, 30).length <= 6);
  assert.ok(adaptiveDateTicks(start, start + 89 * 86_400_000, 90).length <= 5);
  assert.ok(adaptiveDateTicks(start, end, 365).length <= 6);
});

test("axis values use compact human-readable units", () => {
  assert.equal(compactChartValue(250_000_000), "250M");
  assert.equal(compactChartValue(2_000_000_000), "2B");
});
