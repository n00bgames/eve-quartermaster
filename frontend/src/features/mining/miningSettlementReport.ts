import type { MiningSettlement, SettlementPreview } from "../../types/miningSettlement";

type ReportSettlement = MiningSettlement | SettlementPreview;
const whole = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const isk = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function scopeLabel(row: ReportSettlement) {
  if (row.operation_name) return row.operation_name;
  if (row.range_start && row.range_end) {
    return `${new Date(row.range_start).toLocaleDateString()} - ${new Date(row.range_end).toLocaleDateString()}`;
  }
  return row.source_type === "operation" ? "Saved mining operation" : "Mining Ledger range";
}

export function miningSettlementDiscordReport(row: ReportSettlement, name: string, status = "Preview") {
  const mode = row.settlement_mode === "minerals" ? "Mineral shares" : "ISK shares";
  const lines = [
    `**Mining Op Settlement: ${name || scopeLabel(row)}**`,
    `**Scope:** ${scopeLabel(row)} | **Status:** ${status} | **Mode:** ${mode}`,
    `**Refined value:** ${isk.format(row.gross_value)} ISK`,
    `**Reserve / expenses:** ${isk.format(row.reserve_value + row.deduction_total)} ISK`,
    `**Distributable value:** ${isk.format(row.distributable_value)} ISK`,
    "",
    "**Refined output**",
    ...row.outputs.map((output) => {
      const retained = output.retained_quantity ?? 0;
      const suffix = row.settlement_mode === "minerals" && retained > 0 ? ` (retained ${whole.format(retained)})` : "";
      return `- ${output.type_name}: ${whole.format(output.quantity)}${suffix}`;
    }),
    "",
    "**Pilot shares**",
  ];

  for (const pilot of row.participants) {
    const ratio = percent.format((pilot.payout_ratio ?? 0) * 100);
    if (row.settlement_mode === "minerals") {
      const basket = (pilot.mineral_payouts ?? [])
        .map((mineral) => `${mineral.type_name} ${whole.format(mineral.quantity)}`)
        .join(" | ") || "No mineral allocation";
      lines.push(`- **${pilot.display_name}** (${pilot.role}) - ${ratio}%`, `  ${basket}`);
    } else {
      lines.push(`- **${pilot.display_name}** (${pilot.role}) - ${ratio}% - ${isk.format(pilot.payout_isk ?? 0)} ISK`);
    }
  }

  if (row.refining_pilot_name || row.refining_location) {
    lines.push("", `**Refining:** ${row.refining_pilot_name || "Unrecorded pilot"}${row.refining_location ? ` at ${row.refining_location}` : ""}`);
  }
  if (row.notes) lines.push(`**Notes:** ${row.notes}`);
  return lines.join("\n");
}