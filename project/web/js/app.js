import { createPlatformPicker } from "/js/views/platform-picker.js";
import { createCandidatePool } from "/js/views/candidate-pool.js";
import { createGithub } from "/js/views/github.js";
import { createSkillList } from "/js/views/skill-list.js";
import { detailHtml } from "/js/views/detail.js";
import { createHistory } from "/js/views/history.js";
import { createFilters, markQuickButtons } from "/js/views/filters.js";
import { createSettings } from "/js/views/settings.js";
import { createJobStream } from "/js/util/job-stream.js";
import { createJobRunner } from "/js/util/job-runner.js";
import { createProgressBar } from "/js/views/progress-bar.js";
import { createExportController } from "/js/views/export-controller.js";
import { closeModal as hideModal, openModal as showModal } from "/js/util/modal.js";
import { renderPreview } from "/js/views/preview.js";
import { renderBasketBar, renderPlatformCounts as paintPlatformCounts } from "/js/views/status-panel.js";
import { escapeHtml, formatSize, isTyping } from "/js/util/dom.js";
import { getLang, initLang, onLang, setLang, t } from "/js/i18n/index.js";

initLang();

const state = {
  items: [],
  categories: [],
  platforms: [],
  selectedId: "",
  currentJob: "",
  basket: new Set(),
  platform: "generic",
  decisions: {},
  preview: null,
  activeTab: "chapters",
  artifact: null,
  platformPicker: null,
  candidatePool: null,
  filters: {},
  duplicateIds: null
};

const el = {
  list: document.getElementById("list"),
  status: document.getElementById("status"),
  categories: document.getElementById("category-list"),
  detail: document.getElementById("detail"),
  scan: document.getElementById("scan-button"),
  refresh: document.getElementById("refresh-button"),
  search: document.getElementById("search"),
  platform: document.getElementById("platform-select"),
  platformInput: document.getElementById("platform-input"),
  platformListbox: document.getElementById("platform-listbox"),
  mergeName: document.getElementById("merge-name"),
  basketSummary: document.getElementById("basket-summary"),
  selectVisible: document.getElementById("select-visible"),
  clearBasket: document.getElementById("clear-basket"),
  previewButton: document.getElementById("preview-button"),
  modal: document.getElementById("preview-modal"),
  closeModal: document.getElementById("close-modal"),
  previewContent: document.getElementById("preview-content"),
  previewStatus: document.getElementById("preview-status"),
  mergeButton: document.getElementById("merge-button"),
  exportPanel: document.getElementById("export-panel"),
  exportMode: document.getElementById("export-mode"),
  lengthMode: document.getElementById("length-mode"),
  profile: document.getElementById("profile"),
  exportButton: document.getElementById("export-button"),
  exportPreviewButton: document.getElementById("export-preview-button"),
  exportPlatforms: document.getElementById("export-platforms"),
  exportPreview: document.getElementById("export-preview"),
  exportResults: document.getElementById("export-results"),
  historyPlatform: document.getElementById("history-platform"),
  exportStatus: document.getElementById("export-status"),
  candidatePoolButton: document.getElementById("candidate-pool-button"),
  candidatePoolModal: document.getElementById("candidate-pool-modal"),
  candidatePoolList: document.getElementById("candidate-pool-list"),
  candidatePoolClose: document.getElementById("candidate-pool-close"),
  classifyButton: document.getElementById("classify-button"),
  historyButton: document.getElementById("history-button"),
  historyModal: document.getElementById("history-modal"),
  historyBody: document.getElementById("history-body"),
  historyMessage: document.getElementById("history-message"),
  historyClose: document.getElementById("history-close"),
  filterBar: document.getElementById("filter-bar"),
  cancelButton: document.getElementById("cancel-button"),
  jobProgress: document.getElementById("job-progress"),
  scanSummary: document.getElementById("scan-summary"),
  langSelect: document.getElementById("lang-select"),
  settingsButton: document.getElementById("settings-button"),
  settingsModal: document.getElementById("settings-modal"),
  settingsForm: document.getElementById("settings-form"),
  settingsStatus: document.getElementById("settings-status"),
  settingsClose: document.getElementById("settings-close"),
  settingsSave: document.getElementById("settings-save"),
  settingsTest: document.getElementById("settings-test"),
  githubButton: document.getElementById("github-button"),
  githubModal: document.getElementById("github-modal"),
  githubClose: document.getElementById("github-close"),
  githubStatus: document.getElementById("github-status"),
  githubResults: document.getElementById("github-results"),
  githubQuery: document.getElementById("github-query"),
  githubSearchBtn: document.getElementById("github-search-btn")
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Skillmerge": "1", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json().catch(() => ({ ok: false, error: { message: "invalid JSON" } }));
  if (!response.ok || !payload.ok) {
    const error = payload.error || {};
    const failure = new Error(`${error.message || response.status} ${error.fix || ""}`.trim());
    failure.code = error.code || "";
    failure.fix = error.fix || "";
    failure.details = error.details || {};
    throw failure;
  }
  return payload.data;
}

function setStatus(text, tone = "") {
  el.status.textContent = text;
  el.status.className = `status ${tone}`;
}


const skillList = createSkillList({
  container: el.list,
  onOpen: (id) => openDetail(id),
  onToggle: (id) => toggleBasket(id),
  onRetry: () => loadList()
});
skillList.setChecked((id) => state.basket.has(id));

const filterController = createFilters({
  root: el.filterBar,
  getItems: () => state.items,
  onChange: (next) => {
    state.category = "";
    state.filters = { ...state.filters, ...next, uncategorized: false, duplicateIds: null };
    skillList.setFilters(state.filters);
    markQuick("");
    renderCategories();
  }
});

function renderList() {
  skillList.render();
  renderBasket();
}

function renderBasket() {
  renderBasketBar({
    summaryEl: el.basketSummary,
    previewButton: el.previewButton,
    items: state.items,
    basket: state.basket,
    platforms: state.platforms,
    platform: state.platform
  });
}

function renderCategories() {
  if (!state.categories.length && !state.items.length) {
    el.categories.innerHTML = `<li class="muted">${escapeHtml(t("sidebar.empty"))}</li>`;
    return;
  }
  const entries = [{ name: "", label: t("filter.all"), count: state.items.length }].concat(
    state.categories.map((item) => ({ name: item.name, label: item.name, count: item.count }))
  );
  el.categories.innerHTML = entries
    .map(
      (item) => `
      <li>
        <button data-category="${escapeHtml(item.name)}" class="${state.category === item.name ? "active" : ""}" type="button">
          ${escapeHtml(item.label)}<span>${item.count}</span>
        </button>
      </li>`
    )
    .join("");
  el.categories.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      state.category = button.dataset.category;
      state.filters = { ...state.filters, category: state.category, uncategorized: false };
      skillList.setFilters(state.filters);
      markQuick("");
      renderCategories();
    });
  });
}

async function openDetail(id) {
  state.selectedId = id;
  skillList.setSelected(id);
  el.detail.innerHTML = `<p class="muted">${escapeHtml(t("list.loading"))}</p>`;
  try {
    const [skill, artifacts] = await Promise.all([
      api(`/api/skills/${encodeURIComponent(id)}`),
      api(`/api/skills/${encodeURIComponent(id)}/artifacts`).catch(() => ({ items: [] }))
    ]);
    el.detail.innerHTML = detailHtml(skill, artifacts.items || [], state.basket.has(id));
    document.getElementById("add-basket").addEventListener("click", () => {
      toggleBasket(id);
      openDetail(id);
    });
  } catch (error) {
    el.detail.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

function toggleBasket(id) {
  if (state.basket.has(id)) state.basket.delete(id);
  else state.basket.add(id);
  renderList();
}

async function loadList() {
  skillList.showState("loading");
  try {
    const data = await api("/api/skills?limit=500");
    state.items = data.items || [];
    skillList.setItems(state.items);
    filterController.render();
    renderCategories();
    await loadDuplicates();
  } catch (error) {
    const permission = ["UNAUTHENTICATED", "HOST_FORBIDDEN", "ORIGIN_FORBIDDEN", "MISSING_CSRF_HEADER"].includes(error.code);
    skillList.showState(permission ? "permission_error" : "failed", {
      message: error.message,
      fix: error.fix,
      code: error.code
    });
  }
}

async function loadDuplicates() {
  try {
    const data = await api("/api/duplicates");
    const ids = new Set();
    (data.items || []).forEach((group) => (group.ids || []).forEach((id) => ids.add(id)));
    state.duplicateIds = ids;
  } catch (error) {
    state.duplicateIds = null;
  }
}

async function loadCategories() {
  const data = await api("/api/categories");
  state.categories = data.items || [];
  renderCategories();
}

async function loadPlatforms() {
  const data = await api("/api/platforms");
  state.platforms = data.items || [];
  if (!state.platforms.some((item) => item.id === state.platform)) {
    state.platform = state.platforms.length ? state.platforms[0].id : "generic";
  }
  if (!state.platformPicker) {
    state.platformPicker = createPlatformPicker({
      input: el.platformInput,
      listbox: el.platformListbox,
      getItems: () => state.platforms,
      getSelected: () => state.platform,
      onSelect: (item) => {
        state.platform = item.id;
        el.platform.value = item.id;
        renderBasket();
        if (state.preview) preview();
      }
    });
    state.candidatePool = createCandidatePool({
      button: el.candidatePoolButton,
      modal: el.candidatePoolModal,
      list: el.candidatePoolList,
      closeButton: el.candidatePoolClose,
      getItems: () => state.platforms,
      onSelect: (item) => {
        state.platform = item.id;
        el.platform.value = item.id;
        state.platformPicker.setValue(item.id);
        renderBasket();
        if (state.preview) preview();
      }
    });
  }
  state.platformPicker.setItems();
  state.platformPicker.setValue(state.platform);
  renderPlatformCounts(data);
  exportController.render();
  renderBasket();
}

function renderPlatformCounts(data) {
  paintPlatformCounts({
    element: document.getElementById("platform-counts"),
    platforms: state.platforms,
    data
  });
}

const stream = createJobStream({
  getJob: (id) => api(`/api/jobs/${encodeURIComponent(id)}`)
});

const progressBar = createProgressBar({
  container: el.jobProgress,
  summary: el.scanSummary
});

const jobRunner = createJobRunner({ stream, progressBar, el, state, api, setStatus });
const { followJob, cancelCurrent } = jobRunner;

const exportController = createExportController({
  el,
  state,
  api
});

async function startScan() {
  el.scan.disabled = true;
  setStatus(t("status.scanning"));
  try {
    const data = await api("/api/scan", { method: "POST", body: JSON.stringify({ depth: 10 }) });
    setStatus(t("status.queued"));
    followJob(data.job_id, async () => {
      await Promise.all([loadList(), loadCategories()]);
    }, "scan");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    el.scan.disabled = false;
  }
}

async function classify() {
  el.classifyButton.disabled = true;
  setStatus(t("status.scanning"));
  try {
    const data = await api("/api/classify", { method: "POST", body: JSON.stringify({}) });
    setStatus(t("status.classifyQueued"));
    followJob(data.job_id, async () => {
      await Promise.all([loadList(), loadCategories()]);
      setStatus(t("status.classifyDone"), "ok");
    }, "classify");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    el.classifyButton.disabled = false;
  }
}


async function preview() {
  const sources = Array.from(state.basket);
  if (!sources.length) {
    setStatus(t("list.emptyTitle"), "error");
    return;
  }
  el.previewStatus.textContent = t("list.loading");
  try {
    const data = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({
        sources,
        name: el.mergeName.value.trim() || "merged-skill",
        platform: state.platform,
        strategy: "keep-all",
        decisions: state.decisions
      })
    });
    state.preview = data;
    el.previewStatus.textContent = t("preview.estimated", {
      count: sources.length,
      size: formatSize(data.size_estimate.bytes)
    });
    renderPreviewView();
    showModal(el.modal);
  } catch (error) {
    setStatus(error.message, "error");
    el.previewStatus.textContent = error.message;
  }
}

function renderPreviewView() {
  if (!state.preview) return;
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === state.activeTab);
  });
  renderPreview({
    content: el.previewContent,
    status: el.previewStatus,
    mergeButton: el.mergeButton,
    preview: state.preview,
    activeTab: state.activeTab,
    decisions: state.decisions,
    onDecide: (key, action) => {
      state.decisions[key] = action;
    },
    onRePreview: () => preview()
  });
}

async function merge() {
  if (!state.preview) return;
  el.mergeButton.disabled = true;
  el.previewStatus.textContent = t("preview.merging");
  try {
    const data = await api("/api/merge", {
      method: "POST",
      body: JSON.stringify({
        sources: Array.from(state.basket),
        name: el.mergeName.value.trim() || "merged-skill",
        platform: state.platform,
        strategy: "keep-all",
        decisions: state.decisions
      })
    });
    followJob(data.job_id, (result) => {
      state.artifact = result;
      el.exportPanel.classList.remove("hidden");
      el.exportStatus.textContent = "";
      exportController.setDefault(state.platform);
      exportController.resetResults();
      el.previewStatus.textContent = t("preview.done", { path: result.dir_path });
      setStatus(t("preview.done", { path: result.dir_path }), "ok");
      loadCategories().catch(() => {});
    }, "merge");
  } catch (error) {
    el.previewStatus.textContent = error.message;
    el.mergeButton.disabled = false;
  }
}


async function exportArtifact() {
  if (!state.artifact) {
    el.exportStatus.textContent = t("export.needMerge");
    return;
  }
  const items = exportController.getSelectedItems();
  const platforms = items.map((item) => item.id);
  if (!platforms.length) {
    el.exportStatus.textContent = t("export.noPlatform");
    return;
  }
  const mode = el.exportMode.value;
  if (mode === "install") {
    const blocked = items.filter(
      (item) => !(item.format && Array.isArray(item.format.install_scopes) && item.format.install_scopes.length)
    );
    if (blocked.length) {
      el.exportStatus.textContent = t("export.installDisabled");
      return;
    }
  }
  const candidates = items.filter((item) => item.requires_confirm);
  if (candidates.length && !window.confirm(t("export.candidateBatch", { count: candidates.length }))) {
    el.exportStatus.textContent = t("export.candidateCancel");
    return;
  }
  el.exportButton.disabled = true;
  el.exportStatus.textContent = t("list.loading");
  exportController.resetResults();
  try {
    const body = {
      artifact_id: state.artifact.artifact_id,
      platforms,
      mode,
      length_mode: el.lengthMode.value,
      profile: el.profile.value
    };
    if (candidates.length) body.confirm_candidate = true;
    if (mode === "install") body.install_scope = "global";
    const data = await api("/api/export", { method: "POST", body: JSON.stringify(body) });
    followJob(data.job_id, (result) => {
      exportController.renderResults(result);
      el.exportStatus.textContent = t("export.batchDone");
      setStatus(t("export.batchDone"), "ok");
    }, "export");
  } catch (error) {
    el.exportStatus.textContent = error.message;
  } finally {
    el.exportButton.disabled = false;
  }
}

const historyPanel = createHistory({
  modal: el.historyModal,
  body: el.historyBody,
  message: el.historyMessage,
  closeButton: el.historyClose,
  request: api,
  platformSelect: el.historyPlatform,
  platforms: () => state.platforms,
  onChanged: () => Promise.all([loadList(), loadCategories()]).catch(() => {})
});

const settingsPanel = createSettings({
  modal: el.settingsModal,
  form: el.settingsForm,
  status: el.settingsStatus,
  closeButton: el.settingsClose,
  saveButton: el.settingsSave,
  testButton: el.settingsTest,
  request: api,
  onSaved: (config) => {
    if (config && config.language) {
      setLang(config.language);
      el.langSelect.value = config.language;
    }
    Promise.all([loadList(), loadCategories()]).catch(() => {});
  }
});

const githubPanel = createGithub({
  modal: el.githubModal,
  closeButton: el.githubClose,
  request: api,
  statusEl: el.githubStatus,
  resultsEl: el.githubResults,
  queryInput: el.githubQuery,
  searchBtn: el.githubSearchBtn,
  modeButtons: Array.from(document.querySelectorAll(".github-modes [data-mode]")),
  windowButtons: Array.from(document.querySelectorAll(".github-window-row [data-window]")),
  searchRow: document.querySelector(".github-search-row"),
  windowRow: document.querySelector(".github-window-row")
});

function markQuick(active) {
  markQuickButtons(document, active);
}

function applyQuick(kind) {
  const base = { ...state.filters };
  if (kind === "uncategorized") {
    state.category = "";
    state.filters = { ...base, category: "", uncategorized: true, duplicateIds: null, qualityMax: null };
  } else if (kind === "duplicates") {
    state.filters = { ...base, uncategorized: false, duplicateIds: state.duplicateIds || new Set() };
  } else if (kind === "lowQuality") {
    state.filters = { ...base, uncategorized: false, duplicateIds: null, qualityMin: 0, qualityMax: 59 };
  } else {
    state.filters = { ...base, uncategorized: false, duplicateIds: null, qualityMax: null };
  }
  skillList.setFilters(state.filters);
  markQuick(kind);
  renderCategories();
}

el.scan.addEventListener("click", startScan);
el.refresh.addEventListener("click", () =>
  Promise.all([loadList(), loadCategories()]).catch((error) => setStatus(error.message, "error"))
);
el.search.addEventListener("input", (event) => {
  state.filters = { ...state.filters, query: event.target.value };
  skillList.setFilters({ query: event.target.value });
});

el.selectVisible.addEventListener("click", () => {
  skillList.visible().forEach((item) => state.basket.add(item.id));
  renderList();
});
el.clearBasket.addEventListener("click", () => {
  state.basket.clear();
  state.decisions = {};
  state.preview = null;
  renderList();
});
el.previewButton.addEventListener("click", preview);
el.mergeButton.addEventListener("click", merge);
exportController.attach();
el.exportButton.addEventListener("click", exportArtifact);
el.closeModal.addEventListener("click", () => hideModal(el.modal));
el.cancelButton.addEventListener("click", cancelCurrent);
el.classifyButton.addEventListener("click", classify);
el.historyButton.addEventListener("click", () => historyPanel.open());
el.settingsButton.addEventListener("click", () => settingsPanel.open());
el.githubButton.addEventListener("click", () => githubPanel.open());
document.querySelectorAll("[data-quick]").forEach((button) => {
  button.addEventListener("click", () => applyQuick(button.dataset.quick));
});
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.activeTab = tab.dataset.tab;
    renderPreviewView();
  });
});

el.langSelect.value = getLang();
el.langSelect.addEventListener("change", () => setLang(el.langSelect.value));
onLang(() => {
  renderCategories();
  skillList.render();
  renderBasket();
  filterController.render();
  progressBar.refresh();
  exportController.onLang();
  if (state.preview) renderPreviewView();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !isTyping(event.target)) {
    event.preventDefault();
    el.search.focus();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a" && !isTyping(event.target)) {
    event.preventDefault();
    skillList.visible().forEach((item) => state.basket.add(item.id));
    renderList();
  }
  if (event.key === "Escape") {
    if (!el.modal.classList.contains("hidden")) hideModal(el.modal);
    historyPanel.close();
    settingsPanel.close();
    githubPanel.close();
    state.selectedId = "";
    skillList.setSelected("");
    renderList();
  }
});

Promise.all([loadList(), loadCategories(), loadPlatforms()])
  .catch(() => {})
  .finally(() => jobRunner.restoreRunningJob(() => Promise.all([loadList(), loadCategories()])));