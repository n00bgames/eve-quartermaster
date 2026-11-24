import { useState } from "react";
import { PlexWalletScreenshot } from "./PlexWalletScreenshot";
import { draftError, draftKey, parseWalletText, tradeKey, utcDate, type WalletDraft, type WalletTrade } from "./plexWalletParser";

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
export function PlexWalletImport<T>({ api, existing, onSaved, onCancel }: { api: Api; existing: WalletTrade[]; onSaved: (ledger: T, count: number) => void; onCancel: () => void }) {
  const [text, setText] = useState(""), [rows, setRows] = useState<WalletDraft[]>([]), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [confirmed, setConfirmed] = useState(false);
  const existingKeys = new Set(existing.map(tradeKey)), seen = new Set<string>();
  const duplicates = rows.map(row => { const key = draftKey(row), duplicate = existingKeys.has(key) || seen.has(key); seen.add(key); return duplicate; });
  const selected = rows.filter(row => row.selected), invalid = selected.some(row => !!draftError(row));
  const blocked = rows.some((row, i) => row.selected && duplicates[i] && !row.allowDuplicate);
  function resetReview() { setRows([]); setText(""); setConfirmed(false); setError(""); }
  function replaceText(value: string) {
    setText(value); setConfirmed(false); setError("");
    const next = parseWalletText(value), keys = new Set(existingKeys);
    for (const row of next) { const key = draftKey(row); if (row.kind && keys.has(key)) row.selected = false; keys.add(key); }
    setRows(next);
    if (!next.length) setError("No dated PLEX rows found. Crop the transaction table more tightly, or paste/correct the recognized text below.");
  }
  function update(index: number, patch: Partial<WalletDraft>) { setRows(old => old.map((row, i) => i === index ? { ...row, ...patch } : row)); setConfirmed(false); }
  async function save() {
    if (!confirmed || !selected.length || invalid || blocked || busy) return;
    setBusy(true); setError("");
    try {
      const result = await api<{ ledger: T; imported: number }>("/plex/transactions/import", { method: "POST", body: JSON.stringify({ transactions: selected.map(row => ({
        occurred_at: utcDate(row.date), kind: row.kind, quantity: Number(row.quantity), unit_price: row.price, fees: row.fees, note: row.note, allow_duplicate: row.allowDuplicate,
      })) }) });
      onSaved(result.ledger, result.imported);
    } catch (err) { setError(err instanceof Error ? err.message : "Import failed. Review the ledger before retrying."); setConfirmed(false); }
    finally { setBusy(false); }
  }
  return <section className="plex-panel plex-wallet-import" aria-label="Import PLEX wallet trades"><h3>Import wallet screenshot</h3>
    <p>Import completed market trades for PLEX. English wallet transaction tables are supported. Only visible rows are scanned; repeat for further screenshots.</p>
    <PlexWalletScreenshot disabled={busy} onText={replaceText} onReset={resetReview} />
    <details><summary>Recognized text / paste wallet rows</summary><label>Wallet text<textarea aria-label="Wallet text" disabled={busy} rows={6} maxLength={50000} value={text} onChange={e => { setText(e.target.value); setRows([]); setConfirmed(false); }} placeholder={'2026.11.20 12:30 500 PLEX 4,000,000.00 ISK\n2026.11.21 13:00 100 PLEX 4,200,000.00 ISK'} /></label><button disabled={busy || !text.trim()} onClick={() => replaceText(text)}>Rebuild review from text</button><p className="plex-muted">Rebuilding replaces the current review. Rows without both a date and PLEX are ignored. Unknown or ambiguous cells need correction. Each batch is limited to 200 rows.</p></details>
    {error && <p role="alert" className="plex-warning">{error}</p>}
    {!!rows.length && <><p><strong>{rows.length} PLEX rows detected · {selected.length} selected</strong>. Compare every row with the screenshot. Colour alone is not used to guess purchase or sale.</p>
      <div className="plex-actions"><label>Set direction for selected rows<select aria-label="Set selected trade directions" disabled={busy} value="" onChange={e => { const kind = e.target.value as "buy" | "sell"; if (kind) { setRows(old => old.map(row => row.selected ? { ...row, kind } : row)); setConfirmed(false); } }}><option value="">Choose…</option><option value="buy">Purchase</option><option value="sell">Sale</option></select></label><button disabled={busy} onClick={() => { setRows(old => old.map(row => ({ ...row, selected: false }))); setConfirmed(false); }}>Deselect all</button></div>
      <div className="plex-table-wrap"><table className="plex-wallet-table"><thead><tr><th>Import</th><th>Date / time · UTC</th><th>Direction</th><th>PLEX</th><th>ISK / PLEX</th><th>Total fees · ISK</th><th>Notes / checks</th></tr></thead><tbody>{rows.map((row, i) => <tr key={i}>
        <td><input type="checkbox" aria-label={`Import row ${i + 1}`} checked={row.selected} disabled={busy} onChange={e => update(i, { selected: e.target.checked })} /></td>
        <td><input aria-label={`UTC date row ${i + 1}`} disabled={busy} type="datetime-local" step="1" value={row.date} onChange={e => update(i, { date: e.target.value })} /></td>
        <td><select aria-label={`Direction row ${i + 1}`} disabled={busy} value={row.kind} onChange={e => update(i, { kind: e.target.value as WalletDraft["kind"] })}><option value="">Confirm…</option><option value="buy">Purchase</option><option value="sell">Sale</option></select></td>
        <td><input aria-label={`PLEX quantity row ${i + 1}`} disabled={busy} type="number" min="1" step="1" value={row.quantity} onChange={e => update(i, { quantity: e.target.value })} /></td>
        <td><input aria-label={`Unit price row ${i + 1}`} disabled={busy} type="text" inputMode="decimal" value={row.price} onChange={e => update(i, { price: e.target.value })} /></td>
        <td><input aria-label={`Fees row ${i + 1}`} disabled={busy} type="text" inputMode="decimal" value={row.fees} onChange={e => update(i, { fees: e.target.value })} /></td>
        <td><input aria-label={`Notes row ${i + 1}`} disabled={busy} maxLength={2000} value={row.note} onChange={e => update(i, { note: e.target.value })} />{row.selected && draftError(row) && <p className="plex-warning">{draftError(row)}</p>}
          {duplicates[i] && <label className="plex-warning"><input type="checkbox" disabled={busy} checked={row.allowDuplicate} onChange={e => update(i, { allowDuplicate: e.target.checked })} />Possible duplicate: import anyway</label>}
          <details><summary>Source row</summary><p>{row.source}</p></details></td>
      </tr>)}</tbody></table></div>
      <p className="plex-muted">Times are EVE UTC. Prices must be per PLEX, not the trade total. Fees default to zero because this table does not identify all taxes or broker fees; enter those separately for accurate profit. Possible duplicates match minute, direction, quantity and unit price, including existing manual entries.</p>
      <label className="plex-wallet-confirm"><input type="checkbox" disabled={busy} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I checked the selected rows, buy/sell directions, unit prices and fees.</label>
    </>}
    <div className="plex-actions"><button disabled={busy || !confirmed || !selected.length || invalid || blocked} onClick={() => void save()}>{busy ? "Importing…" : `Import ${selected.length} reviewed trades`}</button><button disabled={busy} onClick={onCancel}>Close importer</button></div>
    <p className="plex-muted">The batch saves together, oldest first. Sales need earlier purchases or opening holdings. No wallet image is uploaded and no EVE orders are placed.</p>
  </section>;
}
