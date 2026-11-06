import {useMemo, useState} from 'react';
import type {Hull} from './types';

export function HullCatalog({hulls, selected, choose}: {
  hulls: Hull[]; selected: number; choose: (typeId: number) => void;
}) {
  const groups = useMemo(() => {
    const grouped = new Map<string, Hull[]>();
    for (const hull of hulls) {
      const group = grouped.get(hull.class_name);
      if (group) group.push(hull);
      else grouped.set(hull.class_name, [hull]);
    }
    return grouped;
  }, [hulls]);
  const [selectedClass, setSelectedClass] = useState('');
  const activeClass = groups.has(selectedClass) ? selectedClass
    : hulls.find(hull => hull.type_id === selected)?.class_name ?? groups.keys().next().value ?? '';
  return <section className="matchup-class-catalog" aria-label="Browse ships by class">
    <h4>Browse by ship class</h4>
    <p className="muted">{hulls.length.toLocaleString()} published hulls · {groups.size} classes</p>
    {!hulls.length ? <p>Import the SDE to populate the catalog.</p> : <>
      <label>Ship class
        <select value={activeClass} onChange={event => setSelectedClass(event.target.value)}>
          {[...groups].map(([name, ships]) => <option key={name} value={name}>{name} ({ships.length})</option>)}
        </select>
      </label>
      <div className="matchup-class-ships">
        {groups.get(activeClass)?.map(hull => <button type="button" key={hull.type_id}
          aria-pressed={selected === hull.type_id} onClick={() => choose(hull.type_id)}>{hull.name}</button>)}
      </div>
    </>}
  </section>;
}
