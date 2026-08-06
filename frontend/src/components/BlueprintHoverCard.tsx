import { createPortal } from "react-dom";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import "./blueprintHoverCard.css";

export type BlueprintUse = {
  active?: boolean;
  activity?: string | null;
  status?: string | null;
  job_id?: number | null;
  runs?: number | null;
  facility?: string | null;
  installer?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

export type BlueprintHoverDetails = {
  name: string;
  owner?: string | null;
  kind?: "BPO" | "BPC" | null;
  materialEfficiency?: number | null;
  timeEfficiency?: number | null;
  materialEfficiencyLabel?: string | null;
  timeEfficiencyLabel?: string | null;
  location?: string | null;
  runsRemaining?: number | null;
  use?: BlueprintUse | null;
  definitionOnly?: boolean;
  note?: string | null;
};

export function blueprintHoverDetails(blueprint: {
  blueprint_type_name: string;
  owner_name?: string | null;
  is_copy?: boolean | null;
  material_efficiency?: number | null;
  time_efficiency?: number | null;
  location_name?: string | null;
  runs_remaining?: number | null;
  active_use?: BlueprintUse | null;
}): BlueprintHoverDetails {
  return {
    name: blueprint.blueprint_type_name,
    owner: blueprint.owner_name,
    kind: blueprint.is_copy == null ? null : blueprint.is_copy ? "BPC" : "BPO",
    materialEfficiency: blueprint.material_efficiency,
    timeEfficiency: blueprint.time_efficiency,
    location: blueprint.location_name,
    runsRemaining: blueprint.runs_remaining,
    use: blueprint.active_use,
  };
}

export function BlueprintHoverCard({ details, children, className = "" }: { details: BlueprintHoverDetails; children: ReactNode; className?: string }) {
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const [position, setPosition] = useState({ left: 16, top: 16 });
  const cardRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!anchor || !cardRef.current) return;
    const card = cardRef.current.getBoundingClientRect();
    const gutter = 12;
    const left = Math.max(gutter, Math.min(anchor.left, window.innerWidth - card.width - gutter));
    const below = anchor.bottom + 8;
    const top = below + card.height <= window.innerHeight - gutter
      ? below
      : Math.max(gutter, anchor.top - card.height - 8);
    setPosition({ left, top });
  }, [anchor]);

  const use = details.use;
  const isActive = Boolean(use?.active);
  const efficiencyKnown = details.materialEfficiency != null || details.timeEfficiency != null || details.materialEfficiencyLabel || details.timeEfficiencyLabel;

  return <span
    className={`blueprint-hover-target ${className}`.trim()}
    onMouseEnter={(event) => setAnchor(event.currentTarget.getBoundingClientRect())}
    onMouseLeave={() => setAnchor(null)}
  >
    {children}
    {anchor && createPortal(<div ref={cardRef} className="blueprint-hover-card" style={position} role="tooltip">
      <header><strong>{details.name}</strong><span className={isActive ? "in-use" : "available"}>{isActive ? "In use" : details.definitionOnly ? "Blueprint reference" : "Available"}</span></header>
      <div className="blueprint-hover-meta">
        <span><b>ME</b>{details.materialEfficiencyLabel ?? (details.materialEfficiency != null ? details.materialEfficiency : "—")}</span>
        <span><b>TE</b>{details.timeEfficiencyLabel ?? (details.timeEfficiency != null ? details.timeEfficiency : "—")}</span>
        <span><b>Type</b>{details.kind ?? "—"}</span>
        {details.runsRemaining != null && <span><b>Runs</b>{details.runsRemaining.toLocaleString()}</span>}
      </div>
      <p><b>Location</b>{details.location ?? (details.definitionOnly ? "No synced owned instance" : "Location unavailable")}</p>
      {details.owner && <p><b>Owner</b>{details.owner}</p>}
      {use && <div className={`blueprint-use-summary ${isActive ? "active" : ""}`}>
        <strong>{isActive ? use.activity ?? "Active industry job" : use.activity ?? "Not currently in use"}</strong>
        <span>{[use.status, use.runs != null ? `${use.runs.toLocaleString()} run${use.runs === 1 ? "" : "s"}` : null].filter(Boolean).join(" · ")}</span>
        {(use.facility || use.installer) && <small>{[use.facility, use.installer ? `Installed by ${use.installer}` : null].filter(Boolean).join(" · ")}</small>}
        {use.end_date && <small>Ends {new Date(use.end_date).toLocaleString()}</small>}
      </div>}
      {!use && !details.definitionOnly && <div className="blueprint-use-summary"><strong>Not currently in use</strong></div>}
      {details.definitionOnly && !efficiencyKnown && <small className="blueprint-hover-note">ME/TE and location apply to an owned blueprint instance.</small>}
      {details.note && <small className="blueprint-hover-note">{details.note}</small>}
    </div>, document.body)}
  </span>;
}
