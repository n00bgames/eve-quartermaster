import type { Blueprint } from "../../types/inventory";

const numberFormatter = new Intl.NumberFormat();

function blueprintSyncTime(blueprint: Blueprint): number {
  const value = blueprint.last_synced_at ? new Date(blueprint.last_synced_at).getTime() : 0;
  return Number.isNaN(value) ? 0 : value;
}

export function BlueprintPreview({ blueprints, onOpenIndustry }: { blueprints: Blueprint[]; onOpenIndustry?: () => void }) {
  const originals = blueprints.filter((blueprint) => !blueprint.is_copy).length;
  const copies = blueprints.length - originals;
  const recentBlueprints = [...blueprints]
    .sort((left, right) => blueprintSyncTime(right) - blueprintSyncTime(left) || left.blueprint_type_name.localeCompare(right.blueprint_type_name, undefined, { numeric: true, sensitivity: "base" }))
    .slice(0, 6);

  return <div className="blueprint-preview">
    <div className="status-grid compact">
      <article><span>Total</span><strong>{numberFormatter.format(blueprints.length)}</strong></article>
      <article><span>BPO</span><strong>{numberFormatter.format(originals)}</strong></article>
      <article><span>BPC</span><strong>{numberFormatter.format(copies)}</strong></article>
    </div>
    <div className="mini-list">
      {recentBlueprints.map((blueprint) => <div key={blueprint.id}>
        <strong>{blueprint.blueprint_type_name}</strong>
        <span>{blueprint.owner_name} · {blueprint.is_copy ? "BPC" : "BPO"}{blueprint.product_type_name ? ` · ${blueprint.product_type_name}` : ""}</span>
      </div>)}
      {blueprints.length === 0 && <p className="empty">No blueprints synced yet.</p>}
    </div>
    {onOpenIndustry && <div className="button-row compact"><button type="button" onClick={onOpenIndustry}>Open Blueprint Library</button></div>}
  </div>;
}
