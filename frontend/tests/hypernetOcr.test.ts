import test from "node:test";
import assert from "node:assert/strict";
import { mergeParticipantText, parseParticipantOcr } from "../src/features/hypernet/hypernetOcr.ts";

test("extracts names and singular/plural node counts, marking the seller", () => {
  const rows = parseParticipantOcr("Participants (4)\nLabRat2213\n8 HyperNodes\nSeverin2011\n2 HyperNodes\ntitan enthusiast\n1 HyperNode\nMaegwynn Swift\n1 HyperNode", "LabRat2213");
  assert.deepEqual(rows, [
    { name: "LabRat2213", nodes: 8, seeded: true },
    { name: "Severin2011", nodes: 2, seeded: false },
    { name: "titan enthusiast", nodes: 1, seeded: false },
    { name: "Maegwynn Swift", nodes: 1, seeded: false },
  ]);
});
test("ignores headers, totals, missing names and invalid counts", () => {
  assert.deepEqual(parseParticipantOcr("Participants (4)\n8 HyperNodes\n4 HyperNodes remaining\n8 HyperNodes owned\n512\n16 HyperNodes\nPilot\n900 HyperNodes", "Seller"), []);
});
test("accepts same-line pairs and split Hyper Nodes spelling", () => {
  assert.deepEqual(parseParticipantOcr("Pilot One 2 Hyper Nodes\nAnother Pilot 1 HyperNode", "pilot one"), [
    { name: "Pilot One", nodes: 2, seeded: true }, { name: "Another Pilot", nodes: 1, seeded: false },
  ]);
});
test("tolerates recognized UI label errors without changing character names", () => {
  const rows = parseParticipantOcr("LabRat2213\n8 HuperNodes\nMaegwunn Swift\n1 HuyperNode", "LabRat2213");
  assert.deepEqual(rows, [{ name: "LabRat2213", nodes: 8, seeded: true }, { name: "Maegwunn Swift", nodes: 1, seeded: false }]);
});
test("overlapping imports replace cumulative counts and retain off-screen participants", () => {
  const old = "Off Screen | 3\nPilot One | 2\nSeller | 8 | seeded";
  const rows = [{ name: "pilot one", nodes: 4, seeded: false }, { name: "New Pilot", nodes: 1, seeded: false }];
  const merged = mergeParticipantText(old, rows);
  assert.equal(merged, "Off Screen | 3\npilot one | 4\nSeller | 8 | seeded\nNew Pilot | 1");
  assert.equal(mergeParticipantText(merged, rows), merged);
});
