export type RosterCharacter = { character_id: number; name: string; portrait_url?: string | null; security_status?: number | null };

export type RosterCorporation = { corporation_id?: number | null; corporation_name: string; ticker?: string | null; alliance_id?: number | null; alliance_name?: string | null; member_count?: number | null; characters: RosterCharacter[] };