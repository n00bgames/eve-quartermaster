export type Summary = { owners: number; locations: number; types: number; asset_stacks: number; asset_units: number; blueprints: number; industry_activities: number };

export type Owner = { id: number; owner_kind: string; display_name: string; notes?: string };

export type EveType = { type_id: number; name: string; group_id?: number; group_name?: string | null; category_id?: number | null; category_name?: string | null; volume?: number; market_group_id?: number | null };

export type Location = { id: number; location_kind: string; name: string; notes?: string };

export type Asset = { id: number; ownership_entity_id: number; owner_name: string; owner_kind?: string; type_id: number; type_name: string; quantity: number; location_name?: string; location_id?: number | null; location_flag?: string; source: string; last_synced_at?: string | null; parent_asset_item_id?: number; parent_asset_type_name?: string; is_blueprint_copy?: boolean | null; inventory_family?: string | null; inventory_subtype?: string | null; type_group_id?: number | null; type_group_name?: string | null; type_category_id?: number | null; type_category_name?: string | null; type_market_group_id?: number | null };

export type Blueprint = { id: number; owner_name: string; blueprint_type_id: number; blueprint_type_name: string; product_type_id?: number | null; product_type_name?: string; material_efficiency: number; time_efficiency: number; runs_remaining?: number; is_copy: boolean; location_name?: string; location_id?: number | null; last_synced_at?: string | null; inventory_family?: string | null; inventory_subtype?: string | null; capital_construction_related?: boolean; blueprint_group_id?: number | null; blueprint_group_name?: string | null; blueprint_category_id?: number | null; blueprint_category_name?: string | null; product_group_id?: number | null; product_group_name?: string | null; product_category_id?: number | null; product_category_name?: string | null; product_market_group_id?: number | null };

export type MissingBlueprintItem = { blueprint_type_id: number; blueprint_type_name: string; product_type_id?: number | null; product_type_name?: string | null; product_group_name?: string | null; product_category_name?: string | null; inventory_family?: string | null; inventory_subtype?: string | null; capital_construction_related?: boolean };

export type MissingBlueprintCategory = { category_name: string; total_count: number; items: MissingBlueprintItem[] };

export type MissingBlueprintCatalog = { total_missing: number; owned_bpos: number; categories: MissingBlueprintCategory[] };

export type ActivityInput = { id: number; input_type_id?: number | null; input_type_name: string; quantity: number; consume_type: string };

export type IndustryActivity = { id: number; activity_kind: string; blueprint_type_id?: number | null; blueprint_type_name: string; product_type_id?: number | null; product_type_name?: string; product_quantity: number; time_seconds?: number; inputs: ActivityInput[] };

export type InventoryFamilyFilter = "all" | "ships" | "ammunition" | "drones" | "rigs" | "reactions" | "ram" | "blueprints" | "capital-construction";

export type AssetSortKey = "item" | "owner" | "quantity" | "location" | "flag";

export type AssetFilterKey = Exclude<AssetSortKey, "quantity">;

export type OwnerKindFilter = "character" | "corporation" | "alliance" | "manual_group";

export type AssetFilter = { key: AssetFilterKey; value: string; label: string; mode: "exact" | "contains" };

export type SortDirection = "asc" | "desc";

export type AssetTableSeed = { key: AssetFilterKey; value: string; mode: AssetFilter["mode"]; nonce: number };
