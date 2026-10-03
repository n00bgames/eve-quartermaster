import { useEffect, useRef, useState, type ClipboardEvent, type PointerEvent } from "react";
import type { ApiClient, HyperNetOffer } from "../../types/hypernet";

type Crop = { x: number; y: number; width: number; height: number };
const full: Crop = { x: 0, y: 0, width: 100, height: 100 };
const maxBytes = 10 * 1024 * 1024;

export function HyperNetGridReference({ api, offer, onChanged, disabled = false }: {
  api: ApiClient; offer: HyperNetOffer; onChanged: (offer: HyperNetOffer) => void; disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [picture, setPicture] = useState<{ url: string; width: number; height: number } | null>(null);
  const [crop, setCrop] = useState(full);
  const [stored, setStored] = useState<{ version: string; url: string } | null>(null);
  const [zoom, setZoom] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState("");
  const image = useRef<HTMLImageElement>(null);
  const area = useRef<HTMLDivElement>(null);
  const objectUrl = useRef<string | null>(null);
  const generation = useRef(0);
  const start = useRef<{ x: number; y: number } | null>(null);
  const version = offer.grid_reference?.version;
  const finished = offer.status === "completed" && offer.node_map?.winning_position != null;
  const locked = busy || disabled;
  const endpoint = `/hypernet/offers/${offer.id}/grid-reference`;

  useEffect(() => () => { generation.current++; if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); }, []);
  useEffect(() => { if (editing) area.current?.focus(); }, [editing]);
  useEffect(() => { if (finished) discard(); }, [finished]);
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

  function discard() {
    generation.current++; setPicture(null); setEditing(false);
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
  }
  function load(file: File) {
    if (locked || finished) return;
    discard(); setEditing(true); setError("");
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > maxBytes) {
      setError("Choose a PNG, JPEG, or WebP screenshot of at most 10 MB."); return;
    }
    const run = generation.current, url = URL.createObjectURL(file);
    objectUrl.current = url;
    const probe = new Image();
    probe.onload = () => {
      if (run !== generation.current) return;
      if (probe.naturalWidth * probe.naturalHeight > 16_000_000) { setError("Choose a screenshot of at most 16 megapixels."); return; }
      setPicture({ url, width: probe.naturalWidth, height: probe.naturalHeight }); setCrop(full);
    };
    probe.onerror = () => { if (run === generation.current) setError("Unable to read this screenshot."); };
    probe.src = url;
  }
  function paste(event: ClipboardEvent<HTMLDivElement>) {
    const file = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"))?.getAsFile();
    if (file) { event.preventDefault(); load(file); }
  }
  function point(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(100, (event.clientX - bounds.left) / bounds.width * 100)), y: Math.max(0, Math.min(100, (event.clientY - bounds.top) / bounds.height * 100)) };
  }
  function drag(event: PointerEvent<HTMLDivElement>) {
    if (!start.current || locked) return;
    const end = point(event);
    setCrop({ x: Math.min(start.current.x, end.x), y: Math.min(start.current.y, end.y), width: Math.abs(end.x - start.current.x), height: Math.abs(end.y - start.current.y) });
  }
  async function save() {
    if (!picture || !image.current || !crop.width || !crop.height) return;
    setBusy(true); setError("");
    try {
      const canvas = document.createElement("canvas");
      const x = Math.min(picture.width - 1, Math.round(picture.width * crop.x / 100));
      const y = Math.min(picture.height - 1, Math.round(picture.height * crop.y / 100));
      canvas.width = Math.min(picture.width - x, Math.max(1, Math.round(picture.width * crop.width / 100)));
      canvas.height = Math.min(picture.height - y, Math.max(1, Math.round(picture.height * crop.height / 100)));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Unable to crop this screenshot.");
      context.drawImage(image.current, x, y, canvas.width, canvas.height, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error("Unable to encode the crop.")), "image/png"));
      if (blob.size > maxBytes) throw new Error("Selected crop exceeds 10 MB. Select a smaller grid area.");
      const updated = await api<HyperNetOffer>(endpoint, { method: "PUT", headers: { "Content-Type": "image/png" }, body: blob });
      discard(); onChanged(updated);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save grid reference."); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!window.confirm("Remove the saved grid screenshot? This cannot be undone.")) return;
    setBusy(true); setError("");
    try { const updated = await api<HyperNetOffer>(endpoint, { method: "DELETE" }); discard(); onChanged(updated); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to remove grid reference."); }
    finally { setBusy(false); }
  }

  return <div className="hypernet-grid-reference" aria-label="Grid screenshot reference">
    <h4>Grid screenshot reference</h4>
    <p className="muted">Save a screenshot before the offer ends, then match its winning code to a numbered position below. The saved image is deleted when the offer is completed and a winning position is saved. Expired offers keep it until you remove it.</p>
    {finished ? <p>Offer completed and winning position recorded; no reference image is retained.</p> : <div className="button-row"><button type="button" disabled={locked} onClick={() => setEditing(true)}>{version ? "Replace grid screenshot" : "Add grid screenshot"}</button></div>}
    {loading && <p role="status">Loading grid screenshot…</p>}
    {version && stored?.version === version && <>
      <div className="button-row"><button type="button" onClick={() => setZoom(!zoom)}>{zoom ? "Fit image to width" : "View at original size"}</button><button type="button" disabled={locked} onClick={() => void remove()}>Remove grid screenshot</button></div>
      <small>{offer.grid_reference?.width} × {offer.grid_reference?.height} pixels · lossless PNG</small>
      <div className="hypernet-reference-view"><img src={stored.url} alt="Saved HyperNet node codes for matching the winning position" style={{ width: zoom ? offer.grid_reference?.width : "100%", maxWidth: zoom ? "none" : offer.grid_reference?.width }} /></div>
    </>}
    {editing && !finished && <div className="hypernet-ocr" ref={area} tabIndex={0} onPaste={paste} aria-label="Upload or paste grid screenshot">
      <label>Grid screenshot<input type="file" accept="image/png,image/jpeg,image/webp" disabled={locked} onChange={(event) => { const file = event.target.files?.[0]; if (file) load(file); event.target.value = ""; }} /></label>
      <p>Paste an image here with Ctrl+V, or choose a file. Drag over the grid to crop. Only the selected area is uploaded, at its original pixel resolution. Keep all node positions visible and in the same order.</p>
      {picture && <>
        <div className="hypernet-ocr-crop" onPointerDown={(event) => { if (locked) return; start.current = point(event); event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={drag} onPointerUp={(event) => { drag(event); start.current = null; }} onPointerCancel={() => { start.current = null; }}>
          <img ref={image} src={picture.url} alt="Select the node grid area to retain" draggable={false} />
          <div className="hypernet-ocr-selection" style={{ left: `${crop.x}%`, top: `${crop.y}%`, width: `${crop.width}%`, height: `${crop.height}%` }} />
        </div>
        <div className="form-grid">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}>Grid crop {key} (%)<input type="number" min="0" max="100" step="0.1" disabled={locked} value={Number(crop[key].toFixed(1))} onChange={(event) => setCrop((old) => { const next = { ...old, [key]: Math.max(0, Math.min(100, Number(event.target.value))) }; return { ...next, width: Math.min(next.width, 100 - next.x), height: Math.min(next.height, 100 - next.y) }; })} /></label>)}</div>
        <div className="button-row"><button type="button" disabled={locked} onClick={() => setCrop(full)}>Use full grid image</button><button type="button" disabled={locked || !crop.width || !crop.height} onClick={() => void save()}>{busy ? "Saving…" : "Save selected grid area"}</button></div>
      </>}
      <div className="button-row"><button type="button" disabled={locked} onClick={discard}>Cancel screenshot upload</button></div>
    </div>}
    {error && <div role="alert" className="mini-alert">{error}{version && !stored && <button type="button" disabled={loading} onClick={() => setRetry(retry + 1)}>Retry image load</button>}</div>}
  </div>;
}
