import { useEffect, useState, type ReactElement } from "react";

import { iskFormatter } from "../../lib/market";
import type { CorporationToken, EqmCorporation } from "../../types/corporations";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";
type EveEntityIconComponent = (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;

type CorporationsPageProps = {
  api: ApiClient;
  loadAssets: () => Promise<void>;
  EveEntityIcon: EveEntityIconComponent;
};

export function CorporationsPage({ api, loadAssets, EveEntityIcon }: CorporationsPageProps) {
  const [corporations, setCorporations] = useState<EqmCorporation[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [corpError, setCorpError] = useState<string | null>(null);
  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);
  const [busyAll, setBusyAll] = useState(false);

  async function loadCorporations() {
    setCorporations(await api<EqmCorporation[]>("/corporations"));
  }

  async function refreshCorporationLinks() {
    setCorpError(null);
    setMessage("Refreshing corporation links from enrolled characters...");

    try {
      const result = await api<{ characters_refreshed: number; skipped: number; failed?: number; errors?: string[] }>("/esi/sync/linked-corporations", { method: "POST", body: "{}" });
      const failNote = result.failed ? ` ${result.failed.toLocaleString()} failed; ${result.errors?.[0] ?? "check backend logs"}.` : "";
      setMessage(`Refreshed ${result.characters_refreshed.toLocaleString()} linked character corporation record${result.characters_refreshed === 1 ? "" : "s"}.${failNote}`);
      await loadCorporations();
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Corporation discovery failed");
    }
  }

  async function syncCorporationAssets(token: CorporationToken, corporation: EqmCorporation) {
    setBusyTokenId(token.token_id);
    setCorpError(null);
    setMessage(`Syncing ${corporation.name} assets with ${token.character_name}...`);

    try {
      const result = await api<{ corporation_name: string; asset_rows: number }>(`/esi/sync/corporation-assets/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.asset_rows.toLocaleString()} asset rows for ${result.corporation_name}.`);
      await Promise.all([loadCorporations(), loadAssets()]);
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Corporation asset sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  async function syncCorporationWallets(token: CorporationToken, corporation: EqmCorporation) {
    setBusyTokenId(token.token_id);
    setCorpError(null);
    setMessage(`Syncing ${corporation.name} wallet divisions with ${token.character_name}...`);

    try {
      const result = await api<{ corporation_name: string; wallet_divisions: number }>(`/esi/sync/corporation-wallets/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.wallet_divisions.toLocaleString()} wallet divisions for ${result.corporation_name}.`);
      await loadCorporations();
    } catch (err) {
      setMessage(null);
      setCorpError(err instanceof Error ? err.message : "Corporation wallet sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  async function syncCorporationBlueprints(token: CorporationToken, corporation: EqmCorporation) {
    setBusyTokenId(token.token_id);
    setCorpError(null);
    setMessage(`Syncing ${corporation.name} blueprints with ${token.character_name}...`);

    try {
      const result = await api<{ corporation_name: string; blueprint_rows: number }>(`/esi/sync/corporation-blueprints/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.blueprint_rows.toLocaleString()} blueprint rows for ${result.corporation_name}.`);
      await loadCorporations();
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Corporation blueprint sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  async function syncAllEligible() {
    setBusyAll(true);
    setCorpError(null);
    let assetJobs = 0;
    let blueprintJobs = 0;
    let walletJobs = 0;
    const failures: string[] = [];

    async function attemptSync(label: string, request: () => Promise<unknown>) {
      try {
        await request();
        return true;
      } catch (err) {
        const detail = err instanceof Error ? err.message : "sync failed";
        failures.push(`${label}: ${detail}`);
        return false;
      }
    }

    try {
      for (const [index, corporation] of corporations.entries()) {
        const step = `${index + 1}/${corporations.length}`;
        const assetToken = corporation.eligible_tokens.find((token) => token.can_sync);

        if (assetToken) {
          setMessage(`${step}: syncing ${corporation.name} corporation assets with ${assetToken.character_name}...`);
          if (await attemptSync(`${corporation.name} assets via ${assetToken.character_name}`, () => api(`/esi/sync/corporation-assets/${assetToken.token_id}`, { method: "POST", body: "{}" }))) assetJobs += 1;
        }

        const blueprintToken = corporation.eligible_tokens.find((token) => token.can_sync_blueprints);

        if (blueprintToken) {
          setMessage(`${step}: syncing ${corporation.name} corporation blueprints with ${blueprintToken.character_name}...`);
          if (await attemptSync(`${corporation.name} blueprints via ${blueprintToken.character_name}`, () => api(`/esi/sync/corporation-blueprints/${blueprintToken.token_id}`, { method: "POST", body: "{}" }))) blueprintJobs += 1;
        }

        const walletToken = corporation.eligible_tokens.find((token) => token.can_sync_wallets);

        if (walletToken) {
          setMessage(`${step}: syncing ${corporation.name} wallet divisions with ${walletToken.character_name}...`);
          if (await attemptSync(`${corporation.name} wallets via ${walletToken.character_name}`, () => api(`/esi/sync/corporation-wallets/${walletToken.token_id}`, { method: "POST", body: "{}" }))) walletJobs += 1;
        }
      }

      setMessage(`Synced ${assetJobs} corporation asset ledger${assetJobs === 1 ? "" : "s"}, ${blueprintJobs} blueprint ledger${blueprintJobs === 1 ? "" : "s"}, and ${walletJobs} wallet ledger${walletJobs === 1 ? "" : "s"}.${failures.length ? ` ${failures.length} failed and were skipped.` : ""}`);
      if (failures.length) setCorpError(failures.slice(0, 3).join(" | "));
      await Promise.all([loadCorporations(), loadAssets()]);
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Sync all failed");
    } finally {
      setBusyAll(false);
    }
  }

  useEffect(() => {
    void loadCorporations().catch((err) => setCorpError(err instanceof Error ? err.message : "Unable to load corporations"));
  }, []);

  return <section className="panel stacked"><div className="section-heading"><h3>Corporations</h3><div className="button-row compact"><button type="button" onClick={() => void refreshCorporationLinks()}>Refresh corporation links</button><button type="button" disabled={busyAll || corporations.length === 0} onClick={() => void syncAllEligible()}>{busyAll ? "Syncing all" : "Sync all eligible"}</button></div></div>{message && <div className="notice inline">{message}</div>}{corpError && <div className="mini-alert">{corpError}</div>}<div className="card-list corporation-list">{corporations.map((corporation) => <article key={corporation.id} className="entity-card"><div className="entity-card-heading"><EveEntityIcon kind="corporation" id={corporation.corporation_id} name={corporation.name} size="md" /><div><strong>{corporation.name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</strong><span>{corporation.alliance_id && <EveEntityIcon kind="alliance" id={corporation.alliance_id} name={corporation.alliance_name} size="tiny" />}{corporation.alliance_name ?? "No alliance"} · Corp ID {corporation.corporation_id}</span></div></div><span>CEO {corporation.ceo_character_name ?? corporation.ceo_character_eve_id ?? "unknown"}</span><span className="scope-ok">Members {corporation.member_count?.toLocaleString() ?? "unknown"}</span><span>{corporation.asset_rows.toLocaleString()} tracked asset rows · {corporation.blueprint_rows.toLocaleString()} blueprints</span><span className={corporation.asset_sync_stale ? "scope-warn" : "scope-ok"}>Assets {corporation.last_asset_sync_at ? `${new Date(corporation.last_asset_sync_at).toLocaleString()} (${corporation.last_asset_sync_status ?? "sync"})` : "never synced"}</span><span className={corporation.blueprint_sync_stale ? "scope-warn" : "scope-ok"}>Blueprints {corporation.last_blueprint_sync_at ? `${new Date(corporation.last_blueprint_sync_at).toLocaleString()} (${corporation.last_blueprint_sync_status ?? "sync"})` : "never synced"}</span><span className={corporation.wallet_sync_stale ? "scope-warn" : "scope-ok"}>Wallets {corporation.last_wallet_sync_at ? `${new Date(corporation.last_wallet_sync_at).toLocaleString()} (${corporation.last_wallet_sync_status ?? "sync"})` : "never synced"}</span>{corporation.last_asset_sync_message && <code>{corporation.last_asset_sync_message}</code>}{corporation.last_blueprint_sync_message && <code>{corporation.last_blueprint_sync_message}</code>}{corporation.last_wallet_sync_message && <code>{corporation.last_wallet_sync_message}</code>}<div className="wallet-grid"><span>Wallet divisions</span>{corporation.wallet_divisions.length > 0 ? corporation.wallet_divisions.map((wallet) => <div key={wallet.division}><strong>Division {wallet.division}</strong><span>{iskFormatter.format(wallet.balance)} ISK</span></div>) : <p className="muted">No wallet divisions synced yet.</p>}</div><div className="choice-list"><span>Corp sync tokens</span>{corporation.eligible_tokens.length > 0 ? corporation.eligible_tokens.map((token) => <div className="token-row" key={token.token_id}><span>{token.character_name} · {token.user_display_name}</span><div className="button-row compact">{token.has_corporation_asset_scope ? <button type="button" disabled={!token.can_sync || busyTokenId === token.token_id} onClick={() => void syncCorporationAssets(token, corporation)}>Assets</button> : <span className="scope-warn">Missing asset scope</span>}{token.has_corporation_blueprint_scope ? <button type="button" disabled={!token.can_sync_blueprints || busyTokenId === token.token_id} onClick={() => void syncCorporationBlueprints(token, corporation)}>Blueprints</button> : <span className="scope-warn">Missing blueprint scope</span>}{token.has_corporation_wallet_scope ? <button type="button" disabled={!token.can_sync_wallets || busyTokenId === token.token_id} onClick={() => void syncCorporationWallets(token, corporation)}>Wallets</button> : <span className="scope-warn">Missing wallet scope</span>}</div></div>) : <p className="muted">No linked character tokens found for this corporation yet.</p>}</div></article>)}</div>{corporations.length === 0 && <p className="empty">No corporations imported or linked yet. Re-link a CEO/director through EVE SSO to populate this list.</p>}</section>;
}