type PilotSecurityStatusProps = {
  securityStatus?: number | null;
  compact?: boolean;
};

function statusClass(securityStatus: number): string {
  if (securityStatus <= -5) return "criminal";
  if (securityStatus < 0) return "negative";
  if (securityStatus >= 5) return "excellent";
  return "neutral";
}

export function PilotSecurityStatus({ securityStatus, compact = false }: PilotSecurityStatusProps) {
  if (typeof securityStatus !== "number" || Number.isNaN(securityStatus)) return null;
  const label = securityStatus.toFixed(1);
  return <span className={`pilot-security-status ${statusClass(securityStatus)} ${compact ? "compact" : ""}`} title={`Pilot security status ${label}`}>Sec {label}</span>;
}