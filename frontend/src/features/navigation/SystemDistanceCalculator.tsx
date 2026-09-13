import { useEffect, useRef, useState } from "react";
import type { NavigationSystem } from "../../types/navigation";
import { SystemSearchField } from "./RouteChecker";
import { distanceAU, formatDistance, roughWarpSeconds } from "./systemDistances";
import type { SystemObjects } from "./systemDistances";
import "./systemDistances.css";

type Props = { api: <T>(path: string, options?: RequestInit) => Promise<T> };
const KIND: Record<string, string> = { gate: "Gate", station: "NPC station", upwell: "Upwell", planet: "Planet", moon: "Moon", belt: "Asteroid belt", star: "Star" };

export function SystemDistanceCalculator({ api }: Props) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<NavigationSystem[]>([]);
  const [system, setSystem] = useState<NavigationSystem | null>(null);
  const [data, setData] = useState<SystemObjects | null>(null);
  const [originId, setOriginId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [warp, setWarp] = useState("3");
  const [align, setAlign] = useState("10");
  const [structureId, setStructureId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, []);

  useEffect(() => {
    let active = true;
    if (system || query.trim().length < 2) { setOptions([]); return; }
    const timer = setTimeout(() => {
      void api<NavigationSystem[]>(`/navigation/systems?q=${encodeURIComponent(query.trim())}&limit=12`)
        .then(rows => { if (active) setOptions(rows); })
        .catch(() => { if (active) { setOptions([]); setError("System search unavailable. Please try again."); } });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [query, system, api]);

  function changeQuery(value: string) {
    generation.current += 1;
    setQuery(value); setOptions([]); setSystem(null); setData(null);
    setOriginId(""); setDestinationId(""); setStructureId(""); setError(""); setBusy(false);
  }
  async function load(selected: NavigationSystem, action = "") {
    const version = ++generation.current;
    setBusy(true); setError("");
    try {
      const result = await api<SystemObjects>(`/navigation/systems/${selected.system_id}/objects${action}`, action ? { method: "POST" } : undefined);
      if (version !== generation.current) return;
      setData(result);
      setOriginId(old => result.objects.some(o => o.object_id === old && o.position) ? old : result.objects.find(o => o.position)?.object_id ?? "");
      setDestinationId(old => result.objects.some(o => o.object_id === old && o.position) ? old : "");
    } catch (err) {
      if (version === generation.current) setError(err instanceof Error ? err.message : "Could not load system objects.");
    } finally {
      if (version === generation.current) setBusy(false);
    }
  }
  function pick(selected: NavigationSystem) {
    setSystem(selected); setQuery(selected.name); setOptions([]); setData(null); setOriginId(""); setDestinationId("");
    void load(selected);
  }
  const objects = data?.objects ?? [];
  const origin = objects.find(o => o.object_id === originId);
  const destination = objects.find(o => o.object_id === destinationId);
  const distance = distanceAU(origin, destination);
  const seconds = roughWarpSeconds(distance, warp, align);
  const validInputs = roughWarpSeconds(1, warp, align) !== null;

  return <section className="panel stacked system-distance-calculator" aria-labelledby="system-distance-title">
    <div className="section-heading"><div><h3 id="system-distance-title">System Distances &amp; Warp Time</h3><p>Pick a solar system and a starting object, then select a destination to estimate one warp.</p></div></div>
    <div className="distance-controls">
      <SystemSearchField label="Solar system" value={query} options={options} placeholder="Type at least two letters…" onChange={changeQuery} onPick={pick} />
      <label>From<select aria-label="From" value={originId} disabled={!objects.length || busy} onChange={e => { setOriginId(e.target.value); setDestinationId(""); }}><option value="">Select starting object</option>{objects.map(o => <option key={o.object_id} value={o.object_id} disabled={!o.position}>{KIND[o.kind] ?? o.kind} · {o.name}{!o.position ? " — position unavailable" : ""}</option>)}</select></label>
      <button type="button" disabled={!system || busy} onClick={() => system && void load(system, "/sync")}>{busy ? "Loading objects…" : "Refresh ESI objects"}</button>
    </div>
    {error && <div className="mini-alert" role="alert">{error}</div>}
    {data && <>
      <p className="muted">{data.message}{data.checked_at ? ` Last static ESI check: ${new Date(data.checked_at).toLocaleString()}.` : ""}</p>
      <p className="muted">{data.coverage_note}</p>
      <details><summary>Resolve an additional Upwell structure</summary><div className="distance-controls"><label>Structure ID<input inputMode="numeric" value={structureId} onChange={e => setStructureId(e.target.value)} placeholder="Structure ID in this system" /></label><button type="button" disabled={busy || !/^[1-9]\d{0,15}$/.test(structureId) || !Number.isSafeInteger(Number(structureId))} onClick={() => system && void load(system, `/structures/${structureId}`)}>Resolve using my characters</button></div></details>
      {objects.length === 0 ? <p>No objects stored yet. Use Refresh ESI objects or reimport the SDE.</p> : <div className="distance-object-list"><table><caption>Destinations · distance from {origin?.name ?? "your selected starting object"}</caption><thead><tr><th aria-label="Select destination"><span className="distance-select-heading">Select</span></th><th>Kind</th><th>Object</th><th>Distance</th></tr></thead><tbody>{objects.map(o => <tr key={o.object_id} className={destinationId === o.object_id ? "distance-selected" : ""}><td><input type="radio" name="warp-destination" aria-label={`Warp to ${o.name}`} checked={destinationId === o.object_id} disabled={!origin || !o.position || busy} onChange={() => setDestinationId(o.object_id)} /></td><td>{KIND[o.kind] ?? o.kind}</td><td><label onClick={() => { if (origin && o.position && !busy) setDestinationId(o.object_id); }}>{o.name}</label><small>{o.source.toUpperCase()}{o.object_id === originId ? " · Starting object" : ""}</small></td><td>{origin ? formatDistance(distanceAU(origin, o)) : "Select starting object"}</td></tr>)}</tbody></table></div>}
    </>}
    <div className="distance-estimate-card">
      <div className="distance-controls"><label>Warp speed (AU/s)<input type="number" min="0.01" step="any" value={warp} onChange={e => setWarp(e.target.value)} /></label><label>Align time (seconds)<input type="number" min="0" step="any" value={align} onChange={e => setAlign(e.target.value)} /></label></div>
      {!validInputs && <p role="alert">Enter a warp speed greater than zero and an align time of zero or more.</p>}
      <div aria-live="polite"><h4>Rough warp-time estimate</h4>{seconds !== null && !busy ? <><strong className="distance-time">{seconds.toLocaleString(undefined, { maximumFractionDigits: 1 })} seconds</strong><p>{origin?.name} → {destination?.name} · {formatDistance(distance)}</p>{distance === 0 ? <p>Same position: no warp required.</p> : <p>{formatDistance(distance)} ÷ {warp} AU/s + {align} seconds alignment</p>}</> : <p>{busy ? "Updating object positions…" : "Choose an origin and destination, and enter valid speed and align time."}</p>}</div>
      <p className="mini-alert"><strong>Rough estimate:</strong> Does not include acceleration and deceleration times and should only be used as an estimated reference time. Docking, gate activation, and server delays are also excluded.</p>
    </div>
  </section>;
}
