import type { Blueprint } from "../../types/inventory";

export type BlueprintTechFilter = "all" | "2" | "3";
export type BlueprintProductFilter = "all" | "ships" | "modules";

/** Classify the manufactured product, including T3 subsystems under modules. */
export function matchesBlueprintTechnology(blueprint: Blueprint, tech: BlueprintTechFilter, product: BlueprintProductFilter): boolean {
  if (tech !== "all" && blueprint.product_tech_level !== Number(tech)) return false;
  if (product === "ships") return blueprint.product_category_id === 6;
  if (product === "modules") return blueprint.product_category_id === 7 || blueprint.product_category_id === 32;
  return true;
}
