import { useEffect, useMemo, useState } from "react";
import type { PlanetarySchematic } from "../../types/planetaryIndustry";

import { productionChain } from "./productionChain";

export type PiHangar = { id: string; name: string; items: Record<string, number>; oldest_synced_at: string | null; has_unsynced_items: boolean };
type Result = {
  mode?: "chain";
  stages?: { recipe_id: number; type_id: number; tier: number; produced: number; consumed: number; remaining: number; factories: number; duration_seconds: number }[];
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
  const [feedTier, setFeedTier] = useState<number | null>(null);
  const [stageFactories, setStageFactories] = useState<Record<string, string>>({});
  const [stock, setStock] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const recipe = recipes.find(r => String(r.id) === recipeId);
  const chain = useMemo(() => productionChain(recipes, recipe, feedTier), [recipes, recipe, feedTier]);
  const names = new Map(recipes.flatMap(r => [r.output, ...r.inputs]).map(i => [i.type_id, i.name]));
  const key = JSON.stringify([recipeId, factories, stock, feedTier, stageFactories]);
  const [resultKey, setResultKey] = useState("");

  useEffect(() => {
    setResult(null); setError(null); setBusy(false);
    if (!recipe) return;
    const count = Number(factories);
    const entries = chain.inputs.map(i => [String(i.type_id), Number(stock[String(i.type_id)] || 0)] as const);
    const stageCounts = Object.fromEntries(chain.stages.map(r => [String(r.id), Number(stageFactories[String(r.id)] ?? 1)]));
    if (Object.values(stageCounts).some(n => !Number.isInteger(n) || n < 1 || n > 10000) || !Number.isInteger(count) || count < 1 || count > 10000 || entries.some(([,n]) => !Number.isSafeInteger(n) || n < 0 || n > 1e12)) {
      setError("Enter whole, nonnegative ingredient quantities (up to 1 trillion) and 1–10,000 factories."); return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setBusy(true);
      void api<Result>("/planetary-industry/production-calculator", { method: "POST", signal: controller.signal,
        body: JSON.stringify({ schematic_id: recipe.id, factories: count, inventory: Object.fromEntries(entries), feed_tier: feedTier, stage_factories: stageCounts }),
      }).then(value => { if (!controller.signal.aborted) { setResult(value); setResultKey(key); } })
        .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Calculation failed"); })
        .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [key, recipe, chain]);

  const current = resultKey === key ? result : null;
  return <section className="planetary-shortage-report pi-production-calculator">
    <h3>Production Calculator</h3>
    <p>Choose the final product and the tier of materials you feed into your factory planet. The calculator follows every required recipe and shares your stock across the whole chain.</p>
    <div className="planetary-controls">
      <label>PI recipe<select value={recipeId} onChange={e => {
        setRecipeId(e.target.value); setStock({}); setStageFactories({});
        const chosen = recipes.find(r => String(r.id) === e.target.value);
        setFeedTier(productionChain(recipes, chosen, null).tier === 4 ? 2 : null);
      }}><option value="">Choose a recipe</option>{recipes.map(r => <option key={r.id} value={r.id}>{r.output.name}</option>)}</select></label>
      {recipe && <label>Materials I feed<select value={feedTier ?? "direct"} onChange={e => { setFeedTier(e.target.value === "direct" ? null : Number(e.target.value)); setStock({}); }}>
        <option value="direct">Direct recipe ingredients</option>{Array.from({ length: chain.tier }, (_, tier) => <option key={tier} value={tier}>P{tier}{tier === 0 ? " · raw resources" : " materials"}</option>)}
      </select></label>}
      <label>Final product factories<input type="number" min="1" max="10000" step="1" value={factories} onChange={e => setFactories(e.target.value)} /></label>
    </div>
    {recipe && <>
      <p>{number.format(recipe.output.quantity)} {recipe.output.name} per {duration(recipe.cycle_time)} factory cycle.</p>
      <div className="button-row compact"><button type="button" disabled={!hangar} onClick={() => setStock(Object.fromEntries(chain.inputs.map(i => [String(i.type_id), String(hangar?.items[String(i.type_id)] ?? 0)])))}>Use selected hangar stock</button></div>
      <div className="planetary-controls">{chain.inputs.map(i => <label key={i.type_id}>{i.name}{feedTier === null ? ` · ${number.format(i.quantity)} per cycle` : " · on hand"}<input type="number" min="0" max="1000000000000" step="1" value={stock[String(i.type_id)] ?? ""} placeholder="0" onChange={e => setStock(s => ({ ...s, [String(i.type_id)]: e.target.value }))} /></label>)}</div>
    </>}
    {recipe && feedTier !== null && <>
      <p>Enter the listed feed materials, including any lower-tier ingredients used directly by this recipe. Shared materials are counted once. Intermediate production is allocated to maximize complete {recipe.output.name} batches.</p>
      <div className="planetary-controls">{chain.stages.filter(r => r.id !== recipe.id).map(r => <label key={r.id}>{r.output.name} factories<input type="number" min="1" max="10000" step="1" value={stageFactories[String(r.id)] ?? "1"} onChange={e => setStageFactories(s => ({ ...s, [String(r.id)]: e.target.value }))} /></label>)}</div>
    </>}
    {busy && <p className="muted">Calculating…</p>}
    {error && <p className="mini-alert">{error}</p>}
    {current && <>
      <div className="status-grid planetary-report-summary">
        <article><span>{current.mode === "chain" ? "Staged completion estimate" : "Production ends after"}</span><strong>{duration(current.duration_seconds)}</strong><small>{current.mode === "chain" ? "Each tier finishes before the next starts" : "From starting with this stock"}</small></article>
        {current.mode !== "chain" && <article><span>All factories supplied for</span><strong>{duration(current.full_capacity_seconds)}</strong><small>{current.final_round_factories ? `${current.final_round_factories} factories can run one final cycle` : "No partial final round"}</small></article>}
        <article><span>Total output</span><strong>{number.format(current.output_quantity)}</strong><small>{recipe?.output.name} · {number.format(current.total_batches)} factory cycles</small></article>
      </div>
      <div className="table-wrap"><table><thead><tr><th>Ingredient</th><th>On hand</th><th>Consumed</th><th>Left over</th><th>Limit</th></tr></thead><tbody>{current.ingredients.map(i => <tr key={i.type_id}><td>{names.get(i.type_id)}</td><td>{number.format(i.available)}</td><td>{number.format(i.consumed)}</td><td>{number.format(i.remaining)}</td><td>{i.limiting ? "Limits next output batch" : "—"}</td></tr>)}</tbody></table></div>
      {current.stages && <div className="table-wrap"><table><thead><tr><th>Production stage</th><th>Made</th><th>Used downstream</th><th>Intermediate left over</th><th>Factories</th><th>Runtime</th></tr></thead><tbody>{current.stages.map(stage => <tr key={stage.recipe_id}><td>P{stage.tier} · {names.get(stage.type_id)}</td><td>{number.format(stage.produced)}</td><td>{number.format(stage.consumed)}</td><td>{stage.recipe_id === recipe?.id ? "Final output" : number.format(stage.remaining)}</td><td>{number.format(stage.factories)}</td><td>{duration(stage.duration_seconds)}</td></tr>)}</tbody></table></div>}
      <small className="planetary-report-caveat">{current.mode === "chain" ? "The time estimate runs recipes within each tier in parallel, then starts the next tier. Overlapping tiers in-game may finish sooner. Unused feedstock is left unprocessed; intermediate stock already on hand is not included in feed-tier mode. " : ""}Assumes ingredients are delivered and distributed between factories. Storage, routing, hauling time and partially completed cycles are not simulated.</small>
    </>}
    {!recipes.length && <p className="empty">Import the SDE PI schematic catalog to load recipes.</p>}
  </section>;
}
