import { ShoppingCart } from "lucide-react";
import type { ComponentType, FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import { MarketHubGrid, MarketLegend, MarketMarginHints, MarketTotalsGrid } from "./MarketAppraisalWidgets";
import {
  bestMarketForItem,
  formatMarketIsk,
  marketDepthClass,
  marketHubDestinationId,
  marketHubDestinationName,
  validMarketBuy,
  validMarketSell,
  validMarketSplit,
} from "../../lib/market";
import { BUILTIN_MARKET_HUBS, type MarketAppraisal, type MarketHub, type MarketItemQuote } from "../../types/market";

type MarketUser = { role: string };

type MarketAsset = {
  id: number;
  ownership_entity_id: number;
  type_id: number;
  type_name: string;
  quantity: number;
  owner_name: string;
  source: string;
  location_name?: string;
  location_flag?: string;
};

type MarketSeed = { text: string; nonce: number };

type ItemContextPanelProps = {
  typeId?: number | null;
  itemName?: string | null;
  assets?: MarketAsset[];
  compact?: boolean;
  onOpenAssets?: (itemName: string) => void;
  onOpenMarket?: (text: string) => void;
  onOpenFittings?: (itemName: string) => void;
};

type MarketAppraisalPageProps = {
  currentUser: MarketUser;
  seed?: MarketSeed | null;
  assets: MarketAsset[];
  onOpenAssets: (itemName: string) => void;
  onOpenFittings: (itemName: string) => void;
  api: <T>(path: string, options?: RequestInit) => Promise<T>;
  sendDestinationToEve: (destinationId?: number | null, destinationName?: string) => Promise<void>;
  ItemContextPanel: ComponentType<ItemContextPanelProps>;
  numberFormatter: Intl.NumberFormat;
};

export function MarketAppraisalPage({
  currentUser,
  seed,
  assets,
  onOpenAssets,
  onOpenFittings,
  api,
  sendDestinationToEve,
  ItemContextPanel,
  numberFormatter,
}: MarketAppraisalPageProps) {
  const defaultText = "Interdiction Nullifier I 1\ninterdiction nullfier x1\n1 Interdiction Nullifier II\n1x Interdiction Nullifier I";

  const [hubs, setHubs] = useState<MarketHub[]>(BUILTIN_MARKET_HUBS);
  const [selectedHubs, setSelectedHubs] = useState<string[]>(["jita", "amarr", "hek", "dodixie", "rens"]);
  const [text, setText] = useState(defaultText);
  const [result, setResult] = useState<MarketAppraisal | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMarketAdmin = currentUser.role === "admin";
  const [customHubLabel, setCustomHubLabel] = useState("");
  const [customHubSystem, setCustomHubSystem] = useState("");
  const [customHubMessage, setCustomHubMessage] = useState<string | null>(null);
  const selectedResultHubs = useMemo(() => result?.hubs ?? hubs.filter((hub) => selectedHubs.includes(hub.key)), [hubs, result?.hubs, selectedHubs]);

  useEffect(() => {
    if (!seed?.text) return;

    setText(seed.text);
    setResult(null);
    setError(null);
  }, [seed?.nonce]);

  function ownedSummaryForQuote(item: MarketItemQuote) {
    const matches = assets.filter((asset) => item.type_id ? asset.type_id === item.type_id : asset.type_name.toLowerCase() === (item.type_name ?? item.name).toLowerCase());
    const quantity = matches.reduce((total, asset) => total + asset.quantity, 0);
    const locations = matches.slice(0, 3).map((asset) => `${asset.owner_name} @ ${asset.location_name ?? "Unknown"}${asset.location_flag ? ` (${asset.location_flag})` : ""}`);

    return { quantity, locations };
  }

  const marketInsights = useMemo(() => {
    if (!result) return [];

    return result.items.map((item, index) => ({ key: `${item.input}-${index}`, item, best: bestMarketForItem(item, selectedResultHubs) }))
      .filter(({ best }) => best.margin != null && best.margin > 0 && best.buyHubLabel && best.sellHubLabel)
      .sort((left, right) => (right.best.margin ?? 0) - (left.best.margin ?? 0))
      .slice(0, 5);
  }, [result, selectedResultHubs]);

  function applyHubRows(rows: MarketHub[], selectKey?: string) {
    const nextRows = rows.length ? rows : BUILTIN_MARKET_HUBS;

    setHubs(nextRows);
    setSelectedHubs((current) => {
      const filtered = current.filter((key) => nextRows.some((hub) => hub.key === key && hub.available));

      if (selectKey && nextRows.some((hub) => hub.key === selectKey && hub.available) && !filtered.includes(selectKey)) return [...filtered, selectKey];

      return filtered.length ? filtered : BUILTIN_MARKET_HUBS.map((hub) => hub.key);
    });
  }

  useEffect(() => {
    let cancelled = false;

    api<MarketHub[]>("/market/hubs").then((rows) => {
      if (!cancelled) {
        applyHubRows(rows);
        setCustomHubMessage(null);
      }
    }).catch(() => {
      if (!cancelled) {
        applyHubRows(BUILTIN_MARKET_HUBS);
        setCustomHubMessage("Custom market hubs unavailable; using built-in trade hubs.");
      }
    });

    return () => { cancelled = true; };
  }, [api]);

  function toggleHub(key: string) {
    setSelectedHubs((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  async function addCustomHub() {
    setError(null);
    setCustomHubMessage(null);

    try {
      const hub = await api<MarketHub>("/market/hubs", { method: "POST", body: JSON.stringify({ label: customHubLabel, system_name: customHubSystem }) });
      const rows = await api<MarketHub[]>("/market/hubs");

      applyHubRows(rows, hub.key);
      setCustomHubLabel("");
      setCustomHubSystem("");
      setCustomHubMessage(`Added ${hub.label}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add custom hub.");
    }
  }

  async function removeCustomHub(key: string) {
    setError(null);
    setCustomHubMessage(null);

    try {
      await api(`/market/hubs/${encodeURIComponent(key)}`, { method: "DELETE" });
      const rows = await api<MarketHub[]>("/market/hubs");

      applyHubRows(rows);
      setCustomHubMessage("Custom hub removed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove custom hub.");
    }
  }

  async function appraise(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      setResult(await api<MarketAppraisal>("/market/appraise", { method: "POST", body: JSON.stringify({ text, hubs: selectedHubs }) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Market appraisal failed.");
    } finally {
      setBusy(false);
    }
  }

  async function copySummary() {
    if (!result) return;

    const lines = result.items.map((item) => `${item.quantity} x ${item.type_name ?? item.name}`);

    await navigator.clipboard.writeText(lines.join("\n"));
  }

  return <section className="market-page panel stacked">
    <div className="section-heading">
      <div>
        <h3>Market Appraisal</h3>
        <p>Paste item stacks and compare buy, sell, and split estimates across trade hubs.</p>
      </div>
      {result && <button type="button" onClick={() => void copySummary()}>Copy item list</button>}
    </div>

    <form className="market-layout" onSubmit={(event) => void appraise(event)}>
      <div className="stacked-form">
        <label>Item list<textarea className="market-paste" value={text} onChange={(event) => setText(event.target.value)} placeholder="Interdiction Nullifier I 1&#10;1x Interdiction Nullifier II" /></label>
        <div><span className="muted">Accepted quantity styles: item 1, item x1, 1 item, 1x item.</span></div>
        <button type="submit" disabled={busy || !text.trim() || selectedHubs.length === 0}><ShoppingCart size={18} /> {busy ? "Appraising" : "Appraise"}</button>
      </div>
      <div className="stacked-form">
        <h4>Trade hubs</h4>
        <MarketHubGrid
          hubs={hubs}
          selectedHubs={selectedHubs}
          isMarketAdmin={isMarketAdmin}
          onToggle={toggleHub}
          onRemove={(hubKey) => void removeCustomHub(hubKey)}
          onSetDestination={(destinationId, destinationName) => void sendDestinationToEve(destinationId, destinationName)}
        />
        <p className="muted">C-N4OD and custom system hubs use imported SDE system data to locate their market region.</p>
        {isMarketAdmin && <div className="market-custom-hub-form">
          <strong>Custom market hubs</strong>
          <div className="inline-fields">
            <label>Label<input value={customHubLabel} onChange={(event) => setCustomHubLabel(event.target.value)} placeholder="Alliance staging" /></label>
            <label>Solar system<input value={customHubSystem} onChange={(event) => setCustomHubSystem(event.target.value)} placeholder="C-N4OD" /></label>
            <button type="button" onClick={() => void addCustomHub()}>Add hub</button>
          </div>
          {customHubMessage && <span className="market-custom-message">{customHubMessage}</span>}
        </div>}
      </div>
    </form>

    {error && <div className="mini-alert">{error}</div>}

    {result && <>
      <MarketTotalsGrid hubs={selectedResultHubs} totals={result.totals} />

      <MarketMarginHints insights={marketInsights} />

      <MarketLegend />
      {result.unmatched_count > 0 && <div className="mini-alert">{result.unmatched_count} item line{result.unmatched_count === 1 ? "" : "s"} could not be matched to imported SDE type names.</div>}

      <div className="table-wrap market-table-wrap">
        <table className="market-table">
          <thead>
            <tr><th>Item</th><th>Qty</th>{selectedResultHubs.map((hub) => <th key={hub.key}><span className="market-header-hub"><span>{hub.label}</span>{marketHubDestinationId(hub) ? <button type="button" className="destination-link" title={marketHubDestinationName(hub)} onClick={() => void sendDestinationToEve(marketHubDestinationId(hub), marketHubDestinationName(hub))}>Set dest</button> : null}</span></th>)}</tr>
          </thead>
          <tbody>
            {result.items.map((item, index) => {
              const best = bestMarketForItem(item, selectedResultHubs);
              const owned = ownedSummaryForQuote(item);
              const itemName = item.type_name ?? item.name;
              const canQuoteItem = item.matched && Boolean(item.type_id);
              return <tr key={`${item.input}-${index}`}>
                <td>
                  <strong>{itemName}</strong>
                  <span>{item.matched ? `Type ${item.type_id}` : "No SDE match"}</span>
                  <span className={owned.quantity > 0 ? "context-owned" : "context-missing"}>Owned {numberFormatter.format(owned.quantity)}</span>
                  {owned.locations.length > 0 && <small>{owned.locations.join(" | ")}</small>}
                  <div className="context-actions"><button type="button" onClick={() => onOpenAssets(itemName)}>Assets</button><button type="button" onClick={() => onOpenFittings(itemName)}>Fits</button></div>
                  {item.matched && <details className="inline-context-disclosure"><summary>Context</summary><ItemContextPanel compact typeId={item.type_id} itemName={itemName} assets={assets} onOpenAssets={onOpenAssets} onOpenFittings={onOpenFittings} onOpenMarket={(line) => { setText(line); setResult(null); }} /></details>}
                  {(item.ambiguous_matches ?? []).length > 0 && <small>Also saw: {(item.ambiguous_matches ?? []).map((match) => match.name).join(", ")}</small>}
                </td>
                <td>{numberFormatter.format(item.quantity)}</td>
                {!canQuoteItem ? <td colSpan={selectedResultHubs.length}><div className="market-no-quote">No market lookup until this line matches an imported SDE type.</div></td> : selectedResultHubs.map((hub) => {
                  const quote = (item.hubs ?? {})[hub.key];
                  const buyDepth = marketDepthClass(quote?.buy_orders);
                  const sellDepth = marketDepthClass(quote?.sell_orders);
                  const sellValue = validMarketSell(quote);
                  const splitValue = validMarketSplit(quote);
                  const buyValue = validMarketBuy(quote);
                  return <td key={hub.key}>
                    <div className="market-price-cell">
                      <b className={`market-line ${best.lowestSellKey === hub.key ? "market-best-sell" : ""}`}>Sell {formatMarketIsk(sellValue)}</b>
                      <b className={`market-line ${best.highestSplitKey === hub.key ? "market-best-split" : ""}`}>Split {formatMarketIsk(splitValue)}</b>
                      <b className={`market-line ${best.highestBuyKey === hub.key ? "market-best-buy" : ""}`}>Buy {formatMarketIsk(buyValue)}</b>
                      <small>{sellValue != null && quote?.sell_source && quote.sell_source !== hub.label ? `Sell from ${quote.sell_source}` : <><span className={`market-depth ${sellDepth}`}>{quote?.sell_orders ?? 0}</span> sell orders</>}</small>
                      <small>{buyValue != null && quote?.buy_source && quote.buy_source !== hub.label ? `Buy from ${quote.buy_source}` : <><span className={`market-depth ${buyDepth}`}>{quote?.buy_orders ?? 0}</span> buy orders</>}</small>
                    </div>
                  </td>;
                })}
              </tr>;
            })}
          </tbody>
        </table>
      </div>
    </>}
  </section>;
}
