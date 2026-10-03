export type ParticipantDraft = { name: string; nodes: number; seeded: boolean };

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
    if (!name || /h(?:y|u|uy)per\s*nodes?|participants\s*\(|\||^\d+$/i.test(name) || nodes < 1 || nodes > 512) continue;
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
