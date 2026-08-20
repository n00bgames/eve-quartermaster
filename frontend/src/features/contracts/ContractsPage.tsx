import { useEffect, useMemo, useState, type ReactElement } from "react";

import { ModuleFinder } from "../../components/ModuleFinder";
import { formatDateTime, preferredTimeZone } from "../../lib/time";
import { iskFormatter } from "../../lib/market";
import { matchesSearchTerms } from "../../lib/search";
import type { CharacterHoverNameProps } from "../characters/CharacterHoverName";
import type { ContractToken, EqmContract } from "../../types/contracts";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type SortDirection = "asc" | "desc";
type UserAccount = { id: number; email: string; display_name: string; role: string; timezone?: string; created_at?: string };
type CharacterHoverNameComponent = (props: CharacterHoverNameProps) => ReactElement;

type ContractsPageProps = {
  currentUser: UserAccount;
  api: ApiClient;
  CharacterHoverName: CharacterHoverNameComponent;
};

type ContractSortKey = "contract" | "scope" | "status" | "route" | "money" | "dates";
type ContractStatusFilter = "all" | "active" | "outstanding" | "in_progress" | "finished" | "terminal";

const numberFormatter = new Intl.NumberFormat();

const CONTRACT_STATUS_OPTIONS: { value: ContractStatusFilter; label: string }[] = [
  { value: "all", label: "All contracts" },
  { value: "active", label: "Active" },
  { value: "outstanding", label: "Outstanding" },
  { value: "in_progress", label: "In progress" },
  { value: "finished", label: "Finished" },
  { value: "terminal", label: "Failed / rejected / expired" },
];

function contractMoney(value?: number | null): string {
  return value == null || value === 0 ? "-" : `${iskFormatter.format(value)} ISK`;
}

function contractOwner(contract: EqmContract): string {
  if (contract.scope_type === "corporation") return contract.corporation_name ?? "Corporation";
  return contract.character_name ?? "Character";
}

function contractStatusMatches(contract: EqmContract, filter: ContractStatusFilter): boolean {
  const status = (contract.status ?? "").toLowerCase();
  if (filter === "all") return true;
  if (filter === "active") return status === "outstanding" || status === "in_progress";
  if (filter === "outstanding") return status === "outstanding";
  if (filter === "in_progress") return status === "in_progress";
  if (filter === "finished") return status.startsWith("finished") || status === "completed";
  return ["cancelled", "canceled", "deleted", "expired", "failed", "rejected", "reversed"].includes(status);
}

function contractSortValue(contract: EqmContract, key: ContractSortKey): string | number {
  switch (key) {
    case "contract": return contract.title || contract.contract_type || contract.contract_id;
    case "scope": return `${contract.scope_type} ${contractOwner(contract)}`;
    case "status": return `${contract.status ?? ""} ${contract.contract_type ?? ""}`;
    case "route": return `${contract.start_location_name ?? ""} ${contract.end_location_name ?? ""}`;
    case "money": return Math.max(contract.reward ?? 0, contract.price ?? 0, contract.collateral ?? 0, contract.buyout ?? 0);
    case "dates": return Date.parse(contract.date_issued ?? contract.date_expired ?? "") || 0;
  }
}

export function ContractsPage({ currentUser, api, CharacterHoverName }: ContractsPageProps) {
  const [tokens, setTokens] = useState<ContractToken[]>([]);
  const [contracts, setContracts] = useState<EqmContract[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeZone = preferredTimeZone(currentUser);
  const [sortKey, setSortKey] = useState<ContractSortKey>("dates");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [statusFilter, setStatusFilter] = useState<ContractStatusFilter>("active");
  const [query, setQuery] = useState("");

  async function loadContracts() {
    const [tokenRows, contractRows] = await Promise.all([
      api<ContractToken[]>("/contracts/tokens"),
      api<EqmContract[]>("/contracts"),
    ]);

    setTokens(tokenRows);
    setContracts(contractRows);
  }

  async function syncCharacterContracts(token: ContractToken) {
    setBusy(`character-${token.token_id}`);
    setError(null);

    try {
      const result = await api<{ character_name: string; contracts: number; active_contracts: number }>(`/contracts/sync/character/${token.token_id}`, { method: "POST" });
      setMessage(`Synced ${result.contracts.toLocaleString()} contracts for ${result.character_name}; ${result.active_contracts.toLocaleString()} active.`);
      await loadContracts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Character contract sync failed.");
    } finally {
      setBusy(null);
    }
  }

  async function syncCorporationContracts(token: ContractToken) {
    setBusy(`corporation-${token.token_id}`);
    setError(null);

    try {
      const result = await api<{ corporation_name: string; contracts: number; active_contracts: number }>(`/contracts/sync/corporation/${token.token_id}`, { method: "POST" });
      setMessage(`Synced ${result.contracts.toLocaleString()} corporation contracts for ${result.corporation_name}; ${result.active_contracts.toLocaleString()} active.`);
      await loadContracts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Corporation contract sync failed.");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void loadContracts().catch((err) => setError(err instanceof Error ? err.message : "Unable to load contracts."));
  }, []);

  function toggleContractSort(nextKey: ContractSortKey) {
    if (nextKey === sortKey) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
      return;
    }

    setSortKey(nextKey);
    setSortDirection(nextKey === "dates" || nextKey === "money" ? "desc" : "asc");
  }

  const contractSortMark = (key: ContractSortKey) => sortKey === key ? (sortDirection === "asc" ? "^" : "v") : "";

  const visibleContracts = useMemo(() => {
    return contracts.filter((contract) => contractStatusMatches(contract, statusFilter) && matchesSearchTerms(query, [
      contract.title,
      contract.contract_id,
      contract.contract_type,
      contract.status,
      contract.availability,
      contract.scope_type,
      contractOwner(contract),
      contract.character_name,
      contract.corporation_name,
      contract.start_location_name,
      contract.end_location_name,
    ])).sort((left, right) => {
      const leftValue = contractSortValue(left, sortKey);
      const rightValue = contractSortValue(right, sortKey);
      const result = typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });

      return sortDirection === "asc" ? result : -result;
    });
  }, [contracts, query, sortKey, sortDirection, statusFilter]);

  const statusFilteredCount = useMemo(
    () => contracts.filter((contract) => contractStatusMatches(contract, statusFilter)).length,
    [contracts, statusFilter],
  );

  return (
    <section className="panel stacked contracts-page">
      <div className="section-heading">
        <div><h3>Contracts</h3><p>Pull current character contracts, plus corporation contracts for officer-level tokens and above.</p></div>
        <button type="button" onClick={() => void loadContracts()}>Refresh</button>
      </div>

      {message && <div className="notice inline">{message}</div>}
      {error && <div className="mini-alert">{error}</div>}

      <h4>Linked contract tokens</h4>
      <div className="contract-token-grid">
        {tokens.map((token) => <article className="contract-token-card" key={token.token_id}>
          <strong><CharacterHoverName characterId={token.character_id} name={token.character_name} /></strong>
          <span>{token.user_display_name}{token.corporation_name ? ` · ${token.corporation_name}` : ""}</span>
          <div className="button-row compact">
            {token.has_character_contract_scope ? <button type="button" disabled={busy === `character-${token.token_id}`} onClick={() => void syncCharacterContracts(token)}>{busy === `character-${token.token_id}` ? "Syncing" : "Character contracts"}</button> : <span className="scope-warn">Missing character contract scope</span>}
            {token.has_corporation_contract_scope && token.corporation_id ? <button type="button" disabled={busy === `corporation-${token.token_id}`} onClick={() => void syncCorporationContracts(token)}>{busy === `corporation-${token.token_id}` ? "Syncing" : "Corp contracts"}</button> : <span className="scope-warn">Missing corporation contract scope</span>}
          </div>
        </article>)}
        {tokens.length === 0 && <p className="empty">No ESI-linked characters with contract access are visible to this account.</p>}
      </div>

      <div className="section-heading compact"><h4>Current contracts</h4><div className="button-row compact"><ModuleFinder query={query} onQueryChange={setQuery} label="Search contracts" placeholder="Title, pilot, corporation, route, ID…" resultCount={visibleContracts.length} totalCount={statusFilteredCount} /><label className="compact-field">Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as ContractStatusFilter)}>{CONTRACT_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label></div></div>
      <div className="table-wrap contracts-table-wrap">
        <table className="contracts-table">
          <thead><tr><th><button className="sort-header" type="button" onClick={() => toggleContractSort("contract")}>Contract <span>{contractSortMark("contract")}</span></button></th><th><button className="sort-header" type="button" onClick={() => toggleContractSort("scope")}>Scope <span>{contractSortMark("scope")}</span></button></th><th><button className="sort-header" type="button" onClick={() => toggleContractSort("status")}>Status <span>{contractSortMark("status")}</span></button></th><th><button className="sort-header" type="button" onClick={() => toggleContractSort("route")}>Route <span>{contractSortMark("route")}</span></button></th><th><button className="sort-header" type="button" onClick={() => toggleContractSort("money")}>Money <span>{contractSortMark("money")}</span></button></th><th><button className="sort-header" type="button" onClick={() => toggleContractSort("dates")}>Dates <span>{contractSortMark("dates")}</span></button></th></tr></thead>
          <tbody>
            {visibleContracts.map((contract) => {
              const title = contract.title || `${contract.contract_type ?? "contract"} #${contract.contract_id}`;

              return <tr key={`${contract.scope_type}-${contract.contract_id}`}>
                <td><strong>{title}</strong><span>#{contract.contract_id}</span></td>
                <td><span className="contract-scope-badge">{contract.scope_type}</span><br /><span>{contract.scope_type === "character" ? <CharacterHoverName characterId={contract.character_id} name={contract.character_name ?? "Character"} /> : contractOwner(contract)}</span></td>
                <td><strong>{contract.status ?? "unknown"}</strong><br /><span>{contract.contract_type ?? "unknown"}{contract.availability ? ` · ${contract.availability}` : ""}</span>{contract.for_corporation ? <span><br />For corporation</span> : null}</td>
                <td><strong>{contract.start_location_name ?? "Unknown start"}</strong><br /><span>{contract.end_location_name ?? "No destination"}</span>{contract.volume != null ? <span><br />{numberFormatter.format(contract.volume)} m3</span> : null}</td>
                <td><div className="contract-money-cell"><b>Reward {contractMoney(contract.reward)}</b><b>Price {contractMoney(contract.price)}</b><b>Collateral {contractMoney(contract.collateral)}</b><b>Buyout {contractMoney(contract.buyout)}</b></div></td>
                <td><strong>Issued {formatDateTime(contract.date_issued, timeZone)}</strong><br /><span>Expires {formatDateTime(contract.date_expired, timeZone)}</span>{contract.date_completed ? <span><br />Done {formatDateTime(contract.date_completed, timeZone)}</span> : null}</td>
              </tr>;
            })}
            {contracts.length === 0 && <tr><td colSpan={6}>No contracts synced yet.</td></tr>}
            {contracts.length > 0 && visibleContracts.length === 0 && <tr><td colSpan={6}>No contracts match the current search and status filters.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
