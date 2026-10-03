import { useCallback, useEffect, useState } from "react";
import { Coins, Download, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import "./plex.css";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Kind = "buy" | "opening" | "sell" | "consume";
type Transaction = { id: number; occurred_at: string; kind: Kind; quantity: number; unit_price: number | null; fees: number; note: string; cost_basis: number | null; realized_profit: number | null };
type Ledger = { transactions: Transaction[]; quantity: number; unknown_cost_quantity: number; cost_basis: number | null; known_cost_basis: number; average_cost: number | null; realized_profit: number | null; known_realized_profit: number; unknown_cost_sales: number; trade_cash_flow: number; consumed_quantity: number };
type Market = { best_bid: number | null; best_ask: number | null; spread: number | null; best_bid_volume: number; best_ask_volume: number; buy_volume: number; sell_volume: number; fetched_at: string; stale: boolean; warning?: string };
type Day = { date: string; average: number; highest: number; lowest: number; volume: number; order_count: number };
type History = { history: Day[]; fetched_at: string; stale: boolean; warning?: string };
const isk = (value: number | null | undefined) => value == null ? "Unknown" : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ISK`;
const count = (value: number) => value.toLocaleString();
const labels: Record<Kind, string> = { buy: "Purchase", opening: "Opening holdings / gift / pack", sell: "Sale", consume: "Spent / converted" };
const localDate = (value = new Date().toISOString()) => { const d = new Date(value); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const errorText = (error: unknown) => error instanceof Error ? error.message : "Request failed";

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <article className="plex-metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

export function PlexTrackerPage({ api }: { api: Api }) {
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [market, setMarket] = useState<Market | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [marketError, setMarketError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<Transaction | "new" | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      api<Ledger>("/plex/ledger").then(value => { setLedger(value); setError(""); }).catch(e => setError(errorText(e))),
      api<Market>("/plex/market").then(value => { setMarket(value); setMarketError(""); }).catch(e => setMarketError(errorText(e))),
      api<History>("/plex/history").then(value => { setHistory(value); setHistoryError(""); }).catch(e => setHistoryError(errorText(e))),
    ]);
    setLoading(false);
  }, [api]);
  useEffect(() => { void refresh(); }, [refresh]);

  async function remove(id: number) {
    setBusy(true); setError("");
    try { setLedger(await api<Ledger>(`/plex/transactions/${id}`, { method: "DELETE" })); setDeleting(null); setNotice("Transaction deleted; FIFO costs recalculated."); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  function exportCsv() {
    if (!ledger) return;
    const cell = (value: unknown) => { const text = String(value ?? ""); return `"${(/^[=+\-@\t\r]/.test(text) ? "'" + text : text).replace(/"/g, '""')}"`; };
    const rows = [["Date UTC", "Type", "PLEX", "ISK per PLEX", "Fees ISK", "FIFO cost ISK", "Realized profit ISK", "Notes"], ...ledger.transactions.map(t => [t.occurred_at, t.kind, t.quantity, t.unit_price, t.fees, t.cost_basis, t.realized_profit, t.note])];
    const url = URL.createObjectURL(new Blob([rows.map(row => row.map(cell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = "eqm-plex-ledger.csv"; a.click(); URL.revokeObjectURL(url);
  }

  return <div className="plex-page">
    <header className="plex-heading"><div><h2><Coins size={24} /> PLEX Tracker</h2><p>Your private PLEX holdings, trades, and global market prices.</p></div><div className="plex-actions"><button disabled={loading || busy || editing !== null} onClick={() => void refresh()}><RefreshCw size={16} /> {loading ? "Refreshing…" : "Refresh"}</button><button disabled={!ledger || busy || editing !== null} onClick={() => { setEditing("new"); setNotice(""); }}><Plus size={16} /> Record transaction</button></div></header>
    {error && <div className="plex-warning" role="alert">{error}</div>}
    {notice && <p role="status">{notice}</p>}
    <section className="plex-panel" aria-label="Global PLEX market"><h3>Global market · PLEX</h3>
      {marketError && <p className="plex-warning" role="alert">{marketError}{market && " Displayed prices are from the earlier snapshot below."}</p>}
      {market?.stale && <p className="plex-warning">{market.warning}</p>}
      {market ? <><div className="plex-metrics">
        <Metric label="Highest buy offer" value={isk(market.best_bid)} detail={`${count(market.best_bid_volume)} PLEX offered at this price`} />
        <Metric label="Lowest sell listing" value={isk(market.best_ask)} detail={`${count(market.best_ask_volume)} PLEX listed at this price`} />
        <Metric label="Bid–ask spread" value={isk(market.spread)} detail={market.best_ask && market.spread != null ? `${(market.spread / market.best_ask * 100).toFixed(2)}% of ask` : "One side of the market is unavailable"} />
      </div><p className="plex-muted">ESI snapshot fetched {new Date(market.fetched_at).toLocaleString()}. Refresh uses a five-minute cache. Quotes are per PLEX, before fees; available volume and order conditions limit fills.</p></> : <p>{loading ? "Fetching ESI prices…" : "No market snapshot available. You can still maintain your ledger."}</p>}
    </section>
    {ledger && <><section className="plex-panel"><h3>My holdings</h3><div className="plex-metrics">
      <Metric label="PLEX held" value={count(ledger.quantity)} detail={`${count(ledger.consumed_quantity)} spent / converted`} />
      <Metric label="Remaining FIFO cost" value={isk(ledger.cost_basis)} detail={`Average: ${isk(ledger.average_cost)} per PLEX`} />
      <Metric label="Realized trading profit" value={isk(ledger.realized_profit)} detail={ledger.unknown_cost_sales ? `${ledger.unknown_cost_sales} sales have unknown cost; known portion ${isk(ledger.known_realized_profit)}` : "After recorded acquisition and sale fees"} />
      <Metric label="Value at highest bid · before fees" value={market?.best_bid != null ? isk(ledger.quantity * market.best_bid) : "Unavailable"} detail="Indicative value; not a quote to fill your whole holding" />
    </div>{ledger.unknown_cost_quantity > 0 && <p className="plex-warning">{count(ledger.unknown_cost_quantity)} PLEX have unknown acquisition cost. Known holdings cost {isk(ledger.known_cost_basis)}. Total profit and break-even remain unknown until those costs are entered.</p>}
    <p className="plex-muted">FIFO uses the oldest acquisitions first across this account. Opening holdings can retain an unknown ISK basis; add a note if you use an estimated or replacement value. Trades are entered manually and do not place EVE market orders.</p></section>
    {editing !== null && <TransactionForm key={editing === "new" ? "new" : editing.id} transaction={editing === "new" ? null : editing} api={api} onCancel={() => setEditing(null)} onSaved={value => { setLedger(value); setEditing(null); setNotice("Transaction saved; holdings and FIFO costs updated."); }} />}
    <TradeScenario ledger={ledger} market={market} />
    </>}
    <PriceHistory data={history} error={historyError} loading={loading} />
    {ledger && <section className="plex-panel"><div className="plex-heading"><h3>Transaction ledger</h3><button onClick={exportCsv} disabled={!ledger.transactions.length}><Download size={16} /> Export CSV</button></div>
      {!ledger.transactions.length ? <p>No transactions yet. Record a purchase, or add opening holdings for PLEX you already own.</p> : <div className="plex-table-wrap"><table><thead><tr><th>Date</th><th>Type</th><th>PLEX</th><th>ISK / PLEX</th><th>Fees</th><th>Realized profit</th><th>Notes</th><th>Actions</th></tr></thead><tbody>{ledger.transactions.map(t => <tr key={t.id}><td>{new Date(t.occurred_at).toLocaleString()}</td><td>{labels[t.kind]}</td><td>{count(t.quantity)}</td><td>{t.kind === "consume" ? "—" : isk(t.unit_price)}</td><td>{isk(t.fees)}</td><td>{t.kind === "sell" ? isk(t.realized_profit) : "—"}</td><td className="plex-note">{t.note}</td><td><div className="plex-actions">{deleting === t.id ? <><span>Delete?</span><button disabled={busy} onClick={() => void remove(t.id)}>Confirm</button><button disabled={busy} onClick={() => setDeleting(null)}>Cancel</button></> : <><button aria-label={`Edit transaction ${t.id}`} disabled={busy || editing !== null || loading} onClick={() => { setEditing(t); setNotice(""); }}><Pencil size={14} /></button><button aria-label={`Delete transaction ${t.id}`} disabled={busy || editing !== null || loading} onClick={() => setDeleting(t.id)}><Trash2 size={14} /></button></>}</div></td></tr>)}</tbody></table></div>}
    </section>}
  </div>;
}

function TransactionForm({ transaction, api, onSaved, onCancel }: { transaction: Transaction | null; api: Api; onSaved: (value: Ledger) => void; onCancel: () => void }) {
  const [kind, setKind] = useState<Kind>(transaction?.kind ?? "buy");
  const [date, setDate] = useState(localDate(transaction?.occurred_at));
  const [quantity, setQuantity] = useState(String(transaction?.quantity ?? ""));
  const [price, setPrice] = useState(String(transaction?.unit_price ?? ""));
  const [fees, setFees] = useState(String(transaction?.fees ?? 0));
  const [note, setNote] = useState(transaction?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <form className="plex-panel" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError("");
    try { const data = await api<Ledger>(`/plex/transactions${transaction ? `/${transaction.id}` : ""}`, { method: transaction ? "PUT" : "POST", body: JSON.stringify({ kind, occurred_at: transaction && date === localDate(transaction.occurred_at) ? transaction.occurred_at : new Date(date).toISOString(), quantity: Number(quantity), unit_price: kind === "consume" || price === "" ? null : price, fees: kind === "consume" ? "0" : fees, note }) }); onSaved(data); }
    catch (err) { setError(errorText(err)); }
    finally { setBusy(false); }
  }}><h3>{transaction ? "Edit transaction" : "Record transaction"}</h3>{error && <p role="alert" className="plex-warning">{error}</p>}<fieldset disabled={busy} className="plex-fields">
    <label>Type<select aria-label="Type" value={kind} onChange={e => setKind(e.target.value as Kind)}>{Object.entries(labels).map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
    <label>Date and time · local<input type="datetime-local" required value={date} onChange={e => setDate(e.target.value)} /></label>
    <label>PLEX quantity<input type="number" required min="1" max="1000000000" step="1" value={quantity} onChange={e => setQuantity(e.target.value)} /></label>
    {kind !== "consume" && <><label>{kind === "opening" ? "ISK basis per PLEX · blank if unknown" : "Actual ISK price per PLEX"}<input type="number" required={kind !== "opening"} min={kind === "opening" ? "0" : "0.01"} step="0.01" value={price} onChange={e => setPrice(e.target.value)} /></label>
    <label>Total fees / taxes · ISK<input type="number" required min="0" step="0.01" value={fees} onChange={e => setFees(e.target.value)} /></label></>}
    <label className="plex-wide">Notes / pilot / source<textarea maxLength={2000} value={note} onChange={e => setNote(e.target.value)} placeholder="For example: LabRat · PLEX pack with bonus · historical ISK basis unknown" /></label>
    </fieldset><p className="plex-muted">{kind === "consume" ? "Removes PLEX for Omega, HyperCores, gifts, or other uses. Consumed cost is not a trading loss." : kind === "opening" ? "Include bonus PLEX in quantity. A blank basis means unknown, while zero explicitly means zero cost. Opening holdings are not counted as a new ISK cash purchase." : "Record the completed trade price and total fees, not an unfilled order or today's replacement value."}</p>
    <div className="plex-actions"><button disabled={busy} type="submit">{busy ? "Saving…" : "Save transaction"}</button><button disabled={busy} type="button" onClick={onCancel}>Cancel</button></div>
  </form>;
}

function TradeScenario({ ledger, market }: { ledger: Ledger; market: Market | null }) {
  const [mode, setMode] = useState("holdings");
  const [quantity, setQuantity] = useState("500");
  const [entry, setEntry] = useState("");
  const [target, setTarget] = useState("");
  const [fee, setFee] = useState("0");
  const [purchaseFees, setPurchaseFees] = useState("0");
  const qty = mode === "holdings" ? ledger.quantity : Number(quantity);
  const targetPrice = target === "" ? market?.best_bid ?? null : Number(target);
  const entryPrice = entry === "" ? market?.best_ask ?? null : Number(entry);
  const feeRate = Number(fee) / 100;
  const cost = mode === "holdings" ? ledger.cost_basis : entryPrice == null ? null : qty * entryPrice + Number(purchaseFees);
  const valid = Number.isInteger(qty) && qty > 0 && fee !== "" && feeRate >= 0 && feeRate < 1 && Number(purchaseFees) >= 0 && (entryPrice == null || entryPrice >= 0) && (targetPrice == null || targetPrice >= 0);
  const proceeds = valid && targetPrice != null ? qty * targetPrice * (1 - feeRate) : null;
  const profit = proceeds != null && cost != null ? proceeds - cost : null;
  const breakEven = valid && cost != null ? cost / qty / (1 - feeRate) : null;
  return <section className="plex-panel"><h3>Plan a future sale</h3><p>Compare a target price for your holdings or a hypothetical purchase. This is a spot-trade scenario, not a futures contract or price prediction.</p><div className="plex-fields">
    <label>Scenario<select aria-label="Scenario" value={mode} onChange={e => setMode(e.target.value)}><option value="holdings">Sell all tracked holdings</option><option value="purchase">New hypothetical purchase</option></select></label>
    {mode === "purchase" && <><label>PLEX quantity<input type="number" min="1" step="1" value={quantity} onChange={e => setQuantity(e.target.value)} /></label><label>Purchase ISK / PLEX<input type="number" min="0" step="0.01" placeholder={String(market?.best_ask ?? "")} value={entry} onChange={e => setEntry(e.target.value)} /></label><label>Total purchase fees · ISK<input type="number" min="0" step="0.01" value={purchaseFees} onChange={e => setPurchaseFees(e.target.value)} /></label></>}
    <label>Target sale ISK / PLEX<input type="number" min="0" step="0.01" placeholder={String(market?.best_bid ?? "")} value={target} onChange={e => setTarget(e.target.value)} /></label>
    <label>Combined selling fees / taxes · %<input type="number" min="0" max="99.99" step="0.01" value={fee} onChange={e => setFee(e.target.value)} /></label>
    </div><p className="plex-muted">Blank prices use the displayed market snapshot: ask to buy, bid to sell. Fees default to 0%; enter your applicable total. No fee rate is inferred from skills. Listing at the ask does not guarantee a sale.</p>
    <div className="plex-metrics"><Metric label="Estimated net proceeds" value={isk(proceeds)} /><Metric label="Estimated profit" value={isk(profit)} detail={profit != null && cost != null && cost > 0 ? `${(profit / cost * 100).toFixed(2)}% return on cost` : "Requires a known cost basis and quantity"} /><Metric label="Break-even sale price per PLEX" value={isk(breakEven)} /></div>
    {mode === "holdings" && !ledger.quantity && <p>No holdings yet. Use the hypothetical purchase scenario to plan a trade.</p>}
  </section>;
}

function PriceHistory({ data, error, loading }: { data: History | null; error: string; loading: boolean }) {
  const [days, setDays] = useState(30);
  const latest = data?.history[data.history.length - 1];
  const cutoff = latest ? new Date(`${latest.date}T00:00:00Z`).getTime() - (days - 1) * 86400000 : 0;
  const rows = data?.history.filter(r => new Date(`${r.date}T00:00:00Z`).getTime() >= cutoff) ?? [];
  const low = Math.min(...rows.map(r => r.average)); const high = Math.max(...rows.map(r => r.average));
  const points = rows.map((r, i) => `${40 + i / Math.max(rows.length - 1, 1) * 880},${170 - (r.average - low) / (high - low || 1) * 130}`).join(" ");
  const first = rows[0]; const change = latest && first?.average ? (latest.average / first.average - 1) * 100 : null;
  return <section className="plex-panel"><div className="plex-heading"><h3>Daily market history</h3><label>Window<select aria-label="History window" value={days} onChange={e => setDays(Number(e.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option></select></label></div>
    {error && <p className="plex-warning">{error}</p>}{data?.stale && <p className="plex-warning">{data.warning}</p>}
    {rows.length ? <><div className="plex-metrics"><Metric label={`Daily average · ${latest!.date}`} value={isk(latest!.average)} /><Metric label="Change across displayed history" value={change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`} /><Metric label="Latest daily volume" value={`${count(latest!.volume)} PLEX`} /></div>
      <div className="plex-chart-labels"><span>High average: {isk(high)}</span><span>Low average: {isk(low)}</span></div>
      <svg className="plex-chart" viewBox="0 0 960 190" preserveAspectRatio="none" role="img" aria-label={`Daily average PLEX prices from ${first.date} to ${latest!.date}; change ${change?.toFixed(2)} percent`}><polyline points={points} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" />{rows.length === 1 && <circle cx="40" cy="170" r="4" fill="currentColor" />}</svg>
      <div className="plex-chart-labels"><span>{first.date}</span><span>{latest!.date}</span></div>
      <p className="plex-muted">Daily traded averages, not live bids or asks. ESI history fetched {new Date(data!.fetched_at).toLocaleString()}; cached for one hour.</p>
      <details><summary>View daily prices and volume</summary><div className="plex-table-wrap"><table><thead><tr><th>Date</th><th>Average</th><th>Low</th><th>High</th><th>PLEX traded</th></tr></thead><tbody>{[...rows].reverse().map(r => <tr key={r.date}><td>{r.date}</td><td>{isk(r.average)}</td><td>{isk(r.lowest)}</td><td>{isk(r.highest)}</td><td>{count(r.volume)}</td></tr>)}</tbody></table></div></details>
    </> : <p>{loading ? "Loading daily history…" : "No daily history available."}</p>}
  </section>;
}
