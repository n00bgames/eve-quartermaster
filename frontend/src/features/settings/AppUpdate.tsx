import { useEffect, useState } from "react";
import { ApiError } from "../../lib/apiErrors";
import "./AppUpdate.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Job = { id: string; phase: "queued" | "checking" | "installing" | "starting" | "current" | "succeeded" | "failed"; message: string; revision?: string };
type Status = { enabled: boolean; online: boolean; job: Job | null };
type Watch = { id: string; requestedAt: number };

const ACTIVE = new Set<Job["phase"]>(["queued", "checking", "installing", "starting"]);

export function useAppUpdate(hostId: number | null, settingsOpen: boolean, api: ApiClient) {
  const storageKey = hostId === null ? null : `eqm:app-update:${hostId}`;
  const [watch, setWatch] = useState<Watch | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState(false);

  useEffect(() => {
    const saved = storageKey && sessionStorage.getItem(storageKey);
    setWatch(saved ? { id: saved, requestedAt: Date.now() } : null);
    setStatus(null);
    setError(null);
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey || (!settingsOpen && !watch)) return;
    const controller = new AbortController();
    let timer: number | undefined;

    async function poll() {
      let next = watch ? 2500 : 10000;
      try {
        const result = await api<Status>("/app-update/status", {
          cache: "no-store", signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setReconnecting(false);
        setStatus(result);
        const job = result.job;
        if (job && ACTIVE.has(job.phase)) next = 2500;
        if (watch && job?.id === watch.id && !ACTIVE.has(job.phase)) {
          sessionStorage.removeItem(storageKey!);
          setWatch(null);
          setError(null);
          if (job.phase === "succeeded") {
            window.location.reload();
            return;
          }
        } else if (watch && job?.id !== watch.id && Date.now() - watch.requestedAt > 45000) {
          sessionStorage.removeItem(storageKey!);
          setWatch(null);
          setError("The host did not report this request. Check the helper before trying again.");
        }
      } catch (reason) {
        if (controller.signal.aborted) return;
        setReconnecting(Boolean(watch));
        if (!watch) setError(reason instanceof Error ? reason.message : "Unable to check the update helper.");
      }
      timer = window.setTimeout(poll, next);
    }
    void poll();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [storageKey, settingsOpen, watch, api]);

  async function start() {
    if (!storageKey || watch || !status?.online) return;
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const id = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
    setError(null);
    sessionStorage.setItem(storageKey, id);
    setWatch({ id, requestedAt: Date.now() });
    try {
      await api<Job>("/app-update/jobs", {
        method: "POST",
        headers: { "X-EQM-Update": "1" },
        body: JSON.stringify({ job_id: id }),
      });
    } catch (reason) {
      // A lost response can mean the host received the job. Keep polling in
      // that case, and only clear the watch when the API explicitly refused it.
      if (reason instanceof ApiError && (reason.status < 500 || (reason.status === 503 && reason.message.startsWith("The EQM host update helper")))) {
        sessionStorage.removeItem(storageKey);
        setWatch(null);
        setError(reason.message);
      } else {
        setReconnecting(true);
      }
    }
  }

  return {
    start, status, error, reconnecting,
    busy: Boolean(watch || (status?.job && ACTIVE.has(status.job.phase))),
  };
}

export function AppUpdatePanel({ update }: { update: ReturnType<typeof useAppUpdate> }) {
  const { status, error, reconnecting, busy, start } = update;
  const job = status?.job;
  return (
    <section className="panel stacked app-update-panel">
      <div className="section-heading">
        <div>
          <h3>Application Update</h3>
          <p>Install new EQM code and restart the app on this server. Keep this tab open to refresh it when EQM is ready.</p>
        </div>
        <button type="button" disabled={busy || !status?.online} onClick={() => void start()}>
          {busy ? "Update in progress" : "Check for updates and install"}
        </button>
      </div>
      {status && !status.enabled && <p className="muted">Enable the host update helper to install updates here.</p>}
      {status?.enabled && !status.online && <p className="muted">Waiting for the host update helper.</p>}
      {!status && !error && <p className="muted" role="status">Checking the host helper.</p>}
      {reconnecting && <p className="muted" role="status">Waiting for EQM to reconnect. The host helper runs in the background.</p>}
      {job && <p className={job.phase === "failed" ? "mini-alert" : "muted"} role={job.phase === "failed" ? "alert" : "status"}>
        {job.message}{job.revision && <> Revision {job.revision.slice(0, 12)}.</>}
      </p>}
      {error && <p className="mini-alert" role="alert">{error}</p>}
    </section>
  );
}
