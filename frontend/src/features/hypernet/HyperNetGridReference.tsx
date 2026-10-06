import { useEffect, useState } from "react";
import type { ApiClient, HyperNetOffer } from "../../types/hypernet";
import { HyperNetGridScreenshotEditor } from "./HyperNetGridScreenshotEditor";

export function HyperNetGridReference({ api, offer, onChanged, disabled = false }: {
  api: ApiClient; offer: HyperNetOffer; onChanged: (offer: HyperNetOffer) => void; disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [stored, setStored] = useState<{ version: string; url: string } | null>(null);
  const [zoom, setZoom] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const version = offer.grid_reference?.version;
  const finished = offer.status === "completed" && offer.node_map?.winning_position != null;
  const locked = busy || disabled;
  const endpoint = `/hypernet/offers/${offer.id}/grid-reference`;

  useEffect(() => { setEditing(false); }, [offer.id, finished]);
  useEffect(() => {
    let cancelled = false;
    setStored(null); setError("");
    if (!version) { setLoading(false); return; }
    setLoading(true);
    api<{ data_url: string }>(endpoint).then((result) => {
      if (!cancelled) setStored({ version, url: result.data_url });
    }).catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load grid reference."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [api, endpoint, version, retry]);

  async function save(blob: Blob) {
    if (locked || finished) return;
    setBusy(true); setError("");
    try {
      const updated = await api<HyperNetOffer>(endpoint, { method: "PUT", headers: { "Content-Type": "image/png" }, body: blob });
      setEditing(false); onChanged(updated);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save grid reference."); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm("Remove the saved grid screenshot? This cannot be undone.")) return;
    setBusy(true); setError("");
    try { const updated = await api<HyperNetOffer>(endpoint, { method: "DELETE" }); setEditing(false); onChanged(updated); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to remove grid reference."); }
    finally { setBusy(false); }
  }

  return <div className="hypernet-grid-reference" aria-label="Grid screenshot reference">
    <h4>Grid screenshot reference</h4>
    <p className="muted">Save one screenshot or combine overlapping captures before the offer ends, then match its winning code to a numbered position below. The saved image is deleted when the offer is completed and a winning position is saved. Expired offers keep it until you remove it.</p>
    {finished ? <p>Offer completed and winning position recorded; no reference image is retained.</p> : <div className="button-row"><button type="button" disabled={locked} onClick={() => setEditing(true)}>{version ? "Replace grid screenshot" : "Add grid screenshot"}</button></div>}
    {loading && <p role="status">Loading grid screenshot…</p>}
    {version && stored?.version === version && <>
      <div className="button-row"><button type="button" onClick={() => setZoom(!zoom)}>{zoom ? "Fit image to width" : "View at original size"}</button><button type="button" disabled={locked} onClick={() => void remove()}>Remove grid screenshot</button></div>
      <small>{offer.grid_reference?.width} × {offer.grid_reference?.height} pixels · lossless PNG</small>
      <div className="hypernet-reference-view"><img src={stored.url} alt="Saved HyperNet node codes for matching the winning position" style={{ width: zoom ? offer.grid_reference?.width : "100%", maxWidth: zoom ? "none" : offer.grid_reference?.width }} /></div>
    </>}
    {editing && !finished && <HyperNetGridScreenshotEditor key={offer.id} disabled={locked} onSave={save} onCancel={() => setEditing(false)} />}
    {error && <div role="alert" className="mini-alert">{error}{version && !stored && <button type="button" disabled={loading} onClick={() => setRetry(retry + 1)}>Retry image load</button>}</div>}
  </div>;
}
