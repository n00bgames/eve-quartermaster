export type EsiAuthInfo = {
  ready: boolean;
  message?: string;
  url?: string;
  required_scopes: string[];
};

export type LinkedCharacter = {
  token_id: number;
  character_id: number;
  character_name: string;
  security_status?: number | null;
  linked_user_id: number;
  linked_user_display_name: string;
  can_sync_assets: boolean;
  can_unlink: boolean;
  scopes: string;
  access_token_expires_at?: string;
  linked_at?: string;
  last_sync_at?: string;
  last_sync_type?: string;
  last_sync_status?: string;
  missing_public_scopes: string[];
  missing_standing_scopes: string[];
};

export type ContactSample = {
  contact_id: number;
  name: string;
  contact_type?: string;
  standing: number;
  is_watched: boolean;
};

export type ContactPreviewTarget = {
  token_id: number;
  character_id: number;
  character_name: string;
  create_count: number;
  update_count: number;
  skip_count: number;
  create_sample: ContactSample[];
  update_sample: ContactSample[];
};

export type ContactSyncPreview = {
  source_character_name: string;
  source_contact_count: number;
  overwrite_existing: boolean;
  totals: {
    create: number;
    update: number;
    skip: number;
  };
  targets: ContactPreviewTarget[];
};

export type ContactApplyResult = {
  status: string;
  source_character_name: string;
  created: number;
  updated: number;
  targets: {
    character_name: string;
    created: number;
    updated: number;
    skipped: number;
  }[];
};
