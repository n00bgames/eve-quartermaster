export type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
export type Pilot = { character_id: number; name: string; corporation_id: number | null; corporation_name: string; alliance_id: number | null; alliance_name: string | null; affiliation_available: boolean; highlighted: boolean; alliance_highlighted: boolean };
export type ReportMeta = { token: string; share_url: string | null; is_private: boolean; anonymous: boolean; created_at: string; expires_at: string | null; retention: string; account_name: string; application_version: string; corporation_id: number | null; character_count: number; input_count: number };
export type ScanReport = ReportMeta & { pilots: Pilot[]; unresolved: string[]; warnings: string[]; source: string; highlighted_count: number; system: {id: number; name: string} | null };
export type Condition = { field: "name" | "corporation_name" | "alliance_name"; operator: "contains" | "starts" | "ends" | "equals"; value: string };
export type Highlight = { id: number; kind: "corporation" | "alliance"; eve_id: number; name: string };
export type ScanContext = { retentions: string[]; max_pilots: number; corporations: {id: number; name: string}[]; can_generate: boolean; management_scope: string; creator_name?: string };
