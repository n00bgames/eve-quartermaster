export type AnalyticsPoint = { date?: string | null; corporation_name?: string; value: number };

export type AnalyticsGrowth = { id?: number; name: string; value?: number; delta: number };

export type DuplicateBlueprint = { owner_name: string; blueprint_type_name: string; is_copy: boolean; quantity: number };

export type MetricCatalogItem = { metric: string; version: number; label: string; unit: string; aggregation: string; category: string; supportsCharacter: boolean; supportsCorporation: boolean; chartTypes: string[]; deprecated: boolean; hasData?: boolean };

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
export type AnalyticsSummary = {
  days: number;
  latest_snapshot_at?: string | null;
  latest_snapshot_status?: string | null;
  snapshot_count: number;
  cards: { wallet_total: number; blueprint_total: number; member_total: number; character_count: number };
  top_sp_gainers: AnalyticsGrowth[];
  top_sp_losses: AnalyticsGrowth[];
  top_skill_category_gainers: { name: string; delta: number }[];
  top_skill_category_losses: { name: string; delta: number }[];
  wallet_growth: AnalyticsGrowth[];
  member_growth: AnalyticsGrowth[];
  blueprint_growth: AnalyticsGrowth[];
  duplicate_blueprints: DuplicateBlueprint[];
  manufacturing: ManufacturingAnalytics;
  series: { wallet_totals: AnalyticsPoint[]; member_counts: AnalyticsPoint[]; blueprint_counts: AnalyticsPoint[] };
};