import type {Candidate,IntelReport} from "./types";

type Props={report:IntelReport;kind:string;setKind:(value:string)=>void;max:number;setMax:(value:number)=>void;min:number;setMin:(value:number)=>void;sort:string;setSort:(value:string)=>void;disabled:boolean;onTrack:(candidate:Candidate)=>void;onEvidence:(ids:number[],title:string)=>void};

export function IntelAssociates({report,kind,setKind,max,setMax,min,setMin,sort,setSort,disabled,onTrack,onEvidence}:Props) {
 const filters=report.association_filters;
 const rows=report.summary.associates.filter(row=>row.kind===kind);
 return <section className="panel stacked">
  <h3>Recurring co-attackers</h3>
  <div className="intel-controls">
   <label>Entity type<select value={kind} onChange={e=>setKind(e.target.value)}><option value="character">Characters</option><option value="corporation">Corporations</option><option value="alliance">Alliances</option></select></label>
   <label>Maximum named attackers<select disabled={disabled} value={max} onChange={e=>setMax(Number(e.target.value))}>{[[0,"All fight sizes"],[5,"Up to 5"],[20,"Up to 20"],[50,"Up to 50"],[100,"Up to 100"]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
   <label>Minimum shared UTC days<select disabled={disabled} value={min} onChange={e=>setMin(Number(e.target.value))}>{[1,2,3,5,10].map(value=><option key={value} value={value}>{value}</option>)}</select></label>
   <label>Rank associations by<select disabled={disabled} value={sort} onChange={e=>setSort(e.target.value)}><option value="kills">Shared kills</option><option value="days">Shared UTC days</option></select></label>
  </div>
  <p className="muted">{report.definitions.associates} Affiliations are recorded at the time of each kill.</p>
  <p className="notice inline">Applied: {filters?.max_attackers?`up to ${filters.max_attackers} named attackers`:"all fight sizes"}, at least {filters?.min_days??1} shared UTC day(s), ranked by {filters?.sort==="days"?"shared UTC days":"shared kills"}. Filters affect associations only; combat totals and UTC activity still include the full retained sample.</p>
  <div className="intel-table-wrap"><table><thead><tr><th>Entity</th><th>Shared kills</th><th>Est. engagements</th><th>UTC days</th><th>Subject's kills</th><th>Evidence</th></tr></thead><tbody>{rows.map(row=><tr key={`${row.kind}:${row.id}`}><td><button className="intel-text-button" disabled={disabled} onClick={()=>onTrack({kind:row.kind,eve_id:row.id,name:row.name})}>{row.name}</button></td><td>{row.kills}</td><td>{row.estimated_engagements}</td><td>{row.distinct_days}</td><td>{row.share_of_subject_kills_percent}%</td><td><button onClick={()=>onEvidence(row.evidence,`Co-attacker: ${row.name}`)}>Inspect</button></td></tr>)}</tbody></table></div>
  {!rows.length&&<p>No associations match these filters in the retained evidence.</p>}
  <p className="muted">Top 50 per entity type after filtering; {report.total_associates} matching associations. Shared-kill percentages use all of the subject's observed PvP kills as their denominator.</p>
 </section>;
}
