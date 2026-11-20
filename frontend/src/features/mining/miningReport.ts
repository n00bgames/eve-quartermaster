import type { MiningLedgerPayload, MiningRollupRow } from "../../types/mining.ts";
import { APP_VERSION } from "../../version.ts";

export type MiningReportScope = {
  character_id: string;
  system_id: string;
  operation_id: string;
  date_from: string;
  date_to: string;
};

export const allMiningHistory: MiningReportScope = {
  character_id: "", system_id: "", operation_id: "", date_from: "", date_to: "",
};

export function sameMiningScope(left: MiningReportScope, right: MiningReportScope) {
  return (Object.keys(allMiningHistory) as (keyof MiningReportScope)[]).every((key) => left[key] === right[key]);
}

function metrics(row: Omit<MiningRollupRow, "id" | "name">) {
  return {
    recovered_quantity: row.quantity,
    residue_quantity: row.residue_quantity,
    gross_quantity: row.quantity + row.residue_quantity,
    recovered_volume_m3: row.volume,
    residue_volume_m3: row.residue_volume,
    gross_volume_m3: row.gross_volume,
    estimated_recovered_isk: row.estimated_price,
    estimated_residue_isk: row.estimated_residue_price,
    estimated_gross_isk: row.gross_value,
    measured_efficiency_percent: row.efficiency ?? null,
  };
}

export function buildMiningReport(
  data: MiningLedgerPayload, scope: MiningReportScope,
  loadedAt: string, now = new Date(),
) {
  // Explicit projection: no raw ledger rows, operation notes, full roster or tokens.
  const rows = (items: MiningRollupRow[]) => items.map((row) => ({ name: row.name, ...metrics(row) }));
  const days = data.analytics.by_day.map((row) => row.name).sort();
  return {
    schema_version: "eqm.mining-report.v1",
    application_version: APP_VERSION,
    exported_at_utc: now.toISOString(),
    loaded_from_eqm_at_utc: loadedAt,
    scope: {
      date_from: scope.date_from || null,
      date_to: scope.date_to || null,
      date_basis: "UTC ledger dates; From and To inclusive; null means unbounded",
      character_id: scope.character_id ? Number(scope.character_id) : null,
      character_name: scope.character_id ? data.characters.find((row) => String(row.character_id) === scope.character_id)?.name ?? scope.character_id : "All characters",
      system_id: scope.system_id ? Number(scope.system_id) : null,
      system_name: scope.system_id ? data.systems.find(([id]) => String(id) === scope.system_id)?.[1] ?? scope.system_id : "All systems",
      operation_id: scope.operation_id ? Number(scope.operation_id) : null,
      operation_name: scope.operation_id ? data.operations.find((row) => String(row.id) === scope.operation_id)?.name ?? scope.operation_id : "All history",
    },
    coverage: {
      matching_ledger_rows: data.entry_count,
      first_recorded_day: days[0] ?? null,
      last_recorded_day: days[days.length - 1] ?? null,
      recorded_day_count: days.length,
      basis: "Full analytics returned for the applied filters; independent of ledger pagination and chart display limits",
    },
    totals: { ...metrics(data.analytics.totals), measured_gross_volume_m3: data.analytics.totals.measured_volume },
    by_day: rows(data.analytics.by_day),
    by_ore: rows(data.analytics.by_ore),
    by_character: rows(data.analytics.by_character),
    by_system: rows(data.analytics.by_system),
    notes: [
      "Estimated ISK values are stored ledger valuations, not realized profit or a fresh market appraisal.",
      "Residue and efficiency are measured only where residue data was imported. Null efficiency means unmeasured, not zero.",
      "Gross extraction is recovered volume plus reported residue; missing residue can understate extraction.",
      "Recorded days contain retained observations only. Missing days are not evidence of zero mining or complete ESI coverage.",
      "Loaded-from-EQM time is the report fetch time, not the last ESI sync time.",
    ],
  };
}

export type MiningReport = ReturnType<typeof buildMiningReport>;

function csvCell(value: unknown) {
  let text = value == null ? "" : String(value);
  if (typeof value === "string" && /^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

export function buildMiningReportExport(report: MiningReport, format: "csv" | "json") {
  const period = `${report.scope.date_from ?? "all"}_to_${report.scope.date_to ?? "latest"}`;
  const timestamp = report.exported_at_utc.replace(/\.\d+Z$/, "Z").replace(/:/g, "-");
  const filename = `mining-report-${period}-${timestamp}.${format}`;
  if (format === "json") return { filename, mime: "application/json;charset=utf-8", text: JSON.stringify(report, null, 2) + "\n" };

  const metadata = {
    schema_version: report.schema_version,
    application_version: report.application_version,
    exported_at_utc: report.exported_at_utc,
    loaded_from_eqm_at_utc: report.loaded_from_eqm_at_utc,
    date_from: report.scope.date_from,
    date_to: report.scope.date_to,
    date_basis: report.scope.date_basis,
    character_filter_id: report.scope.character_id,
    character_filter_name: report.scope.character_name,
    system_filter_id: report.scope.system_id,
    system_filter_name: report.scope.system_name,
    operation_filter_id: report.scope.operation_id,
    operation_filter_name: report.scope.operation_name,
    matching_ledger_rows: report.coverage.matching_ledger_rows,
    first_recorded_day: report.coverage.first_recorded_day,
    last_recorded_day: report.coverage.last_recorded_day,
    recorded_day_count: report.coverage.recorded_day_count,
    coverage_basis: report.coverage.basis,
    notes: report.notes.join(" "),
  };
  const metricKeys = Object.keys(report.totals);
  const header = ["section", "name", ...metricKeys, ...Object.keys(metadata)];
  const lines: unknown[][] = [["totals", "Selection total", ...Object.values(report.totals), ...Object.values(metadata)]];
  for (const section of ["by_day", "by_ore", "by_character", "by_system"] as const) {
    for (const row of report[section]) {
      lines.push([section, row.name, ...metricKeys.map((key) => key in row ? row[key as keyof typeof row] : null), ...Object.values(metadata)]);
    }
  }
  return { filename, mime: "text/csv;charset=utf-8", text: "\uFEFF" + [header, ...lines].map((line) => line.map(csvCell).join(",")).join("\r\n") + "\r\n" };
}
