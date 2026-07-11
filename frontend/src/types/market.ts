export type MarketStation = {
  station_id: number;
  name: string;
  type_id?: number | null;
  type_name?: string | null;
  operation_name?: string | null;
};

export type MarketHub = {
  key: string;
  label: string;
  region_id?: number | null;
  region_name?: string | null;
  location_id?: number | null;
  location_ids?: number[];
  system_id?: number | null;
  system_name?: string | null;
  station_names?: string[];
  station_count?: number;
  stations?: MarketStation[];
  destination_id?: number | null;
  destination_name?: string | null;
  destination_kind?: string | null;
  location_scope?: string | null;
  npc_group?: boolean;
  custom?: boolean;
  available: boolean;
};

export const BUILTIN_MARKET_HUBS: MarketHub[] = [
  { key: "jita", label: "Jita 4-4", region_id: 10000002, region_name: "The Forge", location_id: 60003760, available: true },
  { key: "amarr", label: "Amarr", region_id: 10000043, region_name: "Domain", location_id: 60008494, available: true },
  { key: "hek", label: "Hek", region_id: 10000042, region_name: "Metropolis", location_id: 60005686, available: true },
  { key: "dodixie", label: "Dodixie", region_id: 10000032, region_name: "Sinq Laison", location_id: 60011866, available: true },
  { key: "rens", label: "Rens", region_id: 10000030, region_name: "Heimatar", location_id: 60004588, available: true },
];

export type MarketHubQuote = {
  buy?: number | null;
  sell?: number | null;
  split?: number | null;
  buy_total?: number | null;
  sell_total?: number | null;
  split_total?: number | null;
  buy_orders: number;
  sell_orders: number;
  buy_source?: string | null;
  sell_source?: string | null;
};

export type MarketItemQuote = {
  input: string;
  name: string;
  quantity: number;
  type_id?: number | null;
  type_name?: string | null;
  matched: boolean;
  ambiguous_matches: { type_id: number; name: string }[];
  hubs: Record<string, MarketHubQuote>;
};

export type MarketAppraisal = {
  hubs: MarketHub[];
  items: MarketItemQuote[];
  totals: Record<string, { buy_total: number; sell_total: number; split_total: number }>;
  unmatched_count: number;
};
