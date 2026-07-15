import type { MarketAppraisal } from "./market";

export type ManufacturingJobStatus = "draft" | "running" | "completed";
export type ManufacturingOutputDisposition = "pending" | "sold" | "kept";
export type ManufacturingActivityFlag = "manufacturing" | "me" | "te" | "invention" | "copy" | "reaction";

export type ManufacturingCategory = {
  key: string;
  label: string;
};

export type ManufacturingLineItem = {
  id?: number;
  category: string;
  item_type_id?: number | null;
  item_name: string;
  type_name?: string | null;
  quantity: number;
  unit_price?: number | null;
  price_paid?: number | null;
  notes?: string | null;
};

export type ManufacturingJob = {
  id: number;
  name: string;
  output_type_id?: number | null;
  output_type_name?: string | null;
  output_quantity: number;
  activity_flags: ManufacturingActivityFlag[];
  research_runs?: number | null;
  me_start?: number | null;
  me_target?: number | null;
  te_start?: number | null;
  te_target?: number | null;
  copy_runs?: number | null;
  invention_runs?: number | null;
  invention_successes?: number | null;
  status: ManufacturingJobStatus;
  output_disposition: ManufacturingOutputDisposition;
  output_sale_price?: number | null;
  output_sale_notes?: string | null;
  cost_to_run?: number | null;
  time_to_run?: string | null;
  date_started?: string | null;
  time_started?: string | null;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  items: ManufacturingLineItem[];
  entered_total: number;
  paid_total: number;
  savings_total: number;
  category_totals: Record<string, number>;
  category_paid_totals: Record<string, number>;
};

export type ManufacturingPayload = {
  categories: ManufacturingCategory[];
  jobs: ManufacturingJob[];
};

export type ManufacturingAppraisal = MarketAppraisal;
