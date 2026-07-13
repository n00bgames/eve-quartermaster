import type { ReactElement } from "react";
import { useEffect, useState } from "react";

import { PilotSecurityStatus } from "./PilotSecurityStatus";
import type { RosterCorporation } from "../../types/roster";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";

type RosterProps = {
  api: ApiClient;
  EveEntityIcon: (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;
  CharacterHoverName: (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
};

export function Roster({ api, EveEntityIcon, CharacterHoverName }: RosterProps) {
  const [corporations, setCorporations] = useState<RosterCorporation[]>([]);
  const [rosterError, setRosterError] = useState<string | null>(null);

  async function loadRoster() {
    setRosterError(null);
    try {
      setCorporations(await api<RosterCorporation[]>("/characters/roster"));
    } catch (err) {
      setRosterError(err instanceof Error ? err.message : "Unable to load roster");
    }
  }

  useEffect(() => { void loadRoster(); }, []);

  const totalCharacters = corporations.reduce((total, corporation) => total + corporation.characters.length, 0);

  return <section className="panel stacked roster-page"><div className="section-heading"><div><h3>Roster</h3><p>{totalCharacters.toLocaleString()} character{totalCharacters === 1 ? "" : "s"} across {corporations.length.toLocaleString()} corporation{corporations.length === 1 ? "" : "s"}</p></div><button type="button" onClick={() => void loadRoster()}>Refresh</button></div>{rosterError && <div className="mini-alert">{rosterError}</div>}<div className="roster-corporations">{corporations.map((corporation) => <article key={corporation.corporation_id ?? corporation.corporation_name} className="roster-corp"><div className="roster-corp-heading"><div className="entity-card-heading"><EveEntityIcon kind="corporation" id={corporation.corporation_id} name={corporation.corporation_name} size="md" /><div><strong>{corporation.corporation_name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</strong><span>{corporation.alliance_id && <EveEntityIcon kind="alliance" id={corporation.alliance_id} name={corporation.alliance_name} size="tiny" />}{corporation.alliance_name ?? "No alliance"}{corporation.corporation_id ? ` · Corp ID ${corporation.corporation_id}` : ""}</span></div></div><span>{corporation.characters.length.toLocaleString()} listed · Members {corporation.member_count?.toLocaleString() ?? "unknown"}</span></div><div className="roster-character-grid">{corporation.characters.map((character) => <div key={character.character_id} className="roster-character"><EveEntityIcon kind="character" id={character.character_id} name={character.name} /><CharacterHoverName characterId={character.character_id} name={character.name} /><PilotSecurityStatus securityStatus={character.security_status} compact /></div>)}</div></article>)}{corporations.length === 0 && <p className="empty">No roster characters assigned to Quartermaster accounts yet.</p>}</div></section>;
}