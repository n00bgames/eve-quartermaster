export type MiningSettlementStatus = "draft" | "finalized";
export type MiningSettlementMode = "isk" | "minerals";
export type MiningContributionBasis = "estimated_raw_value" | "volume" | "quantity" | "manual";
export type MiningCompensationMethod = "fixed_percentage" | "shares";
export type MiningReserveMethod = "none" | "percentage" | "output_percentage" | "flat_isk";
export type MiningDeductionMethod = "percentage" | "flat_isk";

export type SettlementMineral = {
  type_id: number;
  name: string;
};

export type SettlementPriceSource = {
  key: string;
  label: string;
  available: boolean;
};

export type SettlementOutput = {
  id?: number;
  type_id: number;
  type_name: string;
  quantity: number;
  distributed_quantity?: number;
  retained_quantity?: number;
  unit_price: number;
  total_value?: number;
  stated_refine_percent?: number | null;
  price_source: string;
  price_overridden: boolean;
};

export type SettlementMineralPayout = {
  type_id: number;
  type_name: string;
  quantity: number;
  unit_price: number;
  total_value: number;
};

export type SettlementDeduction = {
  id?: number;
  deduction_type: string;
  description: string;
  calculation_method: MiningDeductionMethod;
  entered_value?: number;
  value?: number;
  normalized_percentage?: number | null;
  calculated_amount?: number;
};

export type SettlementParticipant = {
  id?: number;
  character_id?: number | null;
  display_name: string;
  role: string;
  source: "ledger" | "manual" | "linked_character";
  ore_types?: string[];
  contribution_quantity?: number;
  contribution_volume?: number;
  contribution_value?: number;
  contribution_basis_value?: number;
  contribution_percentage?: number;
  compensation_method: MiningCompensationMethod;
  compensation_value?: number;
  fixed_percentage?: number | null;
  share_weight?: number | null;
  share_weight_overridden: boolean;
  payout_ratio?: number;
  payout_isk?: number;
  mineral_payouts?: SettlementMineralPayout[];
  notes?: string | null;
};

export type SettlementSource = {
  type: "operation" | "range";
  operation_id?: number;
  operation_name?: string;
  range_start?: string;
  range_end?: string;
  character_ids?: number[];
  ledger_entry_ids?: number[];
};

export type MiningSettlement = {
  id: number;
  name: string;
  operation_id?: number | null;
  operation_name?: string | null;
  source_type: "operation" | "range";
  source_filter: SettlementSource;
  range_start?: string | null;
  range_end?: string | null;
  status: MiningSettlementStatus;
  contribution_basis: MiningContributionBasis;
  settlement_mode: MiningSettlementMode;
  price_source: string;
  reserve: {
    method: MiningReserveMethod;
    entered_value: number;
    normalized_percentage?: number | null;
    calculated_amount: number;
  };
  refining_pilot_name?: string | null;
  refining_pilot_character_id?: number | null;
  refining_location?: string | null;
  stated_refine_percent?: number | null;
  source_entry_count: number;
  source_quantity?: number;
  source_volume?: number;
  source_estimated_value?: number;
  gross_value: number;
  reserve_value: number;
  deduction_total: number;
  distributable_value: number;
  fixed_payout_total: number;
  share_pool_value: number;
  participant_payout_total: number;
  unallocated_remainder: number;
  warnings: string[];
  notes?: string | null;
  created_by?: string;
  created_at?: string | null;
  updated_at?: string | null;
  finalized_at?: string | null;
  outputs: SettlementOutput[];
  deductions: SettlementDeduction[];
  participants: SettlementParticipant[];
};

export type SettlementPreview = Omit<MiningSettlement, "id" | "name" | "status" | "reserve" | "created_by" | "created_at" | "updated_at" | "finalized_at"> & {
  reserve_method: MiningReserveMethod;
  reserve_entered_value: number;
  reserve_normalized_percentage?: number | null;
};

export type SettlementOptionsPayload = {
  minerals: SettlementMineral[];
  price_sources: SettlementPriceSource[];
  settlements: MiningSettlement[];
};

export type SettlementAppraisal = {
  items: {
    type_id?: number | null;
    type_name?: string | null;
    hubs: Record<string, { buy?: number | null; sell?: number | null; split?: number | null }>;
  }[];
};
