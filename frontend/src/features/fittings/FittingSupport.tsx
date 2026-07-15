import type { SyntheticEvent } from "react";
import { useMemo } from "react";

import type { CharacterFittingRecord, FittingItem, FittingSearchType, FittingSimulationRequirement, FittingSimulationState, FittingSimulationStats, FittingWeaponEstimate, ResistanceProfile } from "../../types/fittings";

const numberFormatter = new Intl.NumberFormat();

type FittingAsset = { type_id: number; quantity: number; owner_name: string; location_name?: string | null; location_flag?: string | null };
type FittingAssetSummary = { type_id: number; quantity: number; stacks: number; locations: { owner: string; location: string; flag?: string | null; quantity: number }[] };
const CARGO_BAY_LABELS: Record<string, string> = {
  Cargo: "Cargo hold",
  DroneBay: "Drone bay",
  FighterBay: "Fighter hangar",
  FuelBay: "Fuel bay",
  FleetHangar: "Fleet hangar",
  ShipMaintenanceBay: "Ship maintenance bay",
  FleetMaintenanceBay: "Fleet maintenance bay",
  InfrastructureBay: "Infrastructure bay",
  OreHold: "Ore hold",
  MineralHold: "Mineral hold",
  GasHold: "Gas hold",
  IceHold: "Ice hold",
  AmmoHold: "Ammo hold",
  PlanetaryCommoditiesHold: "PI hold",
  CommandCenterHold: "Command center hold",
  QuafeHold: "Quafe hold",
};

export function cargoBayLabel(key: string): string {
  return CARGO_BAY_LABELS[key] ?? key.replace(/([a-z])([A-Z])/g, "$1 $2");
}

export function isCargoBayKey(key: string): boolean {
  return Boolean(CARGO_BAY_LABELS[key]);
}

export function formatVolumeM3(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value)} m3`;
}

export function fittingSlotKey(flag: string): string {

  const normalized = flag.toLowerCase();

  if (flag.startsWith("HiSlot")) return "HiSlot";

  if (flag.startsWith("MedSlot")) return "MedSlot";

  if (flag.startsWith("LoSlot")) return "LoSlot";

  if (flag.startsWith("RigSlot")) return "RigSlot";

  if (flag.startsWith("SubSystemSlot")) return "SubSystemSlot";

  if (flag.startsWith("ServiceSlot")) return "ServiceSlot";

  for (const key of Object.keys(CARGO_BAY_LABELS)) {

    if (flag.startsWith(key)) return key;

  }

  if (normalized.includes("cargo")) return "Cargo";

  return "Other";

}



export function romanLevel(level: number): string {

  return ["0", "I", "II", "III", "IV", "V"][level] ?? String(level);

}



export function eveTypeImageUrl(typeId?: number | null, variant: "icon" | "render" = "icon", size = 64): string {

  return typeId ? `https://images.evetech.net/types/${typeId}/${variant}?size=${size}` : "";

}



export function hideBrokenImage(event: SyntheticEvent<HTMLImageElement>) {

  event.currentTarget.style.display = "none";

}



export function fallbackShipImage(event: SyntheticEvent<HTMLImageElement>, typeId: number) {

  const image = event.currentTarget;

  if (image.dataset.fallback === "icon") {

    image.style.display = "none";

    return;

  }

  image.dataset.fallback = "icon";

  image.src = eveTypeImageUrl(typeId, "icon", 128);

}



export function fittingSkillPlanText(requirements: FittingSimulationRequirement[]): string {

  const missing = new Map<number, FittingSimulationRequirement>();

  for (const row of requirements) {

    if (row.met) continue;

    const existing = missing.get(row.skill_type_id);

    if (!existing || row.required_level > existing.required_level) missing.set(row.skill_type_id, row);

  }

  return [...missing.values()]

    .sort((left, right) => left.skill_name.localeCompare(right.skill_name, undefined, { numeric: true, sensitivity: "base" }))

    .map((row) => `${row.skill_name} ${romanLevel(row.required_level)}`)

    .join("\n");

}





function fittingStatValue(value?: number | null, digits = 0, suffix = ""): string {

  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";

  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value)}${suffix}`;

}



function durationValue(seconds?: number | null): string {

  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "n/a";

  if (seconds < 60) return `${Math.round(seconds)}s`;

  const minutes = Math.floor(seconds / 60);

  const remainder = Math.round(seconds % 60);

  if (minutes < 60) return `${minutes}m ${remainder}s`;

  const hours = Math.floor(minutes / 60);

  const mins = minutes % 60;

  return `${hours}h ${mins}m`;

}



function resistanceBadges(label: string, resists?: ResistanceProfile) {

  if (!resists) return null;

  return <div className="resistance-row"><span>{label}</span><b>EM {Math.round(resists.em * 100)}%</b><b>Th {Math.round(resists.thermal * 100)}%</b><b>Ki {Math.round(resists.kinetic * 100)}%</b><b>Ex {Math.round(resists.explosive * 100)}%</b></div>;

}



const FITTING_STATE_ORDER: FittingSimulationState[] = ["online", "active", "overheated", "offline"];

const DAMAGE_TYPE_LABELS: [keyof ResistanceProfile, string][] = [["em", "EM"], ["thermal", "Therm"], ["kinetic", "Kin"], ["explosive", "Exp"]];



export function nextFittingState(state?: FittingSimulationState): FittingSimulationState {

  const current = state ?? "online";

  const index = FITTING_STATE_ORDER.indexOf(current);

  return FITTING_STATE_ORDER[(index + 1) % FITTING_STATE_ORDER.length];

}



export function fittingStateLabel(state?: FittingSimulationState): string {

  if (state === "active") return "Active";

  if (state === "overheated") return "Overheated";

  if (state === "offline") return "Offline";

  return "Online";

}



function formatDistanceMeters(value?: number | null): string {

  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";

  if (value >= 1000) return fittingStatValue(value / 1000, 1, " km");

  return fittingStatValue(value, 0, " m");

}



function damageBadges(profile?: ResistanceProfile | null, scaleToPercent = false) {

  if (!profile) return null;

  const total = DAMAGE_TYPE_LABELS.reduce((sum, [key]) => sum + Math.max(0, Number(profile[key] ?? 0)), 0);

  if (total <= 0) return null;

  return <div className="damage-row">{DAMAGE_TYPE_LABELS.map(([key, label]) => <b key={key} className={`damage-${key}`}>{label} {scaleToPercent ? `${Math.round((Number(profile[key] ?? 0) / total) * 100)}%` : fittingStatValue(Number(profile[key] ?? 0), 0)}</b>)}</div>;

}



function damageText(profile?: ResistanceProfile | null): string | null {

  if (!profile) return null;

  const total = DAMAGE_TYPE_LABELS.reduce((sum, [key]) => sum + Math.max(0, Number(profile[key] ?? 0)), 0);

  if (total <= 0) return null;

  return DAMAGE_TYPE_LABELS.map(([key, label]) => `${label} ${fittingStatValue(Number(profile[key] ?? 0), 0)}`).join(" / ");

}



function tooltipLine(label: string, value?: string | number | null): string | null {

  if (value === null || value === undefined || value === "") return null;

  return `${label}: ${value}`;

}



export function fittingItemTooltip(item: FittingItem, estimate?: FittingWeaponEstimate): string {

  const lines = [

    item.type_name,

    item.charge_type_name ? `Loaded: ${item.charge_type_name}` : null,

    tooltipLine("State", fittingStateLabel(item.simulation_state)),

    item.quantity > 1 ? tooltipLine("Quantity", item.quantity.toLocaleString()) : null,

  ];

  if (estimate) {

    lines.push(

      tooltipLine("DPS", fittingStatValue(estimate.dps, 1)),

      tooltipLine("Volley", fittingStatValue(estimate.volley, 0)),

      tooltipLine("Optimal", formatDistanceMeters(estimate.optimal_m)),

      tooltipLine("Falloff", formatDistanceMeters(estimate.falloff_m)),

      tooltipLine("Max range", formatDistanceMeters(estimate.range_m)),

      tooltipLine("Missile velocity", estimate.missile_velocity_m_s == null ? null : fittingStatValue(estimate.missile_velocity_m_s, 1, " m/s")),

      tooltipLine("Flight time", estimate.missile_flight_time_s == null ? null : fittingStatValue(estimate.missile_flight_time_s, 1, " s")),

      tooltipLine("Damage", damageText(estimate.damage_types)),

      tooltipLine("Drone control range", formatDistanceMeters(estimate.control_range_m)),

      tooltipLine("Drone velocity", estimate.velocity_m_s == null ? null : fittingStatValue(estimate.velocity_m_s, 1, " m/s")),

      tooltipLine("Repair", estimate.repair_hps == null ? null : fittingStatValue(estimate.repair_hps, 1, " HP/s")),

      tooltipLine("Mining yield", estimate.mining_yield == null ? null : fittingStatValue(estimate.mining_yield, 1)),

      tooltipLine("Salvage bonus", estimate.salvage_bonus == null ? null : fittingStatValue(estimate.salvage_bonus, 2)),

      tooltipLine("ECM strength", estimate.ecm_strength == null ? null : fittingStatValue(estimate.ecm_strength, 2)),

      tooltipLine("Scramble strength", estimate.scramble_strength == null ? null : fittingStatValue(estimate.scramble_strength, 1)),

    );

  }

  lines.push(item.slot_group ? tooltipLine("Slot", item.flag) : null);

  return lines.filter(Boolean).join("\n");

}



export function chargeMatchesModule(item: FittingItem, charge: FittingSearchType): boolean {

  const moduleText = `${item.type_name} ${item.slot_group}`.toLowerCase();

  const chargeText = `${charge.name} ${charge.group_name ?? ""}`.toLowerCase();

  const chargeIsXl = /(^|\s)xl(\s|$)/.test(chargeText) || chargeText.includes("extra large");

  const moduleIsXl = /(^|\s)xl(\s|$)/.test(moduleText) || moduleText.includes("capital") || moduleText.includes("citadel");

  if (chargeText.includes("script")) return /(tracking computer|tracking link|sensor booster|remote sensor|guidance computer|guidance enhancer|missile guidance|omnidirectional tracking|warp disruption field)/.test(moduleText);

  if (moduleText.includes("capacitor booster") || moduleText.includes("ancillary shield booster")) return chargeText.includes("cap booster") || chargeText.includes("capacitor booster");

  if (moduleText.includes("rapid light") || moduleText.includes("light missile")) return !chargeIsXl && chargeText.includes("light missile");

  if (moduleText.includes("heavy assault")) return !chargeIsXl && chargeText.includes("heavy assault missile");

  if (moduleText.includes("heavy missile")) return !chargeIsXl && chargeText.includes("heavy missile") && !chargeText.includes("assault");

  if (moduleText.includes("cruise")) return chargeText.includes("cruise missile") && chargeIsXl === moduleIsXl;

  if (moduleText.includes("torpedo")) return chargeText.includes("torpedo") && chargeIsXl === moduleIsXl;

  if (moduleText.includes("rocket")) return !chargeIsXl && chargeText.includes("rocket");

  if (moduleText.includes("launcher")) return !chargeIsXl && (chargeText.includes("missile") || chargeText.includes("rocket") || chargeText.includes("torpedo"));

  if (moduleText.includes("laser")) return chargeText.includes("frequency crystal");

  if (moduleText.includes("railgun") || moduleText.includes("blaster") || moduleText.includes("hybrid")) return chargeText.includes("hybrid charge");

  if (moduleText.includes("autocannon") || moduleText.includes("artillery") || moduleText.includes("projectile")) return chargeText.includes("projectile ammo");

  return false;

}



export function FittingStatsPanel({ stats }: { stats?: FittingSimulationStats | null }) {

  if (!stats) return null;

  return <div className="fitting-stat-panel">

    <article>

      <h4>Offense</h4>

      <strong>{fittingStatValue(stats.offense.total_dps, 1)} DPS</strong>

      <span>{fittingStatValue(stats.offense.volley, 0)} volley · {formatDistanceMeters(stats.offense.max_range_m)} max range</span>

      {damageBadges(stats.offense.damage_types, true)}

      <div className="fitting-stat-pair"><span>Launchers</span><b>{fittingStatValue(stats.offense.launcher_dps, 1)}</b></div>

      <div className="fitting-stat-pair"><span>Turrets</span><b>{fittingStatValue(stats.offense.turret_dps, 1)}</b></div>

      <div className="fitting-stat-pair"><span>Drones</span><b>{fittingStatValue(stats.offense.drone_dps, 1)}</b></div>

      {stats.offense.weapons.length > 0 && <details><summary>Weapon estimates</summary><div className="mini-list fitting-weapon-list">{stats.offense.weapons.map((weapon) => <div key={`${weapon.name}-${weapon.charge_name ?? "native"}`}><strong>{weapon.name}</strong><span>{fittingStatValue(weapon.dps, 1)} DPS{weapon.charge_name ? ` · ${weapon.charge_name}` : ""}</span></div>)}</div></details>}

    </article>

    <article>

      <h4>Tank</h4>

      <strong>{fittingStatValue(stats.defense.ehp, 0)} EHP</strong>

      <span>{fittingStatValue(stats.defense.shield_peak_recharge, 1)} passive shield HP/s peak</span>

      <div className="fitting-stat-pair"><span>Active tank</span><b>{fittingStatValue(stats.defense.active_tank_hps, 1, " HP/s")}</b></div>

      <div className="fitting-stat-pair"><span>Shield</span><b>{fittingStatValue(stats.defense.shield_hp, 0)} HP</b></div>

      <div className="fitting-stat-pair"><span>Armor</span><b>{fittingStatValue(stats.defense.armor_hp, 0)} HP</b></div>

      <div className="fitting-stat-pair"><span>Hull</span><b>{fittingStatValue(stats.defense.structure_hp, 0)} HP</b></div>

      {resistanceBadges("Shield", stats.defense.shield_resists)}

      {resistanceBadges("Armor", stats.defense.armor_resists)}

      {resistanceBadges("Hull", stats.defense.structure_resists)}

    </article>

    <article>

      <h4>Movement</h4>

      <strong>{fittingStatValue(stats.mobility.max_velocity, 1, " m/s")}</strong>

      <span>{fittingStatValue(stats.mobility.align_time, 1, "s")} align · {fittingStatValue(stats.mobility.warp_speed, 2, " AU/s")} warp</span>

      <div className="fitting-stat-pair"><span>Signature</span><b>{fittingStatValue(stats.mobility.signature_radius, 0, " m")}</b></div>

      <div className="fitting-stat-pair"><span>Mass</span><b>{fittingStatValue(stats.mobility.mass, 0, " kg")}</b></div>

      <div className="fitting-stat-pair"><span>Targets</span><b>{fittingStatValue(stats.targeting.max_targets, 0)}</b></div>

      <div className="fitting-stat-pair"><span>Lock range</span><b>{fittingStatValue(stats.targeting.targeting_range == null ? null : stats.targeting.targeting_range / 1000, 1, " km")}</b></div>

      <div className="fitting-stat-pair"><span>Drone control</span><b>{formatDistanceMeters(stats.targeting.drone_control_range_m)}</b></div>

    </article>

    {(stats.cargo_bays?.length ?? 0) > 0 && <article>

      <h4>Cargo</h4>

      <strong>{formatVolumeM3(stats.cargo_bays?.reduce((sum, bay) => sum + Number(bay.used ?? 0), 0) ?? 0)}</strong>

      <span>{stats.cargo_bays?.filter((bay) => bay.capacity != null).length ?? 0} capacity-backed bay{(stats.cargo_bays?.filter((bay) => bay.capacity != null).length ?? 0) === 1 ? "" : "s"}</span>

      {stats.cargo_bays?.map((bay) => <div key={bay.key} className={bay.ok ? "fitting-stat-pair" : "fitting-stat-pair over-limit"}><span>{bay.label}</span><b>{formatVolumeM3(bay.used)} / {bay.capacity == null ? "?" : formatVolumeM3(bay.capacity)}</b></div>)}

    </article>}
    <article>

      <h4>Capacitor</h4>

      <strong>{stats.capacitor.stable ? `Stable ${fittingStatValue(stats.capacitor.stable_percent, 1, "%")}` : `Lasts ${durationValue(stats.capacitor.depletion_seconds)}`}</strong>

      <span>{fittingStatValue(stats.capacitor.capacity, 0, " GJ")} · {fittingStatValue(stats.capacitor.recharge_time, 1, "s")} recharge</span>

      <div className="fitting-stat-pair"><span>Draw</span><b>{fittingStatValue(stats.capacitor.draw_per_second, 2, " GJ/s")}</b></div>

      <div className="fitting-stat-pair"><span>Peak recharge</span><b>{fittingStatValue(stats.capacitor.peak_recharge, 2, " GJ/s")}</b></div>

      {(stats.capacitor.modules?.length ?? 0) > 0 && <details><summary>Cap flow</summary><div className="mini-list fitting-weapon-list">{stats.capacitor.modules?.map((mod) => <div key={mod.name}><strong>{mod.name}</strong><span>{fittingStatValue(mod.gj_per_second, 2, " GJ/s")} · {durationValue(mod.cycle_seconds)} cycle</span></div>)}</div></details>}

      <div className="fitting-stat-pair"><span>Scan res</span><b>{fittingStatValue(stats.targeting.scan_resolution, 0, " mm")}</b></div>

      <div className="fitting-stat-pair"><span>Sensor</span><b>{fittingStatValue(stats.targeting.sensor_strength, 1)}</b></div>

    </article>

  </div>;

}



type FittingContextNeed = { type_id: number; name: string; required: number; owned: number; missing: number; locations: { owner: string; location: string; flag?: string | null; quantity: number }[] };

function fittingMarketList(needs: FittingContextNeed[], onlyMissing: boolean): string {

  return needs

    .filter((need) => onlyMissing ? need.missing > 0 : true)

    .map((need) => `${onlyMissing ? need.missing : need.required} ${need.name}`)

    .join("\n");

}

function fittingContextNeeds(fitting: CharacterFittingRecord, assets: FittingAsset[], assetSummaries: FittingAssetSummary[] = []): FittingContextNeed[] {

  const required = new Map<number, { name: string; quantity: number }>();

  function add(typeId: number, name: string, quantity: number) {

    const nextQuantity = Math.max(1, quantity || 1);

    const current = required.get(typeId);

    required.set(typeId, { name, quantity: (current?.quantity ?? 0) + nextQuantity });

  }

  add(fitting.ship_type_id, fitting.ship_type_name, 1);

  for (const item of fitting.items) add(item.type_id, item.type_name, item.quantity);

  const assetsByType = new Map<number, FittingAsset[]>();

  for (const asset of assets) assetsByType.set(asset.type_id, [...(assetsByType.get(asset.type_id) ?? []), asset]);

  const summaryByType = new Map(assetSummaries.map((summary) => [summary.type_id, summary]));

  return [...required.entries()].map(([typeId, row]) => {

    const matchingAssets = assetsByType.get(typeId) ?? [];

    const summary = summaryByType.get(typeId);

    const owned = summary ? summary.quantity : matchingAssets.reduce((total, asset) => total + asset.quantity, 0);

    return {

      type_id: typeId,

      name: row.name,

      required: row.quantity,

      owned,

      missing: Math.max(0, row.quantity - owned),

      locations: summary ? summary.locations.slice(0, 6) : matchingAssets.slice(0, 4).map((asset) => ({ owner: asset.owner_name, location: asset.location_name ?? "Unknown location", flag: asset.location_flag, quantity: asset.quantity })),

    };

  }).sort((left, right) => Number(right.missing > 0) - Number(left.missing > 0) || left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: "base" }));

}

export function FittingContextPanel({ fitting, assets, assetSummaries = [], contextLoading = false, onOpenAssets, onOpenMarket }: { fitting: CharacterFittingRecord; assets: FittingAsset[]; assetSummaries?: FittingAssetSummary[]; contextLoading?: boolean; onOpenAssets: (itemName?: string) => void; onOpenMarket: (text: string) => void }) {

  const needs = useMemo(() => fittingContextNeeds(fitting, assets, assetSummaries), [fitting, assets, assetSummaries]);

  const missing = needs.filter((need) => need.missing > 0);

  const hullNeed = needs.find((need) => need.type_id === fitting.ship_type_id);

  const coveredCount = needs.filter((need) => need.missing === 0).length;

  const missingUnits = missing.reduce((total, need) => total + need.missing, 0);

  const missingText = fittingMarketList(needs, true);

  const fullText = fittingMarketList(needs, false);

  return <section className="fitting-context-panel">

    <div className="section-heading compact"><div><h4>Fit Context</h4><p>Inventory and market handoffs for this hull, modules, drones, and cargo.</p></div><div className="context-actions"><button type="button" onClick={() => onOpenAssets()}>Asset Ledger</button><button type="button" disabled={!missingText} onClick={() => onOpenMarket(missingText)}>Price missing</button><button type="button" disabled={!fullText} onClick={() => onOpenMarket(fullText)}>Price full fit</button></div></div>

    {contextLoading && <p className="muted">Checking full visible inventory...</p>}

    <div className="fitting-context-grid"><article><span>Hull</span><strong className={(hullNeed?.owned ?? 0) > 0 ? "context-owned" : "context-missing"}>{(hullNeed?.owned ?? 0) > 0 ? "Owned" : "Missing"}</strong><small>{fitting.ship_type_name} x{numberFormatter.format(hullNeed?.owned ?? 0)}</small></article><article><span>Fit coverage</span><strong>{coveredCount}/{needs.length}</strong><small>{needs.length ? Math.round((coveredCount / needs.length) * 100) : 0}% covered by visible assets</small></article><article><span>Missing units</span><strong className={missingUnits > 0 ? "context-missing" : "context-owned"}>{numberFormatter.format(missingUnits)}</strong><small>{missing.length} item type{missing.length === 1 ? "" : "s"} short</small></article></div>

    <div className="fitting-context-list">{needs.map((need) => <div key={need.type_id} className={`fitting-context-row ${need.missing > 0 ? "missing" : "covered"}`}><b>{need.name}</b><span>Need {numberFormatter.format(need.required)}</span><span>Own {numberFormatter.format(need.owned)}</span><span className={need.missing > 0 ? "missing-count" : "covered-count"}>{need.missing > 0 ? `Short ${numberFormatter.format(need.missing)}` : "Covered"}</span><small>{need.locations.length > 0 ? need.locations.map((location) => `${location.owner} @ ${location.location}${location.flag ? ` (${location.flag})` : ""} x${numberFormatter.format(location.quantity)}`).join(" | ") : "Not in visible assets"}</small><div className="context-actions"><button type="button" onClick={() => onOpenAssets(need.name)}>Assets</button><button type="button" onClick={() => onOpenMarket(`${Math.max(1, need.missing || need.required)} ${need.name}`)}>Price</button></div></div>)}</div>

  </section>;

}
