import type { Catalog } from "./piPlannerTypes";

export const plannerPath = "/planetary-industry/planner";
export const piNumber = (n?: number | null) => n == null ? "—" : new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(n);
export function downloadPi(name: string, value: unknown, mime = "application/json") {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = name; document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
}
export function PiNumberField({ label, value, onChange, min = 0, max, step = "any" }: { label: string; value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number | string }) {
  return <label>{label}<input type="number" required min={min} max={max} step={step} value={Number.isFinite(value) ? value : ""} onChange={e => onChange(e.target.valueAsNumber)} /></label>;
}
export function CommoditySelect({ catalog, value, onChange, filter = () => true, label = "Commodity" }: { catalog: Catalog; value: number; onChange: (v: number) => void; filter?: (id: number) => boolean; label?: string }) {
  return <label>{label}<select aria-label={label} value={value} onChange={e => onChange(Number(e.target.value))}>{Object.values(catalog).filter(i => filter(i.type_id)).sort((a, b) => a.tier - b.tier || a.name.localeCompare(b.name)).map(i => <option key={i.type_id} value={i.type_id}>P{i.tier} · {i.name}</option>)}</select></label>;
}
