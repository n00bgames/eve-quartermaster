import { BadgeDollarSign, Factory, PackageCheck, Warehouse } from "lucide-react";
import type { ReactNode } from "react";

import { iskFormatter } from "../../lib/market";
import type { ManufacturingAnalytics } from "../../types/analytics";

const numberFormatter = new Intl.NumberFormat();

export function ManufacturingAnalyticsWidgets({ summary, days }: { summary: ManufacturingAnalytics; days: number }) {
  return <>
    <article className="analytics-widget manufacturing-analytics-widget">
      <header><Factory size={18} /><div><h4>Manufacturing Output</h4><small>{days}-day ledger | {numberFormatter.format(summary.job_count)} realized jobs</small></div></header>
      <div className="manufacturing-kpi-grid">
        <ManufacturingKpi icon={<PackageCheck size={17} />} label="Items built" value={numberFormatter.format(summary.items_built)} />
        <ManufacturingKpi label="Actual cost" value={iskFormatter.format(summary.actual_cost) + " ISK"} />
        <ManufacturingKpi label="Market input cost" value={iskFormatter.format(summary.current_cost) + " ISK"} />
        <ManufacturingKpi label="Saved" value={iskFormatter.format(summary.savings) + " ISK"} positive={summary.savings >= 0} negative={summary.savings < 0} />
      </div>
      <ManufacturingItemList summary={summary} />
    </article>
    <article className="analytics-widget manufacturing-analytics-widget">
      <header><BadgeDollarSign size={18} /><div><h4>Output Disposition</h4><small>Recorded kept and sold production</small></div></header>
      <div className="manufacturing-kpi-grid">
        <ManufacturingKpi icon={<Warehouse size={17} />} label="Items kept" value={numberFormatter.format(summary.kept_items)} />
        <ManufacturingKpi label="Items sold" value={numberFormatter.format(summary.sold_items)} />
        <ManufacturingKpi label="Sales" value={iskFormatter.format(summary.sales_revenue) + " ISK"} />
        <ManufacturingKpi label="Profit after costs" value={iskFormatter.format(summary.realized_profit) + " ISK"} positive={summary.realized_profit >= 0} negative={summary.realized_profit < 0} />
      </div>
      {summary.sold_items === 0 && summary.kept_items === 0 && <p className="empty">Mark completed output as kept or sold to populate disposition analytics.</p>}
    </article>
  </>;
}

function ManufacturingKpi({ icon, label, value, positive = false, negative = false }: { icon?: ReactNode; label: string; value: string; positive?: boolean; negative?: boolean }) {
  const className = negative ? "negative" : positive ? "positive" : "";
  return <div className={className}><span>{icon}{label}</span><strong>{value}</strong></div>;
}

function ManufacturingItemList({ summary }: { summary: ManufacturingAnalytics }) {
  if (summary.top_items.length === 0) return <p className="empty">Complete a manufacturing entry to begin building production history.</p>;
  return <div className="manufacturing-item-summary">
    {summary.top_items.map((item) => <div key={item.name}>
      <span>{item.name}<small>{item.kept_quantity} kept | {item.sold_quantity} sold</small></span>
      <strong>{numberFormatter.format(item.quantity)} built<small>{iskFormatter.format(item.actual_cost)} ISK cost</small></strong>
    </div>)}
  </div>;
}
