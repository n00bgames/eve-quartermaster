import {observedSpan} from './analyticsModel';
import type {InsightReport as Report,InsightRank,InsightRow} from './insightsModel';
import './insights.css';

const count=(value:number|null)=>value===null?'Unavailable':value.toLocaleString();
const utc=(value:string)=>new Date(value).toISOString().slice(0,19).replace('T',' ');
export function InsightReport({report,publicView=false,onHull,onSystem,onPilot}:{report:Report;publicView?:boolean;
 onHull?:(id:number)=>void;onSystem?:(id:number)=>void;onPilot?:(id:number)=>void}){
 const s=report.summary;
 return <div className="journey-insights-report">
  <p className="muted">{utc(report.scope.from_at)} → {utc(report.scope.to_at)} UTC (end exclusive) · checked {utc(report.checked_at)} UTC</p>
  {!publicView&&report.cohort&&<p>Included pilots: {report.cohort.map(p=>p.name).join(', ')||'None'}</p>}
  <div className="journey-analytics-metrics">{[['Observed visits',count(s.visits)],['Unique systems',count(s.systems)],['Hull segments',count(s.segments)],['Confirmed pilot span',observedSpan(s.seconds)],['Distinct imported kills',count(s.kills)],['Distinct imported losses',count(s.losses)]].map(([label,value])=><div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
  {!report.combat_available&&<p className="notice">Combat is unavailable with the owner’s current permissions; travel remains available.</p>}
  {!publicView&&report.first_at&&<p className="muted">First confirmed hull sample {report.first_at} · Last {report.last_at}</p>}
  <p className="muted">{publicView?'Shared aggregate snapshot.':'Select a hull, system or pilot to narrow the analysis.'} Ranked by {report.scope.metric==='seconds'?'confirmed observation span':report.scope.metric}.</p>
  <Table title="Hull usage and imported combat" rank={report.hulls} onChoose={publicView?undefined:onHull}/>
  {report.systems&&<Table title="Systems in this hull scope" rank={report.systems} onChoose={publicView?undefined:onSystem}/>}
  {report.pilots&&<Table title="Pilot contributions" rank={report.pilots} onChoose={publicView?undefined:onPilot}/>}
  <details><summary>Counting and coverage</summary><ul>{report.notices.map(n=><li key={n}>{n}</li>)}</ul></details>
 </div>;
}

function Table({title,rank,onChoose}:{title:string;rank:InsightRank;onChoose?:(id:number)=>void}){
 return <section className="journey-insights-table"><h5>{title}</h5><p className="muted">{rank.rows.length?rank.offset+1:0}–{rank.offset+rank.rows.length} of {rank.total} groups · totals include all groups. Scroll horizontally for all columns.</p>
  <div className="journey-table-wrap"><table><thead><tr><th>Name</th><th>Visits</th><th>Systems</th><th>Segments</th><th>Confirmed span</th><th>Kills</th><th>Losses</th></tr></thead><tbody>{rank.rows.map((r:InsightRow,i)=><tr key={r.id??`${r.name}:${i}`}><td>{onChoose&&r.id?<button type="button" onClick={()=>onChoose(r.id!)}>{r.name}</button>:r.name}</td><td>{count(r.visits)}</td><td>{count(r.systems)}</td><td>{count(r.segments)}</td><td>{observedSpan(r.seconds)}</td><td>{count(r.kills)}</td><td>{count(r.losses)}</td></tr>)}</tbody></table></div>
  {!rank.rows.length&&<p>No qualifying stored observations or imported combat in this scope.</p>}
 </section>;
}
