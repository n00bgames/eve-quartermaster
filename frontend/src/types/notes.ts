import type { MarketAppraisal, MarketHub } from "./market";

export type NoteKind = "freeform" | "item_list";
export type NoteItemStatus = "needed" | "planned" | "purchased" | "in_transit" | "delivered" | "skipped";
export type NoteAssetScope = "all" | "character" | "corporation";

export type EveTypeCandidate = {
  type_id: number;
  name: string;
  group_name?: string | null;
  category_name?: string | null;
  volume?: number | null;
  published: boolean;
};

export type NoteAssetLocation = {
  owner_name: string;
  location_name: string;
  at_destination: boolean;
  quantity: number;
};

export type NoteItem = {
  id: number;
  type_id?: number | null;
  name: string;
  original_text: string;
  requested_quantity: number;
  status: NoteItemStatus;
  sort_order: number;
  completed: boolean;
  volume?: number | null;
  group_name?: string | null;
  category_name?: string | null;
  candidates: EveTypeCandidate[];
  asset_context: {
    at_destination: number;
    elsewhere: number;
    remaining: number;
    locations: NoteAssetLocation[];
  };
};

export type NoteListRow = {
  id: number;
  note_type: NoteKind;
  title: string;
  body?: string | null;
  tags: string[];
  destination_system_id?: number | null;
  destination_system_name?: string | null;
  destination_security_status?: number | null;
  destination_location_id?: number | null;
  destination_location_name?: string | null;
  source_market_hub_key?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  deleted_at?: string | null;
  item_count: number;
  item_names: string[];
};

export type NoteDetail = NoteListRow & {
  items: NoteItem[];
  summary: {
    item_count: number;
    requested_units: number;
    remaining_units: number;
    completed_items: number;
    unresolved_items: number;
  };
  asset_scope: {
    selected: NoteAssetScope;
    selected_owner_ids: number[];
    owners: { id: number; name: string; kind: string }[];
    freshness: {
      available: boolean;
      latest_synced_at?: string | null;
      oldest_synced_at?: string | null;
      stale: boolean;
      scope_kinds: string[];
      asset_stacks: number;
    };
  };
};

export type NoteSystemResult = {
  system_id: number;
  name: string;
  security_status?: number | null;
  security_class?: string | null;
};

export type NoteLocationResult = {
  id?: number | null;
  eve_location_id?: number | null;
  name: string;
  kind: string;
  source: string;
};

export type NotePriceResult = MarketAppraisal & {
  priced_at: string;
  quantity_mode: "remaining" | "requested";
};

export type { MarketHub };