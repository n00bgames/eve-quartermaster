export type CorporationToken = {
  token_id: number;
  character_name: string;
  user_display_name: string;
  has_corporation_asset_scope: boolean;
  can_sync: boolean;
  has_corporation_blueprint_scope: boolean;
  can_sync_blueprints: boolean;
  has_corporation_wallet_scope?: boolean;
  can_sync_wallets?: boolean;
};

export type CorporationWalletDivision = {
  division: number;
  balance: number;
  last_synced_at?: string | null;
};

export type EqmCorporation = {
  id: number;
  corporation_id: number;
  name: string;
  ticker?: string | null;
  alliance_id?: number | null;
  alliance_name?: string | null;
  ceo_character_eve_id?: number | null;
  ceo_character_name?: string | null;
  member_count?: number | null;
  hide_from_corporation_list?: boolean;
  last_synced_at?: string | null;
  asset_rows: number;
  blueprint_rows: number;
  last_asset_sync_at?: string | null;
  last_asset_sync_status?: string | null;
  last_asset_sync_message?: string | null;
  asset_sync_stale?: boolean;
  last_blueprint_sync_at?: string | null;
  last_blueprint_sync_status?: string | null;
  last_blueprint_sync_message?: string | null;
  blueprint_sync_stale?: boolean;
  last_wallet_sync_at?: string | null;
  last_wallet_sync_status?: string | null;
  last_wallet_sync_message?: string | null;
  wallet_sync_stale?: boolean;
  wallet_divisions: CorporationWalletDivision[];
  eligible_tokens: CorporationToken[];
};