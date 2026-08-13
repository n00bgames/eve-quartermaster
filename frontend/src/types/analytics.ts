export type AnalyticsPoint = { date?: string | null; corporation_id?: number; corporation_name?: string; value: number };

export type AnalyticsGrowth = { id?: number; name: string; value?: number; delta: number };
export type AnalyticsChangeBreakdown = {
  current: number;
  total_delta: number;
  organic_delta: number;
  coverage_delta: number;
  newly_tracked_count: number;
  newly_tracked: { id: number; name: string; value: number; first_observed_at: string }[];
};

export type DuplicateBlueprint = { owner_name: string; blueprint_type_name: string; is_copy: boolean; quantity: number; material_efficiency_levels: number[]; time_efficiency_levels: number[]; in_use: number };

export type DerivedMetricCatalogItem = { metric: string; label: string; unit: string; transform: string; windowDays?: number | null; valueKind: "derived"; materialized: false; requiresAbsolute: boolean; chartTypes: string[]; sourceMetric: string; privacy: string };

export type MetricCatalogItem = { metric: string; version: number; label: string; unit: string; aggregation: string; entityAggregation: string; timeAggregation: string; supportedAggregations: string[]; supportedTransforms: string[]; derivedMetrics: DerivedMetricCatalogItem[]; valueKind: string; dimensions: string[]; privacy: string; category: string; supportsCharacter: boolean; supportsCorporation: boolean; chartTypes: string[]; deprecated: boolean; registered: boolean; description: string; hasData?: boolean };

export type AnalyticsCorporationScope = {
  id: number;
  name: string;
  ticker?: string | null;
  hidden: boolean;
  excluded: boolean;
  managed: boolean;
  affiliation: boolean;
  historical: boolean;
  wallet_totals_visible: boolean;
};

export type AnalyticsCorporationScopeResponse = {
  can_manage: boolean;
  corporations: AnalyticsCorporationScope[];
};
export type AnalyticsMaintenancePreview = {
  strategy: string;
  candidate_rows: {
    snapshot_runs: number;
    blueprint_rows: number;
    skill_rows: number;
    corporation_rows: number;
    metric_rows: number;
  };
};
export type AnalyticsRetentionMode = "full" | "changes";
export type AnalyticsRetentionSettings = {
  mode: AnalyticsRetentionMode;
  can_manage: boolean;
  modes: { key: AnalyticsRetentionMode; label: string; description: string }[];
  note: string;
};
export type ManufacturingAnalyticsItem = {
  name: string;
  quantity: number;
  actual_cost: number;
  savings: number;
  kept_quantity: number;
  sold_quantity: number;
  sales_revenue: number;
  realized_profit: number;
};

export type ManufacturingAnalytics = {
  job_count: number;
  items_built: number;
  current_cost: number;
  actual_cost: number;
  savings: number;
  kept_items: number;
  sold_items: number;
  sales_revenue: number;
  realized_profit: number;
  top_items: ManufacturingAnalyticsItem[];
};
export type ResearchProjectAnalytics = {
  project_count: number;
  active_count: number;
  completed_count: number;
  by_activity: { name: string; count: number }[];
  by_character: { name: string; count: number }[];
};export type MiningAnalytics = {
  entry_count: number;
  recovered_volume: number;
  residue_volume: number;
  gross_volume: number;
  net_value: number;
  efficiency?: number | null;
  measured_volume: number;
  top_by_volume: { name: string; volume: number }[];
  top_by_efficiency: { name: string; efficiency: number }[];
};export type PlanetaryAnalyticsTier = {
  tier: string;
  label: string;
  estimated_units: number;
  estimated_volume: number;
  current_units_per_day: number;
  current_volume_per_day: number;
  product_count: number;
  character_count: number;
};
export type PlanetaryAnalyticsProduct = {
  product_type_id: number;
  product_name: string;
  tier: string;
  estimated_units: number;
  estimated_volume: number;
  current_units_per_day: number;
  current_volume_per_day: number;
  top_character?: string | null;
};
export type PlanetaryCharacterProduct = PlanetaryAnalyticsProduct & {
  character_id: number;
  character_name: string;
};
export type PlanetaryAnalytics = {
  days: number;
  has_history: boolean;
  cards: {
    estimated_volume: number;
    current_volume_per_day: number;
    product_count: number;
    character_count: number;
  };
  tiers: PlanetaryAnalyticsTier[];
  products: PlanetaryAnalyticsProduct[];
  character_products: PlanetaryCharacterProduct[];
};
export type AnalyticsSummary = {
  days: number;
  latest_snapshot_at?: string | null;
  latest_snapshot_status?: string | null;
  snapshot_count: number;
  observation_count: number;
  retention_mode: AnalyticsRetentionMode;
  coverage: {
    requested_from: string;
    requested_to: string;
    available_from?: string | null;
    available_to?: string | null;
    available_seconds: number;
    complete: boolean;
  };
  cards: { wallet_total: number; blueprint_total: number; member_total: number; character_count: number };
  change_composition: {
    skill_points: AnalyticsChangeBreakdown;
    corporation_wallets: AnalyticsChangeBreakdown;
    members: AnalyticsChangeBreakdown;
    blueprints: AnalyticsChangeBreakdown;
  };
  top_sp_gainers: AnalyticsGrowth[];
  top_sp_losses: AnalyticsGrowth[];
  top_skill_category_gainers: { name: string; delta: number }[];
  top_skill_category_losses: { name: string; delta: number }[];
  wallet_growth: AnalyticsGrowth[];
  member_growth: AnalyticsGrowth[];
  blueprint_growth: AnalyticsGrowth[];
  duplicate_blueprints: DuplicateBlueprint[];
  manufacturing: ManufacturingAnalytics;
  mining: MiningAnalytics;
  research_projects: ResearchProjectAnalytics;
  series: { wallet_totals: AnalyticsPoint[]; member_counts: AnalyticsPoint[]; blueprint_counts: AnalyticsPoint[] };
};
