export type ParticipantDraft = { name: string; nodes: number; seeded: boolean };

type OcrWord = { text: string; bbox: { x0: number; y0: number; x1: number; y1: number } };
type OcrLine = { words: OcrWord[]; bbox: OcrWord["bbox"] };

// Use the count's column to ignore portrait fragments, even when OCR merges
// them onto a count line or inserts a separate fragment between name and count.
export function participantTextFromLayout(lines: OcrLine[]): string {
  const ordered = [...lines].sort((a, b) => a.bbox.y0 - b.bbox.y0);
  const pairs: string[] = [];
  for (const line of ordered) {
    const label = line.words.findIndex((word) => /^H(?:y|u|uy)per$/i.test(word.text) || /^H(?:y|u|uy)perNodes?$/i.test(word.text));
    const count = line.words[label - 1];
    if (!count || !/^\d+$/.test(count.text) || /remaining|owned/i.test(line.words.map((word) => word.text).join(" "))) continue;
    const height = Math.max(1, count.bbox.y1 - count.bbox.y0);
    const tolerance = height * 0.6;
    const candidate = ordered.filter((other) => other.bbox.y1 <= line.bbox.y0 + height * 0.2 && line.bbox.y0 - other.bbox.y1 < height * 2)
      .map((other) => ({ ...other, words: other.words.filter((word) => word.bbox.x0 >= count.bbox.x0 - tolerance) }))
      .filter((other) => other.words.length && Math.abs(other.words[0].bbox.x0 - count.bbox.x0) <= tolerance)
      .sort((a, b) => b.bbox.y1 - a.bbox.y1)[0];
    const name = candidate?.words.map((word) => word.text).join(" ");
    if (name && /\p{L}/u.test(name) && !/participants|hyper\s*nodes?/i.test(name)) pairs.push(`${name}\n${count.text} HyperNodes`);
  }
  return pairs.join("\n");
}

export function parseParticipantOcr(text: string, sellerName: string): ParticipantDraft[] {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const rows: ParticipantDraft[] = [];
  for (let i = 0; i < lines.length; i++) {
    // Tesseract commonly reads EVE's "HyperNodes" label as HuperNodes/HuyperNodes.
    // Normalize the fixed UI label only; character names remain untouched for review.
    const match = lines[i].match(/^(.*?)\b(\d+)\s+H(?:y|u|uy)per\s*Nodes?\s*$/i);
    if (!match) continue;
    const name = (match[1].trim() || lines[i - 1] || "").trim();
    const nodes = Number(match[2]);
    if (!name || !/\p{L}/u.test(name) || /h(?:y|u|uy)per\s*nodes?|participants\s*\(|\||^\d+$/i.test(name) || nodes < 1 || nodes > 512) continue;
    rows.push({ name, nodes, seeded: name.toLowerCase() === sellerName.toLowerCase() });
  }
  return rows;
}

export function mergeParticipantText(existing: string, rows: ParticipantDraft[]): string {
  const replacements = new Map(rows.map((row) => [row.name.trim().toLowerCase(), row]));
  const format = (row: ParticipantDraft) => `${row.name.trim()} | ${row.nodes}${row.seeded ? " | seeded" : ""}`;
  const lines = existing.split(/\r?\n/).filter((line) => line.trim()).map((line) => {
    const key = line.split("|")[0].trim().toLowerCase();
    const row = replacements.get(key);
    if (!row) return line;
    replacements.delete(key);
    return format(row);
  });
  return [...lines, ...Array.from(replacements.values()).map(format)].join("\n");
}
