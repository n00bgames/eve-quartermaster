import {useEffect, useState} from 'react';
import type {ApiClient} from '../localScan/types';
import type {FitExample, FitResearch, Hull} from './types';

const value = (n: number | null | undefined, unit = '') =>
  n == null || !Number.isFinite(n) ? 'Unknown' : n.toLocaleString(undefined, {maximumFractionDigits: 1}) + unit;

function Example({example, chooseCounter}: {example: FitExample; chooseCounter: (name: string) => void}) {
  const stats = example.stats;
  return <article className="matchup-example">
    <header><h4><a href={`https://zkillboard.com/kill/${example.killmail_id}/`} target="_blank" rel="noopener noreferrer">
      zKillboard loss #{example.killmail_id} ↗
    </a></h4><time dateTime={example.killmail_time}>{example.killmail_time.slice(0, 10)} UTC</time></header>
    <p className="muted">{example.weapon_families.join(' · ') || 'No identified combat weapon system'}
      {example.estimated_loss_isk != null && ` · ${value(example.estimated_loss_isk)} ISK estimated loss`}</p>
    {stats ? <>
      <dl className="matchup-fit-stats">
        <div><dt>Cycle DPS</dt><dd>{value(stats.offense.total_dps)}</dd></div>
        <div><dt>Volley</dt><dd>{value(stats.offense.volley)}</dd></div>
        <div><dt>Even-mix EHP</dt><dd>{value(stats.defense.ehp)}</dd></div>
        <div><dt>Unpropelled speed</dt><dd>{value(stats.mobility.max_velocity, ' m/s')}</dd></div>
        <div><dt>Align</dt><dd>{value(stats.mobility.align_time, ' s')}</dd></div>
        <div><dt>Lock range</dt><dd>{value(stats.targeting.targeting_range == null ? null : stats.targeting.targeting_range / 1000, ' km')}</dd></div>
      </dl>
      <details><summary>Fitted resistances and weapon ranges</summary>
        <div className="matchup-fit-resists">
          {([['Shield',stats.defense.shield_resists],['Armor',stats.defense.armor_resists],['Hull',stats.defense.structure_resists]] as const).map(([layer,resists]) =>
            <p key={layer}><strong>{layer}</strong> {['em','thermal','kinetic','explosive'].map(damage =>
              `${damage === 'em' ? 'EM' : damage} ${value(resists[damage] == null ? null : resists[damage] * 100, '%')}`).join(' · ')}</p>)}
        </div>
        <ul>{stats.offense.weapons.map((weapon, index) => <li key={index}>{weapon.name}
          {weapon.charge_name ? ` with ${weapon.charge_name}` : ''}
          {weapon.control_range_m != null ? ` · ${value(weapon.control_range_m / 1000, ' km')} drone control` : ''}
          {weapon.optimal_m != null ? ` · ${value(weapon.optimal_m / 1000, ' km')} ${weapon.group.startsWith('Missile Launcher') ? 'estimated flight range' : 'optimal'}` : ''}
          {weapon.falloff_m != null ? ` + ${value(weapon.falloff_m / 1000, ' km')} falloff` : ''}
          {weapon.optimal_m == null && weapon.range_m != null ? ` · ${value(weapon.range_m / 1000, ' km')} estimated reach` : ''}
        </li>)}</ul>
      </details>
    </> : <p className="muted">Stats unavailable for this example. The imported Dogma or recorded slot data is incomplete.</p>}
    <details><summary>Recorded modules and loaded charges ({example.modules.length})</summary>
      <ul>{example.modules.map((module, index) => <li key={index}>
        <small>{module.slot}</small> {module.quantity > 1 ? `${module.quantity} × ` : ''}{module.name}
        {module.charge ? ` · ${module.charge}` : ''}
      </li>)}</ul>
    </details>
    <h4>Potential counter fits</h4>
    {example.counter_fits.length ? <div className="matchup-counter-grid">
      {example.counter_fits.map(counter => <section key={counter.hull + counter.fit}>
        <button type="button" onClick={() => chooseCounter(counter.hull)}>{counter.hull}</button>
        <strong>{counter.fit}</strong><p>{counter.plan}</p><small className="muted">{counter.condition}</small>
      </section>)}
    </div> : <p className="muted">No counter fit suggested from the recorded modules. Check the hull’s role, tackle and supporting ships.</p>}
  </article>;
}

export function FitExamples({hull, context, api, chooseCounter}: {
  hull: Hull; context: string; api: ApiClient; chooseCounter: (name: string) => void;
}) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<FitResearch | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!attempt) return;
    const abort = new AbortController();
    let active = true;
    setLoading(true);
    setError('');
    setResult(null);
    void api<FitResearch>(`/matchups/ships/${hull.type_id}/examples?context=${encodeURIComponent(context)}`, {signal: abort.signal})
      .then(data => {if (active) setResult(data);})
      .catch(reason => {if (active) setError(reason instanceof Error ? reason.message : String(reason));})
      .finally(() => {if (active) setLoading(false);});
    return () => {active = false; abort.abort();};
  }, [attempt, hull.type_id, context, api]);
  return <section className="panel matchup-fit-research">
    <h3>Example fits from public losses</h3>
    <p className="muted">Sample fitted weapons and modules from recent reported losses of this hull. Frequencies apply to this sample.</p>
    <button type="button" disabled={loading} onClick={() => setAttempt(current => current + 1)}>
      {loading ? 'Looking up losses…' : error ? 'Retry zKillboard lookup' : result ? 'Check for examples again' : 'Find example fits'}
    </button>
    {loading && <p role="status">Checking zKillboard losses for {hull.name}…</p>}
    {error && <p role="alert" className="mini-alert">{error}</p>}
    {result && <>
      <p className="muted">Checked {result.scanned_count} recent loss records. {result.sample_count} included fitted equipment.</p>
      {result.observed_weapons.length > 0 && <div className="matchup-tags" aria-label="Weapons observed in sample">
        {result.observed_weapons.map(weapon => <span key={weapon.name}>{weapon.name} · {weapon.count}/{result.sample_count}</span>)}
      </div>}
      {result.examples.length ? <>
        <p className="muted">{result.assumptions}</p>
        {result.examples.map(example => <Example key={example.killmail_id} example={example} chooseCounter={chooseCounter}/>)}
      </> : <p>No usable public fit in this sample for {hull.name}.</p>}
    </>}
    <p><a href={`https://zkillboard.com/ship/${hull.type_id}/losses/`} target="_blank" rel="noopener noreferrer">Browse this hull’s losses on zKillboard ↗</a></p>
  </section>;
}
