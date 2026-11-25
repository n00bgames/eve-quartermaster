import { useState } from "react";
import type { CharacterFittingRecord, FighterTarget, FittingFighters, FittingItem, FittingSearchType } from "../../types/fittings";
import { EveItemName } from "../clientLinks/EveClientLinks";
import "./fighterTubes.css";

type Props = {
  fitting: CharacterFittingRecord;
  fighters?: FittingFighters;
  catalog: FittingSearchType[];
  busy: boolean;
  includeSalvos: boolean;
  target: FighterTarget;
  onSalvos: (enabled: boolean) => void;
  onTarget: (target: FighterTarget) => void;
  onLoad: (index: number, typeId: number, sourceItemId?: number) => Promise<void>;
  onUpdate: (item: FittingItem, changes: Partial<Pick<FittingItem, "quantity" | "flag" | "simulation_state">>) => Promise<void>;
};

const number = (value: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);

export function FighterTubesPanel({ fitting, fighters, catalog, busy, includeSalvos, target, onSalvos, onTarget, onLoad, onUpdate }: Props) {
  const [choices, setChoices] = useState<Record<number, string>>({});
  if (!fighters || (!fighters.tube_count && !fighters.tubes.length)) return null;
  const editable = fitting.is_draft && fitting.can_manage;
  const reserves = fitting.items.filter(item => item.flag === "FighterBay" && item.fighter_class);
  const candidates = catalog.filter(item => item.fighter_class && fighters.limits[item.fighter_class] > 0 && item.name.indexOf("Standup ") !== 0);
  const tubeIndexes = [...new Set([...Array.from({ length: fighters.tube_count }, (_, i) => i), ...fighters.tubes.map(tube => tube.index)])];
  return <section className="fighter-tubes-panel" aria-label="Fighter tubes">
    <div className="section-heading compact">
      <div><h4>Fighter tubes · {fighters.tubes.filter(tube => tube.active && tube.valid).length}/{fighters.tube_count} deployed</h4>
        <p>Squadron limits: {Object.entries(fighters.limits).map(([kind, count]) => `${kind} ${fighters.deployed[kind as keyof typeof fighters.limits] ?? 0}/${count}`).join(" · ")}</p>
      </div>
      <strong className="fighter-total">{number(fighters.total_dps)} fighter DPS</strong>
    </div>
    <div className="fighter-options">
      <label>Damage target<select value={target} disabled={busy} onChange={event => onTarget(event.target.value as FighterTarget)}>
        <option value="capital">Capital ship</option><option value="subcapital">Subcapital ship</option>
        <option value="fighter">Fighter / drone</option><option value="structure">Structure</option>
      </select></label>
      <label className="checkbox-row"><input type="checkbox" checked={includeSalvos} disabled={busy} onChange={event => onSalvos(event.target.checked)} />Include missile salvo burst</label>
    </div>
    <p className="muted">Only deployed squadrons deal damage. Estimates assume full application before target resists and movement. Salvos have limited ammunition; their burst DPS is not sustainable indefinitely.</p>
    <div className="fighter-tube-grid">
      {tubeIndexes.map(index => {
        const tube = fighters.tubes.find(row => row.index === index);
        const item = tube && fitting.items.find(row => row.id === tube.item_id);
        const choice = choices[index] ?? "";
        return <article key={index} className={`fighter-tube${tube?.active ? " deployed" : ""}${tube && !tube.valid ? " invalid" : ""}`}>
          <h5>Tube {index + 1}<span>{tube ? tube.active ? "Deployed" : "Loaded" : "Empty"}</span></h5>
          {tube && item ? <>
            <EveItemName name={tube.name} typeId={tube.type_id} />
            <div className="fighter-squadron-size">
              <label>Fighters<input key={`${item.id}-${item.quantity}`} type="number" min={1} max={tube.max_size} defaultValue={tube.size} disabled={!editable || busy}
                aria-label={`Tube ${index + 1} fighter count`} onBlur={event => {
                  const amount = Number(event.target.value);
                  if (Number.isInteger(amount) && amount >= 1 && amount <= tube.max_size && amount !== tube.size) void onUpdate(item, { quantity: amount });
                  else event.target.value = String(tube.size);
                }} /></label><span>of {tube.max_size} · {tube.fighter_class}</span>
            </div>
            <div className="fighter-damage-row"><span>Primary</span><strong>{number(tube.primary_dps)} DPS</strong></div>
            {tube.abilities.some(ability => ability.kind === "salvo") && <div className="fighter-damage-row"><span>Salvo burst{includeSalvos ? " · included" : " · excluded"}</span><strong>{number(tube.salvo_dps)} DPS</strong></div>}
            {tube.warning && <p role="alert" className="scope-warn">{tube.warning}</p>}
            {editable && <div className="button-row compact">
              <button type="button" disabled={busy} onClick={() => void onUpdate(item, { simulation_state: tube.active ? "online" : "active" })}>{tube.active ? "Recall" : "Deploy"}</button>
              <button type="button" disabled={busy} onClick={() => void onUpdate(item, { flag: "FighterBay", simulation_state: "online" })}>Unload to hangar</button>
            </div>}
          </> : editable ? <>
            <label>Squadron<select aria-label={`Tube ${index + 1} fighter type`} value={choice} disabled={busy} onChange={event => setChoices(previous => ({ ...previous, [index]: event.target.value }))}>
              <option value="">Choose fighters…</option>
              {reserves.length > 0 && <optgroup label="Load from hangar reserves">{reserves.filter(row => row.fighter_class && fighters.limits[row.fighter_class] > 0).map(row => <option key={`bay:${row.id}`} value={`bay:${row.id}`}>{row.type_name} · {row.quantity} in hangar</option>)}</optgroup>}
              <optgroup label="Add new stock">{candidates.map(row => <option key={row.type_id} value={String(row.type_id)}>{row.name} · {row.fighter_max_size ?? "?"} per squadron</option>)}</optgroup>
            </select></label>
            <button type="button" disabled={busy || !choice} onClick={() => {
              if (choice.startsWith("bay:")) { const source = reserves.find(row => row.id === Number(choice.slice(4))); if (source) void onLoad(index, source.type_id, source.id); }
              else void onLoad(index, Number(choice));
            }}>Load &amp; deploy</button>
          </> : <p className="muted">Create an editable draft to load a squadron.</p>}
        </article>;
      })}
    </div>
    {fighters.warnings.map(warning => <p className="scope-warn" key={warning}>{warning}</p>)}
    <p className="muted">Hangar capacity includes loaded squadrons. Loading reserves moves fighters into a tube; unloading returns them. EFT and Send to EVE include all carried fighters in the fighter bay; tube deployment is saved in EQM only.</p>
  </section>;
}
