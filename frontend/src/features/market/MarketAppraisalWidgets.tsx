import {
  formatMarketIsk,
  marketHubDestinationId,
  marketHubDestinationName,
  marketHubSubtitle,
  type MarketItemBest,
} from "../../lib/market";
import type { MarketHub, MarketItemQuote } from "../../types/market";

export type MarketInsight = {
  key: string;
  item: MarketItemQuote;
  best: MarketItemBest;
};

type MarketHubGridProps = {
  hubs: MarketHub[];
  selectedHubs: string[];
  isMarketAdmin: boolean;
  onToggle: (hubKey: string) => void;
  onRemove: (hubKey: string) => void;
  onSetDestination: (destinationId: number, destinationName: string) => void;
};

export function MarketHubGrid({ hubs, selectedHubs, isMarketAdmin, onToggle, onRemove, onSetDestination }: MarketHubGridProps) {
  return <div className="market-hub-grid">
    {hubs.map((hub) => {
      const destinationId = marketHubDestinationId(hub);
      const destinationName = marketHubDestinationName(hub);

      return <label key={hub.key} className={`market-hub-option ${selectedHubs.includes(hub.key) ? "active" : ""} ${!hub.available ? "disabled" : ""} ${hub.custom ? "custom" : ""}`}>
        <input type="checkbox" checked={selectedHubs.includes(hub.key)} disabled={!hub.available} onChange={() => onToggle(hub.key)} />
        <strong>{hub.label}</strong>
        <span>{marketHubSubtitle(hub)}</span>
        {destinationId && <button type="button" className="destination-link market-hub-destination" title={destinationName} onClick={(event) => { event.preventDefault(); event.stopPropagation(); onSetDestination(destinationId, destinationName); }}>Set dest</button>}
        {hub.custom && isMarketAdmin && <button type="button" className="market-hub-delete" onClick={(event) => { event.preventDefault(); event.stopPropagation(); onRemove(hub.key); }}>Remove</button>}
      </label>;
    })}
  </div>;
}

type MarketTotalsGridProps = {
  hubs: MarketHub[];
  totals?: Record<string, { buy_total?: number | null; sell_total?: number | null; split_total?: number | null }>;
};

export function MarketTotalsGrid({ hubs, totals }: MarketTotalsGridProps) {
  return <div className="market-total-grid">
    {hubs.map((hub) => {
      const hubTotals = totals?.[hub.key];
      return <article key={hub.key}>
        <span>{hub.label}</span>
        <strong>{formatMarketIsk(hubTotals?.sell_total)}</strong>
        <small>Sell total</small>
        <small>Split {formatMarketIsk(hubTotals?.split_total)}</small>
        <small>Buy {formatMarketIsk(hubTotals?.buy_total)}</small>
      </article>;
    })}
  </div>;
}

export function MarketMarginHints({ insights }: { insights: MarketInsight[] }) {
  if (insights.length === 0) return <div className="market-no-profit">No profitable station-to-station orders right now.</div>;

  return <div className="market-margin-hints">
    {insights.map(({ key, item, best }) => <article key={key} className="market-margin-card positive">
      <strong>{item.type_name ?? item.name}</strong>
      <span>Buy at {best.buyHubLabel} / sell to {best.sellHubLabel}</span>
      <b>+{formatMarketIsk(best.margin)}</b>
    </article>)}
  </div>;
}

export function MarketLegend() {
  return <div className="market-legend">
    <span><i className="legend-dot healthy" /> Best sell price</span>
    <span><i className="legend-dot buy" /> Best buy order</span>
    <span><i className="legend-dot split" /> Best split estimate</span>
    <span><i className="legend-dot one" /> Thin order depth warns the price may be fragile</span>
  </div>;
}
