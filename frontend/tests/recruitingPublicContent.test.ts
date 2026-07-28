import assert from "node:assert/strict";
import test from "node:test";

import {
  initiallyVisibleListIndexes,
  normalizeConfiguredLine,
  parsePublicDescription,
  RECRUITING_PRIVACY_SUMMARY,
} from "../src/features/recruiting/recruitingPublicContent.ts";

test("removes configured bullet, checkmark, dash, and numbering prefixes", () => {
  assert.equal(normalizeConfiguredLine("\u2713 \u2022 Highsec operations"), "Highsec operations");
  assert.equal(normalizeConfiguredLine("3) Doctrine training"), "Doctrine training");
  assert.equal(normalizeConfiguredLine("\u2014 English communication"), "English communication");
});

test("parses safe markdown-style headings and paragraphs", () => {
  assert.deepEqual(parsePublicDescription("## Who We Are\nFirst line.\n\nSecond paragraph.\n## Where We Operate\nHighsec."), [
    { heading: "Who We Are", paragraphs: ["First line.", "Second paragraph."] },
    { heading: "Where We Operate", paragraphs: ["Highsec."] },
  ]);
});

test("keeps core expectations visible beyond the initial list limit", () => {
  const items = ["One", "Two", "Three", "Four", "Five", "Six", "Discord required", "Optional social event"];
  const visible = initiallyVisibleListIndexes(items, "What we expect");
  assert.equal(visible.has(6), true);
  assert.equal(visible.has(7), false);
});

test("uses the concise public privacy summary", () => {
  assert.match(RECRUITING_PRIVACY_SUMMARY, /does not include wallets, assets, mail, contracts, or location data/);
});
