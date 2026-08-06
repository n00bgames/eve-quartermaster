export type EqmCharacter = {
  id: number;
  character_id?: number;
  name: string;
  security_status?: number | null;
  can_view_detail: boolean;
  owner_user_id?: number | null;
  owner_display_name?: string | null;
  owner_role?: string | null;
  corporation_id?: number | null;
  corporation_name?: string | null;
  alliance_id?: number | null;
  alliance_name?: string | null;
  public_assets_visible?: boolean;
  sync_opt_out?: boolean;
  wallet_history_opt_out?: boolean;
  wallet_corporation_analytics_opt_in?: boolean;
  current_wallet_balance?: number | null;
  wallet_synced_at?: string | null;
  last_synced_at?: string | null;
  can_manage?: boolean;
  can_assign?: boolean;
};

export type CharacterSkillCategorySummary = {
  name: string;
  skill_points: number;
  skill_count: number;
};

export type CharacterSummary = {
  character: {
    id: number;
    character_id: number;
    name: string;
    portrait_url?: string | null;
    security_status?: number | null;
    corporation_name?: string | null;
    alliance_name?: string | null;
    owner_display_name?: string | null;
    owner_role?: string | null;
  };
  total_skill_points: number;
  unallocated_skill_points: number;
  skills_synced_at?: string | null;
  queue_count: number;
  skill_categories: CharacterSkillCategorySummary[];
  asset_rows: number;
  asset_units: number;
  ship_units: number;
  blueprints: number;
  bpos: number;
  bpcs: number;
  fittings: number;
  contracts: number;
  wallet_balance?: number | null;
  wallet_synced_at?: string | null;
};

export type CharacterDossierToken = {
  token_id: number;
  linked_user_id: number;
  linked_user_display_name: string;
  can_sync: boolean;
  has_asset_scope: boolean;
  has_skill_scope: boolean;
  has_fitting_scope: boolean;
  has_contract_scope: boolean;
  has_clone_scope: boolean;
  has_standings_scope: boolean;
  has_wallet_scope: boolean;
  missing_scopes: string[];
  linked_at?: string | null;
};

export type CharacterStandingSourceType = "agent" | "npc_corp" | "faction";

export type CharacterStanding = {
  id: number;
  source_type: CharacterStandingSourceType;
  source_eve_id: number;
  source_name: string;
  standing: number;
  last_synced_at?: string | null;
};
export type CharacterDossierFitting = {
  id: number;
  name: string;
  ship_type_id: number;
  ship_type_name: string;
  is_shared: boolean;
  is_draft: boolean;
  last_synced_at?: string | null;
  updated_at?: string | null;
};

export type CharacterDossierContract = {
  id: number;
  contract_id: number;
  title?: string | null;
  contract_type?: string | null;
  status?: string | null;
  reward?: number | null;
};

export type CharacterKillSample = {
  killmail_id: number;
  killmail_time?: string | null;
  location_name?: string | null;
  victim_character_name?: string | null;
  victim_hull?: string | null;
  smartbomb_used?: boolean;
  is_wardec?: boolean;
  zkb_url?: string | null;
};

export type CharacterDossier = {
  character: EqmCharacter;
  summary: CharacterSummary;
  sync_tokens: CharacterDossierToken[];
  skills: {
    categories: CharacterSkillCategorySummary[];
    queue: {
      id: number;
      queue_position: number;
      skill_type_id: number;
      skill_name: string;
      finished_level: number;
      finish_date?: string | null;
    }[];
  };
  assets: any[];
  blueprints: any[];
  fittings: CharacterDossierFitting[];
  contracts: CharacterDossierContract[];
  standings: {
    synced_at?: string | null;
    entries: CharacterStanding[];
  };
  kill_history: {
    kills_count: number;
    losses_count: number;
    isk_destroyed: number | null;
    isk_lost: number | null;
    kills: CharacterKillSample[];
    losses: CharacterKillSample[];
  };
  permissions: {
    public_assets_visible: boolean;
    sync_opt_out: boolean;
    wallet_history_opt_out: boolean;
    wallet_corporation_analytics_opt_in: boolean;
    can_manage_wallet_privacy: boolean;
    isk_values_visible: boolean;
    can_manage: boolean;
    can_assign: boolean;
  };
};

export type CharacterFocus = {
  characterId?: number | null;
  name?: string;
  nonce: number;
};
