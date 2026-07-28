export type RecruitingOrganization = {
  id: number | null;
  name: string | null;
  ticker?: string | null;
  logo_url?: string | null;
};

export type RecruitingCeo = {
  id: number | null;
  name: string | null;
  portrait_url?: string | null;
  manual_override?: boolean;
};

export type RecruitingPublic = {
  setup_complete: boolean;
  corporation?: RecruitingOrganization;
  alliance?: RecruitingOrganization;
  ceo?: RecruitingCeo;
  primary_timezone?: { name: string; current_time?: string; utc_offset?: string; valid?: boolean } | null;
  activity_window_start?: string;
  activity_window_end?: string;
  public_headline?: string;
  public_subheading?: string;
  public_summary?: string;
  public_body?: string;
  offers?: string[];
  expectations?: string[];
  priorities?: string[];
  privacy_notice?: string;
  required_scopes?: string[];
};

export type RecruitingQuestion = {
  key: string;
  section: string;
  label: string;
  type: "text" | "textarea" | "select" | "checkbox";
  required?: boolean;
  options?: string[];
};

export type RecruitingCharacter = {
  id: number;
  character_id: number;
  name: string;
  portrait_url?: string | null;
  security_status?: number | null;
  total_skill_points?: number | null;
  is_main: boolean;
  verification_status: string;
  token_health: string;
  last_successful_sync_at?: string | null;
  granted_scopes: string[];
  snapshot: Record<string, unknown>;
  employment_history?: Array<Record<string, unknown>>;
  last_sync_error?: string | null;
};

export type RecruitingInterview = {
  id: number;
  scheduled_at?: string | null;
  applicant_timezone?: string | null;
  availability: string[];
  attendance_status: string;
  visible_follow_up?: string | null;
  applicant_acknowledged_at?: string | null;
  recommendation?: string | null;
  completed_at?: string | null;
  answers?: Record<string, string>;
  internal_notes?: string | null;
  interviewer?: string | null;
};

export type RecruitingApplication = {
  id: number;
  status: string;
  discord_username?: string | null;
  discord_display_name?: string | null;
  preferred_name?: string | null;
  pronouns?: string | null;
  timezone?: string | null;
  primary_interest?: string | null;
  answers: Record<string, unknown>;
  acknowledgements: Record<string, boolean>;
  activity_preferences: Record<string, unknown>;
  progress_percent: number;
  missing_requirements: string[];
  characters: RecruitingCharacter[];
  messages: Array<{ id: number; body: string; from_applicant: boolean; author: string; created_at: string }>;
  timeline: Array<{ id: number; previous_status?: string | null; new_status: string; reason?: string | null; created_at: string }>;
  interviews: RecruitingInterview[];
  created_at: string;
  updated_at: string;
  submitted_at?: string | null;
  overlap_hours?: number | null;
  applicant_user_id?: number;
  applicant_name?: string | null;
  applicant_email?: string | null;
  assigned_recruiter_user_id?: number | null;
  assigned_recruiter?: string | null;
  veteran_status?: boolean;
  tags?: string[];
  recruiter_ratings?: Record<string, string>;
  internal_flags?: string[];
  notes?: Array<{ id: number; body?: string | null; redacted: boolean; applicant_visible: boolean; author: string; created_at: string }>;
  recruitment_admin?: boolean;
};

export type RecruitingContext = {
  role: string;
  capabilities: string[];
  is_recruiter: boolean;
  is_recruitment_admin: boolean;
  setup_complete: boolean;
  public: RecruitingPublic;
  application?: RecruitingApplication | null;
  form_options?: Record<string, string[]>;
  application_questions?: RecruitingQuestion[];
};

export type RecruitingSettings = Omit<RecruitingPublic, "primary_timezone"> & {
  id: number;
  primary_timezone: string;
  ceo_manual_override: boolean;
  statuses: string[];
  tags: string[];
  form_options: Record<string, string[]>;
  application_questions: RecruitingQuestion[];
  interview_questions: Array<{ id: number; text: string; active: boolean }>;
  parameter_definitions: Array<{ key: string; label: string; active: boolean }>;
  declined_retention_days: number;
  withdrawn_retention_days: number;
  abandoned_retention_days: number;
  auto_refresh_hours: number;
};

export type RecruitingDashboard = {
  counts: Record<string, number>;
  statuses: string[];
  applications: RecruitingApplication[];
  recruiters?: Array<{ id: number; display_name: string }>;
  tags?: string[];
  parameter_definitions?: Array<{ key: string; label: string; active: boolean }>;
  interview_questions?: Array<{ id: number; text: string; active: boolean }>;
};

export type RecruitingCapabilities = {
  capabilities: string[];
  users: Array<{ id: number; display_name: string; email: string; role: string; capabilities: string[] }>;
};
