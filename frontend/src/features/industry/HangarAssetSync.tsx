import { useEffect, useState } from "react";
import type { EqmCorporation } from "../../types/corporations";
import type { PiHangar } from "./ProductionCalculator";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function HangarAssetSync({ hangar, api, onSynced }: {
  hangar?: PiHangar; api: ApiClient; onSynced: () => Promise<void>;
}) {
  const [source, setSource] = useState<EqmCorporation | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const corporationId = hangar?.corporation_record_id;

  useEffect(() => {
    let active = true;
    setSource(null); setError(null); setMessage(null);
    setLoading(corporationId != null);
    if (corporationId != null) {
      void api<EqmCorporation[]>("/corporations?include_hidden=true")
        .then(rows => { if (active) setSource(rows.find(row => row.id === corporationId) ?? null); })
        .catch(() => { if (active) setError("Corporation sync access could not be loaded. Check your Corporations permission."); })
        .finally(() => { if (active) setLoading(false); });
    }
    return () => { active = false; };
  }, [corporationId, api]);

  const corporation = source?.id === corporationId ? source : null;
  const token = corporation?.eligible_tokens.find(row => row.can_sync && row.has_corporation_asset_scope);

  async function sync() {
    if (!corporation || !token || busy) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      const result = await api<{ corporation_name: string; asset_rows: number; warnings?: string[] }>(
        `/esi/sync/corporation-assets/${token.token_id}`, { method: "POST", body: "{}" },
      );
      setMessage(`Synced ${result.asset_rows.toLocaleString()} asset rows for ${result.corporation_name}. ESI may still return cached stock. Use the import buttons again to update calculator quantities.${result.warnings?.length ? ` ${result.warnings.join(" · ")}` : ""}`);
      try { await onSynced(); }
      catch { setError("Corporation assets synced, but the page could not reload. Refresh the page to read the updated stock."); }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Corporation asset sync failed");
    } finally { setBusy(false); }
  }

  if (!hangar) return null;
  return <div className="pi-hangar-sync">
    <div className="button-row compact"><button type="button" disabled={loading || busy || !token} onClick={() => void sync()}
      title="Refreshes assets across the selected corporation, including this location and nested containers">
      {busy ? "Syncing corporation assets…" : "Sync this corporation’s assets"}
    </button></div>
    <small>Refreshes the whole corporation; ESI does not provide a location-only asset sync.</small>
    {!loading && !busy && !token && !error && <small>{corporationId == null ? "Update the backend to enable sync from this source." : "No authorized corporation asset token is available for this source. Check Corporations for access and ESI scopes."}</small>}
    {message && <p role="status">{message}</p>}
    {error && <p className="mini-alert" role="alert">{error}</p>}
  </div>;
}
