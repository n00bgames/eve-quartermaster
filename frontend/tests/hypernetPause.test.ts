import test from "node:test";
import assert from "node:assert/strict";
import { hypernetPaused, recordingCharacters } from "../src/features/hypernet/hypernetPause.ts";

const meta = { seller_characters: [{ id: 1 }, { id: 2 }], pause: { account_paused: false, characters: [
  { id: 1, name: "Betty", paused: false, effective_paused: false },
  { id: 2, name: "Other pilot", paused: true, effective_paused: true },
] } } as Parameters<typeof recordingCharacters>[0];

test("individual pauses exclude only the selected character from new-record choices", () => {
  assert.equal(hypernetPaused(meta.pause, 1), false);
  assert.equal(hypernetPaused(meta.pause, 2), true);
  assert.deepEqual(recordingCharacters(meta).map(c => c.id), [1]);
});
test("account pause overrides every character, including characters not in its initial list", () => {
  const pause = { ...meta.pause!, account_paused: true };
  assert.equal(hypernetPaused(pause), true); assert.equal(hypernetPaused(pause, 999), true);
  assert.deepEqual(recordingCharacters({ ...meta, pause }), []);
  assert.deepEqual(recordingCharacters(meta).map(c => c.id), [1]);
});
test("missing preferences keep legacy metadata compatible", () => {
  assert.equal(hypernetPaused(undefined, 1), false);
  assert.equal(recordingCharacters({ ...meta, pause: undefined }).length, 2);
});
