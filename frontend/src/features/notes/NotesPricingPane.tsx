import { RefreshCw, ShoppingCart } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { MarketHub, NoteAssetScope, NotePriceResult } from "../../types/notes";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type Props = {
  api: ApiClient;
  noteId: number;
  selectedItemIds: number[];
  assetScope: NoteAssetScope;
  ownerIds: number[];
  sourceHubKey?: string | null;
};

const isk = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function NotesPricingPane({ api, noteId, selectedItemIds, assetScope, ownerIds, sourceHubKey }: Props) {
  const [hubs, setHubs] = useState<MarketHub[]>([]);
  const [selectedHubs, setSelectedHubs] = useState<string[]>([]);
  const [mode, setMode] = useState<"remaining" | "requested">("remaining");
  const [result, setResult] = useState<NotePriceResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api<MarketHub[]>("/notes/market-hubs")
      .then((rows) => {
        setHubs(rows);
        const preferred = sourceHubKey && rows.some((row) => row.key === sourceHubKey) ? [sourceHubKey] : rows.filter((row) => ["jita", "amarr", "hek", "dodixie", "rens"].includes(row.key)).map((row) => row.key);
        setSelectedHubs(preferred);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load market hubs."));
  }, [api, sourceHubKey]);

  const availableHubs = useMemo(() => hubs.filter((hub) => hub.available), [hubs]);

  async function price() {
    if (!selectedItemIds.length) {
      setError("Select one or more item rows before pricing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await api<NotePriceResult>("/notes/" + noteId + "/price", {
        method: "POST",
        body: JSON.stringify({
          item_ids: selectedItemIds,
          quantity_mode: mode,
          hubs: selectedHubs,
          asset_scope: assetScope,
          owner_ids: ownerIds,
        }),
      });
      setResult(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Market pricing failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="notes-pricing-panel">
      <header className="section-heading">
        <div>
          <h4>Market pricing</h4>
          <p>Quotes are temporary and refresh only when requested.</p>
        </div>
        <button type="button" disabled={busy || selectedItemIds.length === 0} onClick={() => void price()}>
          {busy ? <RefreshCw className="spin" size={16} /> : <ShoppingCart size={16} />}
          {busy ? "Pricing" : "Price " + (selectedItemIds.length || "") + " selected"}
        </button>
      </header>

      <div className="notes-price-controls">
        <label>
          Quantity
          <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
            <option value="remaining">Remaining need</option>
            <option value="requested">Full requested</option>
          </select>
        </label>
        <fieldset>
          <legend>Market hubs</legend>
          <div className="notes-hub-options">
            {availableHubs.map((hub) => (
              <label key={hub.key}>
                <input
                  type="checkbox"
                  checked={selectedHubs.includes(hub.key)}
                  onChange={(event) => setSelectedHubs((current) => event.target.checked ? [...current, hub.key] : current.filter((key) => key !== hub.key))}
                />
                {hub.label}
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {error && <div className="mini-alert">{error}</div>}
      {result && (
        <>
          <div className="notes-price-totals">
            {result.hubs.map((hub) => {
              const totals = result.totals[hub.key];
              return (
                <article key={hub.key}>
                  <strong>{hub.label}</strong>
                  <span>Buy {isk.format(totals?.buy_total ?? 0)} ISK</span>
                  <span>Sell {isk.format(totals?.sell_total ?? 0)} ISK</span>
                  <span>Split {isk.format(totals?.split_total ?? 0)} ISK</span>
                </article>
              );
            })}
          </div>
          <div className="table-wrap notes-price-table">
            <table>
              <thead><tr><th>Item</th><th>Qty</th>{result.hubs.map((hub) => <th key={hub.key}>{hub.label}</th>)}</tr></thead>
              <tbody>
                {result.items.map((item) => (
                  <tr key={String(item.type_id) + "-" + item.name}>
                    <td>{item.type_name ?? item.name}</td>
                    <td>{isk.format(item.quantity)}</td>
                    {result.hubs.map((hub) => {
                      const quote = item.hubs[hub.key];
                      return <td key={hub.key}><span className="market-price-cell"><b>{isk.format(quote?.buy ?? 0)} / {isk.format(quote?.sell ?? 0)}</b><small>buy / sell</small></span></td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <small className="muted">Priced {new Date(result.priced_at).toLocaleString()} using {result.quantity_mode === "remaining" ? "remaining need" : "full requested quantities"}.</small>
        </>
      )}
    </section>
  );
}