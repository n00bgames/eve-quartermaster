export type ImplantDogmaAttribute = {
  attribute_id: number;
  name: string;
  display_name?: string | null;
  description?: string | null;
  unit_id?: number | null;
  value: number;
};

export type ImplantDogmaEffect = {
  effect_id: number;
  name: string;
  display_name?: string | null;
  description?: string | null;
  category_id?: number | null;
  is_default?: boolean;
};

export type ImplantDogma = {
  attributes: ImplantDogmaAttribute[];
  effects: ImplantDogmaEffect[];
};

export type JumpCloneImplant = {
  type_id: number;
  name: string;
  slot?: number | null;
  group_name?: string | null;
  market_group_id?: number | null;
  dogma?: ImplantDogma;
};

export type JumpCloneCharacter = {
  id: number;
  character_id: number;
  name: string;
  portrait_url?: string | null;
  owner_display_name?: string | null;
  sync_opt_out?: boolean;
};

export type JumpCloneRecord = {
  id: number;
  character_id: number;
  clone_kind: "active_clone" | "jump_clone" | string;
  jump_clone_id?: number | null;
  name: string;
  location_id?: number | null;
  location_type?: string | null;
  location_name?: string | null;
  system_id?: number | null;
  system_name?: string | null;
  last_synced_at?: string | null;
  implants: JumpCloneImplant[];
};

export type ImplantSetRecord = {
  id: number;
  name: string;
  description?: string | null;
  character_id?: number | null;
  character_name?: string | null;
  owner_user_id: number;
  owner_display_name?: string | null;
  is_shared: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  implants: JumpCloneImplant[];
  can_manage: boolean;
};

export type JumpCloneSyncToken = {
  token_id: number;
  character_id: number;
  character_name: string;
  can_sync: boolean;
  has_clone_scope: boolean;
  has_implant_scope: boolean;
  missing_scopes: string[];
};

export type JumpClonePayload = {
  characters: JumpCloneCharacter[];
  clones: JumpCloneRecord[];
  custom_sets: ImplantSetRecord[];
  sync_tokens: JumpCloneSyncToken[];
};


