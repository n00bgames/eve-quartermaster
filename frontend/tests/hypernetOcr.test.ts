import test from "node:test";
import assert from "node:assert/strict";
import { mergeParticipantText, parseParticipantOcr, participantTextFromLayout } from "../src/features/hypernet/hypernetOcr.ts";

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

function word(text: string, x: number, y: number, width = 60) {
  return { text, bbox: { x0: x, y0: y, x1: x + width, y1: y + 20 } };
}
function line(...words: ReturnType<typeof word>[]) {
  return { words, bbox: { x0: Math.min(...words.map((w) => w.bbox.x0)), y0: Math.min(...words.map((w) => w.bbox.y0)), x1: Math.max(...words.map((w) => w.bbox.x1)), y1: Math.max(...words.map((w) => w.bbox.y1)) } };
}
test("pairs by position, excluding portrait noise on names, counts, and intervening lines", () => {
  const layout = [
    line(word("Participants", 100, 0), word("(2)", 220, 0)),
    line(word("Lf", 20, 50), word("LabRat2213", 100, 50)),
    line(word(".4&/!", 20, 85), word("8", 100, 85, 12), word("HyperNodes", 130, 85)),
    line(word("Maegwynn", 100, 140), word("Swift", 200, 140)),
    line(word("3", 30, 163)),
    line(word("1", 100, 175, 12), word("HyperNode", 130, 175)),
  ];
  assert.deepEqual(parseParticipantOcr(participantTextFromLayout(layout), "LabRat2213"), [
    { name: "LabRat2213", nodes: 8, seeded: true }, { name: "Maegwynn Swift", nodes: 1, seeded: false },
  ]);
});
test("does not pair counts with a heading, distant name, or another column", () => {
  for (const candidate of [word("Participants", 100, 50), word("Pilot", 100, 0), word("Pilot", 250, 50)]) {
    assert.equal(participantTextFromLayout([line(candidate), line(word("2", 100, 90, 12), word("HyperNodes", 130, 90))]), "");
  }
  assert.equal(participantTextFromLayout([line(word("Pilot", 100, 50)), line(word("2", 100, 90, 12), word("HyperNodes", 130, 90), word("remaining", 220, 90))]), "");
});
test("rejects symbol-only portrait artifacts as character names", () => {
  assert.deepEqual(parseParticipantOcr("25% 2 HyperNodes\n: 1 HyperNode", "Seller"), []);
});
