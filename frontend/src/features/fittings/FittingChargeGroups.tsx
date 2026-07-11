import { useEffect, useMemo, useState } from "react";

import type { CharacterFittingRecord, FittingItem, FittingSearchType } from "../../types/fittings";
import { chargeMatchesModule, fittingSlotKey } from "./FittingSupport";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type ChargeGroup = { id: number; name: string; itemIds: number[]; chargeTypeId: number | "" };

type FittingChargeGroupsProps = {
  selected: CharacterFittingRecord;
  fittedControlItems: FittingItem[];
  ammoCatalog: FittingSearchType[];
  editorBusy: boolean;
  api: ApiClient;
  setEditorBusy: (busy: boolean) => void;
  setError: (message: string | null) => void;
  setMessage: (message: string | null) => void;
  onFittingUpdated: (fitting: CharacterFittingRecord) => void;
};

export function FittingChargeGroups({ selected, fittedControlItems, ammoCatalog, editorBusy, api, setEditorBusy, setError, setMessage, onFittingUpdated }: FittingChargeGroupsProps) {
  const [chargeGroups, setChargeGroups] = useState<ChargeGroup[]>([{ id: 1, name: "Group 1", itemIds: [], chargeTypeId: "" as const }]);
  const chargeGroupItems = useMemo(() => fittedControlItems.filter((item) => {
    const slotKey = fittingSlotKey(item.flag);
    return ["HiSlot", "MedSlot", "LoSlot", "SubSystemSlot", "ServiceSlot"].includes(slotKey) && (chargeOptionsForItem(item, ammoCatalog).length > 0 || Boolean(item.charge_type_id));
  }), [fittedControlItems, ammoCatalog]);
  const chargeGroupItemKey = chargeGroupItems.map((item) => item.id).join(",");

  useEffect(() => {
    const availableIds = new Set(chargeGroupItems.map((item) => item.id));
    setChargeGroups((current) => {
      if (chargeGroupItems.length === 0) return [{ id: 1, name: "Group 1", itemIds: [], chargeTypeId: "" as const }];
      const existing: ChargeGroup[] = current.length > 0 ? current.slice(0, 5) : [{ id: 1, name: "Group 1", itemIds: [], chargeTypeId: "" }];
      const next = existing.map((group, index) => ({ ...group, name: group.name || `Group ${index + 1}`, itemIds: group.itemIds.filter((itemId) => availableIds.has(itemId)) }));
      if (next.every((group) => group.itemIds.length === 0)) next[0] = { ...next[0], itemIds: chargeGroupItems.map((item) => item.id) };
      return next;
    });
  }, [selected.id, chargeGroupItemKey]);

  if (chargeGroupItems.length === 0) return null;

  function chargeOptionsForGroup(group: ChargeGroup) {
    const groupItems = chargeGroupItems.filter((item) => group.itemIds.includes(item.id));
    return ammoCatalog.filter((charge) => groupItems.some((item) => chargeMatchesModule(item, charge))).slice(0, 450);
  }

  function updateChargeGroup(groupId: number, changes: Partial<ChargeGroup>) {
    setChargeGroups((current) => current.map((group) => group.id === groupId ? { ...group, ...changes } : group));
  }

  function toggleChargeGroupItem(groupId: number, itemId: number) {
    setChargeGroups((current) => current.map((group) => group.id === groupId ? { ...group, itemIds: group.itemIds.includes(itemId) ? group.itemIds.filter((id) => id !== itemId) : [...group.itemIds, itemId] } : group));
  }

  function addChargeGroup() {
    setChargeGroups((current) => current.length >= 5 ? current : [...current, { id: Math.max(...current.map((group) => group.id), 0) + 1, name: `Group ${current.length + 1}`, itemIds: [], chargeTypeId: "" as const }]);
  }

  function autoBuildChargeGroups() {
    const byName = new Map<string, FittingItem[]>();
    for (const item of chargeGroupItems) byName.set(item.type_name, [...(byName.get(item.type_name) ?? []), item]);
    const entries = [...byName.entries()].sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));
    const next: ChargeGroup[] = entries.slice(0, 5).map(([name, items], index) => ({ id: index + 1, name: name.length > 28 ? `Group ${index + 1}` : name, itemIds: items.map((item) => item.id), chargeTypeId: (items.every((item) => item.charge_type_id === items[0]?.charge_type_id) ? items[0]?.charge_type_id ?? "" : "") as number | "" }));
    if (entries.length > 5) next[4] = { id: 5, name: "Other weapons", itemIds: entries.slice(4).flatMap(([, items]) => items.map((item) => item.id)), chargeTypeId: "" as const };
    setChargeGroups(next.length > 0 ? next : [{ id: 1, name: "Group 1", itemIds: [], chargeTypeId: "" as const }]);
  }

  async function applyChargeGroup(group: ChargeGroup) {
    const groupItems = chargeGroupItems.filter((item) => group.itemIds.includes(item.id));
    const charge = group.chargeTypeId === "" ? null : ammoCatalog.find((item) => item.type_id === group.chargeTypeId) ?? null;
    const applicableItems = charge ? groupItems.filter((item) => chargeMatchesModule(item, charge)) : groupItems;

    if (applicableItems.length === 0) {
      setError("Select at least one compatible launcher, turret, or scripted module for this group.");
      return;
    }

    setEditorBusy(true);
    setError(null);
    try {
      let updated = selected;
      for (const item of applicableItems) {
        updated = await api<CharacterFittingRecord>(`/fittings/${selected.id}/items/${item.id}`, { method: "PATCH", body: JSON.stringify({ charge_type_id: charge ? charge.type_id : null }) });
      }
      onFittingUpdated(updated);
      setMessage(`Applied ${charge?.name ?? "No charge/script"} to ${applicableItems.length} module${applicableItems.length === 1 ? "" : "s"} in ${group.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply charge group");
    } finally {
      setEditorBusy(false);
    }
  }

  return <div className="charge-group-panel">
    <div className="charge-group-actions">
      <strong>Ammo / Script Groups</strong>
      <span>{chargeGroups.length}/5 groups</span>
      <button type="button" disabled={editorBusy || chargeGroups.length >= 5} onClick={addChargeGroup}>Add group</button>
      <button type="button" disabled={editorBusy} onClick={autoBuildChargeGroups}>Auto group weapons</button>
    </div>
    {chargeGroups.map((group) => {
      const options = chargeOptionsForGroup(group);
      const selectedCount = group.itemIds.length;
      const compatibleCount = group.chargeTypeId === "" ? selectedCount : chargeGroupItems.filter((item) => group.itemIds.includes(item.id) && options.some((charge) => charge.type_id === group.chargeTypeId && chargeMatchesModule(item, charge))).length;
      return <section key={group.id} className="charge-group-card">
        <label>Group name<input value={group.name} onChange={(event) => updateChargeGroup(group.id, { name: event.target.value })} /></label>
        <label>Charge / script<select value={group.chargeTypeId} disabled={editorBusy || options.length === 0} onChange={(event) => updateChargeGroup(group.id, { chargeTypeId: event.target.value ? Number(event.target.value) : "" })}>
          <option value="">No charge/script</option>
          {options.map((charge) => <option key={charge.type_id} value={charge.type_id}>{charge.name}</option>)}
        </select></label>
        <button type="button" disabled={editorBusy || selectedCount === 0} onClick={() => void applyChargeGroup(group)}>Apply to group</button>
        <small>{selectedCount} selected{group.chargeTypeId !== "" ? ` · ${compatibleCount} compatible` : ""}</small>
        <div className="charge-group-members">{chargeGroupItems.map((item) => <label key={`${group.id}-${item.id}`} className="check"><input type="checkbox" checked={group.itemIds.includes(item.id)} onChange={() => toggleChargeGroupItem(group.id, item.id)} /> {item.flag} · {item.type_name}{item.charge_type_name ? ` · ${item.charge_type_name}` : ""}</label>)}</div>
      </section>;
    })}
  </div>;
}

function chargeOptionsForItem(item: FittingItem, ammoCatalog: FittingSearchType[]) {
  return ammoCatalog.filter((charge) => chargeMatchesModule(item, charge)).slice(0, 450);
}
