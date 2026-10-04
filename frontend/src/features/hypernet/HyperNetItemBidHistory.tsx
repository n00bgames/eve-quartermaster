import { useEffect, useRef, useState } from "react";
import type { ApiClient, HyperNetItemBidHistory as ItemHistory, HyperNetMeta } from "../../types/hypernet";
import { formatIsk, hypernetItemIcon, profitClass } from "./hypernetPresentation";

export function HyperNetItemBidHistory({ api, item, characters, initialCharacterId, onClose }: {
  api: ApiClient; item: { type_id: number; name: string };
  characters: NonNullable<HyperNetMeta["filter_characters"]>;
  initialCharacterId: string; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [characterId, setCharacterId] = useState(initialCharacterId);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [data, setData] = useState<ItemHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const element = dialog.current!;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    element.showModal();
    return () => { element.close(); opener?.focus(); };
  }, []);
  useEffect(() => {
    let cancelled = false;
    setData(null); setError(null);
    void api<ItemHistory>(`/hypernet/bid-history?type_id=${item.type_id}&offset=${offset}&limit=50${characterId ? `&character_id=${encodeURIComponent(characterId)}` : ""}`)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load item bid history"); });
    return () => { cancelled = true; };
  }, [api, item.type_id, characterId, offset, retry]);
  const stats = data?.summary;
  const metric = (label: string, value: string, detail?: string, tone?: string) => <article className={`hypernet-summary-metric ${tone ?? ""}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
  return <dialog ref={dialog} className="hypernet-item-history panel" aria-labelledby="hypernet-item-history-title" onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <div className="section-heading"><div><span className="eyebrow">Item bid history</span><h3 id="hypernet-item-history-title"><img src={hypernetItemIcon(item)} alt="" />{item.name}</h3></div><button type="button" onClick={onClose} autoFocus>Close</button></div>
    <label className="hypernet-history-character">History character<select aria-label="History character" value={characterId} onChange={(event) => { setData(null); setError(null); setCharacterId(event.target.value); setOffset(0); }}><option value="">All My Characters</option>{characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}</select></label>
    <p className="muted">All recorded bids for this exact item, independent of board search and outcome filters. Wins use the recorded item value, not cash from a later sale. Pending bids and refunded outcomes are excluded from settled results, win rate, and ROI.</p>
    {error ? <div className="mini-alert" role="alert">{error} <button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</button></div> : !data ? <p role="status">Loading item bid history…</p> : stats && <>
      <div className="hypernet-item-history-metrics">
        {metric("Bids recorded", stats.total_bids.toLocaleString(), `${stats.won_bids} won · ${stats.lost_bids} lost · ${stats.pending_bids} pending`)}
        {metric("Settled bid spend", formatIsk(stats.resolved_spend), "Cost of won and lost bids")}
        {metric("ISK lost on losing bids", formatIsk(stats.lost_spend), undefined, stats.lost_spend ? "hypernet-loss" : undefined)}
        {metric("Net from winning bids", formatIsk(stats.won_profit), "Recorded prize values minus winning stakes", profitClass(stats.won_profit))}
        {metric("Net bid result", formatIsk(stats.net_result), "Winning results minus losing stakes", profitClass(stats.net_result))}
        {metric("Prizes won: recorded value", formatIsk(stats.item_value_won))}
        {metric("Pending exposure", formatIsk(stats.pending_spend), `${stats.pending_bids} pending bids`)}
        {metric("Refunded / cancelled stakes", formatIsk(stats.refunded_spend), `${stats.expired_bids} expired · ${stats.cancelled_bids} cancelled`)}
        {metric("Win rate", stats.win_rate_percent == null ? "—" : `${stats.win_rate_percent.toFixed(2)}%`, "Won ÷ (won + lost)")}
        {metric("ROI on settled bids", stats.roi_percent == null ? "—" : `${stats.roi_percent.toFixed(2)}%`, undefined, profitClass(stats.roi_percent))}
      </div>
      {stats.total_bids === 0 ? <p>No recorded bids for this item and character selection.</p> : <>
        <div className="table-scroll"><table className="hypernet-table"><thead><tr><th>Purchased</th><th>Character / seller</th><th>Outcome</th><th>Nodes / odds</th><th>Stake</th><th>Prize value</th><th>Net result</th></tr></thead><tbody>{data.history.map((bid) => <tr key={bid.id}><td>{new Date(bid.created_at).toLocaleString()}</td><td>{bid.character.name}<small>Seller: {bid.seller_name}</small></td><td>{bid.outcome === "expired" ? "Expired · refunded" : bid.outcome}<small>{bid.completed_at ? new Date(bid.completed_at).toLocaleString() : ""}</small></td><td>{bid.nodes_purchased}/{bid.total_nodes}<small>{bid.win_probability_percent.toFixed(2)}%</small></td><td>{formatIsk(bid.total_spent)}</td><td>{formatIsk(bid.item_value_at_completion)}</td><td className={bid.outcome === "pending" ? "" : profitClass(bid.profit_loss)}>{bid.outcome === "pending" ? "Pending" : formatIsk(bid.profit_loss)}</td></tr>)}</tbody></table></div>
        <div className="button-row"><button type="button" disabled={offset === 0} onClick={() => { setData(null); setOffset(Math.max(0, offset - 50)); }}>Previous</button><span>{offset + 1}–{Math.min(offset + data.history.length, stats.total_bids)} of {stats.total_bids} bids</span><button type="button" disabled={offset + data.history.length >= stats.total_bids} onClick={() => { setData(null); setOffset(offset + 50); }}>Next</button></div>
      </>}
    </>}
  </dialog>;
}
