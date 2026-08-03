import type { JumpFreighterRoute } from "../../types/navigation";

export type ReplotConstraint = {
  name: string;
  selectedAlternate: boolean;
};

export function orderedReplotConstraints(
  route: JumpFreighterRoute,
  jumpIndex: number,
  alternateName: string,
  retainedWaypointNames?: ReadonlySet<string>,
): ReplotConstraint[] {
  const normalizedAlternate = alternateName.trim().toLocaleLowerCase();
  const rows: Array<ReplotConstraint & { position: number; rank: number }> = [];

  for (const waypoint of route.requested_waypoints ?? []) {
    if (retainedWaypointNames && !retainedWaypointNames.has(waypoint.name)) continue;
    if (waypoint.name.trim().toLocaleLowerCase() === normalizedAlternate) continue;
    const position = route.jumps.find((jump) => jump.to_system.system_id === waypoint.system_id)?.jump_index ?? Number.MAX_SAFE_INTEGER;
    rows.push({ name: waypoint.name, selectedAlternate: false, position, rank: 1 });
  }

  rows.push({ name: alternateName, selectedAlternate: true, position: jumpIndex, rank: 0 });
  rows.sort((left, right) => left.position - right.position || left.rank - right.rank || left.name.localeCompare(right.name));
  return rows.map(({ name, selectedAlternate }) => ({ name, selectedAlternate }));
}

export function droppedReplotWaypoints(route: JumpFreighterRoute, retainedWaypointNames: ReadonlySet<string>): string[] {
  return (route.requested_waypoints ?? [])
    .map((waypoint) => waypoint.name)
    .filter((name) => !retainedWaypointNames.has(name));
}