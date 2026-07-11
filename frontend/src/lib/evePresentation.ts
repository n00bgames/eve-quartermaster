type NamedSystem = { name?: string | null };

export function isUedamaSystem(system?: NamedSystem | null): boolean {
  return (system?.name ?? "").trim().toLowerCase() === "uedama";
}

export function eveSecurityClass(status?: number | null): string {
  if (typeof status !== "number") return "security-unknown";
  const bucket = Math.max(0, Math.min(10, Math.round(status * 10)));
  return `security-${String(bucket).padStart(2, "0")}`;
}

export function eveSecurityLabel(status?: number | null): string {
  return typeof status === "number" ? status.toFixed(1) : "?";
}
