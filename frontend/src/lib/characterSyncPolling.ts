export const CHARACTER_SYNC_POLL_TIMEOUT_MS = 30 * 60 * 1000;
export const CHARACTER_SYNC_POLL_INTERVAL_MS = 2_000;

type PollableSyncJob = { status: string };

type CharacterSyncPollingOptions<T extends PollableSyncJob> = {
  initialJob: T;
  fetchLatest: (job: T) => Promise<T>;
  onUpdate?: (job: T) => void;
  timeoutMs?: number;
  intervalMs?: number;
  now?: () => number;
  wait?: (milliseconds: number) => Promise<void>;
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
}: CharacterSyncPollingOptions<T>): Promise<T> {
  const startedAt = now();
  let job = initialJob;

  while (isActive(job)) {
    const remainingMs = timeoutMs - (now() - startedAt);
    if (remainingMs <= 0) {
      throw new Error("Character sync is still running after 30 minutes, so polling was stopped. Refresh the page to check its latest status.");
    }
    await wait(Math.min(intervalMs, remainingMs));
    if (now() - startedAt >= timeoutMs) {
      throw new Error("Character sync is still running after 30 minutes, so polling was stopped. Refresh the page to check its latest status.");
    }
    job = await fetchLatest(job);
    onUpdate?.(job);
  }
  return job;
}
