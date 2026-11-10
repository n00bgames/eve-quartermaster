import type { PlanetaryColony, PlanetaryIndustryPayload, PlanetaryPin } from "../../types/planetaryIndustry.ts";
import { scopePlanetaryCharacters } from "./planetaryCharacterScope.ts";
import type { PlanetaryExport, PlanetaryExportFormat } from "./planetaryExport.ts";

export type FacilitiesScope = { character: string; system: string; planet_type: string };
export const defaultFacilitiesScope: FacilitiesScope = { character: "mine", system: "all", planet_type: "all" };

function role(pin: PlanetaryPin) {
  if (pin.is_extractor) return "extractor";
  if (pin.is_factory) return "factory";
  if (/Command Center$/i.test(pin.type_name)) return "command_center";
  if (/Launchpad$/i.test(pin.type_name)) return "launchpad";
  if (/Storage Facility$/i.test(pin.type_name)) return "storage";
  return "infrastructure";
}

function colonyMetadata(colony: PlanetaryColony) {
  return {
    colony_id: colony.id,
    character_id: colony.character_id,
    character_eve_id: colony.character_eve_id,
    character_name: colony.character_name,
    planet_id: colony.planet_id,
    planet_name: colony.planet_name,
    planet_type: colony.planet_type ?? null,
    solar_system_id: colony.solar_system_id ?? null,
    solar_system_name: colony.solar_system_name ?? null,
    security_status: colony.security_status ?? null,
    command_center_level: colony.upgrade_level,
    esi_last_update: colony.esi_last_update ?? null,
    last_synced_at: colony.last_synced_at,
    reported_pin_count: colony.num_pins,
    reported_link_count: colony.link_count,
    reported_route_count: colony.route_count,
    projection: colony.projection,
  };
}

export function buildPlanetaryFacilitiesReport(
  data: PlanetaryIndustryPayload,
  scope: FacilitiesScope = defaultFacilitiesScope,
  generatedAt = new Date(),
) {
  const visible = scopePlanetaryCharacters(data, scope.character);
  const colonies = visible.colonies.filter(colony =>
    (scope.system === "all" || colony.solar_system_name === scope.system)
    && (scope.planet_type === "all" || colony.planet_type === scope.planet_type),
  ).map(colony => ({
    ...colonyMetadata(colony),
    facilities: colony.pins.map(pin => ({
      ...pin,
      facility_role: role(pin),
      // A configured recipe may be in the shared catalog before it is embedded on the pin.
      schematic: pin.schematic ?? data.schematics?.find(recipe => recipe.id === pin.schematic_id) ?? null,
      inbound_route_ids: colony.routes.filter(route => route.destination_pin_id === pin.pin_id).map(route => route.route_id),
      outbound_route_ids: colony.routes.filter(route => route.source_pin_id === pin.pin_id).map(route => route.route_id),
    })),
    routes: colony.routes,
  }));
  const facilities = colonies.flatMap(colony => colony.facilities);
  return {
    schema_version: "eqm.planetary-facilities.v1" as const,
    generated_at: generatedAt.toISOString(),
    source_as_of: data.as_of,
    scope: { ...scope },
    summary: {
      character_count: new Set(colonies.map(colony => colony.character_id)).size,
      colony_count: colonies.length,
      facility_count: facilities.length,
      extractor_count: facilities.filter(pin => pin.is_extractor).length,
      factory_count: facilities.filter(pin => pin.is_factory).length,
      unconfigured_factory_count: facilities.filter(pin => pin.is_factory && !pin.schematic_id && !pin.schematic).length,
      route_count: colonies.reduce((sum, colony) => sum + colony.routes.length, 0),
    },
    notes: [
      "Installed facilities from the selected EQM character, system and planet-type scope; empty and unconfigured facilities are included.",
      "Observed inventory and projected inventory/status/output are separate. Projection warnings and checkpoint timestamps are retained.",
      "Recipe rates describe configured capacity when supplied, not guaranteed production. Missing values remain unknown.",
      "This is an inventory report, not an EVE clipboard layout. Link geometry, facility capacity and CPU/power usage are not supplied by this report.",
    ],
    colonies,
  };
}

type Report = ReturnType<typeof buildPlanetaryFacilitiesReport>;
type Cell = string | number | boolean | null | undefined;
const CSV_FIELDS = [
  "generated_at",
  "source_as_of",
  "character_name",
  "character_id",
  "character_eve_id",
  "colony_id",
  "planet_name",
  "planet_id",
  "planet_type",
  "solar_system_name",
  "solar_system_id",
  "security_status",
  "command_center_level",
  "esi_last_update",
  "last_synced_at",
  "checkpoint_at",
  "projected_at",
  "is_projection",
  "projection_truncated",
  "projection_warning",
  "facility_name",
  "facility_type_id",
  "pin_id",
  "facility_role",
  "latitude",
  "longitude",
  "observed_status",
  "projected_status",
  "content_source",
  "schematic_name",
  "schematic_id",
  "schematic_cycle_seconds",
  "output_name",
  "output_type_id",
  "output_quantity_per_cycle",
  "configured_output_per_day",
  "recipe_inputs_json",
  "install_time",
  "expiry_time",
  "last_cycle_start",
  "extractor_product_name",
  "extractor_product_type_id",
  "extractor_heads",
  "extractor_cycle_seconds",
  "extractor_quantity_per_cycle",
  "extractor_projected_daily_output",
  "extractor_projected_remaining_output",
  "observed_stored_volume_m3",
  "projected_stored_volume_m3",
  "observed_contents_json",
  "projected_contents_json",
  "projected_produced_json",
  "projected_blocked_json",
  "has_inbound_route",
  "inbound_routes_json",
  "outbound_routes_json"
] as const;

function csvCell(value: Cell) {
  if (value == null) return "";
  // Names can come from user-editable upstream data. Keep spreadsheet apps from treating them as formulas.
  const raw = String(value);
  const text = typeof value === "string" && /^[\s]*[=+@-]/.test(raw) ? `'${raw}` : raw;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function csvRows(report: Report) {
  return report.colonies.flatMap(colony => colony.facilities.map(pin => ({
    generated_at: report.generated_at,
    source_as_of: report.source_as_of,
    character_name: colony.character_name,
    character_id: colony.character_id,
    character_eve_id: colony.character_eve_id,
    colony_id: colony.colony_id,
    planet_name: colony.planet_name,
    planet_id: colony.planet_id,
    planet_type: colony.planet_type,
    solar_system_name: colony.solar_system_name,
    solar_system_id: colony.solar_system_id,
    security_status: colony.security_status,
    command_center_level: colony.command_center_level,
    esi_last_update: colony.esi_last_update,
    last_synced_at: colony.last_synced_at,
    checkpoint_at: colony.projection.checkpoint_at,
    projected_at: colony.projection.projected_at,
    is_projection: colony.projection.is_projection,
    projection_truncated: colony.projection.truncated,
    projection_warning: colony.projection.warning,
    facility_name: pin.type_name,
    facility_type_id: pin.type_id,
    pin_id: pin.pin_id,
    facility_role: pin.facility_role,
    latitude: pin.latitude,
    longitude: pin.longitude,
    observed_status: pin.status,
    projected_status: pin.projected_status,
    content_source: pin.content_source,
    schematic_name: pin.schematic?.name,
    schematic_id: pin.schematic_id ?? pin.schematic?.id,
    schematic_cycle_seconds: pin.schematic?.cycle_time,
    output_name: pin.schematic?.output.name,
    output_type_id: pin.schematic?.output.type_id,
    output_quantity_per_cycle: pin.schematic?.output.quantity,
    configured_output_per_day: pin.schematic && pin.schematic.cycle_time > 0
      ? pin.schematic.output.quantity * 86400 / pin.schematic.cycle_time : null,
    recipe_inputs_json: JSON.stringify(pin.schematic?.inputs ?? []),
    install_time: pin.install_time,
    expiry_time: pin.expiry_time,
    last_cycle_start: pin.last_cycle_start,
    extractor_product_name: pin.extractor?.product_name,
    extractor_product_type_id: pin.extractor?.product_type_id,
    extractor_heads: pin.extractor?.head_count,
    extractor_cycle_seconds: pin.extractor?.cycle_time,
    extractor_quantity_per_cycle: pin.extractor?.qty_per_cycle,
    extractor_projected_daily_output: pin.extractor?.projected_daily_output,
    extractor_projected_remaining_output: pin.extractor?.projected_remaining_output,
    observed_stored_volume_m3: pin.observed_stored_volume,
    projected_stored_volume_m3: pin.stored_volume,
    observed_contents_json: JSON.stringify(pin.observed_contents),
    projected_contents_json: JSON.stringify(pin.contents),
    projected_produced_json: JSON.stringify(pin.projected_produced),
    projected_blocked_json: JSON.stringify(pin.projected_blocked),
    has_inbound_route: pin.has_inbound_route,
    inbound_routes_json: JSON.stringify(colony.routes.filter(route => route.destination_pin_id === pin.pin_id)),
    outbound_routes_json: JSON.stringify(colony.routes.filter(route => route.source_pin_id === pin.pin_id)),
  })));
}

export function buildPlanetaryFacilitiesExport(
  data: PlanetaryIndustryPayload,
  format: PlanetaryExportFormat,
  scope: FacilitiesScope = defaultFacilitiesScope,
  generatedAt = new Date(),
): PlanetaryExport {
  const report = buildPlanetaryFacilitiesReport(data, scope, generatedAt);
  const basename = `planetary-facilities-${generatedAt.toISOString().replace(/:/g, "-").replace(/\.\d{3}Z$/, "Z")}`;
  const rows = csvRows(report);
  const fields = CSV_FIELDS;
  return {
    filename: `${basename}.${format}`,
    mimeType: format === "json" ? "application/json;charset=utf-8" : "text/csv;charset=utf-8",
    text: format === "json" ? `${JSON.stringify(report, null, 2)}\n`
      : `\uFEFF${[fields.join(","), ...rows.map(row => fields.map(field => csvCell(row[field as keyof typeof row])).join(","))].join("\r\n")}\r\n`,
    colonyCount: report.summary.colony_count,
    facilityCount: report.summary.facility_count,
    amountRowCount: rows.length,
  };
}
