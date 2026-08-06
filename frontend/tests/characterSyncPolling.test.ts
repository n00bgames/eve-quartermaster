import assert from "node:assert/strict";
import test from "node:test";

import { CHARACTER_SYNC_POLL_TIMEOUT_MS, pollCharacterSyncJob } from "../src/lib/characterSyncPolling.ts";

type Job = { job_id: string; status: "queued" | "running" | "complete" };

test("character sync polling allows jobs to run for up to 30 minutes", async () => {
  let currentTime = 0;
  const updates: string[] = [];
  const jobs: Job[] = [{ job_id: "job-1", status: "running" }, { job_id: "job-1", status: "complete" }];
  const result = await pollCharacterSyncJob<Job>({
    initialJob: { job_id: "job-1", status: "queued" },
    fetchLatest: async () => jobs.shift()!,
    onUpdate: (job) => updates.push(job.status),
    now: () => currentTime,
    wait: async (milliseconds) => { currentTime += milliseconds; },
    intervalMs: CHARACTER_SYNC_POLL_TIMEOUT_MS / 3,
  });
  assert.equal(result.status, "complete");
  assert.deepEqual(updates, ["running", "complete"]);
});

test("character sync polling stops at the 30 minute maximum", async () => {
  let currentTime = 0;
  let requests = 0;
  await assert.rejects(
    pollCharacterSyncJob<Job>({
      initialJob: { job_id: "job-2", status: "running" },
      fetchLatest: async (job) => { requests += 1; return job; },
      now: () => currentTime,
      wait: async (milliseconds) => { currentTime += milliseconds; },
      intervalMs: 10 * 60 * 1000,
    }),
    /still running after 30 minutes/,
  );
  assert.equal(currentTime, CHARACTER_SYNC_POLL_TIMEOUT_MS);
  assert.equal(requests, 2);
});
