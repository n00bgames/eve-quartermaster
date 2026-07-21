export function isAdminRole(role: string): boolean {
  return role === "host" || role === "admin";
}

export function isHostRole(role: string): boolean {
  return role === "host";
}
