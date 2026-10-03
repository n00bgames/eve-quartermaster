import { useId, useState } from "react";
import type { HyperNetNodePositionSummary } from "../../types/hypernet";

export function HyperNetNodeResearch({ summary }: { summary: HyperNetNodePositionSummary }) {
  const controlId = useId();
  const [selection, setSelection] = useState("");
  const [metric, setMetric] = useState<"wins" | "seeded">("wins");
  const key = (group: HyperNetNodePositionSummary["groups"][number]) => `${group.total_nodes}:${group.columns}`;
  const group = summary.groups.find((value) => key(value) === selection) ?? summary.groups[0];
  const maximum = group ? Math.max(1, ...group.positions.map((value) => value[metric])) : 1;
  return <section className="panel hypernet-node-research">
    <h4>Node position history</h4>
    <p>{summary.tracked_offers} offers with saved position maps. Uses all offer history for the selected character, independent of the board’s status/search filters.</p>
    <p className="muted">Positions are manual observations, not node identities. These counts describe your sample; apparent hot spots do not establish a better chance on the next draw. Different layouts are kept separate.</p>
    {!!Object.keys(summary.excluded).length && <p className="muted">Outside the completed-draw sample: {summary.excluded.not_completed ?? 0} tracked but not completed · {summary.excluded.missing_map ?? 0} completed without a map · {summary.excluded.missing_winner ?? 0} completed without a winning position{summary.excluded.invalid_positions ? ` · ${summary.excluded.invalid_positions} invalid maps` : ""}.</p>}
    {!group ? <p className="empty">Save a winning position on a completed offer to start the comparison.</p> : <>
      <div className="hypernet-node-controls"><div><label htmlFor={`${controlId}-layout`}>Compare layout</label><select id={`${controlId}-layout`} value={key(group)} onChange={(event) => setSelection(event.target.value)}>{summary.groups.map((value) => <option key={key(value)} value={key(value)}>{value.total_nodes} nodes · {value.columns} columns</option>)}</select></div><div><label htmlFor={`${controlId}-metric`}>Show</label><select id={`${controlId}-metric`} value={metric} onChange={(event) => setMetric(event.target.value as "wins" | "seeded")}><option value="wins">Winning positions</option><option value="seeded">Seeded positions</option></select></div></div>
      <p><strong>{group.draws} completed draws</strong> · Equal-chance baseline: {(group.draws / group.total_nodes).toFixed(2)} wins per position.</p>
      <p>{group.complete_seed_maps} complete, consistent seed maps · {group.seeded_wins} observed seeded wins vs {group.expected_seeded_wins.toFixed(2)} expected from seeded counts.</p>
      {(group.incomplete_seed_maps > 0 || group.outcome_conflicts > 0) && <p className="mini-alert">Seeded comparison excludes {group.incomplete_seed_maps} incomplete maps and {group.outcome_conflicts} winner conflicts. Their recorded winning positions remain in the draw counts.</p>}
      <div className="hypernet-node-scroll"><div className="hypernet-node-grid" style={{ gridTemplateColumns: `repeat(${group.columns}, minmax(44px, 1fr))` }}>{group.positions.map((cell) => <div key={cell.position} className="hypernet-node-heat" tabIndex={0} style={{ backgroundColor: `rgba(79,179,199,${0.08 + 0.65 * cell[metric] / maximum})` }} title={`Position ${cell.position}: ${cell.wins} wins in ${group.draws} draws; seeded ${cell.seeded} times in ${group.complete_seed_maps} complete maps, winning while seeded ${cell.seeded_wins} times.`} aria-label={`Position ${cell.position}: ${cell.wins} wins in ${group.draws} draws; seeded ${cell.seeded} times; ${cell.seeded_wins} seeded wins`}><span>{cell.position}</span><strong>{cell[metric]}</strong></div>)}</div></div>
      <small className="muted">Each cell shows position number and {metric === "wins" ? "winning count across completed draws" : "times seeded in complete, consistent maps"}. Brighter cells have higher counts. Small samples will be uneven.</small>
    </>}
  </section>;
}
