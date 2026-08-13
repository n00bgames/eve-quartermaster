export const CHARACTER_SYNC_POLL_TIMEOUT_MS = 30 * 60 * 1000;
export const CHARACTER_SYNC_POLL_INTERVAL_MS = 2_000;
export const CHARACTER_SYNC_RESUME_TTL_MS = 6 * 60 * 60 * 1000;

export type StoredSyncJobReference = {
  jobId: string;
  storedAt: number;
};

function resumableStorageKey(scope: string) {
  return `eqm.character-sync.${scope}`;
}

export function rememberCharacterSyncJob(scope: string, jobId: string, storedAt = Date.now()) {
  try {
    globalThis.localStorage?.setItem(resumableStorageKey(scope), JSON.stringify({ jobId, storedAt } satisfies StoredSyncJobReference));
  } catch {
    // Storage can be unavailable in hardened/private browser contexts. Polling still works for the current page.
  }
}

export function forgetCharacterSyncJob(scope: string) {
  try {
    globalThis.localStorage?.removeItem(resumableStorageKey(scope));
  } catch {
    // Treat unavailable storage as already cleared.
  }
}

export function recalledCharacterSyncJob(scope: string, now = Date.now()): StoredSyncJobReference | null {
  try {
    const raw = globalThis.localStorage?.getItem(resumableStorageKey(scope));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredSyncJobReference>;
    if (!parsed.jobId || typeof parsed.storedAt !== "number" || now - parsed.storedAt > CHARACTER_SYNC_RESUME_TTL_MS) {
      forgetCharacterSyncJob(scope);
      return null;
    }
    return { jobId: parsed.jobId, storedAt: parsed.storedAt };
  } catch {
    forgetCharacterSyncJob(scope);
    return null;
  }
}

export function isMissingResumableSyncJob(reason: unknown) {
  const message = reason instanceof Error ? reason.message : String(reason);
  return /not found|backend restart|status 404|\b404\b/i.test(message);
}

type PollableSyncJob = { job_id: string; status: string };

export class CharacterSyncPollingAborted extends Error {
  constructor() {
    super("Character sync polling stopped because the page was left.");
    this.name = "CharacterSyncPollingAborted";
  }
}

export function isCharacterSyncPollingAborted(reason: unknown) {
  return reason instanceof CharacterSyncPollingAborted;
}

type CharacterSyncPollingOptions<T extends PollableSyncJob> = {
  initialJob: T;
  fetchLatest: (job: T) => Promise<T>;
  onUpdate?: (job: T) => void;
  timeoutMs?: number;
  intervalMs?: number;
  now?: () => number;
  wait?: (milliseconds: number) => Promise<void>;
  signal?: AbortSignal;
};

const isActive = (job: PollableSyncJob) => job.status === "queued" || job.status === "running";

export async function pollCharacterSyncJob<T extends PollableSyncJob>({
  initialJob,
  fetchLatest,
  onUpdate,
  timeoutMs = CHARACTER_SYNC_POLL_TIMEOUT_MS,
  intervalMs = CHARACTER_SYNC_POLL_INTERVAL_MS,
  now = Date.now,
  wait = (milliseconds) => new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds)),
  signal,
}: CharacterSyncPollingOptions<T>): Promise<T> {
  const startedAt = now();
  let job = initialJob;

  while (isActive(job)) {
    if (signal?.aborted) throw new CharacterSyncPollingAborted();
    const remainingMs = timeoutMs - (now() - startedAt);
    if (remainingMs <= 0) {
      throw new Error("Character sync is still running after 30 minutes, so polling was stopped. Refresh the page to check its latest status.");
    }
    await wait(Math.min(intervalMs, remainingMs));
    if (signal?.aborted) throw new CharacterSyncPollingAborted();
    if (now() - startedAt >= timeoutMs) {
      throw new Error("Character sync is still running after 30 minutes, so polling was stopped. Refresh the page to check its latest status.");
    }
    job = await fetchLatest(job);
    onUpdate?.(job);
  }
  return job;
}

type TrackCharacterSyncJobOptions<T extends PollableSyncJob> = Omit<CharacterSyncPollingOptions<T>, "initialJob"> & {
  scope: string;
  initialJob: T;
};

export async function trackCharacterSyncJob<T extends PollableSyncJob>({
  scope,
  initialJob,
  ...pollingOptions
}: TrackCharacterSyncJobOptions<T>): Promise<T> {
  rememberCharacterSyncJob(scope, initialJob.job_id);
  const job = await pollCharacterSyncJob({ initialJob, ...pollingOptions });
  if (!isActive(job)) forgetCharacterSyncJob(scope);
  return job;
}

type ResumeCharacterSyncJobOptions<T extends PollableSyncJob> = Omit<CharacterSyncPollingOptions<T>, "initialJob" | "fetchLatest"> & {
  scope: string;
  fetchById: (jobId: string) => Promise<T>;
};

export async function resumeCharacterSyncJob<T extends PollableSyncJob>({
  scope,
  fetchById,
  onUpdate,
  ...pollingOptions
}: ResumeCharacterSyncJobOptions<T>): Promise<T | null> {
  const remembered = recalledCharacterSyncJob(scope);
  if (!remembered) return null;

  let initialJob: T;
  try {
    initialJob = await fetchById(remembered.jobId);
  } catch (reason) {
    if (isMissingResumableSyncJob(reason)) {
      forgetCharacterSyncJob(scope);
      return null;
    }
    throw reason;
  }

  onUpdate?.(initialJob);
  if (!isActive(initialJob)) {
    forgetCharacterSyncJob(scope);
    return initialJob;
  }

  return trackCharacterSyncJob({
    scope,
    initialJob,
    fetchLatest: (job) => fetchById(job.job_id),
    onUpdate,
    ...pollingOptions,
  });
}
