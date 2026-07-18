export type MiningCharacter = {
  character_id: number;
  name: string;
  portrait_url?: string | null;
  can_sync: boolean;
  sync_opt_out: boolean;
};

export type MiningRollupRow = {
  id: number | string;
  name: string;
  quantity: number;
  residue_quantity: number;
  volume: number;
  residue_volume: number;
  gross_volume: number;
  estimated_price: number;
  estimated_residue_price: number;
  gross_value: number;
  efficiency?: number | null;
};

export type MiningTotals = Omit<MiningRollupRow, "id" | "name"> & {
  gross_quantity: number;
  measured_volume: number;
};

export type MiningLedgerEntry = {
  id: number;
  date: string;
  timestamp?: string | null;
  character_id: number;
  character_name: string;
  ore_type_id: number;
  ore_type: string;
  solar_system_id: number;
  solar_system: string;
  quantity: number;
  residue_quantity: number;
  volume: number;
  residue_volume: number;
  estimated_price: number;
  estimated_residue_price: number;
  has_residue_data: boolean;
  source: "esi" | "import";
  operation_id?: number | null;
  operation_name?: string | null;
};

export type MiningParticipant = {
  character_id: number;
  character_name: string;
  role: "miner" | "booster";
  ship_name?: string | null;
  crystal_name?: string | null;
};

export type MiningOperation = {
  id: number;
  name: string;
  solar_system_id?: number | null;
  solar_system_name?: string | null;
  start_at: string;
  end_at: string;
  notes?: string | null;
  created_by: string;
  participants: MiningParticipant[];
  summary: MiningTotals;
};

export type MiningLedgerPayload = {
  characters: MiningCharacter[];
  systems: [number, string][];
  analytics: {
    totals: MiningTotals;
    by_day: MiningRollupRow[];
    by_ore: MiningRollupRow[];
    by_character: MiningRollupRow[];
    by_system: MiningRollupRow[];
  };
  entries: MiningLedgerEntry[];
  entry_count: number;
  page: number;
  page_size: number;
  operations: MiningOperation[];
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
