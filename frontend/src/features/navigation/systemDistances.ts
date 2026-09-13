export type SystemObject = {
  object_id: string; name: string; kind: string; source: string;
  position: { x: number; y: number; z: number } | null;
};
export type SystemObjects = { system_id: number; system_name: string; objects: SystemObject[]; checked_at: string | null; message: string; coverage_note: string };
export const AU_METRES = 149_597_870_700;
export function distanceAU(from: SystemObject | undefined, to: SystemObject | undefined): number | null {
  if (!from?.position || !to?.position) return null;
  const a = from.position, b = to.position;
  if (![a.x, a.y, a.z, b.x, b.y, b.z].every(Number.isFinite)) return null;
  return Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z) / AU_METRES;
}
export function roughWarpSeconds(distance: number | null, speed: string, align: string): number | null {
  if (distance === null || !speed.trim() || !align.trim()) return null;
  const warp = Number(speed), seconds = Number(align);
  if (![distance, warp, seconds].every(Number.isFinite) || distance < 0 || warp <= 0 || seconds < 0) return null;
  const estimate = distance === 0 ? 0 : distance / warp + seconds;
  return Number.isFinite(estimate) ? estimate : null;
}
export function formatDistance(distance: number | null): string {
  if (distance === null) return "Position unavailable";
  if (distance > 0 && distance < 0.000001) return "<0.000001 AU";
  return `${distance.toLocaleString(undefined, { maximumFractionDigits: 6 })} AU`;
}
