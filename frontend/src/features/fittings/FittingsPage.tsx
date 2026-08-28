import { useEffect, useMemo, useState } from "react";
import type { DragEvent } from "react";

import { formatDateTime, preferredTimeZone } from "../../lib/time";
import { FittingChargeGroups } from "./FittingChargeGroups";
import { FittingImportPanel, FittingListPanel, FittingSyncControls } from "./FittingShellPanels";
import { cargoBayLabel, chargeMatchesModule, eveTypeImageUrl, fallbackShipImage, FittingContextPanel, FittingStatsPanel, fittingItemTooltip, fittingSkillPlanText, fittingSlotKey, fittingStateLabel, formatVolumeM3, hideBrokenImage, isCargoBayKey, nextFittingState, romanLevel } from "./FittingSupport";
import { FITTING_PICKER_TABS, fittingPickerBucket } from "../../types/fittings";
import type { CharacterFittingRecord, FittingCargoBay, FittingImportResult, FittingItem, FittingPickerTab, FittingSearchType, FittingSeed, FittingSimulation, FittingSyncToken, FittingsPayload, FittingWeaponEstimate } from "../../types/fittings";
import type { JumpClonePayload } from "../../types/jumpClones";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type FittingsUser = { timezone?: string };
type FittingsAsset = { type_id: number; quantity: number; owner_name: string; location_name?: string | null; location_flag?: string | null };
type FittingAssetSummary = { type_id: number; quantity: number; stacks: number; locations: { owner: string; location: string; flag?: string | null; quantity: number }[] };
type CargoBayGroup = FittingCargoBay & { items: FittingItem[] };

const DEFAULT_CARGO_BAY_KEYS = ["Cargo"] as const;

function fittingItemVolume(item: FittingItem): number {
  return Number(item.volume ?? 0) * Math.max(1, Number(item.quantity ?? 1));
}

function cargoBayUsageText(bay: Pick<FittingCargoBay, "used" | "capacity">): string {
  return `${formatVolumeM3(bay.used)} / ${bay.capacity == null ? "?" : formatVolumeM3(bay.capacity)}`;
}

function fittingEngineLabel(simulation: FittingSimulation | null): string {
  if (!simulation) return "Hybrid engine";
  if (simulation.resource_engine_used === "rust") return "Hybrid · Rust resources + Python stats";
  if (simulation.resource_engine_used === "python-fallback") return "Python fallback · resources + stats";
  if (simulation.resource_engine_used?.startsWith("python-shadow")) {
    return `Hybrid shadow · Python served${simulation.resource_engine_shadow_match === false ? " · mismatch" : " · Rust matched"}`;
  }
  return "Python resources + stats";
}

type FittingsPageProps = {
  currentUser: FittingsUser;
  assets: FittingsAsset[];
  seed?: FittingSeed | null;
  onOpenAssets: (itemName?: string) => void;
  onOpenMarket: (text: string) => void;
  api: ApiClient;
};
export function FittingsPage({ currentUser, assets, seed, onOpenAssets, onOpenMarket, api }: FittingsPageProps) {

  const [payload, setPayload] = useState<FittingsPayload>({ fittings: [], sync_tokens: [], send_tokens: [], editable_flags: [] });

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [syncTokenId, setSyncTokenId] = useState<number | "">("");

  const [simulationCharacterId, setSimulationCharacterId] = useState<number | "">("");

  const [simulationHeat, setSimulationHeat] = useState(false);

  const [simulationImplantChoice, setSimulationImplantChoice] = useState("");

  const [jumpClonePayload, setJumpClonePayload] = useState<JumpClonePayload>({ characters: [], clones: [], custom_sets: [], sync_tokens: [] });

  const [simulation, setSimulation] = useState<FittingSimulation | null>(null);

  const [contextAssetSummaries, setContextAssetSummaries] = useState<FittingAssetSummary[]>([]);

  const [contextAssetBusy, setContextAssetBusy] = useState(false);

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

  const [sendPanelOpen, setSendPanelOpen] = useState(false);

  const [sendTokenId, setSendTokenId] = useState<number | "">("");

  const [sendBusy, setSendBusy] = useState(false);

  const [authBusy, setAuthBusy] = useState(false);



  const editableFlags = payload.editable_flags.length > 0 ? payload.editable_flags : ["HiSlot0", "MedSlot0", "LoSlot0", "RigSlot0", "DroneBay", "Cargo"];



  function replaceFitting(updated: CharacterFittingRecord) {

    setPayload((current) => {

      const exists = current.fittings.some((row) => row.id === updated.id);

      return { ...current, fittings: exists ? current.fittings.map((row) => row.id === updated.id ? updated : row) : [updated, ...current.fittings] };

    });

    setSelectedId(updated.id);

  }



  function flagLabel(flag: string) {

    if (isCargoBayKey(flag)) return cargoBayLabel(flag);

    return flag.replace("HiSlot", "High ").replace("MedSlot", "Mid ").replace("LoSlot", "Low ").replace("RigSlot", "Rig ").replace("SubSystemSlot", "Subsystem ").replace("ServiceSlot", "Service ");

  }


  function itemText(item: FittingSearchType) {
    return [item.name, item.group_name ?? "", item.category_name ?? ""].join(" ").toLowerCase();
  }

  function defaultFlagForPickerItem(item: FittingSearchType) {

    const bucket = item.bucket ?? fittingPickerBucket(item);
    const haystack = itemText(item);

    if (bucket === "Rigs") return "RigSlot0";

    if (bucket === "Drones") return haystack.includes("fighter") ? "FighterBay" : "DroneBay";

    if (bucket === "Ammo") return "Cargo";

    const highTokens = ["launcher", "turret", "smartbomb", "cynosural", "probe launcher", "cloak", "salvager", "tractor beam", "mining laser", "strip miner"];
    const lowTokens = ["armor", "damage control", "ballistic control", "gyrostabilizer", "heat sink", "magnetic field", "reactor control", "power diagnostic", "capacitor power relay", "shield power relay", "shield flux coil", "nanofiber", "inertia", "overdrive", "cargohold", "drone damage", "tracking enhancer", "weapon upgrade", "mining laser upgrade", "co-processor", "signal amplifier"];
    const midTokens = ["shield", "propulsion", "afterburner", "microwarpdrive", "capacitor booster", "target painter", "stasis webifier", "warp disrupt", "warp scram", "tracking computer", "guidance computer", "sensor booster", "ecm", "scanner", "analyzer"];

    if (highTokens.some((token) => haystack.includes(token))) return "HiSlot0";
    if (lowTokens.some((token) => haystack.includes(token))) return "LoSlot0";
    if (midTokens.some((token) => haystack.includes(token))) return "MedSlot0";

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
    api<JumpClonePayload>("/jump-clones").then(setJumpClonePayload).catch(() => setJumpClonePayload({ characters: [], clones: [], custom_sets: [], sync_tokens: [] }));

    const normalizedPayload = { ...next, send_tokens: next.send_tokens ?? [], editable_flags: next.editable_flags ?? [] };

    setPayload(normalizedPayload);

    setSelectedId((current) => current ?? next.fittings[0]?.id ?? null);

    setSyncTokenId((current) => current === "" ? next.sync_tokens.find((token) => token.can_sync)?.token_id ?? next.sync_tokens[0]?.token_id ?? "" : current);

    setImportCharacterId((current) => current === "" ? next.sync_tokens.find((token) => token.can_sync)?.character_id ?? next.sync_tokens[0]?.character_id ?? "" : current);

    setSendTokenId((current) => current === "" ? normalizedPayload.send_tokens.find((token) => token.has_fitting_write_scope)?.token_id ?? normalizedPayload.send_tokens[0]?.token_id ?? "" : current);

  }



  async function authorizeFittingWrite() {

    setAuthBusy(true);

    setError(null);

    try {

      const auth = await api<{ ready: boolean; url?: string; message?: string }>("/esi/auth-url?scope_group=fittings");

      if (!auth.ready || !auth.url) throw new Error(auth.message || "EVE SSO is not configured");

      window.location.assign(auth.url);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to start EVE SSO");

      setAuthBusy(false);

    }

  }



  async function sendToEve(fitting: CharacterFittingRecord) {

    if (sendTokenId === "") return;

    setSendBusy(true);

    setError(null);

    try {

      const result = await api<{ fitting_name: string; character_name: string }>(`/fittings/${fitting.id}/send-to-eve`, { method: "POST", body: JSON.stringify({ token_id: sendTokenId }) });

      setMessage(`${result.fitting_name} was saved to ${result.character_name}'s EVE fitting library.`);

      setSendPanelOpen(false);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to send fitting to EVE");

    } finally {

      setSendBusy(false);

    }

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

      const normalizedQuantity = isCargoBayKey(fittingSlotKey(flag)) ? Math.max(1, quantity || 1) : 1;
      const updated = await api<CharacterFittingRecord>(`/fittings/${fitting.id}/items`, { method: "POST", body: JSON.stringify({ type_id: typeId, flag, quantity: normalizedQuantity }) });

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



  async function loadSimulation(fitting: CharacterFittingRecord | null, characterId: number | "", heat = simulationHeat, implantChoice = simulationImplantChoice) {

    if (!fitting || characterId === "") {

      setSimulation(null);

      return;

    }

    setSimulationBusy(true);

    try {

      const params = new URLSearchParams({ character_id: String(characterId), heat: heat ? "true" : "false" });

      if (implantChoice.startsWith("clone:")) params.set("jump_clone_id", implantChoice.slice("clone:".length));
      if (implantChoice.startsWith("set:")) params.set("implant_set_id", implantChoice.slice("set:".length));

      setSimulation(await api<FittingSimulation>(`/fittings/${fitting.id}/simulation?${params.toString()}`));

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

  const selectedContextTypeIds = useMemo(() => {
    if (!selected) return [];
    return [...new Set([selected.ship_type_id, ...selected.items.map((item) => item.type_id)].filter((typeId) => typeId > 0))];
  }, [selected]);

  const selectedContextKey = selectedContextTypeIds.join(",");

  useEffect(() => {
    if (!selectedContextKey) {
      setContextAssetSummaries([]);
      setContextAssetBusy(false);
      return;
    }
    let cancelled = false;
    setContextAssetBusy(true);
    api<{ items: FittingAssetSummary[] }>("/context/assets-summary", { method: "POST", body: JSON.stringify({ type_ids: selectedContextTypeIds }) })
      .then((result) => { if (!cancelled) setContextAssetSummaries(result.items ?? []); })
      .catch(() => { if (!cancelled) setContextAssetSummaries([]); })
      .finally(() => { if (!cancelled) setContextAssetBusy(false); });
    return () => { cancelled = true; };
  }, [api, selectedContextKey]);

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




  const implantOptions = useMemo(() => {

    const characterId = simulationCharacterId === "" ? null : Number(simulationCharacterId);

    const cloneOptions = jumpClonePayload.clones
      .filter((clone) => characterId !== null && clone.character_id === characterId)
      .map((clone) => ({ value: `clone:${clone.id}`, label: `${clone.name} (${clone.implants.length} implants)` }));

    const setOptions = jumpClonePayload.custom_sets
      .filter((set) => !set.character_id || characterId === null || set.character_id === characterId)
      .map((set) => ({ value: `set:${set.id}`, label: `${set.name} (${set.implants.length} implants)` }));

    return [...cloneOptions, ...setOptions];

  }, [jumpClonePayload, simulationCharacterId]);
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

  const sendToken = useMemo(() => payload.send_tokens.find((token) => token.token_id === sendTokenId) ?? null, [payload.send_tokens, sendTokenId]);



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



  const cargoBayGroups = useMemo<CargoBayGroup[]>(() => {

    const statByKey = new Map((simulation?.stats?.cargo_bays ?? []).map((bay) => [bay.key, bay]));

    const itemsByKey = new Map<string, FittingItem[]>();

    for (const item of selected?.items ?? []) {

      const key = fittingSlotKey(item.flag);

      if (!isCargoBayKey(key)) continue;

      itemsByKey.set(key, [...(itemsByKey.get(key) ?? []), item]);

    }

    const keys = new Set<string>();

    for (const bay of simulation?.stats?.cargo_bays ?? []) keys.add(bay.key);

    for (const key of itemsByKey.keys()) keys.add(key);

    if (selected?.is_draft && selected.can_manage) for (const key of DEFAULT_CARGO_BAY_KEYS) keys.add(key);

    return [...keys].map((key) => {

      const stat = statByKey.get(key);

      const items = [...(itemsByKey.get(key) ?? [])].sort((left, right) => left.type_name.localeCompare(right.type_name, undefined, { numeric: true, sensitivity: "base" }));

      const used = stat?.used ?? items.reduce((sum, item) => sum + fittingItemVolume(item), 0);

      const capacity = stat?.capacity ?? (key === "Cargo" ? selected?.ship_capacity ?? null : null);

      const ok = stat?.ok ?? (capacity == null || used <= Number(capacity) + 0.0001);

      return {

        key,

        label: stat?.label ?? cargoBayLabel(key),

        used,

        capacity,

        ok,

        percent: stat?.percent ?? (capacity && capacity > 0 ? Math.min(999, used / Number(capacity) * 100) : null),

        items,

      };

    }).filter((bay) => bay.capacity != null || bay.used > 0 || bay.items.length > 0 || (selected?.is_draft && selected.can_manage && DEFAULT_CARGO_BAY_KEYS.includes(bay.key as typeof DEFAULT_CARGO_BAY_KEYS[number])));

  }, [selected, simulation?.stats?.cargo_bays]);



  const cargoBayTotals = useMemo(() => {

    const used = cargoBayGroups.reduce((sum, bay) => sum + Number(bay.used ?? 0), 0);

    const capacity = cargoBayGroups.reduce((sum, bay) => bay.capacity == null ? sum : sum + Number(bay.capacity), 0);

    return { used, capacity: capacity > 0 ? capacity : null };

  }, [cargoBayGroups]);


  const estimateByItemId = useMemo(() => {

    const rows = new Map<number, FittingWeaponEstimate>();

    for (const row of simulation?.stats?.offense.weapons ?? []) {

      if (row.item_id != null) rows.set(Number(row.item_id), row);

    }

    return rows;

  }, [simulation?.stats?.offense.weapons]);



  useEffect(() => { setScratch(selected?.copy_text ?? ""); }, [selected?.id, selected?.copy_text]);

  useEffect(() => { setSimulationCharacterId(selected?.character_id ?? simulationCharacterOptions[0]?.character_id ?? ""); }, [selected?.id, simulationCharacterOptions.length]);

  useEffect(() => { void loadSimulation(selected, simulationCharacterId, simulationHeat, simulationImplantChoice); }, [selected?.id, simulationCharacterId, simulationHeat, simulationImplantChoice]);



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
      isCargoBayKey(itemSlotKey) ? "bay-item-actions" : "",
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

            <div className="button-row compact">{selected.can_manage && !selected.is_draft && <button type="button" disabled={editorBusy} onClick={() => void createDraft(selected)}>Create draft</button>}{selected.can_manage && <button type="button" onClick={() => void toggleShare(selected)}>{selected.is_shared ? "Make private" : "Share fitting"}</button>}<button type="button" onClick={() => setSendPanelOpen((open) => !open)}>Send to EVE</button><button type="button" onClick={() => void copyScratch()}>Copy fitting</button></div>

          </div>

          {sendPanelOpen && <div className="fitting-send-panel">

            <div><strong>Send {selected.name} to EVE</strong><span>Choose one of your linked characters. ESI saves a new copy in that character's fitting library.</span></div>

            <label>Target character<select value={sendTokenId} onChange={(event) => setSendTokenId(event.target.value ? Number(event.target.value) : "")}><option value="">Choose character</option>{payload.send_tokens.map((token) => <option key={token.token_id} value={token.token_id}>{token.character_name}{token.has_fitting_write_scope ? "" : " · authorization required"}</option>)}</select></label>

            <div className="button-row compact"><button type="button" onClick={() => setSendPanelOpen(false)}>Cancel</button>{sendToken?.has_fitting_write_scope ? <button type="button" disabled={sendBusy} onClick={() => void sendToEve(selected)}>{sendBusy ? "Sending" : "Send fitting"}</button> : <button type="button" disabled={authBusy} onClick={() => void authorizeFittingWrite()}>{authBusy ? "Opening EVE SSO" : payload.send_tokens.length > 0 ? "Authorize with EVE" : "Link a character with EVE"}</button>}</div>

            {sendToken && !sendToken.has_fitting_write_scope && <div className="scope-warn">Select this same character on EVE SSO to grant <code>{"esi-fittings.write_fittings.v1"}</code>, then return here and send the fit.</div>}

            {payload.send_tokens.length === 0 && <div className="scope-warn">No characters are linked to your EQM account yet. Link one through EVE SSO first.</div>}

          </div>}

          <div className="fitting-sim-toolbar"><label>Simulate as<select value={simulationCharacterId} onChange={(event) => setSimulationCharacterId(event.target.value ? Number(event.target.value) : "")}><option value="">Choose character</option>{simulationCharacterOptions.map((token) => <option key={token.character_id} value={token.character_id}>{token.character_name}</option>)}</select></label><label>Implants<select value={simulationImplantChoice} onChange={(event) => setSimulationImplantChoice(event.target.value)}><option value="">No implants</option>{implantOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><div className="segmented-control compact"><button type="button" className={!simulationHeat ? "active" : ""} onClick={() => setSimulationHeat(false)}>Cold</button><button type="button" className={simulationHeat ? "active hot" : ""} onClick={() => setSimulationHeat(true)}>Hot</button></div><span className="fitting-dev-warning">{fittingEngineLabel(simulation)} · values still in development</span><span className={`fitting-sim-status sim-${simulation?.status ?? "unknown"}`}>{simulationBusy ? "Simulating" : simulation?.status === "pass" ? "Ready" : simulation?.status === "warning" ? "Needs attention" : "Dogma pending"}</span></div>

          <div className="fitting-summary-row">{Object.entries(selected.summary).map(([key, value]) => <span key={key}>{key}: <strong>{value}</strong></span>)}<span>{selected.is_draft ? "Draft" : "ESI synced"}</span><span>{selected.is_shared ? "Shared" : "Private"}</span>{selected.source_fitting_name && <span>From {selected.source_fitting_name}</span>}{selected.last_synced_at && <span>Synced {formatDateTime(selected.last_synced_at, preferredTimeZone(currentUser))}</span>}{selected.updated_at && <span>Edited {formatDateTime(selected.updated_at, preferredTimeZone(currentUser))}</span>}</div>

          {simulation?.notes.map((note) => <div key={note} className="scope-warn">{note}</div>)}

          {selected.description && <p className="muted">{selected.description}</p>}

          <FittingContextPanel fitting={selected} assets={assets} assetSummaries={contextAssetSummaries} contextLoading={contextAssetBusy} onOpenAssets={onOpenAssets} onOpenMarket={onOpenMarket} />

          {selected.can_manage && <div className="fitting-editor-panel fitting-editor-with-picker">

            {selected.is_draft ? <>

              <aside className="fitting-part-picker">

                <div className="section-heading compact"><div><h4>Part Picker</h4><p>Drag parts onto slots, bays, or cargo.</p></div></div>

                <label>Filter rack<input value={itemSearch} onChange={(event) => setItemSearch(event.target.value)} placeholder="Filter by name, group, or type ID" /></label>

                <div className="fitting-picker-tabs">{FITTING_PICKER_TABS.map((tab) => <button key={tab} type="button" className={pickerTab === tab ? "active" : ""} onClick={() => setPickerTab(tab)}>{tab}</button>)}</div>

                <div className="fitting-picker-results">

                  {catalogBusy && <p className="muted">Loading {pickerTab.toLowerCase()}...</p>}

                  {!catalogBusy && groupedPickerResults.map(([group, rows], index) => <details key={group} className="fitting-picker-group" open={index < 2 || Boolean(itemSearch.trim())}><summary>{group}<span>{rows.length.toLocaleString()}</span></summary>{rows.map((item) => <button key={item.type_id} type="button" draggable className={selectedItemTypeId === item.type_id ? "active fitting-picker-item" : "fitting-picker-item"} onClick={() => { setSelectedItemTypeId(item.type_id); setDraftFlag(defaultFlagForPickerItem(item)); }} onDoubleClick={() => void addDraftItemToFlag(selected, item.type_id, defaultFlagForPickerItem(item), draftQuantity, false)} onDragStart={(event) => beginPickerDrag(event, item)}><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.name}<small>{item.group_name ?? `Type ${item.type_id}`}</small></span></button>)}</details>)}

                  {!catalogBusy && itemCatalog[pickerTab].length > 0 && pickerResults.length === 0 && <p className="empty">No {pickerTab.toLowerCase()} match this filter.</p>}

                  {!catalogBusy && itemCatalog[pickerTab].length === 0 && pickerTab !== "Other" && <p className="empty">No {pickerTab.toLowerCase()} loaded yet.</p>}

                  {pickerTab === "Other" && <p className="empty">Other items still use text fitting import or cargo search for now.</p>}

                </div>

              </aside>

              <section className="fitting-draft-targets">

                <div><h4>Draft Workshop</h4><p>{selectedSearchItem ? `Selected ${selectedSearchItem.name}` : "Select or drag an item from the picker."}</p></div>

                <div className="fitting-editor-controls">

                  <label>Slot<select value={draftFlag} onChange={(event) => setDraftFlag(event.target.value)}>{editableFlags.map((flag) => <option key={flag} value={flag}>{flagLabel(flag)}</option>)}</select></label>

                  {isCargoBayKey(fittingSlotKey(draftFlag)) && <label>Qty<input type="number" min="1" value={draftQuantity} onChange={(event) => setDraftQuantity(Math.max(1, Number(event.target.value) || 1))} /></label>}

                  <button type="button" disabled={editorBusy || selectedItemTypeId === ""} onClick={() => void addDraftItem(selected)}>Add selected</button>

                </div>

                <div className="fitting-drop-bays">

                  {cargoBayGroups.filter((bay) => bay.key === "Cargo" || bay.capacity != null || bay.items.length > 0).map((target) => <div key={target.key} className={target.ok ? "fitting-drop-target" : "fitting-drop-target over-limit"} onDragOver={allowFittingDrop} onDrop={(event) => void dropPickerItem(event, target.key)}><strong>{target.label}</strong><span>{fittingTargetCount(target.key)} item{fittingTargetCount(target.key) === 1 ? "" : "s"} · {cargoBayUsageText(target)}</span></div>)}

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

              <h4>Character Readiness{simulation ? ` · ${simulation.character_name}` : ""}</h4>

              {simulation ? <><div className="fitting-readiness-grid"><span>Missing skills<strong>{simulation.summary.missing_skills}</strong></span><span>Slot issues<strong>{simulation.summary.slot_issues}</strong></span><span>Resource issues<strong>{simulation.summary.resource_issues}</strong></span></div><div className="resource-bars">{Object.entries(simulation.resources).map(([key, resource]) => <div key={key} className={resource.ok ? "" : "over-limit"}><span>{key === "powergrid" ? "Powergrid" : key.charAt(0).toUpperCase() + key.slice(1)}<strong>{resource.capacity == null ? `${resource.used.toFixed(1)} / ?` : `${resource.used.toFixed(1)} / ${Number(resource.capacity).toFixed(1)}`}</strong></span><i><b style={{ width: `${Math.min(100, resource.percent ?? 0)}%` }} /></i></div>)}</div><FittingStatsPanel stats={simulation.stats} /><div className="section-heading compact fitting-skillcheck-heading"><h4>Skill Checks</h4>{fittingSkillPlanText(simulation.requirements) && <button type="button" onClick={() => void copyMissingSkillPlan()}>Create Skillplan</button>}</div><div className="mini-list fitting-requirements">{simulation.requirements.filter((row) => !row.met).slice(0, 12).map((row) => <div key={`${row.source_type_id}-${row.skill_type_id}`} className="missing"><strong>{row.skill_name} {romanLevel(row.required_level)}</strong><span>{row.source_name} · trained {romanLevel(row.trained_level)}</span></div>)}{simulation.requirements.length > 0 && simulation.requirements.every((row) => row.met) && <p className="empty">All detected skill requirements met.</p>}{simulation.requirements.length === 0 && <p className="empty">No skill requirements available yet.</p>}</div></> : <p className="empty">Choose a character to simulate this fit.</p>}

            </div>

          </div>

          {selected.can_manage && fittedControlItems.length > 0 && <article className="fitting-module-controls">

            <div><h4>Module States and Charges</h4><span>Use ammo/script groups for charge assignment, then use module rows for position, quantity, and online state.</span></div>

            <FittingChargeGroups selected={selected} fittedControlItems={fittedControlItems} ammoCatalog={itemCatalog.Ammo} editorBusy={editorBusy} api={api} setEditorBusy={setEditorBusy} setError={setError} setMessage={setMessage} onFittingUpdated={(updated) => { replaceFitting(updated); void loadSimulation(updated, simulationCharacterId, simulationHeat); }} />

            <div>{fittedControlItems.map((item) => <div key={item.id} className="fitting-module-control-row"><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.type_name}<small>{item.flag}{item.charge_type_name ? ` · ${item.charge_type_name}` : ""}</small></span>{renderItemControls(item, { showChargeSelector: false })}</div>)}</div>

          </article>}

          {cargoBayGroups.length > 0 && <article className="fitting-cargo-hold fitting-cargo-card"><div><h4>Cargo</h4><span>{formatVolumeM3(cargoBayTotals.used)} carried{cargoBayTotals.capacity == null ? "" : ` / ${formatVolumeM3(cargoBayTotals.capacity)} known capacity`}</span></div><div className="cargo-bay-grid">{cargoBayGroups.map((bay) => <section key={bay.key} className={bay.ok ? "cargo-bay-section fitting-drop-target" : "cargo-bay-section fitting-drop-target over-limit"} onDragOver={allowFittingDrop} onDrop={(event) => void dropPickerItem(event, bay.key)}><div className="cargo-bay-heading"><h5>{bay.label}</h5><span>{cargoBayUsageText(bay)}</span></div>{bay.capacity != null && <i className="cargo-bay-meter"><b style={{ width: `${Math.min(100, bay.percent ?? 0)}%` }} /></i>}<div className="cargo-bay-items">{bay.items.length > 0 ? bay.items.map((item) => <div key={item.id} className="fitting-bay-item" title={fittingItemTooltip(item, estimateByItemId.get(item.id))}><img src={eveTypeImageUrl(item.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} /><span>{item.type_name}</span><strong>{item.quantity > 1 ? `x${item.quantity.toLocaleString()}` : ""}</strong>{renderItemControls(item)}</div>) : <p className="empty">Drop items here.</p>}</div></section>)}</div></article>}
          <details><summary>Text item groups</summary><div className="fitting-items">{groupedItems.map(([group, items]) => <article key={group}><h4>{group}</h4>{items.map((item) => <div key={item.id}><span>{item.type_name}</span><strong>{item.quantity > 1 ? `x${item.quantity}` : ""}</strong><small>{item.flag}</small>{renderItemControls(item)}</div>)}</article>)}</div></details>

          <label>Scratchpad<textarea className="fitting-scratch" value={scratch} onChange={(event) => setScratch(event.target.value)} /></label>

          <p className="muted">Scratchpad edits are local text edits. Draft edits above are saved to EQM and re-simulated.</p>

        </> : <p className="empty">Sync or select a fitting to begin.</p>}

      </section>

    </div>

  </section>;

}
