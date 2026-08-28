import type {
  PlanetaryColony,
  PlanetaryIndustryPayload,
  PlanetaryPin,
  PlanetaryPinContent,
} from "../../types/planetaryIndustry";

export type PlanetaryExportFormat = "csv" | "json";

export type PlanetaryExport = {
  filename: string;
  mimeType: string;
  text: string;
  colonyCount: number;
  facilityCount: number;
  amountRowCount: number;
};

const CSV_FIELDS = [
  "character_name",
  "character_id",
  "character_eve_id",
  "planet_name",
  "planet_id",
  "planet_type",
  "solar_system_name",
  "solar_system_id",
  "security_status",
  "command_center_level",
  "esi_last_update",
  "projected_at",
  "facility_name",
  "facility_type_id",
  "pin_id",
  "facility_role",
  "observed_status",
  "projected_status",
  "schematic_name",
  "schematic_id",
  "schematic_output_name",
  "schematic_output_type_id",
  "schematic_output_quantity_per_cycle",
  "extractor_product_name",
  "extractor_product_type_id",
  "extractor_quantity_per_cycle",
  "extractor_projected_daily_output",
  "extractor_projected_remaining_output",
  "content_name",
  "content_type_id",
  "projected_amount",
  "observed_amount",
  "produced_since_checkpoint",
  "blocked_amount",
  "volume_m3_per_unit",
  "projected_volume_m3",
  "observed_volume_m3",
  "has_inbound_route",
] as const;

type CsvField = typeof CSV_FIELDS[number];
type CsvValue = string | number | boolean | null | undefined;
type CsvRow = Record<CsvField, CsvValue>;

function facilityRole(pin: PlanetaryPin) {
  if (pin.is_extractor) return "extractor";
  if (pin.is_factory) return "factory";
  if (pin.contents.length || pin.observed_contents.length) return "storage";
  return "infrastructure";
}

function contentMap(rows: PlanetaryPinContent[]) {
  return new Map(rows.map((row) => [row.type_id, row]));
}

function facilityRows(colony: PlanetaryColony, pin: PlanetaryPin): CsvRow[] {
  const projected = contentMap(pin.contents);
  const observed = contentMap(pin.observed_contents);
  const produced = contentMap(pin.projected_produced);
  const blocked = contentMap(pin.projected_blocked);
  const typeIds = [...new Set([
    ...projected.keys(),
    ...observed.keys(),
    ...produced.keys(),
    ...blocked.keys(),
  ])].sort((left, right) => {
    const leftName = projected.get(left)?.name ?? observed.get(left)?.name ?? produced.get(left)?.name ?? blocked.get(left)?.name ?? "";
    const rightName = projected.get(right)?.name ?? observed.get(right)?.name ?? produced.get(right)?.name ?? blocked.get(right)?.name ?? "";
    return leftName.localeCompare(rightName) || left - right;
  });
  const contentTypeIds: Array<number | null> = typeIds.length ? typeIds : [null];

  return contentTypeIds.map((typeId) => {
    const content = typeId == null
      ? undefined
      : projected.get(typeId) ?? observed.get(typeId) ?? produced.get(typeId) ?? blocked.get(typeId);
    const projectedContent = typeId == null ? undefined : projected.get(typeId);
    const observedContent = typeId == null ? undefined : observed.get(typeId);
    const volume = content?.volume ?? 0;
    return {
      character_name: colony.character_name,
      character_id: colony.character_id,
      character_eve_id: colony.character_eve_id,
      planet_name: colony.planet_name,
      planet_id: colony.planet_id,
      planet_type: colony.planet_type,
      solar_system_name: colony.solar_system_name,
      solar_system_id: colony.solar_system_id,
      security_status: colony.security_status,
      command_center_level: colony.upgrade_level,
      esi_last_update: colony.esi_last_update,
      projected_at: colony.projection.projected_at,
      facility_name: pin.type_name,
      facility_type_id: pin.type_id,
      pin_id: pin.pin_id,
      facility_role: facilityRole(pin),
      observed_status: pin.status,
      projected_status: pin.projected_status,
      schematic_name: pin.schematic?.name,
      schematic_id: pin.schematic_id,
      schematic_output_name: pin.schematic?.output.name,
      schematic_output_type_id: pin.schematic?.output.type_id,
      schematic_output_quantity_per_cycle: pin.schematic?.output.quantity,
      extractor_product_name: pin.extractor?.product_name,
      extractor_product_type_id: pin.extractor?.product_type_id,
      extractor_quantity_per_cycle: pin.extractor?.qty_per_cycle,
      extractor_projected_daily_output: pin.extractor?.projected_daily_output,
      extractor_projected_remaining_output: pin.extractor?.projected_remaining_output,
      content_name: content?.name,
      content_type_id: typeId,
      projected_amount: projectedContent?.amount,
      observed_amount: observedContent?.amount,
      produced_since_checkpoint: typeId == null ? undefined : produced.get(typeId)?.amount,
      blocked_amount: typeId == null ? undefined : blocked.get(typeId)?.amount,
      volume_m3_per_unit: typeId == null ? undefined : volume,
      projected_volume_m3: projectedContent ? projectedContent.amount * volume : undefined,
      observed_volume_m3: observedContent ? observedContent.amount * volume : undefined,
      has_inbound_route: pin.has_inbound_route,
    };
  });
}

function csvCell(value: CsvValue) {
  if (value == null) return "";
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function timestampForFilename(value: Date) {
  return value.toISOString().replace(/:/g, "-").replace(/\.\d{3}Z$/, "Z");
}

export function buildPlanetaryExport(
  data: PlanetaryIndustryPayload,
  format: PlanetaryExportFormat,
  generatedAt = new Date(),
): PlanetaryExport {
  const rows = data.colonies.flatMap((colony) => colony.pins.flatMap((pin) => facilityRows(colony, pin)));
  const basename = `planetary-industry-${timestampForFilename(generatedAt)}`;
  const facilityCount = data.colonies.reduce((total, colony) => total + colony.pins.length, 0);

  if (format === "json") {
    const payload = {
      schema_version: "eqm.planetary-industry.v1",
      generated_at: generatedAt.toISOString(),
      source_as_of: data.as_of,
      summary: {
        colony_count: data.colonies.length,
        facility_count: facilityCount,
        amount_row_count: rows.length,
      },
      schematics: data.schematics ?? [],
      colonies: data.colonies,
    };
    return {
      filename: `${basename}.json`,
      mimeType: "application/json;charset=utf-8",
      text: `${JSON.stringify(payload, null, 2)}\n`,
      colonyCount: data.colonies.length,
      facilityCount,
      amountRowCount: rows.length,
    };
  }

  const lines = [
    CSV_FIELDS.join(","),
    ...rows.map((row) => CSV_FIELDS.map((field) => csvCell(row[field])).join(",")),
  ];
  return {
    filename: `${basename}.csv`,
    mimeType: "text/csv;charset=utf-8",
    text: `\uFEFF${lines.join("\r\n")}\r\n`,
    colonyCount: data.colonies.length,
    facilityCount,
    amountRowCount: rows.length,
  };
}
