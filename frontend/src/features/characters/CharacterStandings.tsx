import { ArrowDown, ArrowUp, Building2, Flag, Info, Search, UserRound } from "lucide-react";
import { useMemo, useState, type CSSProperties, type ReactNode } from "react";

import type { CharacterStanding, CharacterStandingSourceType } from "../../types/characters";
import "./characterStandings.css";

type StandingFilter = "all" | CharacterStandingSourceType;
type StandingSort = "name" | "standing";

const SOURCE_LABELS: Record<CharacterStandingSourceType, string> = {
  faction: "Factions",
  npc_corp: "NPC corporations",
  agent: "Agents",
};

const SOURCE_ICONS: Record<CharacterStandingSourceType, ReactNode> = {
  faction: <Flag size={17} />,
  npc_corp: <Building2 size={17} />,
  agent: <UserRound size={17} />,
};

function standingTone(value: number): string {
  if (value >= 5) return "excellent";
  if (value > 0) return "positive";
  if (value <= -5) return "hostile";
  if (value < 0) return "negative";
  return "neutral";
}

function standingLabel(value: number): string {
  if (value >= 5) return "Excellent";
  if (value > 0) return "Positive";
  if (value <= -5) return "Hostile";
  if (value < 0) return "Negative";
  return "Neutral";
}

function signedStanding(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function standingMeterStyle(value: number): CSSProperties {
  const clamped = Math.max(-10, Math.min(10, value));
  const start = clamped < 0 ? 50 + clamped * 5 : 50;
  return {
    "--standing-start": `${start}%`,
    "--standing-width": `${Math.abs(clamped) * 5}%`,
  } as CSSProperties;
}

function baseStanding(entry: CharacterStanding): number {
  return entry.base_standing ?? entry.standing;
}

function modifiedStanding(entry: CharacterStanding): number {
  return entry.modified_standing ?? baseStanding(entry);
}

type CharacterStandingsProps = {
  entries: CharacterStanding[];
  syncedAt?: string | null;
  formatDateTime: (value?: string | null) => string;
};

export function CharacterStandings({
  entries,
  syncedAt,
  formatDateTime,
}: CharacterStandingsProps) {
  const [filter, setFilter] = useState<StandingFilter>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<StandingSort>("standing");
  const [descending, setDescending] = useState(true);

  const counts = useMemo(
    () => ({
      all: entries.length,
      faction: entries.filter((entry) => entry.source_type === "faction").length,
      npc_corp: entries.filter((entry) => entry.source_type === "npc_corp").length,
      agent: entries.filter((entry) => entry.source_type === "agent").length,
    }),
    [entries],
  );

  const visible = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return entries
      .filter((entry) => filter === "all" || entry.source_type === filter)
      .filter((entry) => (
        !normalizedQuery
        || entry.source_name.toLocaleLowerCase().includes(normalizedQuery)
        || String(entry.source_eve_id).includes(normalizedQuery)
      ))
      .sort((left, right) => {
        const comparison = sort === "name"
          ? left.source_name.localeCompare(right.source_name)
          : modifiedStanding(left) - modifiedStanding(right);
        return descending ? -comparison : comparison;
      });
  }, [descending, entries, filter, query, sort]);

  const changeSort = (nextSort: StandingSort) => {
    if (sort === nextSort) {
      setDescending((current) => !current);
      return;
    }
    setSort(nextSort);
    setDescending(nextSort === "standing");
  };

  const filters: { key: StandingFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "faction", label: "Factions" },
    { key: "npc_corp", label: "Corporations" },
    { key: "agent", label: "Agents" },
  ];

  return (
    <section className="character-standings">
      <div className="section-heading">
        <div>
          <h4>NPC Standings</h4>
          <p>
            Agent, corporation, and faction relationships
            {syncedAt ? ` · synced ${formatDateTime(syncedAt)}` : ""}
          </p>
        </div>
        <span className="status-badge">{entries.length.toLocaleString()} entries</span>
      </div>

      {entries.length > 0 ? (
        <>
          <div className="standing-explanation">
            <Info size={18} />
            <span>
              <strong>Base</strong> is the unmodified ESI value. <strong>Modified</strong> applies active Diplomacy,
              Connections, or Criminal Connections levels. Social improves future standing gains, so it is not added
              to the current value.
            </span>
          </div>

          <div className="standing-summary-grid">
            {(["faction", "npc_corp", "agent"] as CharacterStandingSourceType[]).map((sourceType) => {
              const sourceEntries = entries.filter((entry) => entry.source_type === sourceType);
              const highest = sourceEntries.reduce<CharacterStanding | null>(
                (best, entry) => !best || modifiedStanding(entry) > modifiedStanding(best) ? entry : best,
                null,
              );
              return (
                <article key={sourceType}>
                  <span>{SOURCE_ICONS[sourceType]} {SOURCE_LABELS[sourceType]}</span>
                  <strong>{sourceEntries.length.toLocaleString()}</strong>
                  <small>
                    {highest ? `Highest modified: ${highest.source_name} ${signedStanding(modifiedStanding(highest))}` : "No stored entries"}
                  </small>
                </article>
              );
            })}
          </div>

          <div className="standing-toolbar">
            <div className="standing-filter" role="group" aria-label="Standing source filter">
              {filters.map((item) => (
                <button
                  type="button"
                  key={item.key}
                  className={filter === item.key ? "active" : ""}
                  onClick={() => setFilter(item.key)}
                >
                  {item.label} <span>{counts[item.key].toLocaleString()}</span>
                </button>
              ))}
            </div>
            <label className="standing-search">
              <Search size={17} />
              <input
                aria-label="Search standings"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search NPC standings"
              />
            </label>
          </div>

          <div className="table-wrap standing-table-wrap">
            <table className="standing-table">
              <thead>
                <tr>
                  <th>
                    <button type="button" className="sort-header" onClick={() => changeSort("name")}>
                      Source
                      {sort === "name" && (descending ? <ArrowDown size={14} /> : <ArrowUp size={14} />)}
                    </button>
                  </th>
                  <th>Type</th>
                  <th>Base</th>
                  <th>
                    <button type="button" className="sort-header" onClick={() => changeSort("standing")}>
                      Modified
                      {sort === "standing" && (descending ? <ArrowDown size={14} /> : <ArrowUp size={14} />)}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((entry) => {
                  const base = baseStanding(entry);
                  const modified = modifiedStanding(entry);
                  const tone = standingTone(modified);
                  return (
                    <tr key={`${entry.source_type}-${entry.source_eve_id}`}>
                      <td>
                        <strong>{entry.source_name}</strong>
                        <small>ID {entry.source_eve_id}</small>
                      </td>
                      <td>
                        <span className="standing-source">
                          {SOURCE_ICONS[entry.source_type]}
                          {SOURCE_LABELS[entry.source_type].replace("NPC ", "").replace(/s$/, "")}
                        </span>
                      </td>
                      <td>
                        <div className="standing-base-value">
                          <strong>{signedStanding(base)}</strong>
                          <span>Unmodified</span>
                        </div>
                      </td>
                      <td>
                        <div className={`standing-value ${tone}`}>
                          <strong>{signedStanding(modified)}</strong>
                          <span>{standingLabel(modified)}</span>
                          <i style={standingMeterStyle(modified)}><b /></i>
                          <small>
                            {entry.modifier_skill && entry.modifier_skill_level > 0
                              ? `${entry.modifier_skill} ${entry.modifier_skill_level}`
                              : "No active modifier"}
                          </small>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {visible.length === 0 && <p className="empty">No standings match this filter.</p>}
          </div>
        </>
      ) : (
        <div className="standing-empty">
          <Flag size={21} />
          <div>
            <strong>No NPC standings synced yet</strong>
            <span>Relink with the standings scope if needed, then use Sync standings above.</span>
          </div>
        </div>
      )}
    </section>
  );
}
