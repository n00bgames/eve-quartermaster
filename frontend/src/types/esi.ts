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
  delete_count: number;
  skip_count: number;
  create_sample: ContactSample[];
  update_sample: ContactSample[];
  delete_sample: ContactSample[];
};

export type ContactSyncPreview = {
  source_character_name: string;
  source_contact_count: number;
  overwrite_existing: boolean;
  exact_match: boolean;
  totals: {
    create: number;
    update: number;
    delete: number;
    skip: number;
  };
  targets: ContactPreviewTarget[];
};

export type ContactSyncJob = {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  created_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
  source_character_name: string;
  total_count: number;
  processed_count: number;
  success_count: number;
  failed_count: number;
  current_character_name?: string | null;
  created: number;
  updated: number;
  deleted: number;
  exact_match: boolean;
  targets: {
    character_name: string;
    status: "complete" | "failed";
    created: number;
    updated: number;
    deleted: number;
    skipped: number;
    error?: string;
  }[];
  errors: string[];
};

export type SyncDatasetFreshness = {
  key: string;
  label: string;
  health: "current" | "active" | "stale" | "failed" | "never_synced" | "missing_scope" | "disabled" | "skipped";
  status?: string | null;
  last_sync_at?: string | null;
  age_seconds?: number | null;
  stale_after_hours: number;
  missing_scopes: string[];
  disabled_reason?: string | null;
  message?: string | null;
  job_id?: number | null;
};

export type SyncFreshnessPayload = {
  generated_at: string;
  summary: {
    linked_characters: number;
    datasets: number;
    current: number;
    active: number;
    attention: number;
    missing_scope: number;
    disabled: number;
    counts: Record<string, number>;
  };
  characters: {
    token_id: number;
    character_id: number;
    character_name: string;
    linked_user_id: number;
    linked_user_display_name: string;
    sync_opt_out: boolean;
    datasets: SyncDatasetFreshness[];
  }[];
  active_batches: {
    job_id: string;
    job_kind: string;
    status: string;
    total_count: number;
    processed_count: number;
    success_count: number;
    failed_count: number;
    skipped_count: number;
    current_character_name?: string | null;
    current_sync_kind?: string | null;
    updated_at?: string | null;
  }[];
  recent_jobs: {
    id: number;
    token_id?: number | null;
    character_name?: string | null;
    sync_type: string;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    message?: string | null;
  }[];
};
