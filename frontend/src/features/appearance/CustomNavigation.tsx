import {DragHandle} from "./DragHandle";
import React, {useEffect, useState, type ReactNode} from "react";
import {useAppearance} from "./AppearanceProvider";
import {addShortcut, defaultNavigation, move, moveModule, navigationWithDefaults, removeShortcut, type NavGroup} from "./model";

function entryText(node: ReactNode): string {
  return React.Children.toArray(node).map(child => {
    if (typeof child === "string" || typeof child === "number") return String(child);
    return React.isValidElement<{children?: ReactNode}>(child) ? entryText(child.props.children) : "";
  }).join("").trim();
}

export function CustomNavigation({entries}: {entries: Record<string, ReactNode>}) {
  const a = useAppearance();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<NavGroup[]>(() => navigationWithDefaults(a.personal.preferences.navigation));
  useEffect(() => setDraft(navigationWithDefaults(a.personal.preferences.navigation)), [a.personal.preferences.navigation]);
  const visible = (id: string) => !!entries[id];
  const label = (id: string) => entryText(entries[id]) || id.replace(/_/g, " ");
  const groups = editing ? draft : navigationWithDefaults(a.personal.preferences.navigation);

  function drop(e: React.DragEvent, target: string, before?: string) {
    e.preventDefault();
    e.stopPropagation();
    const module = e.dataTransfer.getData("application/x-eqm-module");
    const source = e.dataTransfer.getData("application/x-eqm-module-source");
    const group = e.dataTransfer.getData("application/x-eqm-group");
    if (module && source && visible(module)) setDraft(current => moveModule(current, module, source, target, before));
    else if (group) setDraft(current => move(current, current.findIndex(g => g.id === group), current.findIndex(g => g.id === target)));
  }

  return <nav aria-label="Main navigation" className={editing ? "nav-editing" : undefined}>
    <button type="button" disabled={!a.ready || a.busy} onClick={() => {
      setDraft(navigationWithDefaults(a.personal.preferences.navigation));
      setEditing(!editing);
    }}>{editing ? "Cancel navigation edits" : "Customize navigation"}</button>
    {editing && <div className="nav-edit-actions">
      <p>Drag sections or links, or use the arrows. Add shortcuts from any section using the dropdowns below.</p>
      <button disabled={a.busy} onClick={() => void a.save({navigation: draft})}>Save navigation</button>
      <button disabled={a.busy || draft.length >= 20} onClick={() => setDraft(current => [...current, {id: `custom-${Date.now()}`, name: "New section", modules: []}])}>Add section</button>
      <button disabled={a.busy} onClick={() => setDraft(navigationWithDefaults())}>Restore defaults</button>
      <p role="status">{a.busy ? "Saving…" : a.notice}</p>
    </div>}
    {groups.map((g, gi) => {
      if (!editing && !g.modules.some(visible)) return null;
      const sectionName = g.name || "General";
      const available = defaultNavigation.map(source => ({...source, modules: source.modules.filter(m => visible(m) && !g.modules.includes(m))})).filter(source => source.modules.length);
      return <div className={editing ? "nav-custom-group editing" : "nav-custom-group"} key={g.id}
        data-drop-nav-group={g.id} data-drop-nav-module={`${g.id}|`}
        onDragOver={editing ? e => e.preventDefault() : undefined} onDrop={editing && !a.busy ? e => drop(e, g.id) : undefined}>
        {editing ? <fieldset disabled={a.busy}>
          <div className="nav-group-controls">
            <DragHandle label={`Drag section ${sectionName}`} attribute="data-drop-nav-group" onDrop={target => setDraft(current => move(current, gi, current.findIndex(x => x.id === target)))}>⠿</DragHandle>
            <input aria-label={`Section name ${gi + 1}`} value={g.name} maxLength={48} placeholder="General" onChange={e => setDraft(draft.map(x => x.id === g.id ? {...x, name: e.target.value} : x))}/>
            <button disabled={!gi} aria-label={`Move section ${sectionName} up`} onClick={() => setDraft(move(draft, gi, gi - 1))}>↑</button>
            <button disabled={gi === draft.length - 1} aria-label={`Move section ${sectionName} down`} onClick={() => setDraft(move(draft, gi, gi + 1))}>↓</button>
          </div>
          <label className="nav-shortcut-picker">Add shortcut
            <select aria-label={`Add shortcut to ${sectionName}`} value="" disabled={!available.length} onChange={e => {
              const module = e.target.value;
              if (visible(module)) setDraft(current => addShortcut(current, module, g.id));
            }}>
              <option value="">{available.length ? "Choose a navigation item…" : "All available items added"}</option>
              {available.map(source => <optgroup key={source.id} label={source.name || "General"}>
                {source.modules.map(m => <option value={m} key={m}>{label(m)}</option>)}
              </optgroup>)}
            </select>
          </label>
          <p className="nav-shortcut-help">Keeps the original link in its section.</p>
          {!g.modules.length && <button onClick={() => setDraft(draft.filter(x => x.id !== g.id))}>Remove empty section</button>}
        </fieldset> : g.name && <span className="nav-section-label">{g.name}</span>}
        {g.modules.filter(visible).map(m => <div key={m} data-drop-nav-module={`${g.id}|${m}`} className="nav-module"
          onDragOver={editing ? e => e.preventDefault() : undefined} onDrop={editing && !a.busy ? e => drop(e, g.id, m) : undefined}>
          {entries[m]}
          {editing && <fieldset disabled={a.busy} className="nav-module-controls">
            <DragHandle label={`Drag ${label(m)} from ${sectionName}`} attribute="data-drop-nav-module" onDrop={target => {
              const [group, before] = target.split("|");
              setDraft(current => moveModule(current, m, g.id, group, before || undefined));
            }}>⠿</DragHandle>
            <button aria-label={`Move ${label(m)} up in ${sectionName}`} disabled={g.modules.indexOf(m) === 0} onClick={() => setDraft(draft.map(x => x.id === g.id ? {...x, modules: move(x.modules, x.modules.indexOf(m), x.modules.indexOf(m) - 1)} : x))}>↑</button>
            <button aria-label={`Move ${label(m)} down in ${sectionName}`} disabled={g.modules.indexOf(m) === g.modules.length - 1} onClick={() => setDraft(draft.map(x => x.id === g.id ? {...x, modules: move(x.modules, x.modules.indexOf(m), x.modules.indexOf(m) + 1)} : x))}>↓</button>
            <select aria-label={`Move ${label(m)} from ${sectionName} to section`} value={g.id} onChange={e => setDraft(moveModule(draft, m, g.id, e.target.value))}>
              {draft.map(x => <option key={x.id} value={x.id}>{x.name || "General"}</option>)}
            </select>
            {draft.filter(x => x.modules.includes(m)).length > 1 && <button className="nav-remove-shortcut" aria-label={`Remove ${label(m)} shortcut from ${sectionName}`} onClick={() => setDraft(current => removeShortcut(current, m, g.id))}>Remove shortcut</button>}
          </fieldset>}
        </div>)}
      </div>;
    })}
  </nav>;
}
