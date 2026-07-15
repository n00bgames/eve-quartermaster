import { eveTypeImageUrl, hideBrokenImage } from "../fittings/FittingSupport";
import type { ImplantDogmaAttribute, ImplantDogmaEffect, JumpCloneImplant } from "../../types/jumpClones";

function dogmaName(row: ImplantDogmaAttribute | ImplantDogmaEffect): string {
  return row.display_name || row.name;
}

function dogmaValue(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function unitSuffix(unitId?: number | null): string {
  if (unitId == null) return "";
  if (unitId === 105) return "%";
  return ` · unit ${unitId}`;
}

type ImplantDogmaChipProps = {
  implant: JumpCloneImplant;
};

export function ImplantDogmaChip({ implant }: ImplantDogmaChipProps) {
  const attributes = implant.dogma?.attributes ?? [];
  const effects = implant.dogma?.effects ?? [];
  const visibleAttributes = attributes.slice(0, 12);
  const visibleEffects = effects.slice(0, 8);

  return (
    <span className="implant-chip" tabIndex={0}>
      <img src={eveTypeImageUrl(implant.type_id, "icon", 32)} alt="" loading="lazy" onError={hideBrokenImage} />
      <span className="implant-chip-label">{implant.slot ? `Slot ${implant.slot}` : "Implant"} · {implant.name}</span>
      <span className="implant-dogma-card" role="tooltip">
        <span className="implant-dogma-heading">
          <img src={eveTypeImageUrl(implant.type_id, "icon", 64)} alt="" loading="lazy" onError={hideBrokenImage} />
          <span>
            <strong>{implant.name}</strong>
            <small>{implant.slot ? `Slot ${implant.slot}` : "Implant"}{implant.group_name ? ` · ${implant.group_name}` : ""} · Type {implant.type_id}</small>
          </span>
        </span>
        {visibleAttributes.length > 0 ? (
          <span className="implant-dogma-section">
            <b>Dogma attributes</b>
            {visibleAttributes.map((row) => (
              <span key={row.attribute_id} className="implant-dogma-row">
                <span>{dogmaName(row)}</span>
                <strong>{dogmaValue(row.value)}{unitSuffix(row.unit_id)}</strong>
              </span>
            ))}
            {attributes.length > visibleAttributes.length && <small>+{attributes.length - visibleAttributes.length} more attributes</small>}
          </span>
        ) : <small>No dogma attributes loaded for this implant.</small>}
        {visibleEffects.length > 0 && (
          <span className="implant-dogma-section">
            <b>Effects</b>
            {visibleEffects.map((row) => (
              <span key={row.effect_id} className="implant-dogma-row">
                <span>{dogmaName(row)}</span>
                <strong>{row.is_default ? "Default" : "Effect"}</strong>
              </span>
            ))}
            {effects.length > visibleEffects.length && <small>+{effects.length - visibleEffects.length} more effects</small>}
          </span>
        )}
      </span>
    </span>
  );
}