import { ClipboardList } from "lucide-react";

import type { CharacterFittingRecord, FittingSyncToken } from "../../types/fittings";

type FittingSyncControlsProps = {
  tokens: FittingSyncToken[];
  syncToken: FittingSyncToken | null;
  syncTokenId: number | "";
  busyTokenId: number | null;
  onSyncTokenChange: (tokenId: number | "") => void;
  onSync: () => void;
};

export function FittingSyncControls({ tokens, syncToken, syncTokenId, busyTokenId, onSyncTokenChange, onSync }: FittingSyncControlsProps) {
  return <>
    <div className="fitting-sync-row">
      <label>Character<select value={syncTokenId} onChange={(event) => onSyncTokenChange(event.target.value ? Number(event.target.value) : "")}><option value="">Choose character</option>{tokens.map((token) => <option key={token.token_id} value={token.token_id}>{token.character_name}{token.has_fitting_scope ? "" : " - missing fitting scope"}</option>)}</select></label>
      <button type="button" disabled={syncTokenId === "" || !syncToken?.can_sync || busyTokenId === syncTokenId} onClick={onSync}><ClipboardList size={18} /> {busyTokenId === syncTokenId ? "Syncing" : "Sync saved fittings"}</button>
    </div>
    {syncToken && !syncToken.has_fitting_scope && <div className="scope-warn">Missing esi-fittings.read_fittings.v1. Re-link this character through EVE SSO before syncing fittings.</div>}
  </>;
}

type FittingImportPanelProps = {
  importCharacterId: number | "";
  importText: string;
  importBusy: boolean;
  characterOptions: FittingSyncToken[];
  onImportCharacterChange: (characterId: number | "") => void;
  onImportTextChange: (text: string) => void;
  onReadClipboard: () => void;
  onImportText: () => void;
};

export function FittingImportPanel({ importCharacterId, importText, importBusy, characterOptions, onImportCharacterChange, onImportTextChange, onReadClipboard, onImportText }: FittingImportPanelProps) {
  return <details className="fitting-import-panel">
    <summary>Import fit from clipboard</summary>
    <div className="fitting-import-grid">
      <label>Owner character<select value={importCharacterId} onChange={(event) => onImportCharacterChange(event.target.value ? Number(event.target.value) : "")}><option value="">Choose character</option>{characterOptions.map((token) => <option key={token.character_id} value={token.character_id}>{token.character_name}</option>)}</select></label>
      <div className="button-row compact"><button type="button" disabled={importBusy} onClick={onReadClipboard}>Read clipboard</button><button type="button" disabled={importBusy || importCharacterId === "" || !importText.trim()} onClick={onImportText}>{importBusy ? "Importing" : "Import as draft"}</button></div>
      <label className="fitting-import-text">EFT fitting text<textarea value={importText} onChange={(event) => onImportTextChange(event.target.value)} placeholder={"[Caracal, Fleet Caracal]\nBallistic Control System II\n..."} /></label>
    </div>
  </details>;
}

type FittingListPanelProps = {
  filter: string;
  fittings: CharacterFittingRecord[];
  selectedId?: number | null;
  onFilterChange: (value: string) => void;
  onSelectFitting: (fittingId: number) => void;
};

export function FittingListPanel({ filter, fittings, selectedId, onFilterChange, onSelectFitting }: FittingListPanelProps) {
  return <section className="fitting-list-panel">
    <label>Search fittings<input value={filter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Ship, fitting, character, owner" /></label>
    <div className="card-list fitting-list">
      {fittings.map((fitting) => <button key={fitting.id} type="button" className={selectedId === fitting.id ? "active fitting-card" : "fitting-card"} onClick={() => onSelectFitting(fitting.id)}><strong>{fitting.ship_type_name}</strong><span>{fitting.name}</span><small>{fitting.character_name} · {fitting.is_draft ? "draft" : "ESI"}{fitting.is_shared ? " · shared" : " · private"}</small></button>)}
      {fittings.length === 0 && <p className="empty">No saved fittings found.</p>}
    </div>
  </section>;
}