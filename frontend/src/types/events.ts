export type EventType = "fleet" | "mining" | "logistics" | "mission" | "industry" | "training" | "social" | "other";
export type EventLifecycle = "draft" | "scheduled" | "in_progress" | "completed" | "cancelled";
export type RegistrationState = "open" | "closed" | "locked";
export type RsvpStatus = "going" | "maybe" | "declined" | "waitlisted";
export type AttendanceStatus = "attended" | "no_show" | "excused";

export type EventLocation = {
  id?: number;
  location_role: "formup" | "destination" | "route";
  sort_order: number;
  system_id: number;
  system_name?: string | null;
  security_status?: number | null;
  location_id?: number | null;
  eve_location_id?: number | null;
  location_name?: string | null;
  location_name_snapshot?: string | null;
  notes?: string | null;
};

export type EventRegistration = {
  id: number;
  user_id: number;
  user_name?: string | null;
  character_id: number | null;
  character_eve_id: number;
  character_name: string;
  corporation_name?: string | null;
  alliance_name?: string | null;
  registration_status: "registered" | "waitlisted";
  confirmation_status: "confirmed" | "tentative";
  planned_ship_source: string;
  ship_type_id?: number | null;
  ship_name?: string | null;
  saved_fitting_id?: number | null;
  fitting_name?: string | null;
  doctrine_requirement_id?: number | null;
  doctrine_option_id?: number | null;
  role_key?: string | null;
  custom_role?: string | null;
  freeform_ship_description?: string | null;
  notes?: string | null;
  attendance?: AttendanceEntry | null;
};

export type EventRoleRequirement = {
  id?: number;
  role_key: string;
  custom_label?: string | null;
  requested_quantity: number;
  notes?: string | null;
  sort_order: number;
};

export type EventDoctrineOption = {
  id?: number;
  ship_type_id?: number | null;
  ship_name?: string | null;
  fitting_id?: number | null;
  fitting_name?: string | null;
  manual_name_snapshot?: string | null;
  is_primary: boolean;
  sort_order: number;
};

export type EventDoctrineRequirement = {
  id?: number;
  role_requirement_id?: number | null;
  label: string;
  requested_quantity: number;
  notes?: string | null;
  sort_order: number;
  options: EventDoctrineOption[];
};

export type EventPermissions = {
  can_manage: boolean;
  can_record_attendance: boolean;
  can_view_composition: boolean;
};

export type EventSummary = {
  id: number;
  title: string;
  event_type: EventType;
  lifecycle_status: EventLifecycle;
  registration_status: RegistrationState;
  formup_at?: string | null;
  start_at: string;
  end_at?: string | null;
  estimated_duration_minutes?: number | null;
  operational_area?: string | null;
  lead: { character_id?: number | null; name?: string | null };
  doctrine_mode: string;
  doctrine: { id?: number | null; name?: string | null; external_url?: string | null };
  audience_kind: string;
  composition_visibility: string;
  participant_limit?: number | null;
  limit_basis: "users" | "characters";
  formup_location?: EventLocation | null;
  rsvp_counts: Record<string, number>;
  registration_counts: Record<string, number>;
  actual_attendance: number;
  my_rsvp?: { status: RsvpStatus; notes?: string | null } | null;
  my_registrations: EventRegistration[];
  permissions: EventPermissions;
  created_by: { id?: number | null; name?: string | null };
  created_at: string;
  updated_at: string;
};

export type EventDetail = EventSummary & {
  route_notes?: string | null;
  discord_voice_label?: string | null;
  discord_voice_url?: string | null;
  discord_guild_id?: string | null;
  discord_channel_id?: string | null;
  doctrine_notes?: string | null;
  related_url?: string | null;
  instructions?: string | null;
  audience_corporation_id?: number | null;
  audience_alliance_id?: number | null;
  locations: EventLocation[];
  role_requirements: EventRoleRequirement[];
  doctrine_requirements: EventDoctrineRequirement[];
};

export type EventMeta = {
  constants: Record<string, string[]>;
  permissions: { can_create: boolean; can_view_analytics: boolean };
  directory: {
    lead_characters: { id: number; name: string; corporation_name?: string | null; alliance_name?: string | null }[];
    corporations: { id: number; name: string; ticker?: string | null }[];
    alliances: { id: number; name: string; ticker?: string | null }[];
  };
};

export type RegistrationCharacter = {
  id: number;
  character_id: number;
  name: string;
  portrait_url?: string | null;
  already_registered: boolean;
};

export type RegistrationFitting = {
  id: number;
  name: string;
  ship_type_id: number;
  ship_name: string;
};

export type RegistrationOptions = {
  characters: RegistrationCharacter[];
  fittings: RegistrationFitting[];
  roles: string[];
  doctrine_requirements: EventDoctrineRequirement[];
};

export type AttendanceEntry = {
  id: number;
  registration_id?: number | null;
  attendee_source: string;
  attendance_status: AttendanceStatus;
  linked_user_id?: number | null;
  character_id?: number | null;
  character_eve_id?: number | null;
  display_name: string;
  corporation_name?: string | null;
  alliance_name?: string | null;
  checked_in_at?: string | null;
  notes?: string | null;
};

export type AttendanceRegistrationRow = EventRegistration & {
  attendance?: AttendanceEntry | null;
  derived_attendance_status: AttendanceStatus | "unmarked";
};

export type AttendanceRoster = {
  event_id: number;
  eligible: boolean;
  registrations: AttendanceRegistrationRow[];
  unregistered_attendees: AttendanceEntry[];
};

export type CompositionProgress = {
  id: number;
  label: string;
  requested: number;
  registered: number;
  remaining: number;
};

export type EventComposition = {
  event_id: number;
  identity_visible: boolean;
  totals: {
    rsvp: Record<string, number>;
    registration: Record<string, number>;
    confirmation: Record<string, number>;
    attendance: Record<string, number>;
  };
  roles: { label: string; count: number }[];
  hulls: { label: string; count: number }[];
  role_requirements: CompositionProgress[];
  doctrine_requirements: CompositionProgress[];
  users_without_characters: number;
  registrations?: EventRegistration[];
  unregistered_attendees?: AttendanceEntry[];
  responses_without_characters?: { user_id: number; user_name?: string | null; status: string }[];
};

export type AnalyticsCounts = {
  event_count: number;
  rsvp_going: number;
  rsvp_maybe: number;
  rsvp_declined: number;
  rsvp_waitlisted: number;
  registered_characters: number;
  attended_registered: number;
  attended_unregistered: number;
  no_show: number;
  excused: number;
  unmarked: number;
  attendance_rate: { numerator: number; denominator: number; percent?: number | null };
};

export type EventAnalytics = {
  from_at: string;
  to_at: string;
  bucket: "day" | "week" | "month";
  totals: AnalyticsCounts;
  by_event_type: (AnalyticsCounts & { event_type: EventType })[];
  series: (AnalyticsCounts & { period_start: string })[];
};

export type SystemSearchResult = {
  system_id: number;
  name: string;
  security_status?: number | null;
  region_name?: string | null;
};

export type LocationSearchResult = {
  source: "location" | "station";
  location_id?: number | null;
  eve_location_id?: number | null;
  name?: string | null;
};

export type ShipSearchResult = { type_id: number; name: string; group_name?: string | null };
