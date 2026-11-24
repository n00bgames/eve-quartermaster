import test from "node:test";
import assert from "node:assert/strict";
import { parseWalletText, utcDate, draftError, draftKey, tradeKey, walletTextFromWords } from "../src/features/plex/plexWalletParser.ts";

test("mixed trades preserve cents, UTC and explicit directions without interpreting colour", () => {
  const rows = parseWalletText("Date Quantity Type Price Client\n2025.01.01 12:30 1,000 PLEX 4,000,000.01 ISK Demo 7\n2025.01.02 15:45:33 sell 100 PLEX 4,100,000.99 ISK Demo 2\n2025.01.03 10:00 2 Tritanium 6.00 ISK");
  assert.equal(rows.length, 2);
  assert.equal(rows[0].kind, "");
  assert.equal(parseWalletText("2025.01.01 12:30 500 PLEX 4,000,000.00 ISK Sale")[0].kind, "");
  assert.equal(rows[0].quantity, "1000");
  assert.equal(rows[0].price, "4000000.01");
  assert.equal(rows[0].date, "2025-01-01T12:30:00");
  assert.equal(rows[1].kind, "sell");
  assert.equal(rows[1].date, "2025-01-02T15:45:33");
  assert.match(draftError(rows[0]), /purchase or sale/);
  assert.equal(draftError({ ...rows[0], kind: "buy" }), "");
});

test("ambiguous money, invalid dates and OCR digit damage require repair", () => {
  const [row] = parseWalletText("2025.02.30 12:30 PLEX 1O0 4,000,000.00 ISK 400,000,000.00 ISK");
  assert.equal(row.date, ""); assert.equal(row.price, ""); assert.equal(row.quantity, "");
  assert.equal(utcDate("2025-01-01T24:10:00"), null);
  assert.equal(utcDate("2025-01-01T12:30"), "2025-01-01T12:30:00Z");
  assert.equal(utcDate("2025-01-01T12:30:27"), "2025-01-01T12:30:27Z");
  assert.equal(parseWalletText("1,000 PLEX 4,000,000.00 ISK").length, 0);
});

test("duplicate fingerprints use the visible minute and exclude fees/notes", () => {
  const [row] = parseWalletText("2025.01.01 12:30 buy 500 PLEX 4,000,000.00 ISK");
  assert.equal(draftKey(row), tradeKey({ occurred_at: "2025-01-01T12:30:59+00:00", kind: "buy", quantity: 500, unit_price: 4000000 }));
  assert.notEqual(draftKey({ ...row, kind: "sell" }), draftKey(row));
});

test("reassemble column-block OCR words in visual row order", () => {
  const word = (text: string, x: number, y: number) => ({ text, bbox: { x0: x, x1: x + 70, y0: y, y1: y + 12 } });
  const text = walletTextFromWords([word("PLEX", 200, 20), word("PLEX", 200, 40), word("2025.01.01", 0, 20), word("12:30", 80, 20), word("500", 150, 21), word("4,000,000.00", 260, 20), word("2025.01.02", 0, 40), word("12:31", 80, 40), word("100", 150, 41), word("4,100,000.00", 260, 40)]);
  assert.deepEqual(parseWalletText(text).map(r => r.quantity), ["500", "100"]);
});

test("rejects negative, fractional and over-limit values; bounds review size", () => {
  const [row] = parseWalletText("2025.01.01 12:30 buy 500 PLEX 4,000,000.00 ISK");
  for (const patch of [{ quantity: "1.1" }, { quantity: "1000000001" }, { price: "-5" }, { price: "1.001" }, { fees: "NaN" }, { date: "2099-01-01T00:00:00" }]) assert(draftError({ ...row, ...patch }));
  assert.equal(parseWalletText(Array(250).fill(row.source).join("\n")).length, 200);
});
