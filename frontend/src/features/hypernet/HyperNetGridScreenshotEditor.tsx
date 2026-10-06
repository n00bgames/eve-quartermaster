import { useEffect, useRef, useState, type ClipboardEvent, type PointerEvent } from "react";
import { detectGridOverlap, fullGridCrop, gridMaxBytes, gridMaxPixels, pixelCrop, pngBlob, rowSignature, stitchLayout, type GridCrop } from "./gridStitch";

type Shot = { id: number; name: string; url: string; image: HTMLImageElement; crop: GridCrop; overlap: number | null; match: "auto" | "manual" | null };
type Preview = { url: string; blob: Blob; width: number; height: number; seams: number[] };

export function HyperNetGridScreenshotEditor({ disabled, onSave, onCancel }: {
  disabled: boolean; onSave: (blob: Blob) => Promise<void>; onCancel: () => void;
}) {
  const [shots, setShots] = useState<Shot[]>([]);
  const [active, setActive] = useState(0);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(false);
  const area = useRef<HTMLDivElement>(null);
  const urls = useRef(new Set<string>());
  const generation = useRef(0);
  const sequence = useRef(0);
  const start = useRef<{ x: number; y: number } | null>(null);
  const shot = shots[active];
  const locked = disabled || working;
  useEffect(() => {
    area.current?.focus();
    return () => { generation.current++; urls.current.forEach((url) => URL.revokeObjectURL(url)); urls.current.clear(); };
  }, []);
  function forget(url: string) { URL.revokeObjectURL(url); urls.current.delete(url); }
  function invalidate() { if (preview) forget(preview.url); setPreview(null); setError(""); }
  function changeCrop(crop: GridCrop, all = false) {
    invalidate();
    setShots((old) => old.map((s, i) => ({ ...s, crop: all || i === active ? crop : s.crop, overlap: null, match: null })));
  }
  async function load(files: File[]) {
    if (locked || !files.length) return;
    invalidate(); setWorking(true);
    const run = generation.current, added: Shot[] = [], failures: string[] = [];
    let pixels = shots.reduce((n, s) => n + s.image.naturalWidth * s.image.naturalHeight, 0);
    try {
      for (const file of files) {
        if (run !== generation.current) return;
        if (shots.length + added.length >= 64) { failures.push("Use at most 64 captures per grid."); break; }
        if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > gridMaxBytes) {
          failures.push(`${file.name}: choose a PNG, JPEG, or WebP of at most 10 MB.`); continue;
        }
        const url = URL.createObjectURL(file); urls.current.add(url);
        try {
          const image = new Image();
          await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error("Unable to read this screenshot.")); image.src = url; });
          if (run !== generation.current) { forget(url); return; }
          const count = image.naturalWidth * image.naturalHeight;
          if (image.naturalWidth > 32767 || image.naturalHeight > 32767 || count > 16_000_000 || pixels + count > gridMaxPixels) throw new Error("Each capture must be at most 16 megapixels and 32,767 pixels on one side, with at most 64 megapixels across all source captures. Crop screenshots before adding more.");
          pixels += count;
          added.push({ id: ++sequence.current, name: file.name || "Pasted screenshot", url, image, crop: { ...fullGridCrop }, overlap: null, match: null });
        } catch (err) { forget(url); failures.push(`${file.name}: ${err instanceof Error ? err.message : "Unable to read screenshot."}`); }
      }
      if (run !== generation.current) return;
      setShots((old) => [...old, ...added]);
      if (added.length) setActive(shots.length);
      setError(failures.join(" "));
    } finally { if (run === generation.current) setWorking(false); }
  }
  function paste(event: ClipboardEvent<HTMLDivElement>) {
    const files = Array.from(event.clipboardData.items).filter((item) => item.type.startsWith("image/")).map((item) => item.getAsFile()).filter((f): f is File => f !== null);
    if (files.length) { event.preventDefault(); void load(files); }
  }
  function reorder(index: number, direction: number) {
    invalidate();
    const next = [...shots]; [next[index], next[index + direction]] = [next[index + direction], next[index]];
    setShots(next.map((s) => ({ ...s, overlap: null, match: null }))); setActive(index + direction);
  }
  function remove(index: number) {
    invalidate(); forget(shots[index].url);
    setShots(shots.filter((_, i) => i !== index).map((s) => ({ ...s, overlap: null, match: null })));
    setActive(Math.max(0, Math.min(active, shots.length - 2)));
  }
  function point(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(100, (event.clientX - bounds.left) / bounds.width * 100)), y: Math.max(0, Math.min(100, (event.clientY - bounds.top) / bounds.height * 100)) };
  }
  function drag(event: PointerEvent<HTMLDivElement>) {
    if (!start.current || locked) return;
    const end = point(event);
    changeCrop({ x: Math.min(start.current.x, end.x), y: Math.min(start.current.y, end.y), width: Math.abs(end.x - start.current.x), height: Math.abs(end.y - start.current.y) });
  }
  function croppedCanvas(s: Shot) {
    const crop = pixelCrop(s.image.naturalWidth, s.image.naturalHeight, s.crop);
    const canvas = document.createElement("canvas"); canvas.width = crop.width; canvas.height = crop.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Unable to crop this screenshot.");
    context.drawImage(s.image, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height);
    return { canvas, context };
  }
  async function align() {
    setWorking(true); invalidate(); const run = generation.current;
    try {
      const aligned = [...shots]; let previous = null;
      for (let i = 0; i < shots.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 0));
        if (run !== generation.current) return;
        const { canvas, context } = croppedCanvas(shots[i]);
        const signature = rowSignature(context.getImageData(0, 0, canvas.width, canvas.height));
        canvas.width = canvas.height = 0;
        if (previous && shots[i].match !== "manual") {
          const overlap = detectGridOverlap(previous, signature);
          aligned[i] = { ...shots[i], overlap, match: overlap == null ? null : "auto" };
        }
        previous = signature;
      }
      setShots(aligned);
      if (aligned.slice(1).some((s) => s.overlap == null)) setError("Some overlaps could not be matched confidently. Check the capture order and crops, then enter the repeated height in pixels for each unresolved screenshot.");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to align screenshots."); }
    finally { if (run === generation.current) setWorking(false); }
  }
  async function compose() {
    setWorking(true); invalidate(); const run = generation.current;
    let canvas: HTMLCanvasElement | null = null;
    try {
      const crops = shots.map((s) => pixelCrop(s.image.naturalWidth, s.image.naturalHeight, s.crop));
      const layout = stitchLayout(crops.map((c, i) => ({ ...c, overlap: shots[i].overlap })));
      canvas = document.createElement("canvas"); canvas.width = layout.width; canvas.height = layout.height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Unable to combine the grid. Try smaller crops.");
      shots.forEach((s, i) => {
        const c = crops[i], p = layout.placements[i];
        if (p.height) context.drawImage(s.image, c.x, c.y + p.sourceY, c.width, p.height, 0, p.y, c.width, p.height);
      });
      const blob = await pngBlob(canvas);
      if (run !== generation.current) return;
      const url = URL.createObjectURL(blob); urls.current.add(url);
      setPreview({ url, blob, width: layout.width, height: layout.height, seams: layout.placements.slice(1).filter((p) => p.height).map((p) => p.y) });
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to preview the grid."); }
    finally { if (canvas) canvas.width = canvas.height = 0; if (run === generation.current) setWorking(false); }
  }

  return <div className="hypernet-ocr" ref={area} tabIndex={0} onPaste={paste} aria-label="Upload or paste grid screenshots">
    <label>Grid screenshots<input type="file" multiple accept="image/png,image/jpeg,image/webp" disabled={locked} onChange={(event) => { void load(Array.from(event.target.files ?? [])); event.target.value = ""; }} /></label>
    <p>Choose multiple files or paste captures one at a time with Ctrl+V. Arrange them from top to bottom and crop each to the grid. Keep the same window size and columns, turn Hide unavailable off, and overlap one or two complete rows between captures. All crops and stitching happen in your browser.</p>
    {shots.length > 0 && <>
      <ol className="hypernet-stitch-sources">{shots.map((s, i) => <li key={s.id}>
        <button type="button" disabled={locked} aria-pressed={i === active} onClick={() => setActive(i)}><img src={s.url} alt="" />{i + 1}. {s.name}</button>
        <div className="button-row"><button type="button" disabled={locked || i === 0} aria-label={`Move screenshot ${i + 1} up`} onClick={() => reorder(i, -1)}>↑</button><button type="button" disabled={locked || i === shots.length - 1} aria-label={`Move screenshot ${i + 1} down`} onClick={() => reorder(i, 1)}>↓</button><button type="button" disabled={locked} aria-label={`Remove screenshot ${i + 1}`} onClick={() => remove(i)}>Remove</button></div>
        {i > 0 && <label>Overlap with previous crop (pixels)<input type="number" min="0" step="1" disabled={locked} value={s.overlap ?? ""} aria-label={`Screenshot ${i + 1} overlap pixels`} onChange={(event) => { invalidate(); const value = event.target.value === "" ? null : Number(event.target.value); setShots((old) => old.map((item, j) => j === i ? { ...item, overlap: value, match: value == null ? null : "manual" } : item)); }} /><small>{s.match === "auto" ? "Automatically aligned — verify the seam" : s.match === "manual" ? "Manual alignment" : "Needs alignment"}</small></label>}
      </li>)}</ol>
      {shot && <>
        <h5>Crop screenshot {active + 1}</h5>
        <small>{shot.image.naturalWidth} × {shot.image.naturalHeight} source pixels. Remove headings and toolbars; keep the same grid width in every crop.</small>
        <div className="hypernet-ocr-crop" onPointerDown={(event) => { if (locked) return; start.current = point(event); event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={drag} onPointerUp={(event) => { drag(event); start.current = null; }} onPointerCancel={() => { start.current = null; }}>
          <img src={shot.url} alt={`Select the grid area in screenshot ${active + 1}`} draggable={false} />
          <div className="hypernet-ocr-selection" style={{ left: `${shot.crop.x}%`, top: `${shot.crop.y}%`, width: `${shot.crop.width}%`, height: `${shot.crop.height}%` }} />
        </div>
        <div className="form-grid">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}>Grid crop {key} (%)<input type="number" min="0" max="100" step="0.1" disabled={locked} value={Number(shot.crop[key].toFixed(1))} onChange={(event) => { const next = { ...shot.crop, [key]: Math.max(0, Math.min(100, Number(event.target.value))) }; changeCrop({ ...next, width: Math.min(next.width, 100 - next.x), height: Math.min(next.height, 100 - next.y) }); }} /></label>)}</div>
        <div className="button-row"><button type="button" disabled={locked} onClick={() => changeCrop({ ...fullGridCrop })}>Use full grid image</button>{shots.length > 1 && <button type="button" disabled={locked} onClick={() => changeCrop({ ...shot.crop }, true)}>Apply this crop to all captures</button>}</div>
      </>}
      <div className="button-row">{shots.length > 1 && <button type="button" disabled={locked} onClick={() => void align()}>Detect overlaps</button>}<button type="button" disabled={locked} onClick={() => void compose()}>{shots.length > 1 ? "Preview combined grid" : "Preview selected grid area"}</button></div>
    </>}
    {working && <p role="status">Preparing grid screenshots…</p>}
    {preview && <>
      <h5>Grid preview</h5><small>{preview.width} × {preview.height} pixels · lossless PNG · {(preview.blob.size / 1024 / 1024).toFixed(2)} MB</small>
      <p>Check every seam for repeated or missing rows and confirm the codes stay in order. Dashed seam guides are only in this preview.</p>
      <div className="button-row"><button type="button" onClick={() => setZoom(!zoom)}>{zoom ? "Fit preview to width" : "Preview at original size"}</button></div>
      <div className="hypernet-reference-view"><div className="hypernet-stitch-preview" style={{ width: zoom ? preview.width : "100%", maxWidth: zoom ? "none" : preview.width }}>
        <img src={preview.url} alt="Combined grid preview" />{preview.seams.map((y, i) => <span key={i} className="hypernet-stitch-seam" style={{ top: `${y / preview.height * 100}%` }} title={`Seam ${i + 1} at pixel ${y}`} />)}
      </div></div>
      <div className="button-row"><button type="button" disabled={locked} onClick={() => void onSave(preview.blob)}>{disabled ? "Saving…" : shots.length > 1 ? "Save combined grid" : "Save selected grid area"}</button></div>
    </>}
    {error && <div role="alert" className="mini-alert">{error}</div>}
    <div className="button-row"><button type="button" disabled={disabled} onClick={onCancel}>Cancel screenshot upload</button></div>
  </div>;
}
