import { useEffect, useState } from "react";
import type { PlanetarySchematic } from "../../types/planetaryIndustry";

export type PiHangar = { id: string; name: string; items: Record<string, number>; oldest_synced_at: string | null; has_unsynced_items: boolean };
type Result = {
  total_batches: number; output_quantity: number; duration_seconds: number;
  full_capacity_seconds: number; final_round_factories: number;
  ingredients: { type_id: number; available: number; consumed: number; remaining: number; limiting: boolean; required_per_round: number }[];
};
const number = new Intl.NumberFormat();
const duration = (seconds: number) => `${Math.floor(seconds / 86400)}d ${Math.floor(seconds % 86400 / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;

export function ProductionCalculator({ recipes, hangar, api }: {
  recipes: PlanetarySchematic[]; hangar?: PiHangar;
  api: <T>(path: string, options?: RequestInit) => Promise<T>;
}) {
  const [recipeId, setRecipeId] = useState("");
  const [factories, setFactories] = useState("1");
  const [stock, setStock] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const recipe = recipes.find(r => String(r.id) === recipeId);
  const key = JSON.stringify([recipeId, factories, stock]);
  const [resultKey, setResultKey] = useState("");

  useEffect(() => {
    setResult(null); setError(null); setBusy(false);
    if (!recipe) return;
    const count = Number(factories);
    const entries = recipe.inputs.map(i => [String(i.type_id), Number(stock[String(i.type_id)] || 0)] as const);
    if (!Number.isInteger(count) || count < 1 || count > 10000 || entries.some(([,n]) => !Number.isSafeInteger(n) || n < 0 || n > 1e12)) {
      setError("Enter whole, nonnegative ingredient quantities (up to 1 trillion) and 1–10,000 factories."); return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setBusy(true);
      void api<Result>("/planetary-industry/production-calculator", { method: "POST", signal: controller.signal,
        body: JSON.stringify({ schematic_id: recipe.id, factories: count, inventory: Object.fromEntries(entries) }),
      }).then(value => { if (!controller.signal.aborted) { setResult(value); setResultKey(key); } })
        .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Calculation failed"); })
        .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [key, recipe]);

  const current = resultKey === key ? result : null;
  return <section className="planetary-shortage-report pi-production-calculator">
    <h3>Production Calculator</h3>
    <p>Calculate complete factory cycles from ingredients on hand. Factories share a finite stockpile; no ongoing extraction or upstream production is assumed.</p>
    <div className="planetary-controls">
      <label>PI recipe<select value={recipeId} onChange={e => { setRecipeId(e.target.value); setStock({}); }}><option value="">Choose a recipe</option>{recipes.map(r => <option key={r.id} value={r.id}>{r.output.name}</option>)}</select></label>
      <label>Factories<input type="number" min="1" max="10000" step="1" value={factories} onChange={e => setFactories(e.target.value)} /></label>
    </div>
    {recipe && <>
      <p>{number.format(recipe.output.quantity)} {recipe.output.name} per {duration(recipe.cycle_time)} factory cycle.</p>
      <div className="button-row compact"><button type="button" disabled={!hangar} onClick={() => setStock(Object.fromEntries(recipe.inputs.map(i => [String(i.type_id), String(hangar?.items[String(i.type_id)] ?? 0)])))}>Use selected hangar stock</button></div>
      <div className="planetary-controls">{recipe.inputs.map(i => <label key={i.type_id}>{i.name} · {number.format(i.quantity)} per cycle<input type="number" min="0" max="1000000000000" step="1" value={stock[String(i.type_id)] ?? ""} placeholder="0" onChange={e => setStock(s => ({ ...s, [String(i.type_id)]: e.target.value }))} /></label>)}</div>
    </>}
    {busy && <p className="muted">Calculating…</p>}
    {error && <p className="mini-alert">{error}</p>}
    {current && <>
      <div className="status-grid planetary-report-summary">
        <article><span>Production ends after</span><strong>{duration(current.duration_seconds)}</strong><small>From starting with this stock</small></article>
        <article><span>All factories supplied for</span><strong>{duration(current.full_capacity_seconds)}</strong><small>{current.final_round_factories ? `${current.final_round_factories} factories can run one final cycle` : "No partial final round"}</small></article>
        <article><span>Total output</span><strong>{number.format(current.output_quantity)}</strong><small>{recipe?.output.name} · {number.format(current.total_batches)} factory cycles</small></article>
      </div>
      <div className="table-wrap"><table><thead><tr><th>Ingredient</th><th>On hand</th><th>Consumed</th><th>Left over</th><th>Limit</th></tr></thead><tbody>{current.ingredients.map(i => <tr key={i.type_id}><td>{recipe?.inputs.find(r => r.type_id === i.type_id)?.name}</td><td>{number.format(i.available)}</td><td>{number.format(i.consumed)}</td><td>{number.format(i.remaining)}</td><td>{i.limiting ? "Limiting ingredient" : "—"}</td></tr>)}</tbody></table></div>
      <small className="planetary-report-caveat">Assumes ingredients are delivered and distributed between factories. Storage, routing, hauling time and partially completed cycles are not simulated.</small>
    </>}
    {!recipes.length && <p className="empty">Import the SDE PI schematic catalog to load recipes.</p>}
  </section>;
}
