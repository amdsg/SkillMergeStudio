import test from "node:test";
import assert from "node:assert/strict";

import { ProgressModel } from "./progress-model.js";

test("determinate percent uses current and total", () => {
  const model = new ProgressModel();
  const state = model.update({ seq: 1, phase: "parse", current: 37, total: 120 });
  assert.equal(state.mode, "determinate");
  assert.equal(state.percent, 31);
  assert.equal(state.current, 37);
  assert.equal(state.total, 120);
});

test("zero null or overflow total stays indeterminate", () => {
  for (const total of [0, null, undefined, "x"]) {
    const model = new ProgressModel();
    const state = model.update({ seq: 1, phase: "walk", current: 5, total });
    assert.equal(state.mode, "indeterminate", `total=${total}`);
    assert.equal(state.percent, null, `total=${total}`);
  }
  const overflow = new ProgressModel();
  const state = overflow.update({ seq: 1, phase: "parse", current: 20, total: 10 });
  assert.equal(state.mode, "indeterminate");
  assert.equal(state.percent, null);
});

test("old seq frames are dropped and percent never goes backwards", () => {
  const model = new ProgressModel();
  model.update({ seq: 5, phase: "parse", current: 40, total: 100 });
  const stale = model.update({ seq: 4, phase: "parse", current: 10, total: 100 });
  assert.equal(stale.current, 40);
  assert.equal(stale.percent, 40);
  const backwards = model.update({ seq: 6, phase: "parse", current: 30, total: 100 });
  assert.equal(backwards.current, 30);
  assert.equal(backwards.percent, 40);
});

test("overall weighting parse 70 and write 100", () => {
  const model = new ProgressModel();
  const parseStart = model.update({ seq: 1, phase: "parse", current: 0, total: 10 });
  assert.equal(parseStart.overallPercent, 15);
  const parseEnd = model.update({ seq: 2, phase: "parse", current: 10, total: 10 });
  assert.equal(parseEnd.overallPercent, 70);
  const writeEnd = model.update({ seq: 3, phase: "write", current: 10, total: 10 });
  assert.equal(writeEnd.overallPercent, 100);
});

test("walk never reports an overall percent", () => {
  const model = new ProgressModel();
  const state = model.update({ seq: 1, phase: "walk", current: 0, total: 0 });
  assert.equal(state.mode, "indeterminate");
  assert.equal(state.overallPercent, null);
  const known = model.update({ seq: 2, phase: "walk", current: 3, total: 0 });
  assert.equal(known.overallPercent, null);
});

test("unknown phases never produce a percent", () => {
  const model = new ProgressModel();
  const state = model.update({ seq: 1, phase: "start", current: 1, total: 10 });
  assert.equal(state.mode, "indeterminate");
  assert.equal(state.percent, null);
  assert.equal(state.overallPercent, null);
});

test("terminal states: succeeded 100, cancelled and failed below 100", () => {
  const done = new ProgressModel();
  done.update({ seq: 1, phase: "write", current: 10, total: 10 });
  const succeeded = done.finish("succeeded");
  assert.equal(succeeded.mode, "terminal");
  assert.equal(succeeded.percent, 100);
  assert.equal(succeeded.overallPercent, 100);

  const cancelledModel = new ProgressModel();
  cancelledModel.update({ seq: 1, phase: "parse", current: 5, total: 10 });
  const cancelled = cancelledModel.finish("cancelled");
  assert.equal(cancelled.percent, 50);
  assert.equal(cancelled.overallPercent, 43);
  assert.equal(cancelled.cancelled, true);

  const failedModel = new ProgressModel();
  failedModel.update({ seq: 1, phase: "parse", current: 10, total: 10 });
  const failed = failedModel.finish("failed");
  assert.equal(failed.percent, 99);
  assert.equal(failed.overallPercent, 70);
  assert.equal(failed.cancelled, false);
});

test("cancel request keeps real percent and does not jump to 100", () => {
  const model = new ProgressModel();
  model.update({ seq: 1, phase: "parse", current: 3, total: 10 });
  const cancelling = model.cancelRequested();
  assert.equal(cancelling.status, "cancelling");
  assert.equal(cancelling.percent, 30);
  const after = model.update({ seq: 2, phase: "parse", current: 9, total: 10 });
  assert.equal(after.percent, 30);
  assert.equal(after.mode, "determinate");
});

test("phase order only moves forward", () => {
  const model = new ProgressModel();
  model.update({ seq: 1, phase: "parse", current: 1, total: 10 });
  const back = model.update({ seq: 2, phase: "walk", current: 2, total: 0 });
  assert.equal(back.phase, "parse");
  assert.equal(back.current, 1);
});