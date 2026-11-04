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

test("temporary gateway errors retry the same job with backoff, without replaying its start", async () => {
 let currentTime=0,attempts=0;const waits:number[]=[];const ids:string[]=[];
 const result=await pollCharacterSyncJob<Job>({initialJob:{job_id:'existing',status:'running'},
  fetchLatest:async job=>{ids.push(job.job_id);attempts++;if(attempts<4)throw Object.assign(new Error('Gateway'),{status:[502,503,504][attempts-1]});return {...job,status:'complete'};},
  now:()=>currentTime,wait:async ms=>{waits.push(ms);currentTime+=ms;}});
 assert.equal(result.status,'complete');assert.deepEqual(ids,['existing','existing','existing','existing']);assert.deepEqual(waits,[2000,4000,8000,10000]);
});
test("persistent gateway failures remain bounded by the polling deadline", async () => {
 let currentTime=0;
 await assert.rejects(pollCharacterSyncJob<Job>({initialJob:{job_id:'bounded',status:'running'},fetchLatest:async()=>{throw Object.assign(new Error('Gateway'),{status:504});},now:()=>currentTime,wait:async ms=>{currentTime+=ms;},timeoutMs:15000}),/still running/);
 assert.equal(currentTime,15000);
});
test("authentication and missing-job failures are not retried", async () => {
 for(const status of [401,403,404]){let count=0;
  await assert.rejects(pollCharacterSyncJob<Job>({initialJob:{job_id:'private',status:'running'},fetchLatest:async()=>{count++;throw Object.assign(new Error('Denied'),{status});},wait:async()=>{}}),/Denied/);assert.equal(count,1);
 }
});
test("cancellation during transient failure exits polling",async()=>{
 const abort=new AbortController();
 await assert.rejects(pollCharacterSyncJob<Job>({initialJob:{job_id:'cancel',status:'running'},fetchLatest:async()=>{abort.abort();throw Object.assign(new Error('Gateway'),{status:504});},signal:abort.signal,wait:async()=>{}}),/page was left/);
});
