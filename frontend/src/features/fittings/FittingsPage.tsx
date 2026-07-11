import { useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";

import { formatDateTime, preferredTimeZone } from "../../lib/time";
import { FittingChargeGroups } from "./FittingChargeGroups";
import { FittingImportPanel, FittingListPanel, FittingSyncControls } from "./FittingShellPanels";
import { chargeMatchesModule, eveTypeImageUrl, fallbackShipImage, FittingContextPanel, FittingStatsPanel, fittingItemTooltip, fittingSkillPlanText, fittingSlotKey, fittingStateLabel, hideBrokenImage, nextFittingState, romanLevel } from "./FittingSupport";
import { FITTING_PICKER_TABS, fittingPickerBucket } from "../../types/fittings";
import type { CharacterFittingRecord, FittingImportResult, FittingItem, FittingPickerTab, FittingSearchType, FittingSeed, FittingSimulation, FittingSyncToken, FittingsPayload, FittingWeaponEstimate } from "../../types/fittings";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type FittingsUser = { timezone?: string };
type FittingsAsset = { type_id: number; quantity: number; owner_name: string; location_name?: string | null; location_flag?: string | null };

type FittingsPageProps = {
  currentUser: FittingsUser;
  assets: FittingsAsset[];
  seed?: FittingSeed | null;
  onOpenAssets: (itemName?: string) => void;
  onOpenMarket: (text: string) => void;
  api: ApiClient;
};
export function FittingsPage({ currentUser, assets, seed, onOpenAssets, onOpenMarket, api }: FittingsPageProps) {

  const [payload, setPayload] = useState<FittingsPayload>({ fittings: [], sync_tokens: [], editable_flags: [] });

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [syncTokenId, setSyncTokenId] = useState<number | "">("");

  const [simulationCharacterId, setSimulationCharacterId] = useState<number | "">("");

  const [simulationHeat, setSimulationHeat] = useState(false);

  const [simulation, setSimulation] = useState<FittingSimulation | null>(null);

  const [simulationBusy, setSimulationBusy] = useState(false);

  const [filter, setFilter] = useState("");

  const [scratch, setScratch] = useState("");

  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);

  const [editorBusy, setEditorBusy] = useState(false);

  const [itemSearch, setItemSearch] = useState("");

  const [itemCatalog, setItemCatalog] = useState<Record<FittingPickerTab, FittingSearchType[]>>({ Modules: [], Rigs: [], Ammo: [], Drones: [], Other: [] });

  const [catalogBusy, setCatalogBusy] = useState(false);

  const [selectedItemTypeId, setSelectedItemTypeId] = useState<number | "">("");

  const [draftFlag, setDraftFlag] = useState("Cargo");

  const [draftQuantity, setDraftQuantity] = useState(1);

  const [pickerTab, setPickerTab] = useState<FittingPickerTab>("Modules");

  const [importCharacterId, setImportCharacterId] = useState<number | "">("");

  const [importText, setImportText] = useState("");

  const [importBusy, setImportBusy] = useState(false);

  const [message, setMessage] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);



  const editableFlags = payload.editable_flags.length > 0 ? payload.editable_flags : ["HiSlot0", "MedSlot0", "LoSlot0", "RigSlot0", "DroneBay", "Cargo"];



  function replaceFitting(updated: CharacterFittingRecord) {

    setPayload((current) => {

      const exists = current.fittings.some((row) => row.id === updated.id);

      return { ...current, fittings: exists ? current.fittings.map((row) => row.id === updated.id ? updated : row) : [updated, ...current.fittings] };

    });

    setSelectedId(updated.id);

  }



  function flagLabel(flag: string) {

    if (flag === "Cargo") return "Cargo hold";

    if (flag === "DroneBay") return "Drone bay";

    if (flag === "FighterBay") return "Fighter bay";

    return flag.replace("HiSlot", "High ").replace("MedSlot", "Mid ").replace("LoSlot", "Low ").replace("RigSlot", "Rig ").replace("SubSystemSlot", "Subsystem ").replace("ServiceSlot", "Service ");

  }



  function defaultFlagForPickerItem(item: FittingSearchType) {

    const bucket = item.bucket ?? fittingPickerBucket(item);

    if (bucket === "Rigs") return "RigSlot0";

    if (bucket === "Drones") return "DroneBay";

    if (bucket === "Ammo") return "Cargo";

    return "HiSlot0";

  }



  function beginPickerDrag(event: DragEvent, item: FittingSearchType) {

    event.dataTransfer.setData("application/eqm-type-id", String(item.type_id));

    event.dataTransfer.effectAllowed = "copy";

    setSelectedItemTypeId(item.type_id);

    setDraftFlag(defaultFlagForPickerItem(item));

  }



  function allowFittingDrop(event: DragEvent) {

    if (selected?.is_draft && selected.can_manage) {

      event.preventDefault();

      event.dataTransfer.dropEffect = "copy";

    }

  }



  async function dropPickerItem(event: DragEvent, flag: string) {

    event.preventDefault();

    if (!selected?.is_draft || !selected.can_manage) return;

    const draggedTypeId = Number(event.dataTransfer.getData("application/eqm-type-id"));

    const typeId = Number.isFinite(draggedTypeId) && draggedTypeId > 0 ? draggedTypeId : selectedItemTypeId;

    if (typeId === "" || !typeId) return;

    setDraftFlag(flag);

    setSelectedItemTypeId(typeId);

    await addDraftItemToFlag(selected, typeId, flag, draftQuantity, false);

  }



  async function loadFittings() {

    const next = await api<FittingsPayload>("/fittings");

    setPayload({ ...next, editable_flags: next.editable_flags ?? [] });

    setSelectedId((current) => current ?? next.fittings[0]?.id ?? null);

    setSyncTokenId((current) => current === "" ? next.sync_tokens.find((token) => token.can_sync)?.token_id ?? next.sync_tokens[0]?.token_id ?? "" : current);

    setImportCharacterId((current) => current === "" ? next.sync_tokens.find((token) => token.can_sync)?.character_id ?? next.sync_tokens[0]?.character_id ?? "" : current);

  }



  async function syncFittings() {

    if (syncTokenId === "") return;

    const token = payload.sync_tokens.find((row) => row.token_id === syncTokenId);

    setBusyTokenId(syncTokenId);

    setError(null);

    setMessage(`Syncing saved fittings for ${token?.character_name ?? "character"}...`);

    try {

      const result = await api<{ character_name: string; fitting_count: number }>(`/esi/sync/character-fittings/${syncTokenId}`, { method: "POST", body: "{}" });

      setMessage(`Synced ${result.fitting_count.toLocaleString()} saved fitting${result.fitting_count === 1 ? "" : "s"} for ${result.character_name}.`);

      await loadFittings();

    } catch (err) {

      setMessage(null);

      setError(err instanceof Error ? err.message : "Fitting sync failed");

    } finally {

      setBusyTokenId(null);

    }

  }



  async function toggleShare(fitting: CharacterFittingRecord) {

    setError(null);

    try {

      const updated = await api<CharacterFittingRecord>(`/fittings/${fitting.id}`, { method: "PATCH", body: JSON.stringify({ is_shared: !fitting.is_shared }) });

      replaceFitting(updated);

      setMessage(`${updated.name} is now ${updated.is_shared ? "shared" : "private"}.`);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to update fitting visibility");

    }

  }



  async function createDraft(fitting: CharacterFittingRecord) {

    setEditorBusy(true);

    setError(null);

    try {

      const draft = await api<CharacterFittingRecord>(`/fittings/${fitting.id}/draft`, { method: "POST", body: "{}" });

      replaceFitting(draft);

      setMessage(`Created editable draft from ${fitting.name}.`);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to create fitting draft");

    } finally {

      setEditorBusy(false);

    }

  }



  async function addDraftItemToFlag(fitting: CharacterFittingRecord | null, typeId: number | "", flag: string, quantity: number, clearSearch = false) {

    if (!fitting || typeId === "") return;

    setEditorBusy(true);

    setError(null);

    try {

      const updated = await api<CharacterFittingRecord>(`/fittings/${fitting.id}/items`, { method: "POST", body: JSON.stringify({ type_id: typeId, flag, quantity: Math.max(1, quantity || 1) }) });

      replaceFitting(updated);

      if (clearSearch) {

        setItemSearch("");

        setSelectedItemTypeId("");

        setDraftQuantity(1);

      }

      void loadSimulation(updated, simulationCharacterId, simulationHeat);

      setMessage("Draft fitting updated.");

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to add fitting item");

    } finally {

      setEditorBusy(false);

    }

  }



  async function addDraftItem(fitting: CharacterFittingRecord | null) {

    await addDraftItemToFlag(fitting, selectedItemTypeId, draftFlag, draftQuantity, true);

  }



  async function updateDraftItem(fitting: CharacterFittingRecord | null, item: FittingItem, changes: Partial<Pick<FittingItem, "flag" | "quantity" | "charge_type_id" | "simulation_state">>) {

    if (!fitting) return;

    setEditorBusy(true);

    setError(null);

    try {

      const updated = await api<CharacterFittingRecord>(`/fittings/${fitting.id}/items/${item.id}`, { method: "PATCH", body: JSON.stringify(changes) });

      replaceFitting(updated);

      void loadSimulation(updated, simulationCharacterId, simulationHeat);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to update fitting item");

    } finally {

      setEditorBusy(false);

    }

  }



  async function removeDraftItem(fitting: CharacterFittingRecord | null, item: FittingItem) {

    if (!fitting) return;

    setEditorBusy(true);

    setError(null);

    try {

      const updated = await api<CharacterFittingRecord>(`/fittings/${fitting.id}/items/${item.id}`, { method: "DELETE" });

      replaceFitting(updated);

      void loadSimulation(updated, simulationCharacterId, simulationHeat);

      setMessage(`${item.type_name} removed from draft.`);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to remove fitting item");

    } finally {

      setEditorBusy(false);

    }

  }



  async function readFittingClipboard() {

    setError(null);

    try {

      const text = await navigator.clipboard.readText();

      setImportText(text);

      setMessage(text.trim() ? "Clipboard fitting text loaded." : "Clipboard was empty.");

    } catch (err) {

      setError(err instanceof Error ? err.message : "Browser blocked clipboard read. Paste the fitting text into the box instead.");

    }

  }



  async function importFittingText() {

    if (importCharacterId === "") {

      setError("Choose the character who should own this imported draft.");

      return;

    }

    if (!importText.trim()) {

      setError("Paste an EFT-style fitting before importing.");

      return;

    }

    setImportBusy(true);

    setError(null);

    try {

      const result = await api<FittingImportResult>("/fittings/import-text", { method: "POST", body: JSON.stringify({ character_id: importCharacterId, text: importText }) });

      replaceFitting(result.fitting);

      setImportText("");

      void loadSimulation(result.fitting, simulationCharacterId, simulationHeat);

      setMessage(result.warnings.length > 0 ? `Imported ${result.fitting.name} as a draft with ${result.warnings.length} skipped line${result.warnings.length === 1 ? "" : "s"}.` : `Imported ${result.fitting.name} as an editable draft.`);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to import fitting text");

    } finally {

      setImportBusy(false);

    }

  }


  async function copyScratch() {

    await navigator.clipboard.writeText(scratch);

    setMessage("Fitting copied to clipboard.");

  }



  async function copyMissingSkillPlan() {

    const unresolved = simulation?.requirements.filter((row) => !row.met && /^Type \d+$/.test(row.skill_name)) ?? [];

    if (unresolved.length > 0) {

      setError("Some required skill names are still unresolved. Refresh/rebuild after the SDE import before creating an EVE skillplan.");

      return;

    }

    const plan = simulation ? fittingSkillPlanText(simulation.requirements) : "";

    if (!plan) {

      setMessage("No missing skills detected for this fitting.");

      return;

    }

    await navigator.clipboard.writeText(`${plan}\n`);

    setMessage("Missing fitting skills copied as a skillplan.");

  }



  async function loadSimulation(fitting: CharacterFittingRecord | null, characterId: number | "", heat = simulationHeat) {

    if (!fitting || characterId === "") {

      setSimulation(null);

      return;

    }

    setSimulationBusy(true);

    try {

      setSimulation(await api<FittingSimulation>(`/fittings/${fitting.id}/simulation?character_id=${characterId}&heat=${heat ? "true" : "false"}`));

    } catch (err) {

      setSimulation(null);

      setError(err instanceof Error ? err.message : "Fitting simulation failed");

    } finally {

      setSimulationBusy(false);

    }

  }



  useEffect(() => { void loadFittings().catch((err) => setError(err instanceof Error ? err.message : "Unable to load fittings")); }, []);

  useEffect(() => {

    if (!seed?.text) return;

    setFilter(seed.text);

    const term = seed.text.toLowerCase();

    const match = payload.fittings.find((fitting) => [fitting.ship_type_name, fitting.name].some((value) => value.toLowerCase().includes(term)));

    if (match) setSelectedId(match.id);

  }, [seed?.nonce, payload.fittings]);





  const filteredFittings = useMemo(() => {

    const term = filter.trim().toLowerCase();

    const rows = term ? payload.fittings.filter((fitting) => [fitting.name, fitting.ship_type_name, fitting.character_name, fitting.owner_display_name, fitting.description, fitting.is_draft ? "draft" : "esi"].filter(Boolean).some((value) => String(value).toLowerCase().includes(term))) : payload.fittings;

    return [...rows].sort((left, right) => Number(right.is_draft) - Number(left.is_draft) || left.ship_type_name.localeCompare(right.ship_type_name, undefined, { numeric: true, sensitivity: "base" }) || left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: "base" }));

  }, [payload.fittings, filter]);



  const selected = payload.fittings.find((fitting) => fitting.id === selectedId) ?? filteredFittings[0] ?? null;

  const syncToken = payload.sync_tokens.find((token) => token.token_id === syncTokenId) ?? null;

  const allPickerItems = useMemo(() => FITTING_PICKER_TABS.flatMap((tab) => itemCatalog[tab]), [itemCatalog]);

  const selectedSearchItem = selectedItemTypeId === "" ? null : allPickerItems.find((item) => item.type_id === selectedItemTypeId) ?? null;

  const pickerResults = useMemo(() => {

    const term = itemSearch.trim().toLowerCase();

    return itemCatalog[pickerTab]

      .map((item) => ({ ...item, bucket: item.bucket ?? fittingPickerBucket(item) }))

      .filter((item) => !term || [item.name, item.group_name, item.category_name, String(item.type_id)].filter(Boolean).some((value) => String(value).toLowerCase().includes(term)));

  }, [itemCatalog, itemSearch, pickerTab]);

  const groupedPickerResults = useMemo(() => {

    const groups = new Map<string, FittingSearchType[]>();

    for (const item of pickerResults) {

      const key = item.group_name || item.category_name || "Other";

      groups.set(key, [...(groups.get(key) ?? []), item]);

    }

    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));

  }, [pickerResults]);



  const activeCatalogCount = itemCatalog[pickerTab].length;

  useEffect(() => {

    if (!selected?.is_draft || !selected.can_manage || pickerTab === "Other" || activeCatalogCount > 0) return;

    let cancelled = false;

    setCatalogBusy(true);

    void api<FittingSearchType[]>(`/fittings/item-catalog?bucket=${encodeURIComponent(pickerTab)}&limit=12000`).then((rows) => {

      if (!cancelled) setItemCatalog((current) => ({ ...current, [pickerTab]: rows.map((row) => ({ ...row, bucket: fittingPickerBucket(row) })) }));

    }).catch((err) => {

      if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load fitting catalog");

    }).finally(() => {

      if (!cancelled) setCatalogBusy(false);

    });

    return () => { cancelled = true; };

  }, [pickerTab, selected?.id, selected?.is_draft, selected?.can_manage, activeCatalogCount]);



  useEffect(() => {

    if (!selected?.can_manage || itemCatalog.Ammo.length > 0) return;

    let cancelled = false;

    void api<FittingSearchType[]>("/fittings/item-catalog?bucket=Ammo&limit=12000").then((rows) => {

      if (!cancelled) setItemCatalog((current) => ({ ...current, Ammo: rows.map((row) => ({ ...row, bucket: fittingPickerBucket(row) })) }));

    }).catch((err) => {

      if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load charge catalog");

    });

    return () => { cancelled = true; };

  }, [selected?.id, selected?.can_manage, itemCatalog.Ammo.length]);



  const simulationCharacterOptions = useMemo(() => {

    const byId = new Map<number, FittingSyncToken>();

    for (const token of payload.sync_tokens) byId.set(token.character_id, token);

    return [...byId.values()].sort((left, right) => left.character_name.localeCompare(right.character_name));

  }, [payload.sync_tokens]);



  const groupedItems = useMemo(() => {

    const groups = new Map<string, FittingItem[]>();

    for (const item of selected?.items ?? []) groups.set(item.slot_group, [...(groups.get(item.slot_group) ?? []), item]);

    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));

  }, [selected]);



  const visualSlotGroups = useMemo(() => {

    const groups = [

      { key: "HiSlot", label: "High" },

      { key: "MedSlot", label: "Mid" },

      { key: "LoSlot", label: "Low" },

      { key: "RigSlot", label: "Rigs" },

      { key: "SubSystemSlot", label: "Subsystems" },

      { key: "ServiceSlot", label: "Services" },

    ];

    return groups.map((group) => {

      const items = (selected?.items ?? []).filter((item) => fittingSlotKey(item.flag) === group.key).sort((left, right) => left.flag.localeCompare(right.flag, undefined, { numeric: true }));

      const simulatedSlot = simulation?.slots.find((slot) => slot.key === group.key);

      const capacity = simulatedSlot?.capacity ?? Math.max(items.length, 0);

      return { ...group, items, capacity, used: simulatedSlot?.used ?? items.length, ok: simulatedSlot?.ok ?? true };

    }).filter((group) => group.capacity || group.items.length > 0);

  }, [selected, simulation]);



  const cargoHoldItems = useMemo(() => (selected?.items ?? []).filter((item) => fittingSlotKey(item.flag) === "Cargo").sort((left, right) => left.type_name.localeCompare(right.type_name, undefined, { numeric: true, sensitivity: "base" })), [selected]);



  const bayGroups = useMemo(() => [

    { key: "DroneBay", label: "Drones" },

    { key: "FighterBay", label: "Fighters" },

    { key: "Other", label: "Other" },

  ].map((group) => ({ ...group, items: (selected?.items ?? []).filter((item) => fittingSlotKey(item.flag) === group.key) })).filter((group) => group.items.length > 0), [selected]);



  const estimateByItemId = useMemo(() => {

    const rows = new Map<number, FittingWeaponEstimate>();

    for (const row of simulation?.stats?.offense.weapons ?? []) {

      if (row.item_id != null) rows.set(Number(row.item_id), row);

    }

    return rows;

  }, [simulation?.stats?.offense.weapons]);



  useEffect(() => { setScratch(selected?.copy_text ?? ""); }, [selected?.id, selected?.copy_text]);

  useEffect(() => { setSimulationCharacterId(selected?.character_id ?? simulationCharacterOptions[0]?.character_id ?? ""); }, [selected?.id, simulationCharacterOptions.length]);

  useEffect(() => { void loadSimulation(selected, simulationCharacterId, simulationHeat); }, [selected?.id, simulationCharacterId, simulationHeat]);



  function fittingTargetCount(targetKey: string) {

    return (selected?.items ?? []).filter((item) => fittingSlotKey(item.flag) === fittingSlotKey(targetKey)).length;

  }



  function chargeOptionsForItem(item: FittingItem) {

    return itemCatalog.Ammo.filter((charge) => chargeMatchesModule(item, charge)).slice(0, 450);

  }



  function slotStateClass(item: FittingItem | undefined) {

    if (!item) return "";

    const state = item.simulation_state ?? "online";

    const globallyHot = simulationHeat && state !== "offline" && ["High slots", "Medium slots", "Low slots"].includes(item.slot_group);

    return [state === "active" ? "state-active" : "", state === "overheated" || globallyHot ? "state-overheated" : "", state === "offline" ? "state-offline" : ""].filter(Boolean).join(" ");

  }



  async function cycleDraftItemState(item: FittingItem) {

    if (!selected?.can_manage || editorBusy) return;

    await updateDraftItem(selected, item, { simulation_state: nextFittingState(item.simulation_state) });

  }



  const fittedControlItems = useMemo(() => (selected?.items ?? [])

    .filter((item) => ["HiSlot", "MedSlot", "LoSlot", "RigSlot", "SubSystemSlot", "ServiceSlot"].includes(fittingSlotKey(item.flag)))

    .sort((left, right) => left.flag.localeCompare(right.flag, undefined, { numeric: true })), [selected]);



  const renderItemControls = (item: FittingItem, options: { showChargeSelector?: boolean } = {}) => {

    if (!selected?.can_manage) return null;

    const chargeOptions = chargeOptionsForItem(item);
    const itemSlotKey = fittingSlotKey(item.flag);
    const canShowChargeSelector = (options.showChargeSelector ?? true) && ["HiSlot", "MedSlot", "LoSlot", "SubSystemSlot", "ServiceSlot"].includes(itemSlotKey) && (chargeOptions.length > 0 || Boolean(item.charge_type_id));
    const actionClassName = [
      selected.is_draft ? "fitting-item-actions" : "fitting-item-actions simulation-only",
      canShowChargeSelector ? "has-charge-selector" : "no-charge-selector",
      ["Cargo", "DroneBay", "FighterBay"].includes(itemSlotKey) ? "bay-item-actions" : "",
    ].filter(Boolean).join(" ");

    return <div className={actionClassName}>

      {selected.is_draft && <select value={item.flag} disabled={editorBusy} onChange={(event) => void updateDraftItem(selected, item, { flag: event.target.value })}>{editableFlags.map((flag) => <option key={flag} value={flag}>{flagLabel(flag)}</option>)}</select>}

      {canShowChargeSelector && <select value={item.charge_type_id ?? ""} disabled={editorBusy || chargeOptions.length === 0} onChange={(event) => void updateDraftItem(selected, item, { charge_type_id: event.target.value ? Number(event.target.value) : null })}>

        <option value="">No charge/script</option>

        {chargeOptions.map((charge) => <option key={charge.type_id} value={charge.type_id}>{charge.name}</option>)}

      </select>}

      {selected.is_draft && <input type="number" min="1" value={item.quantity} disabled={editorBusy} onChange={(event) => void updateDraftItem(selected, item, { quantity: Number(event.target.value) || 1 })} />}

      <button type="button" className={`state-button state-${item.simulation_state ?? "online"}`} disabled={editorBusy} onClick={() => void cycleDraftItemState(item)}>{fittingStateLabel(item.simulation_state)}</button>

      {selected.is_draft && <button type="button" className="danger-button" disabled={editorBusy} onClick={() => void removeDraftItem(selected, item)}>Remove</button>}

    </div>;

  };



  return <section className="panel stacked fittings-page">

    <div className="section-heading">

      <div><h3>Saved Fittings</h3><p>Pull fittings from ESI, create editable EQM drafts, simulate readiness, and copy EFT-style text back out.</p></div>

      <div className="button-row compact"><button type="button" onClick={() => void loadFittings()}>Refresh</button></div>

    </div>

    {message && <div className="notice inline">{message}</div>}

    {error && <div className="mini-alert">{error}</div>}

    <FittingSyncControls tokens={payload.sync_tokens} syncToken={syncToken} syncTokenId={syncTokenId} busyTokenId={busyTokenId} onSyncTokenChange={setSyncTokenId} onSync={() => void syncFittings()} />

    <FittingImportPanel importCharacterId={importCharacterId} importText={importText} importBusy={importBusy} characterOptions={simulationCharacterOptions} onImportCharacterChange={setImportCharacterId} onImportTextChange={setImportText} onReadClipboard={() => void readFittingClipboard()} onImportText={() => void importFittingText()} />


    <div className="fittings-grid">

      <FittingListPanel filter={filter} fittings={filteredFittings} selectedId={selected?.id} onFilterChange={setFilter} onSelectFitting={setSelectedId} />

      <section className="fitting-detail-panel">

        {selected ? <>

          <div className="section-heading compact">

            <div><h3>{selected.ship_type_name}</h3><p>{selected.name} · {selected.character_name}{selected.owner_display_name ? ` · ${selected.owner_display_name}` : ""}</p></div>

            <div className="button-row compact">{selected.can_manage && !selected.is_draft && <button type="button" disabled={editorBusy} onClick={() => void createDraft(selected)}>Create draft</button>}{selected.can_manage && <button type="button" onClick={() => void toggleShare(selected)}>{selected.is_shared ? "Make private" : "Share fitting"}</button>}<button type="button" onClick={() => void copyScratch()}>Copy fitting</button></div>

          </div>

          <div className="fitting-sim-toolbar"><label>Simulate as<select value={simulationCharacterId} onChange={(event) => setSimulationCharacterId(event.target.value ? Number(event.target.value) : "")}><option value="">Choose character</option>{simulationCharacterOptions.map((token) => <option key={token.character_id} value={token.character_id}>{token.character_name}</option>)}</select></label><div className="segmented-control compact"><button type="button" className={!simulationHeat ? "active" : ""} onClick={() => setSimulationHeat(false)}>Cold</button><button type="button" className={simulationHeat ? "active hot" : ""} onClick={() => setSimulationHeat(true)}>Hot</button></div><span className={`fitting-sim-status sim-${simulation?.status ?? "unknown"}`}>{simulationBusy ? "Simulating" : simulation?.status === "pass" ? "Ready" : simulation?.status === "warning" ? "Needs attention" : "Dogma pending"}</span></div>

          <div className="fitting-summary-row">{Object.entries(selected.summary).map(([key, value]) => <span key={key}>{key}: <strong>{value}</strong></span>)}<span>{selected.is_draft ? "Draft" : "ESI synced"}</span><span>{selected.is_shared ? "Shared" : "Private"}</span>{selected.source_fitting_name && <span>From {selected.source_fitting_name}</span>}{selected.last_synced_at && <span>Synced {formatDateTime(selected.last_synced_at, preferredTimeZone(currentUser))}</span>}{selected.updated_at && <span>Edited {formatDateTime(selected.updated_at, preferredTimeZone(currentUser))}</span>}</div>

          {simulation?.notes.map((note) => <div key={note} className="scope-warn">{note}</div>)}

          {selected.description && <p className="muted">{selected.description}</p>}

          <FittingContextPanel fitting={selected} assets={assets} onOpenAssets={onOpenAssets} onOpenMarket={onOpenMarket} />

          {selected.can_manage && <div className="fitting-editor-panel fitting-editor-with-picker">

            {selected.is_draft ? <>

              <aside className="fitting-part-picker">

                <div className="section-heading compact"><div><h4>Part Picker</h4><p>Drag parts onto slots, bays, or cargo.</p></div></div>

                <label>Filter rack<input value={itemSearch} onChange={(event) => setItemSearch(event.target.value)} placeholder="Filter by name, group, or type ID" /></label>

                <div className="fitting-picker-tabs">{FITTING_PICKER_TABS.map((tab) => <button key={tab} type="button" className={pickerTab === tab ? "active" : ""} onClick={() => setPickerTab(tab)}>{tab}</button>)}</div>

                <div className="fitting-picker-results">

                  {catalogBusy && <p className="muted">Loading {pickerTab.toLowerCase()}...</p>}

                  {!catalogBusy && groupedPickerResults.map(([group, rows], index) => <details key={group} className="fitting-picker-group" open={index < 2 || Boolean(itemSearch.trim())}><summary>{group}<span>{rows.length.toLocaleString()}</span></summary>{rows.map((item) => <button key={item.type_id} type="button" draggable className={selectedItemTypeId === item.type_id ? "active fitting-picker-item" : "fitting-picker-item"} onClick={() => { setSelectedItemTypeId(item.type_id); setDraftFlag(defaultFlagForPickerItem(item)); }} onDoubleClick={() => void addDraftItemToFlag(selected, item.type_id, draftFlag, draftQuantity, false)} onDragStart={(event) => beginPickerDrag(event, item)}><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.name}<small>{item.group_name ?? `Type ${item.type_id}`}</small></span></button>)}</details>)}

                  {!catalogBusy && itemCatalog[pickerTab].length > 0 && pickerResults.length === 0 && <p className="empty">No {pickerTab.toLowerCase()} match this filter.</p>}

                  {!catalogBusy && itemCatalog[pickerTab].length === 0 && pickerTab !== "Other" && <p className="empty">No {pickerTab.toLowerCase()} loaded yet.</p>}

                  {pickerTab === "Other" && <p className="empty">Other items still use text fitting import or cargo search for now.</p>}

                </div>

              </aside>

              <section className="fitting-draft-targets">

                <div><h4>Draft Workshop</h4><p>{selectedSearchItem ? `Selected ${selectedSearchItem.name}` : "Select or drag an item from the picker."}</p></div>

                <div className="fitting-editor-controls">

                  <label>Slot<select value={draftFlag} onChange={(event) => setDraftFlag(event.target.value)}>{editableFlags.map((flag) => <option key={flag} value={flag}>{flagLabel(flag)}</option>)}</select></label>

                  <label>Qty<input type="number" min="1" value={draftQuantity} onChange={(event) => setDraftQuantity(Math.max(1, Number(event.target.value) || 1))} /></label>

                  <button type="button" disabled={editorBusy || selectedItemTypeId === ""} onClick={() => void addDraftItem(selected)}>Add selected</button>

                </div>

                <div className="fitting-drop-bays">

                  {[{ flag: "Cargo", label: "Cargo hold" }, { flag: "DroneBay", label: "Drone bay" }, { flag: "FighterBay", label: "Fighter bay" }].map((target) => <div key={target.flag} className="fitting-drop-target" onDragOver={allowFittingDrop} onDrop={(event) => void dropPickerItem(event, target.flag)}><strong>{target.label}</strong><span>{fittingTargetCount(target.flag)} item{fittingTargetCount(target.flag) === 1 ? "" : "s"}</span></div>)}

                </div>

              </section>

            </> : <div className="scope-warn">Create a draft before changing modules, rigs, drones, or cargo. The original ESI fitting stays untouched.</div>}

          </div>}

          <div className="fitting-workbench">

            <div className="fitting-visual">

              <div className="ship-core"><img src={eveTypeImageUrl(selected.ship_type_id, "render", 512)} alt="" loading="lazy" onError={(event) => fallbackShipImage(event, selected.ship_type_id)} /><div><strong>{selected.ship_type_name}</strong><span>{selected.name}</span></div></div>

              {visualSlotGroups.map((group) => <div key={group.key} className={`slot-band ${group.ok ? "" : "over-limit"}`}>

                <span>{group.label} <small>{group.used}/{group.capacity ?? "?"}</small></span>

                <div>{Array.from({ length: Math.max(group.capacity ?? 0, group.items.length) }).map((_, index) => {

                  const item = group.items[index];

                  const targetFlag = `${group.key}${index}`;

                  return <div

                    key={`${group.key}-${index}`}

                    className={[item ? "slot-dot filled" : "slot-dot", item ? slotStateClass(item) : "", selected.is_draft && selected.can_manage ? "droppable" : ""].filter(Boolean).join(" ")}

                    title={item ? `${fittingItemTooltip(item, estimateByItemId.get(item.id))}\nClick to cycle module state.` : `${group.label} slot ${index + 1}`}

                    onClick={() => item && void cycleDraftItemState(item)}

                    onDragOver={allowFittingDrop}

                    onDrop={(event) => void dropPickerItem(event, targetFlag)}

                  >{item ? <>

                    <img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} />

                    <span>{item.type_name}</span>

                    {item.charge_type_name && <small className="slot-charge">{item.charge_type_name}</small>}

                    <em>{fittingStateLabel(item.simulation_state)}</em>

                    {selected.is_draft && selected.can_manage && <button type="button" className="slot-remove-button" aria-label={`Remove ${item.type_name}`} disabled={editorBusy} onClick={(event) => { event.stopPropagation(); void removeDraftItem(selected, item); }}>x</button>}

                  </> : <span>Empty</span>}</div>;

                })}</div>

              </div>)}

            </div>

            <div className="fitting-sim-panel">

              <h4>Character Readiness</h4>

              {simulation ? <><div className="fitting-readiness-grid"><span>Missing skills<strong>{simulation.summary.missing_skills}</strong></span><span>Slot issues<strong>{simulation.summary.slot_issues}</strong></span><span>Resource issues<strong>{simulation.summary.resource_issues}</strong></span></div><div className="resource-bars">{Object.entries(simulation.resources).map(([key, resource]) => <div key={key} className={resource.ok ? "" : "over-limit"}><span>{key === "powergrid" ? "Powergrid" : key.charAt(0).toUpperCase() + key.slice(1)}<strong>{resource.capacity == null ? `${resource.used.toFixed(1)} / ?` : `${resource.used.toFixed(1)} / ${Number(resource.capacity).toFixed(1)}`}</strong></span><i><b style={{ width: `${Math.min(100, resource.percent ?? 0)}%` }} /></i></div>)}</div><FittingStatsPanel stats={simulation.stats} /><div className="section-heading compact fitting-skillcheck-heading"><h4>Skill Checks</h4>{fittingSkillPlanText(simulation.requirements) && <button type="button" onClick={() => void copyMissingSkillPlan()}>Create Skillplan</button>}</div><div className="mini-list fitting-requirements">{simulation.requirements.filter((row) => !row.met).slice(0, 12).map((row) => <div key={`${row.source_type_id}-${row.skill_type_id}`} className="missing"><strong>{row.skill_name} {romanLevel(row.required_level)}</strong><span>{row.source_name} · trained {romanLevel(row.trained_level)}</span></div>)}{simulation.requirements.length > 0 && simulation.requirements.every((row) => row.met) && <p className="empty">All detected skill requirements met.</p>}{simulation.requirements.length === 0 && <p className="empty">No skill requirements available yet.</p>}</div></> : <p className="empty">Choose a character to simulate this fit.</p>}

            </div>

          </div>

          {selected.can_manage && fittedControlItems.length > 0 && <article className="fitting-module-controls">

            <div><h4>Module States and Charges</h4><span>Use ammo/script groups for charge assignment, then use module rows for position, quantity, and online state.</span></div>

            <FittingChargeGroups selected={selected} fittedControlItems={fittedControlItems} ammoCatalog={itemCatalog.Ammo} editorBusy={editorBusy} api={api} setEditorBusy={setEditorBusy} setError={setError} setMessage={setMessage} onFittingUpdated={(updated) => { replaceFitting(updated); void loadSimulation(updated, simulationCharacterId, simulationHeat); }} />

            <div>{fittedControlItems.map((item) => <div key={item.id} className="fitting-module-control-row"><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.type_name}<small>{item.flag}{item.charge_type_name ? ` · ${item.charge_type_name}` : ""}</small></span>{renderItemControls(item, { showChargeSelector: false })}</div>)}</div>

          </article>}

          {(cargoHoldItems.length > 0 || (selected.is_draft && selected.can_manage)) && <article className="fitting-cargo-hold fitting-drop-target" onDragOver={allowFittingDrop} onDrop={(event) => void dropPickerItem(event, "Cargo")}><div><h4>Cargo Hold</h4><span>{cargoHoldItems.length.toLocaleString()} carried item{cargoHoldItems.length === 1 ? "" : "s"}</span></div><div>{cargoHoldItems.length > 0 ? cargoHoldItems.map((item) => <div key={item.id} className="fitting-bay-item" title={fittingItemTooltip(item, estimateByItemId.get(item.id))}><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.type_name}</span><strong>{item.quantity > 1 ? `x${item.quantity.toLocaleString()}` : ""}</strong>{renderItemControls(item)}</div>) : <p className="empty">Drop ammo, charges, or cargo here.</p>}</div></article>}

          {bayGroups.length > 0 && <div className="fitting-bays">{bayGroups.map((group) => <article key={group.key}><h4>{group.label}</h4>{group.items.map((item) => <div key={item.id} className="fitting-bay-item" title={fittingItemTooltip(item, estimateByItemId.get(item.id))}><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.type_name}</span><strong>{item.quantity > 1 ? `x${item.quantity.toLocaleString()}` : ""}</strong>{renderItemControls(item)}</div>)}</article>)}</div>}

          <details><summary>Text item groups</summary><div className="fitting-items">{groupedItems.map(([group, items]) => <article key={group}><h4>{group}</h4>{items.map((item) => <div key={item.id}><span>{item.type_name}</span><strong>{item.quantity > 1 ? `x${item.quantity}` : ""}</strong><small>{item.flag}</small>{renderItemControls(item)}</div>)}</article>)}</div></details>

          <label>Scratchpad<textarea className="fitting-scratch" value={scratch} onChange={(event) => setScratch(event.target.value)} /></label>

          <p className="muted">Scratchpad edits are local text edits. Draft edits above are saved to EQM and re-simulated.</p>

        </> : <p className="empty">Sync or select a fitting to begin.</p>}

      </section>

    </div>

  </section>;

}
