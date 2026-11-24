import { useEffect, useRef, useState, type ClipboardEvent, type PointerEvent } from "react";
import type { Worker } from "tesseract.js";
import { walletTextFromWords } from "./plexWalletParser";

type Crop = { x: number; y: number; width: number; height: number };
const full: Crop = { x: 0, y: 0, width: 100, height: 100 };

export function PlexWalletScreenshot({ onText, onReset, disabled }: { onText: (text: string) => void; onReset: () => void; disabled: boolean }) {
  const [picture, setPicture] = useState<{ url: string; width: number; height: number } | null>(null);
  const [crop, setCrop] = useState<Crop>(full);
  const [scanning, setScanning] = useState(false), [progress, setProgress] = useState(""), [error, setError] = useState("");
  const worker = useRef<Worker | null>(null), run = useRef(0), url = useRef<string | null>(null);
  const image = useRef<HTMLImageElement | null>(null), start = useRef<{ x: number; y: number } | null>(null);
  function cancel() { run.current++; setScanning(false); setProgress(""); if (worker.current) { void worker.current.terminate().catch(() => {}); worker.current = null; } }
  useEffect(() => () => { run.current++; if (worker.current) void worker.current.terminate().catch(() => {}); if (url.current) URL.revokeObjectURL(url.current); }, []);
  function load(file: File) {
    if (disabled) return;
    cancel(); onReset(); setError(""); setPicture(null);
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = null;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) { setError("Choose a PNG, JPEG or WebP under 10 MB."); return; }
    const current = run.current, nextUrl = URL.createObjectURL(file); url.current = nextUrl;
    const probe = new Image();
    probe.onload = () => {
      if (current !== run.current) return;
      if (probe.naturalWidth * probe.naturalHeight > 16_000_000) { setError("Resize to less than 16 megapixels first."); return; }
      setPicture({ url: nextUrl, width: probe.naturalWidth, height: probe.naturalHeight }); setCrop(full);
    };
    probe.onerror = () => { if (current === run.current) setError("Unable to read this image."); };
    probe.src = nextUrl;
  }
  function paste(event: ClipboardEvent<HTMLDivElement>) {
    const file = Array.from(event.clipboardData.items).find(item => item.type.startsWith("image/"))?.getAsFile();
    if (file && !disabled) { event.preventDefault(); load(file); }
  }
  function point(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(100, (event.clientX - bounds.left) / bounds.width * 100)), y: Math.max(0, Math.min(100, (event.clientY - bounds.top) / bounds.height * 100)) };
  }
  function drag(event: PointerEvent<HTMLDivElement>) {
    if (!start.current || scanning || disabled) return;
    onReset();
    const end = point(event);
    setCrop({ x: Math.min(start.current.x, end.x), y: Math.min(start.current.y, end.y), width: Math.abs(end.x - start.current.x), height: Math.abs(end.y - start.current.y) });
  }
  async function scan() {
    if (!picture || !image.current || crop.width < 1 || crop.height < 1 || disabled) return;
    const current = ++run.current;
    onReset();
    setScanning(true); setError(""); setProgress("Loading local OCR…");
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      const canvas = document.createElement("canvas"), left = Math.round(picture.width * crop.x / 100), top = Math.round(picture.height * crop.y / 100);
      const width = Math.min(picture.width - left, Math.max(1, Math.round(picture.width * crop.width / 100))), height = Math.min(picture.height - top, Math.max(1, Math.round(picture.height * crop.height / 100)));
      const scale = Math.min(2, Math.sqrt(4_000_000 / (width * height)));
      canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Could not prepare screenshot.");
      context.drawImage(image.current, left, top, width, height, 0, 0, canvas.width, canvas.height);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
      // Invert dark EVE tables, retaining legible red/green text as grey.
      const brightness = pixels.data.reduce((sum, n, index) => sum + (index % 4 === 0 ? n : 0), 0) / (pixels.data.length / 4);
      if (brightness < 140) {
        for (let i = 0; i < pixels.data.length; i += 4) pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = 255 - Math.max(pixels.data[i], pixels.data[i + 1], pixels.data[i + 2]);
        context.putImageData(pixels, 0, 0);
      }
      const task = async () => {
        const { createWorker, PSM } = await import("tesseract.js");
        if (current !== run.current) return "";
        const active = await createWorker("eng", 1, { workerPath: "/ocr/worker.min.js", corePath: "/ocr", langPath: "/ocr", workerBlobURL: false,
          logger: message => { if (current === run.current) setProgress(`${message.status} ${Math.round((message.progress ?? 0) * 100)}%`); } });
        if (current !== run.current) { await active.terminate(); return ""; }
        worker.current = active;
        await active.setParameters({ tessedit_pageseg_mode: PSM.SPARSE_TEXT, preserve_interword_spaces: "1" });
        const { data } = await active.recognize(canvas, {}, { blocks: true });
        const words = (data.blocks ?? []).flatMap(b => b.paragraphs.flatMap(p => p.lines.flatMap(l => l.words)));
        return words.length ? walletTextFromWords(words) : data.text;
      };
      const text = await Promise.race([task(), new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new Error("OCR timed out. Try a smaller crop.")), 90000); })]);
      if (current === run.current) onText(text);
    } catch (err) { if (current === run.current) setError(err instanceof Error ? err.message : "Screenshot recognition failed."); }
    finally { clearTimeout(timeout); if (current === run.current) cancel(); }
  }
  return <div onPaste={paste} tabIndex={0} aria-label="Paste wallet screenshot here" className="plex-wallet-image">
    <p>Paste a screenshot here with Ctrl+V, or choose a file. Drag a crop around the complete wallet transaction rows, including date, PLEX, quantity and unit price. Images stay in your browser.</p>
    <label>Wallet screenshot<input disabled={disabled || scanning} type="file" accept="image/png,image/jpeg,image/webp" onChange={e => { const file = e.target.files?.[0]; if (file) load(file); e.target.value = ""; }} /></label>
    {picture && <><div className="plex-wallet-crop" onPointerDown={e => { if (disabled || scanning) return; start.current = point(e); e.currentTarget.setPointerCapture(e.pointerId); }} onPointerMove={drag} onPointerUp={e => { drag(e); start.current = null; }} onPointerCancel={() => { start.current = null; }}>
      <img ref={image} src={picture.url} alt="Wallet screenshot to scan" draggable={false} /><div style={{ left: `${crop.x}%`, top: `${crop.y}%`, width: `${crop.width}%`, height: `${crop.height}%` }} />
    </div><div className="plex-fields">{(["x", "y", "width", "height"] as const).map(key => <label key={key}>Crop {key} %<input type="number" min="0" max="100" step=".1" disabled={disabled || scanning} value={Number(crop[key].toFixed(1))} onChange={e => { onReset(); setCrop(old => { const next = { ...old, [key]: Math.max(0, Math.min(100, Number(e.target.value))) }; return { ...next, width: Math.min(next.width, 100 - next.x), height: Math.min(next.height, 100 - next.y) }; }); }} /></label>)}</div>
    <div className="plex-actions"><button disabled={disabled || scanning} onClick={() => { onReset(); setCrop(full); }}>Full image</button><button disabled={disabled || scanning || crop.width < 1 || crop.height < 1} onClick={() => void scan()}>Scan wallet screenshot</button>{scanning && <button onClick={cancel}>Cancel scan</button>}</div></>}
    {scanning && <p role="status">{progress}</p>}{error && <p role="alert" className="plex-warning">{error}</p>}
  </div>;
}
