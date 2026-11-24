/** Conservative English wallet parsing. Unreadable cells stay blank for review. */
export type WalletDraft = { date: string; kind: "" | "buy" | "sell"; quantity: string; price: string; fees: string; note: string; selected: boolean; allowDuplicate: boolean; source: string };
export type WalletTrade = { occurred_at: string; kind: string; quantity: number; unit_price: number | string | null };
type Word = { text: string; bbox: { x0: number; x1: number; y0: number; y1: number } };
const datePattern = /\b(20\d{2})[.\/-](\d{2})[.\/-](\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?\b/;

export function utcDate(value: string): string | null {
  const match = value.replace("T", " ").match(datePattern);
  if (!match) return null;
  const [, year, month, day, hour, minute, second = "00"] = match;
  const iso = `${year}-${month}-${day}T${hour}:${minute}:${second}Z`;
  const date = new Date(iso);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 19) === iso.slice(0, 19) ? iso : null;
}

export function walletTextFromWords(words: Word[]): string {
  // Sparse OCR often reads entire columns as separate blocks. Recover visual rows.
  const rows: { y: number; height: number; words: Word[] }[] = [];
  for (const word of [...words].sort((a, b) => a.bbox.y0 - b.bbox.y0)) {
    const y = (word.bbox.y0 + word.bbox.y1) / 2, height = word.bbox.y1 - word.bbox.y0;
    const row = rows.find(r => Math.abs(r.y - y) <= Math.max(r.height, height) * .55);
    if (row) { row.words.push(word); row.y = row.words.reduce((sum, w) => sum + (w.bbox.y0 + w.bbox.y1) / 2, 0) / row.words.length; }
    else rows.push({ y, height, words: [word] });
  }
  return rows.sort((a, b) => a.y - b.y).map(r => r.words.sort((a, b) => a.bbox.x0 - b.bbox.x0).map(w => w.text).join(" ")).join("\n");
}

export function parseWalletText(text: string): WalletDraft[] {
  const result: WalletDraft[] = [];
  for (const source of text.slice(0, 50000).split(/\r?\n/)) {
    const match = source.match(datePattern);
    if (!match || !/\bPLEX\b/i.test(source)) continue;
    const rest = source.replace(match[0], "");
    // Require decimal cents; multiple money values stay blank rather than guessing.
    const prices = [...rest.matchAll(/(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?![\d.,])/g)];
    const price = prices.length === 1 ? prices[0][0].replace(/,/g, "") : "";
    // Only examine the date/PLEX/price prefix, excluding client and station names.
    const prefixEnd = prices[0] ? prices[0].index! + prices[0][0].length : rest.length;
    const prefix = rest.slice(0, prefixEnd).replace(/\bPLEX\b/ig, "").replace(/\b(?:buy|bought|purchase|sell|sold|sale|ISK)\b/ig, "");
    const integers = prefix.replace(/(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}/g, "").trim().match(/(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![\w.,])/g) ?? [];
    const date = utcDate(match[0]);
    const directionText = rest.slice(0, prices[0]?.index ?? rest.length);
    result.push({ date: date?.slice(0, 19) ?? "", kind: /\b(buy|bought|purchase)\b/i.test(directionText) ? "buy" : /\b(sell|sold|sale)\b/i.test(directionText) ? "sell" : "",
      quantity: integers.length === 1 ? integers[0].replace(/,/g, "") : "", price, fees: "0", note: "Wallet screenshot", selected: true, allowDuplicate: false, source });
    if (result.length === 200) break;
  }
  return result;
}

export function tradeKey(row: WalletTrade): string {
  return [row.occurred_at.slice(0, 16), row.kind, row.quantity, Number(row.unit_price)].join("|");
}
export function draftKey(row: WalletDraft): string {
  return tradeKey({ occurred_at: utcDate(row.date) ?? "", kind: row.kind, quantity: Number(row.quantity), unit_price: row.price });
}
export function draftError(row: WalletDraft, now = Date.now()): string {
  const date = utcDate(row.date);
  if (!date || Date.parse(date) > now) return "Check UTC date/time.";
  if (!row.kind) return "Choose purchase or sale.";
  if (!/^\d+$/.test(row.quantity) || Number(row.quantity) < 1 || Number(row.quantity) > 1e9) return "Check whole PLEX quantity.";
  if (!/^\d{1,18}(?:\.\d{1,2})?$/.test(row.price) || Number(row.price) <= 0) return "Check ISK price per PLEX.";
  if (!/^\d{1,18}(?:\.\d{1,2})?$/.test(row.fees)) return "Check total fees in ISK.";
  return "";
}
