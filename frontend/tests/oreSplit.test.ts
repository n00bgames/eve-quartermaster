import assert from "node:assert/strict";
import test from "node:test";
import { ORE_SPLIT_PRESETS, oreSplitClipboard, parseOreStacks, parseSplitPercent, splitOreStacks } from "../src/features/mining/oreSplit.ts";

test("synthetic clipboard rows with trailing backslashes give a conserving 15% split", () => {
  const parsed = parseOreStacks("Compressed Brimful Coesite\t100005\\\r\nCompressed Coesite\t20003\\\r\nCompressed Zeolites\t50003");
  assert.deepEqual(parsed.issues, []);
  const rows = splitOreStacks(parsed.ores, 1500);
  assert.deepEqual(rows.map(row => [row.cut, row.remaining]), [[15001n, 85004n], [3000n, 17003n], [7500n, 42503n]]);
  for (const row of rows) assert.equal(row.cut + row.remaining, row.total);
});
test("uncompressed stays separate; duplicates combine before rounding in input order", () => {
  const parsed = parseOreStacks("Coesite\t1\nCompressed Coesite\t10\ncoesite\t1\n");
  assert.equal(parsed.duplicateRows, 1);
  assert.deepEqual(parsed.ores, [{ name: "Coesite", quantity: 2n }, { name: "Compressed Coesite", quantity: 10n }]);
  assert.equal(splitOreStacks(parsed.ores, 2500)[0].cut, 1n);
});
test("tabs accept EVE extra columns, optional header and common thousands separators", () => {
  const parsed = parseOreStacks("Name\tQuantity\tGroup\nCompressed Ore\t1,234\tMoon Asteroids\nOther Ore\t2\u202f345\tOre\nThird Ore\t3 456\nFourth Ore\t4\u00a0567");
  assert.deepEqual(parsed.issues, []);
  assert.deepEqual(parsed.ores.map(row => row.quantity), [1234n, 2345n, 3456n, 4567n]);
});
test("space-separated lists preserve multiword and numeric ore names", () => {
  const parsed = parseOreStacks("Compressed Coesite 1,234\nKangite X-Grade 100\nVeldspar II-Grade 2 000\nOre 2026 10");
  assert.deepEqual(parsed.issues, []);
  assert.deepEqual(parsed.ores.map(row => [row.name, row.quantity]), [["Compressed Coesite", 1234n], ["Kangite X-Grade", 100n], ["Veldspar II-Grade", 2000n], ["Ore 2026", 10n]]);
});
test("bad quantities are identified by line instead of silently included or skipped", () => {
  for (const quantity of ["-1", "1.5", "12,34", "1e6", "NaN", "Infinity", "", "1,234 567"]) {
    const parsed = parseOreStacks(`Good Ore\t1\nBad Ore\t${quantity}`);
    assert.equal(parsed.issues.length, 1, quantity);
    assert.equal(parsed.issues[0].line, 2);
  }
});
test("empty rows and zero quantity are handled; a name without a quantity is an error", () => {
  assert.deepEqual(parseOreStacks(" \n\t\n").ores, []);
  assert.equal(parseOreStacks("Zero Ore\t0").ores[0].quantity, 0n);
  assert.equal(parseOreStacks("Coesite").issues.length, 1);
});
test("percent bounds and decimal precision are validated explicitly", () => {
  for (const [text, expected] of [["0", 0], ["100", 10000], ["15", 1500], ["12.25", 1225], [".5", 50], [" 5.00 ", 500]] as const) {
    assert.equal(parseSplitPercent(text).basisPoints, expected);
  }
  for (const text of ["", "-1", "100.01", "101", "15.123", "NaN", "1e2", "15%", "Infinity"]) assert.notEqual(parseSplitPercent(text).error, null, text);
});
test("all requested presets exist; zero and 100% never lose or create units", () => {
  assert.deepEqual(ORE_SPLIT_PRESETS, [5, 10, 15, 20, 25, 50]);
  const ores = [{ name: "Coesite", quantity: 247n }];
  assert.deepEqual(splitOreStacks(ores, 0)[0], { name: "Coesite", total: 247n, cut: 0n, remaining: 247n });
  assert.deepEqual(splitOreStacks(ores, 10000)[0], { name: "Coesite", total: 247n, cut: 247n, remaining: 0n });
});
test("half-unit ties round up, with exact arithmetic above JavaScript safe integers", () => {
  assert.equal(splitOreStacks([{ name: "Ore", quantity: 1n }], 5000)[0].cut, 1n);
  const parsed = parseOreStacks("Coesite\t9007199254740993");
  assert.equal(splitOreStacks(parsed.ores, 5000)[0].cut, 4503599627370497n);
});
test("copy text contains EVE-style names and ungrouped exact whole quantities", () => {
  const rows = splitOreStacks(parseOreStacks("Compressed Coesite\t1,000\nZeolites\t1").ores, 1500);
  assert.equal(oreSplitClipboard(rows, "cut"), "Compressed Coesite\t150\nZeolites\t0");
  assert.equal(oreSplitClipboard(rows, "remaining"), "Compressed Coesite\t850\nZeolites\t1");
});
test("large inputs fail visibly and invalid split arguments cannot produce quantities", () => {
  assert.equal(parseOreStacks("x".repeat(100001)).issues.length, 1);
  assert.equal(parseOreStacks("Ore\t1\n".repeat(2001)).issues.length, 1);
  assert.equal(parseOreStacks("Ore\t" + "1".repeat(31)).issues.length, 1);
  for (const percent of [-1, 10001, NaN, 1.1]) assert.throws(() => splitOreStacks([], percent));
});
