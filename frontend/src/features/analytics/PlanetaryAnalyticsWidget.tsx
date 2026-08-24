import { Boxes, Factory, Gauge, Users } from "lucide-react";
import { useMemo, useState } from "react";

import type { PlanetaryAnalytics, PlanetaryCharacterProduct } from "../../types/analytics";


const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function PlanetaryAnalyticsWidget({
  summary,
}: {
  summary: PlanetaryAnalytics;
}) {
  const [tier, setTier] = useState("all");
  const [productId, setProductId] = useState("all");
  const products = useMemo(
    () => summary.products.filter((row) => tier === "all" || row.tier === tier),
    [summary.products, tier],
  );
  const rankings = useMemo(() => {
    const filtered = summary.character_products.filter((row) => (
      (tier === "all" || row.tier === tier)
      && (productId === "all" || row.product_type_id === Number(productId))
    ));
    if (productId !== "all") return filtered.sort((left, right) => (
      (right.estimated_volume - left.estimated_volume)
      || (right.current_volume_per_day - left.current_volume_per_day)
    ));
    const grouped = new Map<number, PlanetaryCharacterProduct>();
    for (const row of filtered) {
      const current = grouped.get(row.character_id) ?? {
        ...row,
        product_type_id: 0,
        product_name: "All selected commodities",
        tier: tier === "all" ? "P0-P4" : tier,
        estimated_units: 0,
        estimated_volume: 0,
        current_units_per_day: 0,
        current_volume_per_day: 0,
      };
      current.estimated_units += row.estimated_units;
      current.estimated_volume += row.estimated_volume;
      current.current_units_per_day += row.current_units_per_day;
      current.current_volume_per_day += row.current_volume_per_day;
      grouped.set(row.character_id, current);
    }
    return [...grouped.values()].sort((left, right) => (
      (right.estimated_volume - left.estimated_volume)
      || (right.current_volume_per_day - left.current_volume_per_day)
    ));
  }, [summary.character_products, tier, productId]);
  const rankingLabel = productId === "all"
    ? "All selected commodities"
    : summary.products.find((row) => row.product_type_id === Number(productId))?.product_name;

  function selectTier(nextTier: string) {
    setTier(nextTier);
    setProductId("all");
  }

  return <article id="analytics-planetary" className="analytics-widget planetary-analytics-widget analytics-category-anchor">
    <header>
      <div><Factory size={18} /><div><h4>Planetary Production</h4><small>Projected extractor and routed factory output</small></div></div>
      <span>{summary.days}-day history</span>
    </header>
    <div className="planetary-analytics-kpis">
      <span><Gauge size={17} /><small>Current throughput</small><b>{compact.format(summary.cards.current_volume_per_day)} m3/day</b></span>
      <span><Factory size={17} /><small>Estimated production</small><b>{compact.format(summary.cards.estimated_volume)} m3</b></span>
      <span><Boxes size={17} /><small>Products</small><b>{summary.cards.product_count}</b></span>
      <span><Users size={17} /><small>Producers</small><b>{summary.cards.character_count}</b></span>
    </div>
    {!summary.has_history && summary.cards.product_count > 0 && <p className="notice inline">Current rates are available. A later successful PI sync will begin the historical production totals.</p>}
    <div className="metric-chip-row planetary-tier-row">
      <button type="button" className={tier === "all" ? "metric-chip active" : "metric-chip"} onClick={() => selectTier("all")}>All tiers<small>{compact.format(summary.cards.current_volume_per_day)} m3/day</small></button>
      {summary.tiers.map((row) => <button type="button" key={row.tier} className={tier === row.tier ? "metric-chip active" : "metric-chip"} onClick={() => selectTier(row.tier)}>{row.tier} · {row.label}<small>{compact.format(row.current_volume_per_day)} m3/day · {row.character_count} pilots</small></button>)}
    </div>
    <div className="planetary-analytics-columns">
      <section>
        <div className="subsection-heading"><h5>Products</h5><small>Each commodity's leading producer</small></div>
        <div className="table-wrap planetary-product-table"><table><thead><tr><th>Commodity</th><th>Tier</th><th>Current / day</th><th>{summary.days}d estimated</th><th>Top producer</th></tr></thead><tbody>
          {products.map((row) => <tr key={row.product_type_id} className={productId === String(row.product_type_id) ? "selected" : ""} onClick={() => setProductId(String(row.product_type_id))}><td>{row.product_name}</td><td>{row.tier}</td><td>{number.format(row.current_units_per_day)}</td><td>{number.format(row.estimated_units)}</td><td>{row.top_character ?? "Baseline pending"}</td></tr>)}
          {products.length === 0 && <tr><td colSpan={5}>No PI products have been observed for this tier.</td></tr>}
        </tbody></table></div>
      </section>
      <section>
        <div className="subsection-heading"><h5>Producer ranking</h5><small>{rankingLabel}</small></div>
        <label>Commodity<select value={productId} onChange={(event) => setProductId(event.target.value)}><option value="all">All selected commodities</option>{products.map((row) => <option key={row.product_type_id} value={row.product_type_id}>{row.product_name}</option>)}</select></label>
        <div className="widget-list">
          {rankings.slice(0, 12).map((row) => <div className="widget-row" key={`${row.character_id}-${row.product_type_id}`}><span>{row.character_name}<small>{row.product_name} · {row.tier}</small></span><strong>{productId === "all" ? (summary.has_history ? `${number.format(row.estimated_volume)} m3` : `${number.format(row.current_volume_per_day)} m3/day`) : (summary.has_history ? `${number.format(row.estimated_units)} units` : `${number.format(row.current_units_per_day)} / day`)}</strong><i style={{ width: `${Math.max(4, row.current_volume_per_day / Math.max(...rankings.map((item) => item.current_volume_per_day), 1) * 100)}%` }} /></div>)}
          {rankings.length === 0 && <p className="empty">No producers match this filter.</p>}
        </div>
      </section>
    </div>
  </article>;
}
