export type SectionPermission = {
  key: string;
  label: string;
  default_roles: string[];
};

export type SectionSettings = {
  sections: SectionPermission[];
  disabled_sections: string[];
};

export type RoleDefinition = {
  name: string;
  display_name: string;
  base_role: string;
  is_system: boolean;
  sort_order?: number;
  rank?: number;
};

export type PermissionMatrix = {
  sections: SectionPermission[];
  roles: string[];
  role_permissions: {
    id: number;
    role: string;
    section: string;
    can_view: boolean;
  }[];
  user_permissions: {
    id: number;
    user_id: number;
    section: string;
    can_view: boolean;
  }[];
};

export type SdeStatus = {
  default_source_path: string;
  categories: number;
  groups: number;
  types: number;
  regions?: number;
  constellations?: number;
  systems?: number;
  stargates?: number;
  dogma_attributes?: number;
  dogma_effects?: number;
  type_dogma_attributes?: number;
  type_dogma_effects?: number;
  blueprint_activities: number;
  activity_inputs: number;
};

export type SdeImportResult = SdeStatus & {
  source_path: string;
  skipped_activities: number;
};

export type SdeImportProgress = {
  running: boolean;
  status: string;
  stage?: string | null;
  source_path?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  stats?: Partial<SdeImportResult> | null;
};
