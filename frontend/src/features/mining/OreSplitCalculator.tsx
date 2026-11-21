import { useMemo, useRef, useState } from "react";
import { ORE_SPLIT_PRESETS, oreSplitClipboard, parseOreStacks, parseSplitPercent, splitOreStacks } from "./oreSplit";
import "./oreSplit.css";

export function OreSplitCalculator() {
  const [input, setInput] = useState("");
  const [percent, setPercent] = useState("15");
  const [sliderPercent, setSliderPercent] = useState(15);
  const [message, setMessage] = useState("");
  const [copyFailed, setCopyFailed] = useState(false);
  const [fallback, setFallback] = useState("");
  const revision = useRef(0);
  const parsed = useMemo(() => parseOreStacks(input), [input]);
  const percentage = parseSplitPercent(percent);
  const valid = percentage.basisPoints !== null && parsed.issues.length === 0;
  const rows = useMemo(() => valid ? splitOreStacks(parsed.ores, percentage.basisPoints!) : [], [parsed, valid, percentage.basisPoints]);

  function changed() {
    revision.current += 1;
    setMessage(""); setFallback(""); setCopyFailed(false);
  }
  function changePercent(value: string) {
    changed(); setPercent(value);
    const next = parseSplitPercent(value);
    if (next.basisPoints !== null) setSliderPercent(next.basisPoints / 100);
  }
  async function copy(column: "cut" | "remaining") {
    if (!rows.length || !valid) return;
    const text = oreSplitClipboard(rows, column), current = revision.current;
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text);
      if (current !== revision.current) return;
      setCopyFailed(false); setFallback("");
      setMessage(column === "cut" ? "Cut amounts copied." : "Remaining amounts copied.");
    } catch {
      if (current !== revision.current) return;
      setCopyFailed(true); setFallback(text);
      setMessage("Clipboard access is unavailable. Select and copy the text below.");
    }
  }

  return <details className="ore-split-calculator">
    <summary><strong>Ore Split Calculator</strong><span>Paste ore quantities and calculate a percentage cut.</span></summary>
    <div className="ore-split-content">
      <p>Paste an EVE item list or one ore name and quantity per line. Compressed and uncompressed ores stay separate. This calculator uses only your pasted list.</p>
      <label>Ore names and quantities<textarea rows={5} value={input} onChange={event => { changed(); setInput(event.target.value); }} spellCheck={false}
        placeholder={"Compressed Brimful Coesite\t100000\nCompressed Coesite\t20000\nZeolites\t500"} aria-describedby="ore-split-input-help" /></label>
      <small id="ore-split-input-help">Tabs or spaces between the name and quantity; grouped quantities such as 100,000 are accepted. Repeated names combine before rounding.</small>
      <div className="ore-split-percent-controls">
        <label>Split percentage (%)<input type="number" min="0" max="100" step="0.01" inputMode="decimal" value={percent}
          onChange={event => changePercent(event.target.value)} aria-invalid={percentage.error !== null} aria-describedby={percentage.error ? "ore-split-percent-error" : undefined} /></label>
        <label>Adjust split percentage<input type="range" min="0" max="100" step="0.01" value={sliderPercent} onChange={event => changePercent(event.target.value)}
          aria-valuetext={`${sliderPercent}%`} /></label>
      </div>
      <div className="ore-split-presets" role="group" aria-label="Split percentage presets">{ORE_SPLIT_PRESETS.map(value =>
        <button key={value} type="button" aria-pressed={percentage.basisPoints === value * 100} onClick={() => changePercent(String(value))}>{value}%</button>)}</div>
      {percentage.error && <p id="ore-split-percent-error" className="mini-alert" role="alert">{percentage.error}</p>}
      {parsed.issues.length > 0 && <div className="mini-alert" role="alert"><strong>Fix these rows to calculate the complete split:</strong><ul>{parsed.issues.slice(0, 10).map((issue, index) =>
        <li key={index}>{issue.line === null ? "" : `Line ${issue.line}: `}{issue.message}</li>)}</ul>{parsed.issues.length > 10 && <p>And {parsed.issues.length - 10} more invalid rows.</p>}</div>}
      <p className="ore-split-rounding">Cut amounts round to the nearest whole unit; half units round up. Remaining = original quantity − cut amount.</p>
      {parsed.duplicateRows > 0 && <p>Combined {parsed.duplicateRows} repeated ore {parsed.duplicateRows === 1 ? "row" : "rows"} before rounding.</p>}
      {rows.length > 0 && <div className="ore-split-table-wrap"><table><caption>{Number(percent)}% ore split · whole units</caption><thead><tr><th scope="col">Ore</th><th scope="col">Original</th><th scope="col">Cut off ({Number(percent)}%)</th><th scope="col">Remaining</th></tr></thead><tbody>{rows.map(row =>
        <tr key={row.name}><th scope="row">{row.name}</th><td data-label="Original">{row.total.toLocaleString()}</td><td data-label={`Cut off (${Number(percent)}%)`}><strong>{row.cut.toLocaleString()}</strong></td><td data-label="Remaining">{row.remaining.toLocaleString()}</td></tr>)}</tbody></table></div>}
      {!input.trim() && <p className="muted">Paste ore quantities above to see your split.</p>}
      <div className="button-row compact ore-split-actions"><button type="button" disabled={!rows.length || !valid} onClick={() => void copy("cut")}>Copy cut amounts</button>
        <button type="button" disabled={!rows.length || !valid} onClick={() => void copy("remaining")}>Copy remaining amounts</button>
        <button type="button" disabled={!input} onClick={() => { changed(); setInput(""); }}>Clear ore list</button></div>
      {message && <p role={copyFailed ? "alert" : "status"}>{message}</p>}
      {fallback && <label>Copyable ore quantities<textarea readOnly rows={4} value={fallback} onFocus={event => event.target.select()} /></label>}
    </div>
  </details>;
}
