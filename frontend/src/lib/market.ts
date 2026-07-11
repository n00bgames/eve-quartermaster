import type { MarketHub, MarketHubQuote, MarketItemQuote } from "../types/market";

export const iskFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export type MarketItemBest = {
  lowestSellKey?: string;
  highestBuyKey?: string;
  highestSplitKey?: string;
  margin?: number | null;
  buyHubLabel?: string;
  sellHubLabel?: string;
};

export function formatMarketIsk(value?: number | null): string {
  return value == null ? "-" : `${iskFormatter.format(value)} ISK`;
}

export function positiveMarketValue(value?: number | null): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

export function validMarketSell(quote?: MarketHubQuote | null): number | null {
  return (quote?.sell_orders ?? 0) > 0 ? positiveMarketValue(quote?.sell) : null;
}

export function validMarketBuy(quote?: MarketHubQuote | null): number | null {
  return (quote?.buy_orders ?? 0) > 0 ? positiveMarketValue(quote?.buy) : null;
}

export function validMarketSplit(quote?: MarketHubQuote | null): number | null {
  const split = positiveMarketValue(quote?.split);
  return validMarketSell(quote) != null && validMarketBuy(quote) != null ? split : null;
}

export function marketDepthClass(count?: number | null): string {
  if (!count || count <= 1) return "one";
  if (count < 5) return "thin";
  return "healthy";
}

export function bestMarketForItem(item: MarketItemQuote, hubs: MarketHub[]): MarketItemBest {
  if (!item.matched || !item.type_id) return {};

  const quotes = hubs.map((hub) => ({ hub, quote: (item.hubs ?? {})[hub.key] })).filter(({ quote }) => Boolean(quote));

  const lowestSell = quotes
    .map((entry) => ({ ...entry, value: validMarketSell(entry.quote) }))
    .filter((entry) => entry.value != null)
    .sort((left, right) => (left.value ?? Infinity) - (right.value ?? Infinity))[0];

  const highestBuy = quotes
    .map((entry) => ({ ...entry, value: validMarketBuy(entry.quote) }))
    .filter((entry) => entry.value != null)
    .sort((left, right) => (right.value ?? -Infinity) - (left.value ?? -Infinity))[0];

  const highestSplit = quotes
    .map((entry) => ({ ...entry, value: validMarketSplit(entry.quote) }))
    .filter((entry) => entry.value != null)
    .sort((left, right) => (right.value ?? -Infinity) - (left.value ?? -Infinity))[0];

  const tradePairs = quotes.flatMap((buyQuote) => {
    const buyAt = validMarketSell(buyQuote.quote);
    if (buyAt == null) return [];

    return quotes
      .filter((sellQuote) => buyQuote.hub.key !== sellQuote.hub.key)
      .map((sellQuote) => {
        const sellTo = validMarketBuy(sellQuote.quote);
        if (sellTo == null) return null;

        return {
          buyHubLabel: buyQuote.hub.label,
          sellHubLabel: sellQuote.hub.label,
          margin: (sellTo - buyAt) * item.quantity,
        };
      })
      .filter((pair): pair is { buyHubLabel: string; sellHubLabel: string; margin: number } => pair !== null && pair.margin > 0);
  });

  const bestTrade = tradePairs.sort((left, right) => right.margin - left.margin)[0];

  return {
    lowestSellKey: lowestSell?.hub.key,
    highestBuyKey: highestBuy?.hub.key,
    highestSplitKey: highestSplit?.hub.key,
    margin: bestTrade?.margin ?? null,
    buyHubLabel: bestTrade?.buyHubLabel,
    sellHubLabel: bestTrade?.sellHubLabel,
  };
}

export function marketHubDestinationId(hub: MarketHub) {
  return hub.destination_id ?? hub.location_id ?? hub.system_id ?? null;
}

export function marketHubDestinationName(hub: MarketHub) {
  return hub.destination_name ?? hub.station_names?.[0] ?? hub.system_name ?? hub.label;
}

export function marketHubSubtitle(hub: MarketHub) {
  if (hub.npc_group) return "best NPC hub";
  const stationText = hub.station_count ? `${hub.station_count} station${hub.station_count === 1 ? "" : "s"}` : null;
  if (hub.destination_name && hub.location_scope === "station") return `${hub.destination_name}${hub.region_name ? ` - ${hub.region_name}` : ""}`;
  if (hub.system_name && hub.region_name) return `${hub.system_name} - ${hub.region_name}${stationText ? ` - ${stationText}` : ""}`;
  if (hub.system_name) return `${hub.system_name}${stationText ? ` - ${stationText}` : " - region not resolved"}`;
  if (hub.region_name) return `${hub.region_name} - region ${hub.region_id}`;
  if (hub.region_id) return `region ${hub.region_id}`;
  return "region not resolved";
}
