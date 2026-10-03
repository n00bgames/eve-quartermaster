import { ClipboardEvent, PointerEvent, useEffect, useRef, useState } from "react";
import type { Worker } from "tesseract.js";
import type { HyperNetOffer } from "../../types/hypernet";
import { mergeParticipantText, parseParticipantOcr, participantTextFromLayout, type ParticipantDraft } from "./hypernetOcr";

type Crop = { x: number; y: number; width: number; height: number };
const full: Crop = { x: 0, y: 0, width: 100, height: 100 };

function reviewRows(text: string): ParticipantDraft[] | null {
  const rows: ParticipantDraft[] = [];
  for (const line of text.split(/\r?\n/).filter((value) => value.trim())) {
    const parts = line.split("|").map((value) => value.trim());
    if (parts.length < 2 || parts.length > 3 || !parts[0] || !/^\d+$/.test(parts[1]) ||
        Number(parts[1]) < 1 || Number(parts[1]) > 512 || (parts[2] && parts[2] !== "seeded")) return null;
    rows.push({ name: parts[0], nodes: Number(parts[1]), seeded: parts[2] === "seeded" });
  }
  return rows.length && new Set(rows.map((row) => row.name.toLowerCase())).size === rows.length ? rows : null;
}

export function HyperNetParticipantInput({ offer }: { offer: HyperNetOffer }) {
  const [text, setText] = useState(() => mergeParticipantText("", (offer.participants ?? []).map((row) => ({ name: row.participant_name, nodes: row.nodes_owned, seeded: row.is_seller }))));
  const [open, setOpen] = useState(false);
  const [picture, setPicture] = useState<{ url: string; width: number; height: number } | null>(null);
  const [crop, setCrop] = useState<Crop>(full);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState("");
  const [review, setReview] = useState("");
  const worker = useRef<Worker | null>(null);
  const run = useRef(0);
  const objectUrl = useRef<string | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const image = useRef<HTMLImageElement | null>(null);
  const importArea = useRef<HTMLDivElement | null>(null);
  const rows = reviewRows(review);
  const merged = rows ? mergeParticipantText(text, rows) : "";
  const mergedRows = reviewRows(merged);
  const exceedsTotal = !!mergedRows && mergedRows.reduce((sum, row) => sum + row.nodes, 0) > offer.total_nodes;

  useEffect(() => { if (open) importArea.current?.focus(); }, [open]);

  function cancelScan() {
    run.current++; setScanning(false);
    if (worker.current) { void worker.current.terminate().catch(() => {}); worker.current = null; }
  }
  useEffect(() => () => {
    run.current++;
    if (worker.current) void worker.current.terminate().catch(() => {});
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
  }, []);

  function loadFile(file: File) {
    cancelScan(); setError(null); setRaw(""); setReview(""); setPicture(null);
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setError("Choose a PNG, JPEG, or WebP screenshot smaller than 10 MB."); return;
    }
    const current = run.current;
    const url = URL.createObjectURL(file); objectUrl.current = url;
    const probe = new Image();
    probe.onload = () => {
      if (current !== run.current) return;
      if (probe.naturalWidth * probe.naturalHeight > 16_000_000) { setError("Crop or resize the screenshot to less than 16 megapixels first."); return; }
      setPicture({ url, width: probe.naturalWidth, height: probe.naturalHeight }); setCrop(full);
    };
    probe.onerror = () => { if (current === run.current) setError("Unable to read this image. Try a PNG screenshot."); };
    probe.src = url;
  }
  function paste(event: ClipboardEvent<HTMLDivElement>) {
    const file = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"))?.getAsFile();
    if (file) { event.preventDefault(); setOpen(true); loadFile(file); }
  }
  function point(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(100, (event.clientX - bounds.left) / bounds.width * 100)), y: Math.max(0, Math.min(100, (event.clientY - bounds.top) / bounds.height * 100)) };
  }
  function drag(event: PointerEvent<HTMLDivElement>) {
    if (!start.current || scanning) return;
    const end = point(event);
    setCrop({ x: Math.min(start.current.x, end.x), y: Math.min(start.current.y, end.y), width: Math.abs(end.x - start.current.x), height: Math.abs(end.y - start.current.y) });
  }

  async function scan() {
    if (!picture || !image.current || crop.width < 1 || crop.height < 1) return;
    const current = ++run.current;
    setScanning(true); setError(null); setRaw(""); setReview(""); setProgress("Loading recognition engine…");
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      const canvas = document.createElement("canvas");
      const left = Math.round(picture.width * crop.x / 100), top = Math.round(picture.height * crop.y / 100);
      const width = Math.min(picture.width - left, Math.max(1, Math.round(picture.width * crop.width / 100)));
      const height = Math.min(picture.height - top, Math.max(1, Math.round(picture.height * crop.height / 100)));
      const scale = Math.min(2, Math.sqrt(4_000_000 / (width * height)));
      canvas.width = Math.max(1, Math.round(width * scale)); canvas.height = Math.max(1, Math.round(height * scale));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Your browser could not prepare the screenshot.");
      context.drawImage(image.current, left, top, width, height, 0, 0, canvas.width, canvas.height);
      // EVE uses light text on dark/translucent backgrounds. Invert brightness
      // before recognition so highlighted names remain visible to the engine.
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < pixels.data.length; i += 4) {
        const value = 255 - Math.max(pixels.data[i], pixels.data[i + 1], pixels.data[i + 2]);
        pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = value;
      }
      context.putImageData(pixels, 0, 0);
      const task = async () => {
        const { createWorker, PSM } = await import("tesseract.js");
        if (current !== run.current) throw new Error("Scan cancelled");
        const activeWorker = await createWorker("eng", 1, {
          workerPath: "/ocr/worker.min.js", corePath: "/ocr", langPath: "/ocr", workerBlobURL: false,
          logger: (message) => { if (current === run.current) setProgress(`${message.status}${typeof message.progress === "number" ? ` ${Math.round(message.progress * 100)}%` : ""}`); },
        });
        if (current !== run.current) { await activeWorker.terminate(); throw new Error("Scan cancelled"); }
        worker.current = activeWorker;
        await activeWorker.setParameters({ tessedit_pageseg_mode: PSM.SPARSE_TEXT });
        const { data } = await activeWorker.recognize(canvas, {}, { blocks: true });
        const lines = (data.blocks ?? []).flatMap((block) => block.paragraphs.flatMap((paragraph) => paragraph.lines));
        const paired = participantTextFromLayout(lines);
        if (current !== run.current) throw new Error("Scan cancelled");
        // A tight text-only crop can favor the original colors/block layout.
        // Keep the spatial result on ties; never combine competing spellings.
        context.drawImage(image.current!, left, top, width, height, 0, 0, canvas.width, canvas.height);
        await activeWorker.setParameters({ tessedit_pageseg_mode: PSM.SINGLE_BLOCK });
        const original = (await activeWorker.recognize(canvas)).data.text;
        return parseParticipantOcr(original, offer.seller.name).length > parseParticipantOcr(paired, offer.seller.name).length
          ? { raw: original, paired: original } : { raw: data.text, paired };
      };
      const result = await Promise.race([task(), new Promise<never>((_, reject) => { timeout = setTimeout(() => reject(new Error("Recognition timed out. Select a smaller area and try again.")), 90_000); })]);
      if (current !== run.current) return;
      setRaw(result.raw);
      const extracted = parseParticipantOcr(result.paired, offer.seller.name);
      setReview(mergeParticipantText("", extracted));
      if (!extracted.length) setError("No name/node pairs found. Select only the participant names and their HyperNode counts, then try again.");
    } catch (err) {
      if (current === run.current) setError(err instanceof Error ? err.message : "Unable to scan the screenshot.");
    } finally {
      clearTimeout(timeout);
      if (current === run.current) { cancelScan(); setProgress(""); }
    }
  }

  return <div className="hypernet-participant-input" onPaste={paste}>
    <label>Participants (optional)<textarea name="participants" rows={4} value={text} onChange={(event) => setText(event.target.value)} placeholder={`Character Name | 1\n${offer.seller.name} | ${offer.seller_owned_nodes} | seeded`} /><small>One participant per line: name | cumulative nodes | optional “seeded”.</small></label>
    <button type="button" onClick={() => { if (open) cancelScan(); setOpen(!open); }}> {open ? "Close screenshot import" : "Import participants from screenshot"}</button>
    {open && <div ref={importArea} className="hypernet-ocr" tabIndex={0} aria-label="Screenshot import; paste an image here">
      <p>Press Ctrl+V (⌘V on Mac) to paste a screenshot, or choose an image file below. You can also paste an image directly into the Participants field to open this importer. Recognition runs in your browser; the image is not uploaded. Drag over the participant list, including names and counts. Portraits and the heading are OK; exclude other panels.</p>
      <label>Screenshot<input type="file" accept="image/png,image/jpeg,image/webp" disabled={scanning} onChange={(event) => { const file = event.target.files?.[0]; if (file) loadFile(file); event.target.value = ""; }} /></label>
      {picture && <>
        <div className="hypernet-ocr-crop" onPointerDown={(event) => { if (scanning) return; start.current = point(event); event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={drag} onPointerUp={(event) => { drag(event); start.current = null; }} onPointerCancel={() => { start.current = null; }}>
          <img ref={image} src={picture.url} alt="Screenshot to scan" draggable={false} />
          <div className="hypernet-ocr-selection" style={{ left: `${crop.x}%`, top: `${crop.y}%`, width: `${crop.width}%`, height: `${crop.height}%` }} />
        </div>
        <div className="form-grid four">{(["x", "y", "width", "height"] as const).map((key) => <label key={key}>Crop {key} (%)<input type="number" min="0" max="100" step="0.1" disabled={scanning} value={Number(crop[key].toFixed(1))} onChange={(event) => setCrop((old) => { const next = { ...old, [key]: Math.max(0, Math.min(100, Number(event.target.value))) }; return { ...next, width: Math.min(next.width, 100 - next.x), height: Math.min(next.height, 100 - next.y) }; })} /></label>)}</div>
        <div className="button-row"><button type="button" disabled={scanning} onClick={() => setCrop(full)}>Use full image</button><button type="button" disabled={scanning || crop.width < 1 || crop.height < 1} onClick={() => void scan()}>Scan selected area</button>{scanning && <button type="button" onClick={cancelScan}>Cancel scan</button>}</div>
      </>}
      {scanning && <p role="status">{progress}</p>}
      {error && <div className="mini-alert" role="alert">{error}</div>}
      {raw && <>
        <label>Review extracted participants<textarea rows={6} value={review} onChange={(event) => setReview(event.target.value)} /><small>Check every name and count. Add “| seeded” for seller-owned nodes. Only visible rows can be extracted; import additional crops for a scrolled list.</small></label>
        <p>{rows?.length ?? 0} participants · {rows?.reduce((sum, row) => sum + row.nodes, 0) ?? 0} nodes in this selection. Matching names replace counts in the field; they are not added together. Sold/seeded totals remain unchanged.</p>
        {!rows && <p className="mini-alert">Enter unique names and whole node counts using name | nodes | optional seeded.</p>}
        {rows && !mergedRows && <p className="mini-alert">The existing participant field contains invalid or duplicate lines. Correct those before merging this selection.</p>}
        {exceedsTotal && <p className="mini-alert">The combined participant list exceeds this offer’s total nodes. Correct it before applying.</p>}
        <button type="button" disabled={!rows || !mergedRows || exceedsTotal || scanning} onClick={() => { setText(merged); setOpen(false); }}>Use reviewed participants</button>
        <details><summary>Raw recognized text</summary><pre>{raw}</pre></details>
      </>}
    </div>}
  </div>;
}
