export const FALLBACK_TIMEZONE = "UTC";

export const BROWSER_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || FALLBACK_TIMEZONE;

export const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Australia/Sydney",
];

type TimezoneUser = { timezone?: string | null };

export function timezoneChoices(current?: string | null): string[] {
  return [...new Set([current || BROWSER_TIMEZONE, BROWSER_TIMEZONE, ...COMMON_TIMEZONES].filter((zone): zone is string => Boolean(zone)))];
}

export function preferredTimeZone(user?: TimezoneUser | null): string {
  return user?.timezone || BROWSER_TIMEZONE || FALLBACK_TIMEZONE;
}

export function formatDateTime(value?: string | null, timeZone = BROWSER_TIMEZONE): string {
  if (!value) return "never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short", timeZone }).format(date);
}

export function formatTimeOnly(value?: string | null, timeZone = BROWSER_TIMEZONE): string {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", timeZone }).format(date);
}

export function localizeUtcHourLabel(label: string, timeZone = BROWSER_TIMEZONE): string {
  const match = label.match(/^(\d{2}):00-(\d{2}):00 UTC$/);
  if (!match) return label;
  const today = new Date();
  const start = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate(), Number(match[1])));
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  return `${label} (${formatTimeOnly(start.toISOString(), timeZone)}-${formatTimeOnly(end.toISOString(), timeZone)} ${timeZone})`;
}

export function formatDurationMs(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatEveTime(value?: string | null): string {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const formatted = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(date);
  return `${formatted} EVE`;
}

export function formatCountdown(value?: string | null, now = Date.now()): string {
  if (!value) return "Time not set";
  const target = new Date(value).getTime();
  if (!Number.isFinite(target)) return "Time unknown";
  const remaining = target - now;
  if (remaining <= 0) return "Now";
  const totalMinutes = Math.max(1, Math.ceil(remaining / 60000));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}
