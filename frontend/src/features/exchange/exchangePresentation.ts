import type { ExchangeListing } from "../../types/exchange";

const isk = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export function formatIsk(value?: number | null): string {
  return value == null ? "Not listed" : `${isk.format(value)} ISK`;
}

export function formatExchangeDate(value?: string | null, empty = "No expiration"): string {
  if (!value) return empty;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function exchangeListingUrl(publicId: string): string {
  return `${window.location.origin}/#exchange/${publicId}`;
}

export function exchangeManifest(listing: ExchangeListing): string {
  return listing.items.map((item) => `${item.name}\t${item.quantity * listing.quantity_total}`).join("\n");
}

export function auctionPriceLabel(listing: ExchangeListing): string {
  if (listing.highest_bid != null) return formatIsk(listing.highest_bid);
  return formatIsk(listing.minimum_bid);
}