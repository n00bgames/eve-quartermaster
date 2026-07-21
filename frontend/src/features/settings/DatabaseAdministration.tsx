import { DatabaseBackup, Download, Trash2, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import "./databaseAdministration.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type DatabaseStatus = {
  dialect: string;
  revision: string;
  size_bytes: number;
  table_count: number;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

async function responseError(response: Response): Promise<string> {
  const payload = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (typeof payload?.detail === "string") return payload.detail;
  return `${response.status} ${response.statusText || "Request failed"}`;
}

function downloadName(response: Response): string {
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return decodeURIComponent(encoded ?? plain ?? "eqm-database.eqmbackup");
}

export function DatabaseAdministration({ api }: { api: ApiClient }) {
  const [status, setStatus] = useState<DatabaseStatus | null>(null);
  const [backupFile, setBackupFile] = useState<File | null>(null);
  const [restoreConfirmation, setRestoreConfirmation] = useState("");
  const [restorePassword, setRestorePassword] = useState("");
  const [clearConfirmation, setClearConfirmation] = useState("");
  const [clearPassword, setClearPassword] = useState("");
  const [busy, setBusy] = useState<"export" | "import" | "clear" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    setStatus(await api<DatabaseStatus>("/database/status"));
  }

  async function exportBackup() {
    setBusy("export");
    setError(null);
    setMessage(null);
    try {
      const token = localStorage.getItem("eq_access_token");
      const response = await fetch(`${API_BASE}/database/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = downloadName(response);
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("Database backup exported. Store it somewhere private.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Database export failed.");
    } finally {
      setBusy(null);
    }
  }

  async function importBackup() {
    if (!backupFile) return;
    setBusy("import");
    setError(null);
    setMessage(null);
    try {
      const token = localStorage.getItem("eq_access_token");
      const response = await fetch(`${API_BASE}/database/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-EQM-Confirmation": restoreConfirmation,
          "X-EQM-Password": restorePassword,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: backupFile,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const payload = await response.json() as { created_at?: string | null };
      setRestoreConfirmation("");
      setRestorePassword("");
      setBackupFile(null);
      setMessage(`Database restored${payload.created_at ? ` from backup created ${new Date(payload.created_at).toLocaleString()}` : ""}. Sign in again if your restored account differs.`);
      await loadStatus();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Database import failed.");
    } finally {
      setBusy(null);
    }
  }

  async function clearDatabase() {
    setBusy("clear");
    setError(null);
    setMessage(null);
    try {
      await api("/database/clear", {
        method: "POST",
        body: JSON.stringify({ confirmation: clearConfirmation, current_password: clearPassword }),
      });
      setClearConfirmation("");
      setClearPassword("");
      setMessage("Database cleared. Your host account and the database schema were retained.");
      await loadStatus();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Database clear failed.");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void loadStatus().catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load database status."));
  }, []);

  return (
    <>
      <section className="panel stacked database-backup-panel">
        <div className="section-heading">
          <div><h3>Database Backup</h3><p>Export a complete portable snapshot of EQM data for this schema version.</p></div>
          <button type="button" disabled={busy !== null} onClick={() => void loadStatus()}>Refresh</button>
        </div>
        {message && <div className="notice inline">{message}</div>}
        {error && <div className="mini-alert">{error}</div>}
        <div className="status-grid compact">
          <article><DatabaseBackup size={18} /><span>Database size</span><strong>{status ? formatBytes(status.size_bytes) : "Loading"}</strong></article>
          <article><span>Tables</span><strong>{status?.table_count ?? 0}</strong></article>
          <article><span>Schema</span><strong>{status?.revision ?? "Unknown"}</strong></article>
        </div>
        <div className="database-backup-note">Backups include accounts, password hashes, encrypted ESI tokens, and private operational data. Environment secrets and the mounted SDE files are not included. Protect exported files accordingly.</div>
        <button type="button" disabled={busy !== null} onClick={() => void exportBackup()}><Download size={18} /> {busy === "export" ? "Exporting backup" : "Export database backup"}</button>
      </section>

      <section className="panel stacked database-danger-zone">
        <div className="database-danger-heading"><Trash2 size={22} /><div><h3>Database Danger Zone</h3><p>Restore and clear operations replace or permanently remove stored data.</p></div></div>

        <article className="database-restore-card">
          <div><h4>Import database backup</h4><p>The backup must match the running EQM schema. Restore is transactional: a failed import rolls back to the current database.</p></div>
          <label>EQM backup file<input type="file" accept=".eqmbackup,application/vnd.eqm.database-backup" onChange={(event) => setBackupFile(event.target.files?.[0] ?? null)} /></label>
          <label>Type RESTORE EQM DATABASE<input value={restoreConfirmation} onChange={(event) => setRestoreConfirmation(event.target.value)} autoComplete="off" /></label>
          <label>Current host password<input type="password" value={restorePassword} onChange={(event) => setRestorePassword(event.target.value)} autoComplete="current-password" /></label>
          <button type="button" className="danger" disabled={busy !== null || !backupFile || restoreConfirmation !== "RESTORE EQM DATABASE" || !restorePassword} onClick={() => void importBackup()}><Upload size={18} /> {busy === "import" ? "Restoring database" : "Restore backup"}</button>
        </article>

        <article className="database-clear-card">
          <div><h4>Clear database</h4><p><strong>This is irreversible.</strong> All ESI records, industry history, assets, SDE imports, notes, analytics, and other application data will be erased. Only your signed-in host account and the schema are retained.</p></div>
          <label>Type CLEAR EQM DATABASE<input value={clearConfirmation} onChange={(event) => setClearConfirmation(event.target.value)} autoComplete="off" /></label>
          <label>Current host password<input type="password" value={clearPassword} onChange={(event) => setClearPassword(event.target.value)} autoComplete="current-password" /></label>
          <button type="button" className="danger" disabled={busy !== null || clearConfirmation !== "CLEAR EQM DATABASE" || !clearPassword} onClick={() => void clearDatabase()}><Trash2 size={18} /> {busy === "clear" ? "Clearing database" : "Permanently clear database"}</button>
        </article>
      </section>
    </>
  );
}
