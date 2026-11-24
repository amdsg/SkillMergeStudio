import { createTutorialOverlay } from "./tutorial-overlay.js";
import { createSearchPanel } from "./search-panel.js";
import { createUpgradePanel } from "./upgrade-panel.js";
import { createConfigPreview } from "./config-preview.js";
import { renderTargetPicker } from "./convert-panel.js";
import { createAgentClient } from "../../lib/agent-client.js";
import { setLocale, t } from "../lib/i18n/index.js";

const root = document.getElementById("wb-root");
const localeSwitch = document.getElementById("locale-switch");
const tutorialButton = document.getElementById("tutorial-button");
const client = createAgentClient();

function applyLocale(locale) {
  setLocale(locale);
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of document.querySelectorAll("[data-i18n-placeholder]")) {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  }
}

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function stateLine() {
  const p = el("p");
  p.dataset.i18n = "wb.state.empty";
  return p;
}

function field(placeholderKey) {
  const input = el("input");
  input.type = "text";
  if (placeholderKey) input.dataset.i18nPlaceholder = placeholderKey;
  return input;
}

function button(labelKey) {
  const node = el("button");
  node.type = "button";
  node.dataset.i18n = labelKey;
  return node;
}

function downloadPanel(host) {
  const panel = el("section", "download-panel");
  const repo = field("wb.convert.search.placeholder");
  const run = button("wb.button.download");
  const state = stateLine();
  panel.append(repo, run, state);
  host.append(panel);
  run.addEventListener("click", async () => {
    state.dataset.i18n = "wb.state.loading";
    try {
      const data = await client.download({ repo_full_name: repo.value });
      state.textContent = `${data.dir_path || ""} · ${(data.files || []).length} files`;
    } catch (error) {
      state.dataset.i18n = "wb.state.failed";
      state.dataset.errorCode = error.code || "E_INTERNAL";
    }
  });
  return panel;
}

function mergePanel(host) {
  const panel = el("section", "merge-panel");
  const sources = field("wb.convert.search.placeholder");
  const run = button("wb.button.merge");
  const state = stateLine();
  panel.append(sources, run, state);
  host.append(panel);
  run.addEventListener("click", async () => {
    state.dataset.i18n = "wb.state.loading";
    try {
      const names = sources.value.split(",").map((s) => s.trim()).filter(Boolean);
      const data = await client.merge({ sources: names });
      state.textContent = `conflicts: ${data.merge_plan?.conflict_count ?? 0}`;
    } catch (error) {
      state.dataset.i18n = "wb.state.failed";
      state.dataset.errorCode = error.code || "E_INTERNAL";
    }
  });
  return panel;
}

function convertPanel(host) {
  const panel = el("section", "convert-panel");
  const source = field("wb.convert.search.placeholder");
  const pickerHost = el("div", "convert-targets");
  const run = button("wb.button.convert");
  const state = stateLine();
  panel.append(source, pickerHost, run, state);
  host.append(panel);
  let targetId = null;
  client.targets().then((data) => {
    renderTargetPicker(pickerHost, data.items || [], {});
  }).catch(() => {});
  pickerHost.addEventListener("click", (event) => {
    const row = event.target.closest("[data-target-id]");
    if (row) targetId = row.dataset.targetId;
  });
  run.addEventListener("click", async () => {
    state.dataset.i18n = "wb.state.loading";
    try {
      const data = await client.convert({ target_id: targetId, source_path: source.value, source_kind: "skill" });
      state.textContent = `${data.artifact_dir || ""} · tier ${data.tier || "unknown"}`;
    } catch (error) {
      state.dataset.i18n = "wb.state.failed";
      state.dataset.errorCode = error.code || "E_INTERNAL";
    }
  });
  return panel;
}

function writePanel(host) {
  const panel = el("section", "write-panel");
  const list = el("div", "capability-list");
  panel.append(list);
  host.append(panel);
  client.settings().then((data) => {
    for (const cap of data.capabilities || []) {
      const row = el("p");
      row.dataset.capabilityId = cap.capability_id;
      const toggle = button(null);
      toggle.textContent = `${cap.capability_id}: ${cap.enabled ? "on" : "off"}`;
      if (!cap.enabled) {
        toggle.addEventListener("click", async () => {
          try {
            await client.enableCapability(cap.capability_id, { risk_ack: data.risk_ack_version });
            toggle.textContent = `${cap.capability_id}: on`;
          } catch {
            toggle.textContent = `${cap.capability_id}: failed`;
          }
        });
      }
      row.append(toggle);
      list.append(row);
    }
  }).catch(() => {});
  return panel;
}

const PANELS = {
  search: (host) => createSearchPanel(host, client).panel,
  download: downloadPanel,
  merge: mergePanel,
  convert: convertPanel,
  config_preview: (host) => createConfigPreview(host, client).panel,
  write: writePanel,
  upgrade: (host) => createUpgradePanel(host, client).panel,
};

function showStep(step) {
  root.replaceChildren();
  const factory = PANELS[step];
  if (factory) factory(root);
  for (const node of document.querySelectorAll(".wb-nav [data-step]")) {
    node.classList.toggle("active", node.dataset.step === step);
  }
  applyLocale("zh");
}

for (const node of document.querySelectorAll(".wb-nav [data-step]")) {
  node.addEventListener("click", () => showStep(node.dataset.step));
}

localeSwitch?.addEventListener("change", (event) => applyLocale(event.target.value));

tutorialButton?.addEventListener("click", () => {
  const existing = document.querySelector(".tutorial-overlay");
  if (existing) {
    existing.remove();
    return;
  }
  createTutorialOverlay(root);
});

applyLocale("zh");
showStep("search");

export { root, applyLocale, showStep };
