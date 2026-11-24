import { ProgressModel } from "/js/util/progress-model.js";
import { phaseLabel } from "/js/util/phases.js";
import { t } from "/js/i18n/index.js";

const FRAME_INTERVAL_MS = 100;

function noop() {
  return {
    begin() {},
    update() {},
    finish() {},
    reset() {},
    cancelRequested() {},
    showSummary() {},
    refresh() {}
  };
}

export function createProgressBar({ container, summary }) {
  if (!container) return noop();

  const model = new ProgressModel();
  const meta = document.createElement("div");
  const text = document.createElement("span");
  const percentEl = document.createElement("span");
  const track = document.createElement("div");
  const fill = document.createElement("div");

  meta.className = "progress-meta";
  text.className = "progress-text";
  percentEl.className = "progress-percent";
  track.className = "progress-track";
  fill.className = "progress-fill";
  meta.append(text, percentEl);
  track.append(fill);
  container.append(meta, track);

  let timer = 0;
  let lastFrame = 0;

  function renderSummary(result) {
    if (!summary || !result) return;
    const stats = result.stats || {};
    const parts = [];
    if (Number(stats.found) > 0) parts.push(t("summary.found", { count: stats.found }));
    if (Number(stats.new) > 0) parts.push(t("summary.new", { count: stats.new }));
    if (Number(stats.updated) > 0) parts.push(t("summary.updated", { count: stats.updated }));
    if (Number(stats.skipped_permission) > 0) parts.push(t("summary.skipped", { count: stats.skipped_permission }));
    if (Number(stats.pruned) > 0) parts.push(t("summary.pruned", { count: stats.pruned }));
    if (Number(stats.dup_locations) > 0) parts.push(t("summary.duplicates", { count: stats.dup_locations }));
    if (stats.limit_hit) parts.push(t("summary.limit"));
    if (stats.time_limit_hit) parts.push(t("summary.timeout"));
    if (result.cancelled) parts.push(t("summary.cancelled"));
    summary.textContent = "";
    if (!parts.length) {
      summary.classList.add("hidden");
      return;
    }
    const label = document.createElement("span");
    label.textContent = parts.join(" · ");
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "scan-summary-button";
    clear.textContent = t("summary.clear");
    clear.addEventListener("click", () => {
      summary.textContent = "";
      summary.classList.add("hidden");
    });
    summary.append(label, clear);
    summary.classList.remove("hidden");
  }

  function paint() {
    const state = model.snapshot();
    const label = state.phase ? phaseLabel(state.phase) : "";
    const determinate = state.mode === "determinate" && state.percent !== null;
    let statusText = "";
    let percentText = "";
    if (state.mode === "terminal") {
      statusText =
        state.status === "succeeded"
          ? t("progress.succeeded")
          : state.status === "cancelled"
            ? t("progress.cancelled")
            : t("progress.failed");
      if (state.status === "succeeded") percentText = "100%";
    } else if (state.status === "cancelling") {
      statusText = t("progress.cancelling");
      if (determinate) percentText = `${state.percent}%`;
    } else if (determinate) {
      statusText = t("progress.summary", {
        phase: label,
        current: state.current,
        total: state.total,
        percent: state.percent
      });
      percentText = `${state.percent}%`;
    } else if (state.phase === "walk" && state.current > 0) {
      statusText = t("progress.walk", { count: state.current });
    } else {
      statusText = t("progress.indeterminate", { phase: label || t("phase.unknown", { phase: "?" }) });
    }

    text.textContent = statusText;
    percentEl.textContent = percentText;
    container.dataset.mode = state.mode;
    container.dataset.status = state.status;
    container.setAttribute("aria-busy", state.mode === "terminal" || state.status === "cancelling" ? "false" : "true");
    if (determinate) {
      container.setAttribute("aria-valuenow", String(state.percent));
      fill.style.width = `${state.percent}%`;
    } else if (state.mode === "terminal" && state.status === "succeeded") {
      container.setAttribute("aria-valuenow", "100");
      fill.style.width = "100%";
    } else {
      container.removeAttribute("aria-valuenow");
      fill.style.width = "35%";
    }
    container.setAttribute("aria-valuetext", statusText);
  }

  function schedule() {
    if (timer) return;
    const wait = Math.max(0, FRAME_INTERVAL_MS - (Date.now() - lastFrame));
    timer = setTimeout(() => {
      timer = 0;
      lastFrame = Date.now();
      try {
        paint();
      } catch (error) {
        console.warn("progress paint failed", error);
      }
    }, wait);
  }

  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = 0;
    }
  }

  return {
    begin() {
      clearTimer();
      container.classList.remove("hidden");
      model.reset();
      paint();
    },
    update(payload) {
      try {
        model.update(payload);
        schedule();
      } catch (error) {
        console.warn("progress update failed", error);
      }
    },
    cancelRequested() {
      model.cancelRequested();
      paint();
    },
    finish(status) {
      clearTimer();
      try {
        model.finish(status);
        paint();
      } catch (error) {
        console.warn("progress finish failed", error);
      }
    },
    reset() {
      clearTimer();
      model.reset();
      container.classList.add("hidden");
    },
    refresh() {
      paint();
    },
    showSummary(result) {
      renderSummary(result);
    }
  };
}