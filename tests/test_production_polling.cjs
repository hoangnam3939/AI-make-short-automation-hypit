const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../app/static/app.js"), "utf8");

function setup() {
  const rendered = [];
  const timers = new Map();
  const hidden = new Set();
  let timerId = 0;
  const context = vm.createContext({
    currentProductionJobId: "current",
    productionPollTimer: null,
    productionPollVersion: 0,
    productionStageText: {},
    STAGE_LABELS: {},
    sceneReviewBanner: {
      dataset: {},
      classList: { add: (name) => hidden.add(name), remove: (name) => hidden.delete(name) },
    },
    sceneReviewText: {},
    approveSceneBtn: { dataset: {}, disabled: false },
    retrySceneBtn: {},
    skipSceneBtn: {},
    i18n: { t: (key) => key },
    applyRunModeUi() {},
    renderProductionScenes() {},
    renderQualityWarnings() {},
    renderProductionLanguages() {},
    renderPreviewPanel: (jobId, job) => rendered.push({ jobId, scene: job.awaiting_review_scene }),
    showNotice: (message) => rendered.push({ error: message }),
    console: { warn() {} },
    fetch: async () => ({ ok: true, json: async () => job(3) }),
    setInterval: (callback) => { timers.set(++timerId, callback); return timerId; },
    clearInterval: (timer) => timers.delete(timer),
  });
  for (const name of ["stopProductionPolling", "startProductionPolling", "pollProductionJob", "renderSceneReviewBanner", "resolveSceneReview"]) {
    const match = source.match(new RegExp(`^(?:async )?function ${name}\\([^]*?^}`, "m"));
    assert.ok(match, `Missing function ${name}`);
    vm.runInContext(match[0], context);
  }
  return { context, rendered, timers, hidden };
}

function job(scene, status = "generating_scenes") {
  return { awaiting_review_scene: scene, status, run_mode: "review", scenes_done: 3, scenes_total: 5, languages: {} };
}

test("an old job cannot hide the current scene review or stop its timer", async () => {
  const { context, rendered, hidden, timers } = setup();
  context.startProductionPolling("current");
  await context.pollProductionJob("current");
  context.fetch = async () => { throw new Error("Must not request old job"); };
  await context.pollProductionJob("old");
  context.renderSceneReviewBanner("old", job(null, "done"));
  assert.equal(hidden.has("section-hidden"), false);
  assert.equal(context.approveSceneBtn.dataset.sceneN, "3");
  assert.equal(rendered.length, 1);
  assert.equal(timers.size, 1);
});

test("a late response cannot overwrite a newer review state", async () => {
  const { context, rendered, hidden } = setup();
  let finishOldResponse;
  context.fetch = () => new Promise((resolve) => { finishOldResponse = resolve; });
  const oldPoll = context.pollProductionJob("current");
  context.fetch = async () => ({ ok: true, json: async () => job(3) });
  await context.pollProductionJob("current");
  finishOldResponse({ ok: true, json: async () => job(null, "done") });
  await oldPoll;
  assert.equal(rendered.length, 1);
  assert.equal(hidden.has("section-hidden"), false);
  assert.equal(context.approveSceneBtn.dataset.sceneN, "3");
});

test("switching jobs discards a response already in flight", async () => {
  const { context, rendered } = setup();
  let finishResponse;
  context.fetch = () => new Promise((resolve) => { finishResponse = resolve; });
  const poll = context.pollProductionJob("current");
  context.currentProductionJobId = "next";
  finishResponse({ ok: true, json: async () => job(1) });
  await poll;
  assert.equal(rendered.length, 0);
});

test("starting another polling loop clears the previous interval", async () => {
  const { context, timers } = setup();
  context.startProductionPolling("current");
  context.currentProductionJobId = "next";
  context.startProductionPolling("next");
  await context.pollProductionJob("next");
  assert.equal(timers.size, 1);
  context.stopProductionPolling();
  assert.equal(timers.size, 0);
});

test("a failed review submission keeps the controls and shows the error", async () => {
  const { context, rendered, hidden } = setup();
  context.renderSceneReviewBanner("current", job(3));
  context.fetch = async () => ({ ok: false, json: async () => ({ detail: "Please try again" }) });
  await context.resolveSceneReview("approve");
  assert.deepEqual(rendered, [{ error: "Please try again" }]);
  assert.equal(hidden.has("section-hidden"), false);
  assert.equal(context.approveSceneBtn.disabled, false);
});

test("a stale banner cannot submit a decision for a different job", async () => {
  const { context } = setup();
  context.renderSceneReviewBanner("current", job(3));
  context.currentProductionJobId = "next";
  let calls = 0;
  context.fetch = async () => { calls += 1; };
  await context.resolveSceneReview("skip");
  assert.equal(calls, 0);
});
