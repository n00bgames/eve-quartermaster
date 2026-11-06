import {useEffect,useState} from 'react';
import {BookOpen,Crosshair,Shield,Target} from 'lucide-react';
import type {ApiClient} from '../localScan/types';
import {EveItemName} from '../clientLinks/EveClientLinks';
import type {Card,Catalog,Composition,Hull} from './types';
import {LayoutRegion} from '../appearance/LayoutRegion';
import {HullCatalog} from './HullCatalog';
import {FitExamples} from './FitExamples';
import './matchups.css';

function HullIcon({id}:{id:number}){
 const [bad,setBad]=useState(false);
 return bad?<span className="matchup-hull-icon" aria-hidden="true">◇</span>:<img className="matchup-hull-icon" src={`https://images.evetech.net/types/${id}/icon?size=64`} alt="" referrerPolicy="no-referrer" onError={()=>setBad(true)}/>;
}
export function MatchupsPage({api}:{api:ApiClient}){
 const params=new URLSearchParams(window.location.hash.split('?')[1]??'');
 const initial=Number(params.get('ship'))||0,scan=params.get('scan');
 const [catalog,setCatalog]=useState<Catalog|null>(null),[query,setQuery]=useState(''),[results,setResults]=useState<Hull[]>([]),[searching,setSearching]=useState(false);
 const [id,setId]=useState(initial),[card,setCard]=useState<Card|null>(null),[context,setContext]=useState('small_gang'),[variant,setVariant]=useState('unknown');
 const [text,setText]=useState(''),[composition,setComposition]=useState<Composition|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[cardError,setCardError]=useState(''),[searchError,setSearchError]=useState(''),[atlas,setAtlas]=useState(false);
 useEffect(()=>{let stop=false;void api<Catalog>('/matchups/catalog').then(v=>{if(!stop)setCatalog(v);}).catch(e=>{if(!stop)setError(String(e));});return()=>{stop=true;};},[api]);
 useEffect(()=>{setResults([]);setSearchError('');setSearching(false);if(query.trim().length<2)return;let stop=false;const abort=new AbortController();setSearching(true);
  const timer=window.setTimeout(()=>void api<Hull[]>(`/matchups/ships?q=${encodeURIComponent(query.trim())}`,{signal:abort.signal}).then(v=>{if(!stop)setResults(v);}).catch(e=>{if(!stop)setSearchError(String(e));}).finally(()=>{if(!stop)setSearching(false);}),180);
  return()=>{stop=true;abort.abort();window.clearTimeout(timer);};
 },[query,api]);
 useEffect(()=>{setCard(null);setCardError('');if(!id)return;let stop=false;const abort=new AbortController();void api<Card>(`/matchups/ships/${id}?context=${context}`,{signal:abort.signal}).then(v=>{if(!stop)setCard(v);}).catch(e=>{if(!stop)setCardError(String(e));});return()=>{stop=true;abort.abort();};},[id,context,api]);
 useEffect(()=>{if(!scan)return;let stop=false;void api<Composition>(`/matchups/scans/${encodeURIComponent(scan)}`).then(v=>{if(!stop){setComposition(v);setId(v.ships.find(s=>s.type_id)?.type_id??0);}}).catch(e=>{if(!stop)setError(String(e));});return()=>{stop=true;};},[scan,api]);
 function choose(typeId:number){setId(typeId);setVariant('unknown');setQuery('');setAtlas(false);}
 function chooseCounter(name:string){
  const hull=catalog?.hulls.find(entry=>entry.name===name);
  if(hull)choose(hull.type_id);
  else setQuery(name);
 }
 async function analyze(){setBusy(true);setError('');try{const v=await api<Composition>('/matchups/analyze',{method:'POST',body:JSON.stringify({text})});setComposition(v);setText('');choose(v.ships.find(s=>s.type_id)?.type_id??0);}catch(e){setError(String(e));}finally{setBusy(false);}}
 const profiles=card?.variants.filter(v=>variant==='unknown'||variant===v.key)??[];
 return <LayoutRegion region="matchups" className="matchups-page stacked">
  <section data-layout-id="matchups-command" data-layout-label="Matchups controls" className="panel matchup-command"><div className="matchup-eyebrow">PVP KNOWLEDGEBASE / FC’S FIELD MANUAL</div><header><div><h2><Crosshair/> Matchups</h2><p>Know the hull. Question the fit. Pick your engagement.</p></div><label>Engagement context<select aria-label="Engagement context" value={context} onChange={e=>setContext(e.target.value)}><option value="small_gang">Solo / small gang</option><option value="fleet">Fleet command</option></select></label></header>
   <div className="matchup-tabs"><button type="button" aria-pressed={!atlas} onClick={()=>setAtlas(false)}><Target size={16}/> Hulls & matchups</button><button type="button" aria-pressed={atlas} onClick={()=>setAtlas(true)}><BookOpen size={16}/> Weapon recognition</button></div>
   <p className="muted">Hull facts come from your imported SDE. Tactics are sourced reference scenarios; d-scan cannot reveal a fit, pilot, allegiance or win probability.</p>
  </section>
  {error&&<p key="matchups-error" role="alert" className="mini-alert">{error}</p>}
  <div data-layout-id="matchups-workspace" data-layout-label="Hull references and weapon guide">{atlas?<section className="panel matchup-atlas"><h3>Look At: weapon recognition</h3><p>Compare the mounted weapon at the same size and a similar camera angle. Use silhouette plus firing behavior; neither establishes the exact ammo or every fitted module.</p><p><a href="https://wiki.eveuniversity.org/Turret_Recognition" target="_blank" rel="noopener noreferrer">Open mounted-turret reference ↗</a> · <a href="https://wiki.eveuniversity.org/Identifying_Visual_Effects" target="_blank" rel="noopener noreferrer">Visual effects reference ↗</a></p>
   <p className="muted">The embedded, size-by-size screenshot atlas is still to be collected and verified. Inventory icons are not substituted for mounted 3D weapon images.</p>
   <div className="matchup-weapon-grid">{catalog?.weapons.map(w=><article key={w.key}><span className="matchup-eyebrow">COMPARE WITH {catalog.weapons.find(x=>x.key===w.pair)?.name.toUpperCase()}</span><h4>{w.name}</h4><p>{w.cue}</p><p className="muted">{w.behavior}</p></article>)}</div>
  </section>:<>
  <div className="matchup-workspace"><aside className="panel matchup-picker"><h3>Identify the threat</h3><label>Ship hull<input aria-label="Search ship hulls" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Deimos, Caracal, Arazu…" autoComplete="off"/></label>
   {searchError&&<p role="alert">{searchError}</p>}{searching&&<p role="status">Searching hulls…</p>}
   <div className="matchup-search-results">{results.map(h=><button type="button" key={h.type_id} onClick={()=>choose(h.type_id)}><HullIcon id={h.type_id}/><span><strong>{h.name}</strong><small>{h.class_name} · {h.curated?'Reference variants':'Base facts only'}</small></span></button>)}</div>
   {query.trim().length>=2&&!searching&&!results.length&&!searchError&&<p className="muted">No matching published hull. Check the name and SDE import.</p>}
   {!query&&catalog&&<><HullCatalog hulls={catalog.hulls??catalog.starters} selected={id} choose={choose}/>
    <h4>Written matchup guides</h4><div className="matchup-starters">{catalog.starters.map(h=><button type="button" aria-pressed={id===h.type_id} key={h.type_id} onClick={()=>choose(h.type_id)}>{h.name}</button>)}</div></>}
   <details className="matchup-paste"><summary>Analyze a pasted d-scan</summary><p className="muted">Read-only analysis; no report link, sightings, pilot lookup or stored scan is created. Counts need not all be hostile.</p><label>D-scan text<textarea aria-label="Matchups d-scan" rows={6} maxLength={500000} value={text} onChange={e=>setText(e.target.value)} placeholder="Copy d-scan rows with Ctrl+A, Ctrl+C"/></label><button type="button" disabled={busy||!text.trim()} onClick={()=>void analyze()}>{busy?'Analyzing…':'Build threat list'}</button></details>
   {composition&&<section className="matchup-composition"><h4>{composition.total.toLocaleString()} ships in input</h4><p className="muted">{composition.covered.toLocaleString()} have reference variants · {composition.unresolved} unresolved objects · {composition.ignored.length} skipped rows</p><div className="matchup-roster">{composition.ships.map(r=><button type="button" key={r.type_id??r.type_name} disabled={!r.type_id} aria-pressed={id===r.type_id} onClick={()=>choose(r.type_id!)}><span>{r.type_name}<small>{r.observed} observed{r.manual?` + ${r.manual} manual`:''}</small></span><strong>{r.count}</strong></button>)}</div><h4>Possible roles · overlapping</h4><div className="matchup-tags">{composition.possible_roles.map(r=><span key={r.name}>{r.name}: {r.count}</span>)}</div><p className="muted">{composition.note}</p></section>}
  </aside><div className="matchup-detail">
   {cardError&&<p role="alert" className="mini-alert">{cardError}</p>}
   {!card&&!cardError&&<section className="panel matchup-empty"><Crosshair size={44}/><h3>{id?'Loading hull reference…':'What just landed on your gate?'}</h3><p>Search a hull, pick a starter reference, or bring a D-Scan into Matchups.</p><p className="muted">Start with range control, tackle and support. A low base resistance cannot tell you what is actually fitted.</p></section>}
   {card&&<>
    <section className="panel matchup-facts"><header><HullIcon key={card.type_id} id={card.type_id}/><div><span className="matchup-eyebrow">IMPORTED HULL FACTS</span><h2><EveItemName name={card.name} typeId={card.type_id}/></h2><p className="muted">{card.class_name} · {card.curated?'Reference variants available':'Tactical profile not yet reviewed'}</p></div></header>
     {card.weapon_profile&&<div className="matchup-hull-weapons">
       <h3>Weapon systems</h3>
       {card.weapon_profile.bonused.length > 0
        ? <><p className="muted">Weapon families supported by hull bonuses</p><div className="matchup-tags">{card.weapon_profile.bonused.map(weapon=><span key={weapon}>{weapon}</span>)}</div></>
        : <p className="muted">{card.weapon_profile.effects_loaded?'No weapon bonus identified in imported effects.':'Weapon bonus data unavailable in this SDE import.'}</p>}
       {card.weapon_profile.mounts.length > 0 && <p className="muted">{card.weapon_profile.mounts.join(' · ')}</p>}
       {card.class_name==='Strategic Cruiser'&&<p className="muted">Offensive subsystems change weapon bonuses and hardpoints.</p>}
     </div>}
     <h3><Shield size={18}/> Base resistance map</h3><div className="matchup-resist-grid">{card.layers.map(layer=><article key={layer.name}><h4>{layer.name}</h4>{Object.entries(layer.resists).map(([damage,value])=><div key={damage} className={`matchup-resist ${damage}`}><span>{damage==='em'?'EM':damage}</span><div className="matchup-resist-track"><i style={{width:`${value??0}%`}}/></div><strong>{value===null?'Unknown':`${value}%`}</strong></div>)}<p className="muted">{layer.weakest.length?`Lowest base: ${layer.weakest.join(' / ').toUpperCase()}`:'Incomplete SDE values; no hole inferred.'}</p></article>)}</div><p className="muted">{card.resist_note} <a href={card.fact_source.url} target="_blank" rel="noopener noreferrer">CCP data ↗</a></p>
    </section>
    <FitExamples key={card.type_id} hull={card} context={context} api={api} chooseCounter={chooseCounter}/>
    {card.variants.length>0&&<section className="panel matchup-variants"><header><div><span className="matchup-eyebrow">FIT-DEPENDENT / EDITORIAL SCENARIOS</span><h3>What might it be fitted for?</h3></div><label>Observed fit clue<select aria-label="Observed fit clue" value={variant} onChange={e=>setVariant(e.target.value)}><option value="unknown">Unknown · show all alternatives</option>{card.variants.map(v=><option key={v.key} value={v.key}>{v.name}</option>)}</select></label></header>
     {variant==='unknown'&&card.variants.length>0&&<p className="muted">These are alternatives to investigate. None was detected by the scan. Choosing a clue narrows the guidance; it does not verify the fit.</p>}
     {profiles.map(v=><article className="matchup-variant" key={v.key}><h3>{v.name}</h3><div className="matchup-tags">{v.tags.map(t=><span key={t}>{t}</span>)}</div><dl><dt>Range / control envelope</dt><dd>{v.range_note}</dd><dt>Tank hypothesis</dt><dd>{v.tank}</dd><dt>Incoming damage</dt><dd>{v.damage}</dd><dt>Look for</dt><dd>{v.confirm.join(' · ')}</dd></dl><p className="matchup-plan"><strong>{context==='fleet'?'FC focus':'Pilot focus'}:</strong> {v.plan}</p><h4>Counter tools & example hulls</h4><div className="matchup-counter-grid">{v.counter_tools.map(c=><section key={c.name}><h4>{c.name}</h4><strong>{c.examples.join(' / ')}</strong><p>{c.plan}</p><small className="muted">{c.condition}</small></section>)}</div><footer><a href={v.source.url} target="_blank" rel="noopener noreferrer">{v.source.title} ↗</a><span>Source checked {v.reviewed_at} · counter plans are EQM judgments, not statistical win rates</span></footer></article>)}
    </section>}
   </>}
  </div></div>
  </>}</div>
  <section data-layout-id="matchups-foundation" data-layout-label="Knowledgebase coverage" className="panel matchup-foundation"><h3>Sources and coverage</h3><p>Hull classes, bonuses and base resistances follow your imported CCP data. Public loss examples show fittings observed at the time of loss. Counter fits are conditional suggestions based on those modules and your engagement context.</p></section>
 </LayoutRegion>;
}
