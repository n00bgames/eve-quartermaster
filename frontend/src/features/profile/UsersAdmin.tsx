import {AdminRecovery} from "./PasswordRecovery";
import { useEffect, useState, type ReactElement, type ReactNode } from "react";

import type { EqmCharacter } from "../../types/characters";
import type { ProfileUserAccount } from "../../types/profile";
import type { RoleDefinition } from "../../types/settings";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type ManagedFormComponent = (props: { children: ReactNode; onSubmit: (form: FormData) => Promise<void>; submitLabel?: string }) => ReactElement;

type UserInvite = {
  id: number;
  email: string;
  role: string;
  roles?: string[];
  status?: string;
  created_by_display_name?: string | null;
  created_at?: string | null;
  expires_at?: string | null;
  accepted_at?: string | null;
  revoked_at?: string | null;
  invite_url?: string;
};

type UsersAdminProps = {
  currentUser: ProfileUserAccount;
  api: ApiClient;
  ManagedForm: ManagedFormComponent;
  accountLabel: (user: ProfileUserAccount) => string;
};

export function UsersAdmin({ currentUser, api, ManagedForm, accountLabel }: UsersAdminProps) {
  const [users, setUsers] = useState<ProfileUserAccount[]>([]);
  const [invites, setInvites] = useState<UserInvite[]>([]);
  const [characters, setCharacters] = useState<EqmCharacter[]>([]);
  const [accounts, setAccounts] = useState<ProfileUserAccount[]>([]);
  const [roleDefinitions, setRoleDefinitions] = useState<RoleDefinition[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [latestInviteUrl, setLatestInviteUrl] = useState<string | null>(null);
  const [userError, setUserError] = useState<string | null>(null);

  const roles = roleDefinitions.length ? roleDefinitions.map((role) => role.name) : ["host", "admin", "director", "fleet_commander", "officer", "member", "intel_analyst", "quartermaster", "view_only"];
  const roleLabel = (roleName: string) => roleDefinitions.find((role) => role.name === roleName)?.display_name ?? roleName;

  async function loadUsers() {
    setUsers(await api<ProfileUserAccount[]>("/auth/users"));
  }

  async function loadRoles() {
    setRoleDefinitions(await api<RoleDefinition[]>("/auth/roles"));
  }

  async function loadInvites() {
    setInvites(await api<UserInvite[]>("/auth/invites"));
  }

  async function loadCharacterAssignments() {
    const [visibleCharacters, assignableAccounts] = await Promise.all([
      api<EqmCharacter[]>("/characters"),
      api<ProfileUserAccount[]>("/characters/accounts"),
    ]);

    setCharacters(visibleCharacters);
    setAccounts(assignableAccounts);
  }

  async function runUserAction(action: () => Promise<string>, refreshInvites = false) {
    setUserError(null);

    try {
      const nextMessage = await action();
      setMessage(nextMessage);
      await Promise.all([loadUsers(), loadCharacterAssignments()]);
      if (refreshInvites) await loadInvites();
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "User action failed");
    }
  }

  async function createAccount(form: FormData) {
    await runUserAction(async () => {
      const user = await api<ProfileUserAccount>("/auth/users", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), display_name: form.get("display_name"), password: form.get("password"), roles: form.getAll("roles") }),
      });

      return `${user.display_name} created.`;
    });
  }

  async function createInvite(form: FormData) {
    await runUserAction(async () => {
      const invite = await api<UserInvite>("/auth/invites", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), roles: form.getAll("roles") }),
      });

      if (invite.invite_url) {
        setLatestInviteUrl(invite.invite_url);
        await navigator.clipboard.writeText(invite.invite_url).catch(() => undefined);
      }

      return `Invite generated for ${invite.email}.`;
    }, true);
  }

  async function updateRoles(userId: number, assignedRoles: string[]) {
    await runUserAction(async () => {
      const user = await api<ProfileUserAccount>(`/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify({ roles: assignedRoles }) });
      return `${user.display_name} roles: ${(user.roles ?? [user.role]).map(roleLabel).join(", ")}.`;
    });
  }

  async function updateDisplayName(userId: number, form: FormData) {
    await runUserAction(async () => {
      const user = await api<ProfileUserAccount>(`/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify({ display_name: form.get("display_name") }) });
      return `${accountLabel(user)} renamed.`;
    });
  }

  async function resetPassword(userId: number, form: FormData) {
    await runUserAction(async () => {
      const user = await api<ProfileUserAccount>(`/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify({ password: form.get("password") }) });
      if(userId===currentUser.id){localStorage.removeItem("eq_access_token");await api("/auth/logout",{method:"POST"});window.location.assign("/");}
      return `${user.display_name}'s password was reset. Previous sessions have been signed out.`;
    });
  }

  async function deleteAccount(user: ProfileUserAccount) {
    if (!window.confirm(`Delete ${user.display_name}? This unlinks their ESI tokens and cannot be undone.`)) return;

    await runUserAction(async () => {
      await api<{ status: string }>(`/auth/users/${user.id}`, { method: "DELETE" });
      return `${user.display_name} deleted.`;
    });
  }

  async function revokeInvite(invite: UserInvite) {
    if (!window.confirm(`Revoke invite for ${invite.email}?`)) return;

    await runUserAction(async () => {
      await api<UserInvite>(`/auth/invites/${invite.id}`, { method: "DELETE" });
      return `Invite for ${invite.email} revoked.`;
    }, true);
  }

  async function assignCharacter(character: EqmCharacter, ownerUserId: string) {
    setUserError(null);

    try {
      const updated = await api<EqmCharacter>(`/characters/${character.id}`, { method: "PATCH", body: JSON.stringify({ owner_user_id: ownerUserId || null }) });
      setCharacters((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(`${updated.name} assigned to ${updated.owner_display_name ?? "Unassigned"}.`);
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "Character assignment failed");
    }
  }

  useEffect(() => {
    void Promise.all([loadUsers(), loadInvites(), loadCharacterAssignments(), loadRoles()]).catch((err) => setUserError(err instanceof Error ? err.message : "Unable to load users"));
  }, []);

  return <div className="two-column"><section className="panel stacked"><h3>User Administration</h3><h4>Accounts</h4>{message && <div className="notice inline">{message}</div>}{latestInviteUrl && <div className="invite-link"><code>{latestInviteUrl}</code><button type="button" onClick={() => void navigator.clipboard.writeText(latestInviteUrl)}>Copy link</button></div>}{userError && <div className="mini-alert">{userError}</div>}<div className="card-list">{users.map((user) => <article key={user.id}><strong>{accountLabel(user)}</strong><span>{user.email}</span><ManagedForm submitLabel="Rename" onSubmit={(form) => updateDisplayName(user.id, form)}><label>Display name<input name="display_name" defaultValue={accountLabel(user)} required /></label></ManagedForm><AccountRoleEditor user={user} roles={roles} roleLabel={roleLabel} hostAccess={currentUser.role === "host"} onSave={assigned => updateRoles(user.id, assigned)} /><AdminRecovery userId={user.id} ownAccount={user.id===currentUser.id}/><ManagedForm submitLabel="Reset password" onSubmit={(form) => resetPassword(user.id, form)}><label>New password<input name="password" type="password" minLength={8} required /></label></ManagedForm><div className="card-actions"><button className="danger" type="button" disabled={user.id === currentUser.id || (user.role === "host" && currentUser.role !== "host")} onClick={() => void deleteAccount(user)}>{user.id === currentUser.id ? "Signed in" : user.role === "host" && currentUser.role !== "host" ? "Host protected" : "Delete user"}</button></div></article>)}</div></section><section className="panel stacked"><h3>Create Invite</h3><ManagedForm submitLabel="Generate invite" onSubmit={createInvite}><label>Email<input name="email" type="email" required /></label><label>Roles (select one or more)<select name="roles" multiple size={6} defaultValue={["member"]}>{roles.map((role) => <option key={role} value={role} disabled={role === "host" && currentUser.role !== "host"}>{roleLabel(role)}</option>)}</select></label></ManagedForm><h3>Pending Invites</h3><div className="card-list invite-list">{invites.map((invite) => <article key={invite.id}><strong>{invite.email}</strong><span>{(invite.roles ?? [invite.role]).map(roleLabel).join(" · ")} · {invite.status ?? "pending"}</span><span>Created {invite.created_at ? new Date(invite.created_at).toLocaleString() : "recently"}{invite.created_by_display_name ? ` by ${invite.created_by_display_name}` : ""}</span>{invite.accepted_at && <span>Accepted {new Date(invite.accepted_at).toLocaleString()}</span>}{invite.revoked_at && <span>Revoked {new Date(invite.revoked_at).toLocaleString()}</span>}<div className="card-actions"><button className="danger" type="button" disabled={invite.status !== "pending"} onClick={() => void revokeInvite(invite)}>Revoke</button></div></article>)}{invites.length === 0 && <p className="empty">No invites yet.</p>}</div><h3>Create Account Manually</h3><ManagedForm submitLabel="Create account" onSubmit={createAccount}><label>Display name<input name="display_name" required /></label><label>Email<input name="email" type="email" required /></label><label>Roles (select one or more)<select name="roles" multiple size={6} defaultValue={["member"]}>{roles.map((role) => <option key={role} value={role} disabled={role === "host" && currentUser.role !== "host"}>{roleLabel(role)}</option>)}</select></label><label>Temporary password<input name="password" type="password" minLength={8} required /></label></ManagedForm><h3>Character Assignment</h3><div className="card-list character-assignment-list">{characters.map((character) => <article key={character.id}><strong>{character.name}</strong>{character.character_id && <span>Character ID {character.character_id}</span>}<span>{character.owner_display_name ?? "Unassigned"}</span><span>{character.corporation_name ?? "Unknown corporation"}{character.alliance_name ? ` · ${character.alliance_name}` : ""}</span><label>EQM Account<select value={character.owner_user_id ?? ""} onChange={(event) => void assignCharacter(character, event.target.value)}><option value="">Unassigned</option>{accounts.map((account) => <option key={account.id} value={account.id}>{accountLabel(account)} ({account.role})</option>)}</select></label></article>)}{characters.length === 0 && <p className="empty">No characters available for assignment.</p>}</div></section></div>;
}
function AccountRoleEditor({user,roles,roleLabel,hostAccess,onSave}: {user:ProfileUserAccount;roles:string[];roleLabel:(role:string)=>string;hostAccess:boolean;onSave:(roles:string[])=>Promise<void>}) {
  const saved = (user.roles ?? [user.role]).slice().sort().join(",");
  const [selected,setSelected] = useState<string[]>(saved.split(","));
  const [busy,setBusy] = useState(false);
  useEffect(() => setSelected(saved.split(",")), [saved]);
  const protectedHost = (user.roles ?? [user.role]).includes("host") && !hostAccess;
  return <fieldset className="account-roles"><legend>Roles</legend><p className="muted">Permissions from selected roles are combined.</p><div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:"8px"}}>{roles.map(role=><label key={role} style={{display:"flex",alignItems:"center",gap:"8px"}}><input type="checkbox" style={{width:"auto"}} checked={selected.includes(role)} disabled={busy || protectedHost || (role==="host" && !hostAccess)} onChange={e=>setSelected(current=>e.target.checked?[...current,role]:current.filter(r=>r!==role))}/>{roleLabel(role)}</label>)}</div><button type="button" disabled={busy || protectedHost || selected.length===0 || selected.slice().sort().join(",")===saved} onClick={()=>{setBusy(true);void onSave(selected).finally(()=>setBusy(false));}}>{busy?"Saving…":"Save roles"}</button></fieldset>;
}
