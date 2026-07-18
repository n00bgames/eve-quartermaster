import { Beaker } from "lucide-react";

import type { ResearchProjectAnalytics } from "../../types/analytics";

export function ResearchAnalyticsWidget({ summary, days }: { summary: ResearchProjectAnalytics; days: number }) {
  const maxCharacter = Math.max(...summary.by_character.map((row) => row.count), 1);
  return <article className="analytics-widget research-analytics-widget">
    <header><div><Beaker size={18} /><h4>Research Projects</h4></div><small>{days}-day activity plus current queues</small></header>
    <div className="research-analytics-kpis"><span><b>{summary.project_count.toLocaleString()}</b> recorded</span><span><b>{summary.active_count.toLocaleString()}</b> active</span><span><b>{summary.completed_count.toLocaleString()}</b> delivered</span></div>
    <div className="widget-list">{summary.by_character.map((row) => <div key={row.name} className="widget-row"><span>{row.name}</span><strong>{row.count.toLocaleString()} projects</strong><i style={{ width: `${Math.max(5, row.count / maxCharacter * 100)}%` }} /></div>)}{summary.by_character.length === 0 && <p className="empty">No research projects synced yet.</p>}</div>
    {summary.by_activity.length > 0 && <div className="metric-chip-row">{summary.by_activity.map((row) => <span key={row.name} className="metric-chip has-data">{row.name}<small>{row.count.toLocaleString()}</small></span>)}</div>}
  </article>;
}