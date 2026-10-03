import { useRef, useState } from "react";
import type { ApiClient, HyperNetNodeMap, HyperNetOffer } from "../../types/hypernet";

const emptyMap: HyperNetNodeMap = { columns: 4, seeded_positions: [], winning_position: null };

export function HyperNetNodeTracker({ api, offer, onChanged }: { api: ApiClient; offer: HyperNetOffer; onChanged: (offer: HyperNetOffer) => void }) {
  const [draft, setDraft] = useState<HyperNetNodeMap>(() => offer.node_map ?? emptyMap);
  const [saved, setSaved] = useState<HyperNetNodeMap | null>(offer.node_map ?? null);
  const [mode, setMode] = useState<"seed" | "winner">("seed");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const lastSeed = useRef<number | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved ?? emptyMap);
  const seeded = new Set(draft.seeded_positions);
  const complete = seeded.size === offer.seller_owned_nodes;
  const winnerSeeded = draft.winning_position !== null && seeded.has(draft.winning_position);
  const conflict = offer.status === "completed" && complete && draft.winning_position !== null &&
    (offer.winner === "seller" || offer.winner === "external") && winnerSeeded !== (offer.winner === "seller");

  function change(next: HyperNetNodeMap) { setDraft(next); setMessage(""); setError(null); }
  function select(position: number, range: boolean) {
    if (mode === "winner") change({ ...draft, winning_position: draft.winning_position === position ? null : position });
    else {
      const anchor = range && lastSeed.current !== null ? lastSeed.current : position;
      const remove = seeded.has(position);
      for (let value = Math.min(anchor, position); value <= Math.max(anchor, position); value++) {
        if (remove) seeded.delete(value); else seeded.add(value);
      }
      lastSeed.current = position;
      change({ ...draft, seeded_positions: [...seeded].sort((a, b) => a - b) });
    }
  }
  async function save() {
    setBusy(true); setError(null); setMessage("");
    try {
      const updated = await api<HyperNetOffer>(`/hypernet/offers/${offer.id}/nodes`, { method: "PUT", body: JSON.stringify(draft) });
      setDraft(updated.node_map ?? emptyMap); setSaved(updated.node_map ?? null); setMessage("Node positions saved."); onChanged(updated);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save node positions"); }
    finally { setBusy(false); }
  }

  return <section className="panel hypernet-node-tracker" aria-label="Node position tracker">
    <div className="section-heading compact"><div><h4>Node position tracker</h4><p>Record the layout you see in-game, left-to-right then top-to-bottom. Numbers identify positions, not the node’s code.</p></div></div>
    <p className="muted">Keep “Hide unavailable” off in-game. Match the column count before selecting nodes; changing columns rearranges these numbered positions. Only compare offers captured in the same order.</p>
    <div className="hypernet-node-controls">
      <label>Grid columns<select value={draft.columns} disabled={busy} onChange={(event) => change({ ...draft, columns: Number(event.target.value) as HyperNetNodeMap["columns"] })}>{[2, 4, 8, 16].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <div className="button-row" aria-label="Node selection mode"><button type="button" aria-pressed={mode === "seed"} disabled={busy} onClick={() => setMode("seed")}>Mark seeded nodes</button><button type="button" aria-pressed={mode === "winner"} disabled={busy} onClick={() => setMode("winner")}>Mark winning node</button></div>
    </div>
    <p><strong>{seeded.size}/{offer.seller_owned_nodes} seeded positions recorded</strong> · {draft.winning_position === null ? "Winner not recorded" : `Winning position: ${draft.winning_position}${winnerSeeded ? " (seeded)" : " (not marked seeded)"}`}</p>
    {!complete && <p className="mini-alert">The position count differs from the offer’s seeded count. You can save partial records; they are excluded from seeded-win comparisons until the counts match.</p>}
    {conflict && <p className="mini-alert">This winning position conflicts with the reconciled seller/external winner. Correct the map or reconciliation; seeded-win comparisons exclude this record.</p>}
    <div className="hypernet-node-scroll"><div className="hypernet-node-grid" style={{ gridTemplateColumns: `repeat(${draft.columns}, minmax(44px, 1fr))` }}>
      {Array.from({ length: offer.total_nodes }, (_, index) => {
        const position = index + 1, isSeeded = seeded.has(position), won = draft.winning_position === position;
        const label = `Position ${position}, row ${Math.floor(index / draft.columns) + 1}, column ${index % draft.columns + 1}${isSeeded ? ", seeded" : ""}${won ? ", winner" : ""}`;
        return <button type="button" key={position} className={`hypernet-node-cell${isSeeded ? " seeded" : ""}${won ? " winner" : ""}`} disabled={busy} aria-label={label} title={label} aria-pressed={mode === "seed" ? isSeeded : won} onClick={(event) => select(position, event.shiftKey)}><span>{position}</span><small>{won ? "★" : isSeeded ? "S" : "·"}</small></button>;
      })}
    </div></div>
    <p className="muted">S = seeded · ★ = winning node. Shift-click a second position to mark or clear a range. Marking a winner does not complete the offer or change its profit; reconcile it separately.</p>
    <div className="button-row"><button type="button" disabled={busy || !dirty} onClick={() => void save()}>{busy ? "Saving…" : "Save node positions"}</button><button type="button" disabled={busy || !dirty} onClick={() => change(saved ?? emptyMap)}>Discard changes</button><button type="button" disabled={busy || !seeded.size} onClick={() => change({ ...draft, seeded_positions: [] })}>Clear seeded positions</button><button type="button" disabled={busy || draft.winning_position === null} onClick={() => change({ ...draft, winning_position: null })}>Clear winner</button></div>
    {dirty && <small className="muted">Unsaved position changes</small>}
    {message && <p role="status">{message}</p>}{error && <div role="alert" className="mini-alert">{error}</div>}
  </section>;
}
