import { MapIcon } from "lucide-react";

import { eveSecurityClass, eveSecurityLabel } from "../../lib/evePresentation";
import type { JumpFreighterAlternate, JumpFreighterJump } from "../../types/navigation";

function stationLabel(alternate: JumpFreighterAlternate) {
  if (alternate.station_status === "no_station") return "NO STATION";
  if (alternate.station_status === "red_only") return "ONLY RED STATIONS";
  return `${alternate.station_count.toLocaleString()} station${alternate.station_count === 1 ? "" : "s"}`;
}

export function JumpAlternatePicker({
  jump,
  fuelTypeName,
  numberFormatter,
  selectedSystemId,
  onSelect,
  onReplot,
  busy = false,
}: {
  jump: JumpFreighterJump;
  fuelTypeName: string;
  numberFormatter: Intl.NumberFormat;
  selectedSystemId?: number;
  onSelect: (systemId?: number) => void;
  onReplot: (systemId: number) => void;
  busy?: boolean;
}) {
  const selected = jump.alternates.find((alternate) => alternate.system.system_id === selectedSystemId);

  return <section className="jf-alternate-panel">
    <div className="jf-alternate-heading">
      <div>
        <strong>Alternate jump point</strong>
        <small>Reachable from {jump.from_system.name}. Select one to inspect it, then replot the full route through it.</small>
      </div>
      <select
        aria-label={`Alternate jump point for jump ${jump.jump_index}`}
        value={selectedSystemId ?? ""}
        onChange={(event) => onSelect(event.target.value ? Number(event.target.value) : undefined)}
      >
        <option value="">Show {jump.alternates.length} reachable alternate{jump.alternates.length === 1 ? "" : "s"}</option>
        {jump.alternates.map((alternate) => <option key={alternate.system.system_id} value={alternate.system.system_id}>
          {alternate.system.name} · {alternate.distance_ly} LY · {stationLabel(alternate)}
        </option>)}
      </select>
    </div>
    {jump.alternates.length === 0 && <p className="empty">No alternate low/null systems can reach this leg and still rejoin the next planned waypoint within range.</p>}
    {selected && <div className="jf-alternate-detail">
      <div>
        <strong>{selected.system.name}</strong>
        <span className={`security-badge ${eveSecurityClass(selected.system.security_status)}`}>{eveSecurityLabel(selected.system.security_status)}</span>
        <span className={`jf-station-status station-${selected.station_status}`}>{stationLabel(selected)}</span>
      </div>
      <dl>
        <div><dt>Jump</dt><dd>{selected.distance_ly} LY</dd></div>
        <div><dt>Fuel</dt><dd>{numberFormatter.format(selected.fuel_units)} {fuelTypeName}</dd></div>
        <div><dt>24h kills</dt><dd>{selected.kills_24h.count.toLocaleString()}</dd></div>
        <div><dt>Last-hour traffic</dt><dd>{selected.jump_activity?.observations ? `${selected.jump_activity.jumps_last_hour.toLocaleString()} jumps · ${selected.jump_activity.ship_kills_last_hour.toLocaleString()} ship kills · ${selected.jump_activity.pod_kills_last_hour.toLocaleString()} pod kills` : "Unavailable"}</dd></div>
        <div><dt>{selected.can_rejoin ? "To next waypoint" : "From planned destination"}</dt><dd>{selected.can_rejoin ? `${selected.rejoin_distance_ly ?? 0} LY` : `${selected.distance_to_planned_ly} LY`}</dd></div>
      </dl>
      <button type="button" className="jf-replot-alternate" disabled={busy} onClick={() => onReplot(selected.system.system_id)}><MapIcon size={17} /> {busy ? "Replotting" : `Replot via ${selected.system.name}`}</button>
    </div>}
  </section>;
}
