export type ShipClassChoice={id:number;name:string;subcaps_excluded:boolean};

export function ShipClassFilters({classes,excluded,onChange}:{classes:ShipClassChoice[];excluded:number[];onChange:(ids:number[])=>void}){
 return <section className="ship-class-options">
  <div className="scan-report-actions"><button type="button" onClick={()=>onChange(classes.filter(c=>c.subcaps_excluded).map(c=>c.id))}>Subcaps</button><button type="button" disabled={!excluded.length} onClick={()=>onChange([])}>Clear exclusions</button></div>
  <p className="muted">Capsules are always excluded. Subcaps excludes shuttles and all XL/XXL hull classes, including freighters and jump freighters.</p>
  <details><summary>Exclude ship classes ({excluded.length})</summary><div className="ship-class-grid">{classes.map(c=><label className="check" key={c.id}><input type="checkbox" checked={excluded.includes(c.id)} onChange={e=>onChange(e.target.checked?[...excluded,c.id]:excluded.filter(id=>id!==c.id))}/>{c.name}</label>)}</div>{!classes.length&&<p className="muted">Import the SDE to load ship classes.</p>}</details>
 </section>;
}
