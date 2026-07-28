import assert from "node:assert/strict";
import test from "node:test";

import { startRecruitmentSso } from "../src/features/recruiting/recruitingSso.ts";

test("saves the draft before navigating the separate SSO tab", async () => {
  const events: string[] = [];
  let finishSaving: (() => void) | undefined;
  const saveDraft = () => new Promise<void>((resolve) => {
    finishSaving = () => { events.push("saved"); resolve(); };
  });
  const authWindow = {
    close: () => events.push("closed"),
    location: { replace: (url: string) => events.push(`navigated:${url}`) },
  };

  const pending = startRecruitmentSso({
    openWindow: () => { events.push("opened"); return authWindow; },
    saveDraft,
    loadAuthUrl: async () => { events.push("loaded-url"); return { ready: true, url: "https://login.eveonline.com/authorize" }; },
  });

  assert.deepEqual(events, ["opened"]);
  finishSaving?.();
  await pending;
  assert.deepEqual(events, ["opened", "saved", "loaded-url", "navigated:https://login.eveonline.com/authorize"]);
});

test("closes the empty SSO tab when draft persistence fails", async () => {
  let closed = false;
  await assert.rejects(() => startRecruitmentSso({
    openWindow: () => ({ close: () => { closed = true; }, location: { replace: () => undefined } }),
    saveDraft: async () => { throw new Error("Draft save failed"); },
    loadAuthUrl: async () => ({ ready: true, url: "https://login.eveonline.com/authorize" }),
  }), /Draft save failed/);
  assert.equal(closed, true);
});