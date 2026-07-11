export type CharacterKillSample = {
  killmail_id: number;
  killmail_time?: string | null;
  zkb_url?: string | null;
  total_value?: number | null;
  victim_hull?: string | null;
  victim_character_name?: string | null;
  victim_corporation_name?: string | null;
  victim_alliance_name?: string | null;
  final_blow_character_name?: string | null;
  final_blow_corporation_name?: string | null;
  final_blow_alliance_name?: string | null;
  final_blow_ship_type_name?: string | null;
  attacker_count?: number | null;
  location_name?: string | null;
  smartbomb_used?: boolean;
  war_id?: number | null;
  is_wardec?: boolean;
};

export type NavigationKillmailSample = {
  killmail_id?: number | null;
  killmail_time?: string | null;
  zkb_url?: string | null;
  total_value?: number | null;
  smartbomb_used?: boolean;
  war_id?: number | null;
  is_wardec?: boolean;
  victim_hull?: string | null;
  victim?: {
    character_id?: number | null;
    character_name?: string | null;
    corporation_id?: number | null;
    corporation_name?: string | null;
    alliance_id?: number | null;
    alliance_name?: string | null;
  } | null;
  attacker_count?: number | null;
  combatant_count?: number | null;
  location_id?: number | null;
  location_kind?: string | null;
  location_name?: string | null;
  final_blow?: {
    character_id?: number | null;
    character_name?: string | null;
    corporation_id?: number | null;
    corporation_name?: string | null;
    alliance_id?: number | null;
    alliance_name?: string | null;
    ship_type_name?: string | null;
  } | null;
};

export type JumpFreighterKillSummary = {
  hours: number;
  count: number;
  latest_killmail_time?: string | null;
  sample_killmails: {
    killmail_id: number;
    killmail_time?: string | null;
    zkb_url?: string | null;
    victim_hull?: string | null;
    smartbomb_used?: boolean;
    war_id?: number | null;
    is_wardec?: boolean;
    victim_character_id?: number | null;
    victim_character_name?: string | null;
    victim_corporation_id?: number | null;
    victim_corporation_name?: string | null;
    victim_alliance_id?: number | null;
    victim_alliance_name?: string | null;
    attacker_count?: number | null;
    location_kind?: string | null;
    location_name?: string | null;
    final_blow_character_id?: number | null;
    final_blow_character_name?: string | null;
    final_blow_corporation_id?: number | null;
    final_blow_corporation_name?: string | null;
    final_blow_alliance_id?: number | null;
    final_blow_alliance_name?: string | null;
    final_blow_ship_type_name?: string | null;
  }[];
};
