export const ORE_SPLIT_PRESETS = [5, 10, 15, 20, 25, 50] as const;
export type OreStack = { name: string; quantity: bigint };
export type OreParseIssue = { line: number | null; message: string };
export type OreSplitRow = { name: string; total: bigint; cut: bigint; remaining: bigint };

const quantityPattern = /^(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,3}(?:[ \u00a0\u202f]\d{3})+)$/;

/** Percentages have at most two decimal places; integer basis points avoid float rounding. */
export function parseSplitPercent(text: string): { basisPoints: number | null; error: string | null } {
  const value = text.trim();
  if (!/^(?:\d{1,3}(?:\.\d{0,2})?|\.\d{1,2})$/.test(value)) {
    return { basisPoints: null, error: "Enter a percentage from 0 to 100, with up to two decimal places." };
  }
  const [whole, fraction = ""] = value.split(".");
  const basisPoints = Number(whole || "0") * 100 + Number(fraction.padEnd(2, "0"));
  if (basisPoints > 10_000) return { basisPoints: null, error: "Percentage must be between 0 and 100." };
  return { basisPoints, error: null };
}

/** Parse EVE name/quantity clipboard rows without resolving names or contacting a service. */
export function parseOreStacks(text: string): { ores: OreStack[]; issues: OreParseIssue[]; duplicateRows: number } {
  const ores: OreStack[] = [], issues: OreParseIssue[] = [];
  const byName = new Map<string, OreStack>();
  let duplicateRows = 0;
  if (text.length > 100_000) return { ores, issues: [{ line: null, message: "Paste up to 100,000 characters at a time." }], duplicateRows };
  // A trailing backslash is common when copying a list from a chat message.
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  if (lines.filter(line => line.trim()).length > 2_000) {
    return { ores, issues: [{ line: null, message: "Paste up to 2,000 ore rows at a time." }], duplicateRows };
  }
  let firstRow = true;
  lines.forEach((raw, index) => {
    const line = raw.trim().replace(/\\+\s*$/, "").trim();
    if (!line) return;
    let name = "", quantity = "";
    if (line.includes("\t")) {
      const fields = line.split("\t");
      name = fields[0].trim();
      quantity = fields[1]?.trim() ?? "";
    } else {
      // Prefer a complete grouped quantity, so "Coesite 1 000" is 1000 units.
      const fields = /^(.*?)\s+(\d{1,3}(?:[, \u00a0\u202f]\d{3})+|\d+)\s*$/.exec(line);
      if (fields) [, name, quantity] = fields;
    }
    if (firstRow && name.toLowerCase() === "name" && quantity.toLowerCase() === "quantity") {
      firstRow = false;
      return;
    }
    firstRow = false;
    name = name.trim().replace(/\s+/g, " ");
    if (!name || !quantityPattern.test(quantity)) {
      issues.push({ line: index + 1, message: "Use an ore name followed by a whole, nonnegative quantity. Tabs are best; extra tab-separated columns are ignored." });
      return;
    }
    const digits = quantity.replace(/[, \u00a0\u202f]/g, "");
    if (digits.length > 30) {
      issues.push({ line: index + 1, message: "Quantity is too large; use at most 30 digits." });
      return;
    }
    const key = name.toLowerCase(), previous = byName.get(key);
    if (previous) {
      previous.quantity += BigInt(digits);
      duplicateRows += 1;
    } else {
      const ore = { name, quantity: BigInt(digits) };
      ores.push(ore);
      byName.set(key, ore);
    }
  });
  return { ores, issues, duplicateRows };
}

export function splitOreStacks(ores: OreStack[], basisPoints: number): OreSplitRow[] {
  if (!Number.isInteger(basisPoints) || basisPoints < 0 || basisPoints > 10_000) throw new Error("Invalid split percentage.");
  return ores.map(({ name, quantity }) => {
    if (quantity < 0n) throw new Error("Ore quantities cannot be negative.");
    // Round positive half units up. Derive the remainder from the rounded cut
    // so no unit can be lost or created by independently rounding both sides.
    const cut = (quantity * BigInt(basisPoints) + 5_000n) / 10_000n;
    return { name, total: quantity, cut, remaining: quantity - cut };
  });
}

export function oreSplitClipboard(rows: OreSplitRow[], column: "cut" | "remaining"): string {
  return rows.map(row => `${row.name}\t${row[column]}`).join("\n");
}
