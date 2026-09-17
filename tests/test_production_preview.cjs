const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../app/static/app.js"), "utf8");

function setup() {
  const elements = new Map();
  let sourceChanges = 0;
  function element(id) {
    if (elements.has(id)) return elements.get(id);
    const classes = new Set();
    const result = {
      dataset: {}, paused: true, disabled: false, value: "", innerHTML: "",
      classList: {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        contains: (name) => classes.has(name),
        toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
      },
      setAttribute(name, value) { this[name] = value; },
      removeAttribute(name) { delete this[name]; },
    };
    elements.set(id, result);
    return result;
  }
  const video = element("preview-video");
  Object.defineProperty(video, "src", {
    configurable: true,
    get() { return this.currentSrc; },
    set(value) { this.currentSrc = value; sourceChanges += 1; },
  });
  const tabs = ["scene", "raw", "narration", "sfx"].map((stage) => {
    const tab = element(`preview-tab-${stage}`);
    tab.dataset.stage = stage;
    return tab;
  });
  const context = vm.createContext({
    currentProductionJobId: "current", previewJobId: null, previewJob: null,
    previewSceneN: null, previewSelectionManual: false, previewStage: null,
    previewLangCode: null, previewLastSrc: null, lastForcedReviewScene: null,
    previewLangWrap: element("preview-lang-wrap"), previewLangSelect: element("preview-lang-select"),
    previewVideoEl: video, previewEmptyHint: element("preview-empty-hint"),
    languageNameByCode: {},
    document: { getElementById: element, querySelectorAll: () => tabs },
    renderProductionScenes() {},
    URL, window: { location: { href: "http://localhost/?production_job=current" } },
    step6Section: { scrollIntoView() {} },
    startProductionPolling(jobId) { this.restoredJobId = jobId; },
  });
  for (const name of ["_sceneIsViewable", "availablePreviewScene", "selectPreviewScene", "setPreviewStage", "computePreviewSrc", "updatePreviewVideoSrc", "resetPreviewPanel", "renderPreviewPanel", "restoreProductionFromUrl"]) {
    const match = source.match(new RegExp(`^function ${name}\\([^]*?^}`, "m"));
    assert.ok(match, `Missing function ${name}`);
    vm.runInContext(match[0], context);
  }
  return { context, element, sourceChanges: () => sourceChanges };
}

function snapshot(reviewScene = 3) {
  return {
    awaiting_review_scene: reviewScene,
    scenes: { 1: { status: "done" }, 2: { status: "done" }, 3: { status: "done" }, 4: { status: "queued" } },
    raw_video_available: true,
    languages: {
      vi: { narration_video_available: true, sfx_video_available: true },
      en: { narration_video_available: true, sfx_video_available: false },
    },
  };
}

test("completed scene stays visible after approval while the next scene generates", () => {
  const { context, element, sourceChanges } = setup();
  context.renderPreviewPanel("current", snapshot());
  const next = snapshot(null);
  next.scenes[4].status = "generating";
  context.renderPreviewPanel("current", next);
  assert.equal(context.previewVideoEl.src, "/api/production/current/scenes/3/video");
  assert.equal(element("preview-tab-scene").disabled, false);
  assert.equal(element("preview-video").classList.contains("section-hidden"), false);
  assert.equal(sourceChanges(), 1);
});

test("tab and language switches use the cached current snapshot immediately", () => {
  const { context } = setup();
  context.renderPreviewPanel("current", snapshot());
  context.setPreviewStage("raw");
  context.updatePreviewVideoSrc();
  assert.equal(context.previewVideoEl.src, "/api/production/current/video/raw");
  context.setPreviewStage("narration");
  context.previewLangCode = "en";
  context.updatePreviewVideoSrc();
  assert.equal(context.previewVideoEl.src, "/api/production/current/video?language_code=en&stage=narration");
});

test("manually selected completed scene survives new reviews and repeated polls", () => {
  const { context, sourceChanges } = setup();
  context.renderPreviewPanel("current", snapshot());
  context.selectPreviewScene(1);
  const next = snapshot(4);
  next.scenes[4].status = "done";
  context.renderPreviewPanel("current", next);
  context.renderPreviewPanel("current", next);
  assert.equal(context.previewSceneN, 1);
  assert.equal(context.previewVideoEl.src, "/api/production/current/scenes/1/video");
  assert.equal(sourceChanges(), 2);
});

test("old jobs cannot mix their scene numbers into the current video URL", () => {
  const { context, sourceChanges } = setup();
  context.renderPreviewPanel("current", snapshot(1));
  context.renderPreviewPanel("old", snapshot(3));
  assert.equal(context.previewVideoEl.src, "/api/production/current/scenes/1/video");
  assert.equal(sourceChanges(), 1);
});

test("a failed review with no completed clips does not enable an invalid video", () => {
  const { context, element } = setup();
  const failed = snapshot(1);
  failed.scenes = { 1: { status: "failed" }, 2: { status: "queued" } };
  failed.raw_video_available = false;
  failed.languages = {};
  context.renderPreviewPanel("current", failed);
  assert.equal(element("preview-tab-scene").disabled, true);
  assert.equal(context.previewLastSrc, null);
});

test("receiving another review does not interrupt a playing video", () => {
  const { context, sourceChanges } = setup();
  context.renderPreviewPanel("current", snapshot(1));
  context.previewVideoEl.paused = false;
  context.renderPreviewPanel("current", snapshot(3));
  assert.equal(context.previewSceneN, 1);
  assert.equal(sourceChanges(), 1);
});

test("production URL resumes monitoring an existing job without starting production", () => {
  const { context } = setup();
  const calls = [];
  context.startProductionPolling = (jobId) => calls.push(jobId);
  context.restoreProductionFromUrl();
  assert.deepEqual(calls, ["current"]);
  context.window.location.href = "http://localhost/?production_job=invalid/path";
  context.restoreProductionFromUrl();
  assert.deepEqual(calls, ["current"]);
});
