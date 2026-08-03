export const isk = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export function formatIsk(value?: number | null, compact = false): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (compact) return `${new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 }).format(value)} ISK`;
  return `${isk.format(value)} ISK`;
}

export function localInputValue(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export function countdown(seconds: number): string {
  if (seconds <= 0) return "Expired";
  const hours = Math.floor(seconds / 3600);
  const days = Math.floor(hours / 24);
  if (days) return `${days}d ${hours % 24}h`;
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

export function profitClass(value?: number | null): string {
  if (value == null) return "hypernet-neutral";
  return value >= 0 ? "hypernet-profit" : "hypernet-loss";
}
