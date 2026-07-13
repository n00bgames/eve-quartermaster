const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

function formatApiError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const maybeMessage = (detail as { message?: unknown }).message;
    if (typeof maybeMessage === "string") return maybeMessage;
    const nestedDetail = (detail as { detail?: unknown }).detail;
    if (typeof nestedDetail === "string") return nestedDetail;
    return JSON.stringify(detail);
  }
  return "Request failed";
}

function requestTimeoutMs(path: string): number {
  if (path.startsWith("/esi/sync/")) return 300000;
  if (path.startsWith("/sde/import-status")) return 20000;
  if (path.startsWith("/sde/import")) return 1800000;
  if (path.startsWith("/navigation/gatecheck")) return 180000;
  if (path.startsWith("/navigation/industrial-threat")) return 180000;
  if (path.startsWith("/navigation/pvp-intel")) return 180000;
  if (path.startsWith("/navigation/local-threat")) return 600000;
  if (path.startsWith("/navigation/jump-freighter")) return 180000;
  if (path.startsWith("/market/appraise")) return 180000;
  if (path.startsWith("/contracts/sync/")) return 180000;
  if (path.startsWith("/mail/")) return 60000;
  return 20000;
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("eq_access_token");
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), requestTimeoutMs(path));
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options?.signal ?? controller.signal,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options?.headers },
    });
    const contentType = response.headers.get("content-type") ?? "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      if (typeof payload === "string") {
        const detail = payload.trim() || response.statusText || "Request failed";
        throw new Error(`${response.status} ${detail}`);
      }
      throw new Error(formatApiError(payload.detail ?? payload.message ?? "Request failed"));
    }
    if (typeof payload === "string") throw new Error(`Unexpected non-JSON response from ${path}: ${payload.slice(0, 120)}`);
    return payload;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw new Error(`Request timed out while calling ${path}.`);
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}
