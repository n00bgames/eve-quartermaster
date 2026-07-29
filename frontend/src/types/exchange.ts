export type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export type ExchangeItem = {
  id?: number;
  type_id?: number | null;
  name: string;
  quantity: number;
  notes?: string | null;
};

export type ExchangeAppraisal = {
  hub_key: string;
  hub_name: string;
  immediate_buy_value?: number | null;
  immediate_sell_value?: number | null;
  replacement_value?: number | null;
  asking_delta?: number | null;
  asking_delta_percent?: number | null;
  source: string;
  priced_at?: string | null;
};

export type ExchangeClaim = {
  id: number;
  claimant_name: string;
  quantity: number;
  total_price?: number | null;
  status: string;
  expires_at?: string | null;
};

export type ExchangeBid = {
  id: number;
  bidder_name: string;
  bidder_contact?: string | null;
  bidder_user_id?: number | null;
  external: boolean;
  quantity: number;
  amount: number;
  message?: string | null;
  status: string;
  expires_at?: string | null;
  created_at?: string | null;
};

export type ExchangeListing = {
  public_id: string;
  listing_type: string;
  status: string;
  title: string;
  summary?: string | null;
  description?: string | null;
  seller_user_id?: number | null;
  seller_name: string;
  seller_character_id?: number | null;
  seller_corporation_id?: number | null;
  seller_corporation_name?: string | null;
  contact_method?: string | null;
  quantity_total: number;
  quantity_available: number;
  asking_price?: number | null;
  unit_price?: number | null;
  minimum_bid?: number | null;
  reserve_price?: number | null;
  sell_as_complete_lot: boolean;
  bid_visibility?: "public" | "highest_only" | "private";
  bid_count?: number;
  highest_bid?: number | null;
  next_minimum_bid?: number | null;
  reserve_met?: boolean;
  auction_ended?: boolean;
  visibility: string;
  eligibility_notes?: string | null;
  location: string;
  location_text?: string | null;
  division_name?: string | null;
  condition_notes?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  is_owner?: boolean;
  public_view?: boolean;
  items: ExchangeItem[];
  appraisals: ExchangeAppraisal[];
  claims?: ExchangeClaim[];
  bids?: ExchangeBid[];
};

export type SellerCharacter = {
  id: number;
  character_id: number;
  name: string;
  corporation_name?: string | null;
};

export type ExchangeDraftAppraisal = {
  appraisals: ExchangeAppraisal[];
  unmatched_items: string[];
  quantity_total: number;
};