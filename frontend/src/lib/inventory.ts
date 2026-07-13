import type { Asset, Blueprint, InventoryFamilyFilter } from "../types/inventory";

export const inventoryFamilyLabels: Record<InventoryFamilyFilter, string> = {
  all: "All",
  ships: "Ships",
  ammunition: "Ammunition",
  drones: "Drones/Fighters",
  rigs: "Rigs",
  reactions: "Reactions",
  ram: "RAM",
  blueprints: "Blueprints",
  "capital-construction": "Capital construction",
};

export function sortedUnique(values: (string | null | undefined)[]): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort((left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));
}

function familyFromLineage(categoryName?: string | null, groupName?: string | null): InventoryFamilyFilter | "other" {
  const category = (categoryName ?? "").toLowerCase();
  const group = (groupName ?? "").toLowerCase();
  if (category === "ship") return "ships";
  if (category === "charge") return "ammunition";
  if (category === "drone" || category === "fighter" || group.includes("drone") || group.includes("fighter")) return "drones";
  if (group.includes("rig")) return "rigs";
  if (group.includes("reaction")) return "reactions";
  if (group.includes("r.a.m") || group.includes("ram")) return "ram";
  if (category === "blueprint") return "blueprints";
  return "other";
}

function normalizeInventoryFamily(value?: string | null): InventoryFamilyFilter | "other" {
  return value === "ships" || value === "ammunition" || value === "drones" || value === "rigs" || value === "reactions" || value === "ram" || value === "blueprints" ? value : "other";
}

function familyFromText(...values: (string | null | undefined)[]): InventoryFamilyFilter | "other" {
  const text = values.filter(Boolean).join(" ").toLowerCase();
  if (text.includes("reaction formula") || text.includes(" reaction ")) return "reactions";
  if (text.includes("drone") || text.includes("fighter")) return "drones";
  if (text.includes("r.a.m") || text.includes("ram-")) return "ram";
  return "other";
}

export function assetFamily(asset: Asset): InventoryFamilyFilter | "other" {
  const reported = normalizeInventoryFamily(asset.inventory_family);
  return reported !== "other" ? reported : familyFromLineage(asset.type_category_name, asset.type_group_name);
}

export function blueprintFamily(blueprint: Blueprint): InventoryFamilyFilter | "other" {
  const reported = normalizeInventoryFamily(blueprint.inventory_family);
  if (reported !== "other") return reported;
  const lineage = familyFromLineage(blueprint.product_category_name, blueprint.product_group_name);
  if (lineage !== "other") return lineage;
  return familyFromText(blueprint.blueprint_type_name, blueprint.product_type_name, blueprint.blueprint_group_name);
}

export function assetSubtype(asset: Asset): string | null {
  return asset.inventory_subtype ?? asset.type_group_name ?? null;
}

export function blueprintSubtype(blueprint: Blueprint): string | null {
  const text = `${blueprint.blueprint_type_name} ${blueprint.product_type_name ?? ""}`.toLowerCase();
  if (blueprint.inventory_subtype) return blueprint.inventory_subtype;
  if (blueprint.product_group_name) return blueprint.product_group_name;
  if (text.includes("reaction formula")) return "Reaction Formula";
  if (text.includes("r.a.m")) return "R.A.M.";
  return blueprint.blueprint_group_name ?? null;
}

export function looksCapitalRelated(...values: (string | null | undefined)[]): boolean {
  const text = values.filter(Boolean).join(" ").toLowerCase();
  return ["capital", "dreadnought", "carrier", "force auxiliary", "supercarrier", "titan", "freighter", "jump freighter"].some((term) => text.includes(term));
}

export function matchesInventoryFamily(family: InventoryFamilyFilter, rowFamily: InventoryFamilyFilter | "other", capitalRelated = false): boolean {
  if (family === "all") return true;
  if (family === "capital-construction") return capitalRelated;
  return rowFamily === family;
}

export function visibleAssetQuantity(assets: Asset[], itemName?: string | null): number {
  if (!itemName) return 0;
  const normalized = itemName.toLowerCase();
  return assets.filter((asset) => asset.type_name.toLowerCase() === normalized).reduce((total, asset) => total + asset.quantity, 0);
}

export function visibleAssetLocations(assets: Asset[], itemName?: string | null): string[] {
  if (!itemName) return [];
  const normalized = itemName.toLowerCase();
  return assets
    .filter((asset) => asset.type_name.toLowerCase() === normalized && asset.location_name)
    .slice(0, 4)
    .map((asset) => `${asset.owner_name} @ ${asset.location_name}${asset.location_flag ? ` (${asset.location_flag})` : ""} x${asset.quantity.toLocaleString()}`);
}
