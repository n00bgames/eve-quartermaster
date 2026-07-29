export type PlanetarySyncToken = {
  token_id: number;
  character_id: number;
  character_eve_id: number;
  character_name: string;
  has_scope: boolean;
  can_sync: boolean;
};

export type PlanetaryPinContent = {
  type_id: number;
  name: string;
  amount: number;
  volume: number;
};

export type PlanetarySchematicMaterial = {
  type_id: number;
  name: string;
  quantity: number;
  volume: number;
};

export type PlanetarySchematic = {
  id: number;
  name: string;
  cycle_time: number;
  output: PlanetarySchematicMaterial;
  inputs: PlanetarySchematicMaterial[];
};
export type PlanetaryPin = {
  pin_id: number;
  type_id: number;
  type_name: string;
  latitude?: number | null;
  longitude?: number | null;
  install_time?: string | null;
  expiry_time?: string | null;
  last_cycle_start?: string | null;
  status: "online" | "active" | "expiring" | "expired";
  schematic_id?: number | null;
  schematic?: PlanetarySchematic | null;
  is_factory: boolean;
  is_extractor: boolean;
  has_inbound_route: boolean;
  stored_volume: number;
  contents: PlanetaryPinContent[];
  extractor?: {
    cycle_time?: number | null;
    head_radius?: number | null;
    head_count: number;
    product_type_id?: number | null;
    product_name?: string | null;
    qty_per_cycle?: number | null;
    cycle_count: number;
    projected_program_output: number;
    projected_daily_output: number;
    projected_remaining_output: number;
    projection_source: "dogma" | "documented_default";
  } | null;
};

export type PlanetaryColony = {
  id: number;
  character_id: number;
  character_eve_id: number;
  character_name: string;
  character_portrait_url?: string | null;
  planet_id: number;
  planet_name: string;
  planet_type?: string | null;
  solar_system_id?: number | null;
  solar_system_name?: string | null;
  security_status?: number | null;
  upgrade_level: number;
  num_pins: number;
  esi_last_update?: string | null;
  last_synced_at: string;
  link_count: number;
  route_count: number;
  summary: {
    extractors: number;
    expired_extractors: number;
    expiring_extractors: number;
    factories: number;
    starved_factories: number;
    stored_volume: number;
    projected_daily_output: number;
  };
  pins: PlanetaryPin[];
  routes: {
    route_id: number;
    source_pin_id: number;
    destination_pin_id: number;
    content_type_id: number;
    content_name: string;
    quantity: number;
    waypoints: number[];
  }[];
};

export type PlanetaryIndustryPayload = {
  as_of: string;
  characters: { id: number; name: string; portrait_url?: string | null }[];
  sync_tokens: PlanetarySyncToken[];
  colonies: PlanetaryColony[];
  summary: {
    colonies: number;
    characters: number;
    expired_extractors: number;
    expiring_extractors: number;
    starved_factories: number;
    stored_volume: number;
  };
};

export type CharacterSyncJob = {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  total_count: number;
  processed_count: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  current_character_name?: string | null;
  errors: string[];
};
