import React, { useState } from "react";
import type { Asset, Blueprint, InventoryFamilyFilter } from "../../types/inventory";
import { BlueprintHoverCard, blueprintHoverDetails } from "../../components/BlueprintHoverCard";
import { EveItemName } from "../clientLinks/EveClientLinks";
import { blueprintFamily, blueprintSubtype, inventoryFamilyLabels, matchesInventoryFamily, sortedUnique, visibleAssetLocations, visibleAssetQuantity } from "../../lib/inventory";
import { matchesBlueprintTechnology, type BlueprintTechFilter, type BlueprintProductFilter } from "./blueprintFilters";
import "./blueprintFilters.css";
const numberFormatter = new Intl.NumberFormat();

export function BlueprintList({ blueprints, assets = [], renderExportControls, missingBlueprints, onOpenMarket, onOpenAssets }: { blueprints: Blueprint[]; assets?: Asset[]; renderExportControls?: (filters: Record<string, unknown>) => React.ReactNode; missingBlueprints?: React.ReactNode; onOpenMarket?: (text: string) => void; onOpenAssets?: (itemName: string) => void }) {

  const [kindFilter, setKindFilter] = useState<"all" | "bpo" | "bpc">("all");

  const [ownerFilter, setOwnerFilter] = useState<string | null>(null);

  const [categoryFilter, setCategoryFilter] = useState<InventoryFamilyFilter>("all");

  const [techFilter, setTechFilter] = useState<BlueprintTechFilter>("all");
  const [productFilter, setProductFilter] = useState<BlueprintProductFilter>("all");

  const [subtypeFilter, setSubtypeFilter] = useState("");

  const [searchText, setSearchText] = useState("");

  const [sortKey, setSortKey] = useState<"name" | "me" | "te">("name");

  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const bpoCount = blueprints.filter((blueprint) => !blueprint.is_copy).length;

  const bpcCount = blueprints.filter((blueprint) => blueprint.is_copy).length;

  const ownerOptions = sortedUnique(blueprints.map((blueprint) => blueprint.owner_name));

  const ownerCounts = new Map<string, number>();

  for (const blueprint of blueprints) ownerCounts.set(blueprint.owner_name, (ownerCounts.get(blueprint.owner_name) ?? 0) + 1);

  const blueprintCategoryOptions: InventoryFamilyFilter[] = ["all", "ships", "ammunition", "drones", "rigs", "reactions", "ram", "capital-construction"];

  const kindFilteredBlueprints = kindFilter === "all" ? blueprints : blueprints.filter((blueprint) => kindFilter === "bpc" ? blueprint.is_copy : !blueprint.is_copy);

  const ownerFilteredBlueprints = ownerFilter ? kindFilteredBlueprints.filter((blueprint) => blueprint.owner_name === ownerFilter) : kindFilteredBlueprints;

  const categoryFilteredBlueprints = ownerFilteredBlueprints.filter((blueprint) => matchesBlueprintTechnology(blueprint, techFilter, productFilter)).filter((blueprint) => matchesInventoryFamily(categoryFilter, blueprintFamily(blueprint), Boolean(blueprint.capital_construction_related)));

  const subtypeOptions = sortedUnique(categoryFilteredBlueprints.map(blueprintSubtype));

  const subtypeFilteredBlueprints = subtypeFilter ? categoryFilteredBlueprints.filter((blueprint) => blueprintSubtype(blueprint) === subtypeFilter) : categoryFilteredBlueprints;

  const searchNeedle = searchText.trim().toLowerCase();

  const filteredBlueprints = searchNeedle ? subtypeFilteredBlueprints.filter((blueprint) => [blueprint.blueprint_type_name, blueprint.product_type_name, blueprint.owner_name, blueprint.location_name, blueprint.product_category_name, blueprint.product_group_name, blueprint.is_copy ? "BPC" : "BPO", blueprint.research_shadow ? "in research" : null, blueprint.active_use?.activity, `ME ${blueprint.material_efficiency}`, `TE ${blueprint.time_efficiency}`].filter(Boolean).join(" ").toLowerCase().includes(searchNeedle)) : subtypeFilteredBlueprints;

  const visibleBlueprints = [...filteredBlueprints].sort((left, right) => {

    const direction = sortDirection === "asc" ? 1 : -1;

    if (sortKey === "name") return left.blueprint_type_name.localeCompare(right.blueprint_type_name, undefined, { numeric: true, sensitivity: "base" }) * direction;

    const leftValue = sortKey === "me" ? left.material_efficiency : left.time_efficiency;

    const rightValue = sortKey === "me" ? right.material_efficiency : right.time_efficiency;

    return (leftValue - rightValue || left.blueprint_type_name.localeCompare(right.blueprint_type_name, undefined, { numeric: true, sensitivity: "base" })) * direction;

  });



  function chooseSort(nextSortKey: "name" | "me" | "te") {

    if (sortKey === nextSortKey) {

      setSortDirection((current) => current === "asc" ? "desc" : "asc");

      return;

    }

    setSortKey(nextSortKey);

    setSortDirection(nextSortKey === "name" ? "asc" : "desc");

  }



  function sortLabel(key: "name" | "me" | "te") {

    return sortKey === key ? (sortDirection === "asc" ? "up" : "down") : "";

  }



  function applyBlueprintSubtypeFilter(blueprint: Blueprint) {

    const family = blueprintFamily(blueprint);

    setCategoryFilter(family === "other" ? "all" : family);

    setSubtypeFilter(blueprintSubtype(blueprint) ?? "");

  }


  return <div className="blueprint-browser">
    <div className="blueprint-controls">
      <div className="blueprint-filter">
        <button type="button" className={kindFilter === "all" ? "active" : ""} onClick={() => setKindFilter("all")}>All <span>{blueprints.length.toLocaleString()}</span></button>
        <button type="button" className={kindFilter === "bpo" ? "active" : ""} onClick={() => setKindFilter("bpo")}>BPO <span>{bpoCount.toLocaleString()}</span></button>
        <button type="button" className={kindFilter === "bpc" ? "active" : ""} onClick={() => setKindFilter("bpc")}>BPC <span>{bpcCount.toLocaleString()}</span></button>
      </div>
      <div className="blueprint-filter sort">
        <button type="button" className={sortKey === "name" ? "active" : ""} onClick={() => chooseSort("name")}>A-Z <span>{sortLabel("name")}</span></button>
        <button type="button" className={sortKey === "me" ? "active" : ""} onClick={() => chooseSort("me")}>ME <span>{sortLabel("me")}</span></button>
        <button type="button" className={sortKey === "te" ? "active" : ""} onClick={() => chooseSort("te")}>TE <span>{sortLabel("te")}</span></button>
      </div>
    </div>
    <div className="blueprint-filter family-filter">
      {blueprintCategoryOptions.map((family) => <button type="button" key={family} className={categoryFilter === family ? "active" : ""} onClick={() => { setCategoryFilter(family); setSubtypeFilter(""); }}>{inventoryFamilyLabels[family]}</button>)}
    </div>
    <div className="blueprint-tech-row">
      <label>Tech level<select aria-label="Tech level" value={techFilter} onChange={(event) => { setTechFilter(event.target.value as BlueprintTechFilter); setSubtypeFilter(""); }}><option value="all">All tech levels</option><option value="2">T2</option><option value="3">T3</option></select></label>
      <label>Product category<select aria-label="Product category" value={productFilter} onChange={(event) => { setProductFilter(event.target.value as BlueprintProductFilter); setCategoryFilter("all"); setSubtypeFilter(""); }}><option value="all">All products</option><option value="ships">Ships</option><option value="modules">Modules / subsystems</option></select></label>
    </div>
    <div className="blueprint-refine-row">
      <label className="blueprint-search">Search blueprints<input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Blueprint, product, owner, location, hull class, ammo, rig" /></label>
      <label>Subtype<select value={subtypeFilter} onChange={(event) => setSubtypeFilter(event.target.value)}><option value="">All subtypes</option>{subtypeOptions.map((subtype) => <option key={subtype} value={subtype}>{subtype}</option>)}</select></label>
    </div>
    <div className="blueprint-filter owners"><button type="button" className={ownerFilter === null ? "active" : ""} onClick={() => setOwnerFilter(null)}>All owners <span>{blueprints.length.toLocaleString()}</span></button>{ownerOptions.map((owner) => <button type="button" key={owner} className={ownerFilter === owner ? "active" : ""} onClick={() => setOwnerFilter(owner)}>{owner} <span>{(ownerCounts.get(owner) ?? 0).toLocaleString()}</span></button>)}</div>
    {renderExportControls?.({ kind: kindFilter, owner: ownerFilter, category: categoryFilter, tech_level: techFilter, product_category: productFilter, subtype: subtypeFilter || null, search: searchText.trim(), sort_key: sortKey, sort_direction: sortDirection })}
    <p className="muted" role="status">Showing {visibleBlueprints.length.toLocaleString()} of {blueprints.length.toLocaleString()} owned blueprints.</p>
    <div className="card-list">{visibleBlueprints.map((bp) => { const ownedOutput = visibleAssetQuantity(assets, bp.product_type_name); const outputLocations = visibleAssetLocations(assets, bp.product_type_name); return <article key={bp.id}><BlueprintHoverCard details={blueprintHoverDetails(bp)}><strong>{bp.blueprint_type_name}</strong></BlueprintHoverCard><span><button type="button" className="inline-filter" onClick={() => setOwnerFilter(bp.owner_name)}>{bp.owner_name}</button> · {bp.product_type_name ?? "No product"}</span>{bp.product_group_name && <small>{bp.product_category_name ? `${bp.product_category_name} / ` : ""}{bp.product_group_name}</small>}{bp.product_type_name && <div className="blueprint-context"><span className={ownedOutput > 0 ? "context-owned" : "context-missing"}>Owned output: {numberFormatter.format(ownedOutput)}</span>{outputLocations.length > 0 && <small>{outputLocations.join(" | ")}</small>}<div className="context-actions">{onOpenAssets && <button type="button" onClick={() => onOpenAssets(bp.product_type_name!)}>Assets</button>}{onOpenMarket && <button type="button" onClick={() => onOpenMarket(`1 ${bp.product_type_name}`)}>Price output</button>}</div></div>}<div className="badge-row"><button type="button" className="bp-badge" onClick={() => chooseSort("me")}>ME {bp.material_efficiency}</button><button type="button" className="bp-badge" onClick={() => chooseSort("te")}>TE {bp.time_efficiency}</button><button type="button" className={bp.is_copy ? "bp-badge copy" : "bp-badge original"} onClick={() => setKindFilter(bp.is_copy ? "bpc" : "bpo")}>{bp.is_copy ? "BPC" : "BPO"}</button>{bp.research_shadow && <span className="bp-badge research">In research · {bp.active_use?.activity ?? "Active"}</span>}{bp.product_group_name && <button type="button" className="bp-badge" onClick={() => applyBlueprintSubtypeFilter(bp)}>{bp.product_group_name}</button>}{bp.capital_construction_related && <button type="button" className="bp-badge original" onClick={() => { setCategoryFilter("capital-construction"); setSubtypeFilter(""); }}>Capital chain</button>}</div></article>; })}{blueprints.length === 0 && <p className="empty">No blueprints yet.</p>}{blueprints.length > 0 && visibleBlueprints.length === 0 && <p className="empty">{searchNeedle ? `No blueprints match "${searchText.trim()}".` : "No blueprints match this filter."}</p>}</div>
    {missingBlueprints}
  </div>;

}
