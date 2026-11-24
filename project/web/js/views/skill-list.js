import { escapeHtml, formatSize, formatTime } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";

const ROW_HEIGHT = 92;
const OVERSCAN = 6;

function sourceLabel(source) {
  if (source === "manual") return t("source.manual");
  if (source === "ai") return t("source.ai");
  return t("source.keyword");
}

export function createSkillList(options) {
  const { container, onOpen, onToggle, onRetry } = options;
  let items = [];
  let filters = {
    query: "",
    category: "",
    platform: "",
    sizeMin: null,
    sizeMax: null,
    qualityMin: null,
    qualityMax: null,
    mtimeFrom: null,
    copiesMin: null,
    uncategorized: false,
    duplicateIds: null
  };
  let selectedId = "";
  let activeIndex = -1;
  let isChecked = () => false;
  let viewState = "ready";
  let viewPayload = {};
  let frame = 0;
  let index = { category: new Map(), platform: new Map(), positions: [] };

  function rebuildIndex() {
    index = { category: new Map(), platform: new Map(), positions: items.map((_item, position) => position) };
    items.forEach((item, position) => {
      const category = item.category || t("common.uncategorized");
      if (!index.category.has(category)) index.category.set(category, []);
      index.category.get(category).push(position);
      const platform = item.platform_origin || "unknown";
      if (!index.platform.has(platform)) index.platform.set(platform, []);
      index.platform.get(platform).push(position);
    });
  }

  function intersect(left, right) {
    const lookup = new Set(right);
    return left.filter((position) => lookup.has(position));
  }

  function candidates() {
    const groups = [];
    if (filters.category) groups.push(index.category.get(filters.category) || []);
    if (filters.platform) groups.push(index.platform.get(filters.platform) || []);
    if (!groups.length) return index.positions;
    return groups.reduce((left, right) => intersect(left, right));
  }

  function passes(item, needle) {
    const size = Number(item.size_bytes || 0);
    if (filters.sizeMin !== null && size < filters.sizeMin) return false;
    if (filters.sizeMax !== null && size >= filters.sizeMax) return false;
    if (filters.qualityMin !== null && Number(item.quality_score || 0) < filters.qualityMin) return false;
    if (filters.qualityMax !== null && Number(item.quality_score || 0) > filters.qualityMax) return false;
    if (filters.mtimeFrom !== null && Number(item.mtime || 0) < filters.mtimeFrom) return false;
    if (filters.copiesMin !== null && Number(item.locations_count || 1) < filters.copiesMin) return false;
    if (filters.uncategorized && (item.category || t("common.uncategorized")) !== t("common.uncategorized")) return false;
    if (filters.duplicateIds && !filters.duplicateIds.has(item.id)) return false;
    if (!needle) return true;
    return `${item.name || ""} ${item.description || ""}`.toLowerCase().includes(needle);
  }

  function rows() {
    const needle = filters.query.trim().toLowerCase();
    const result = [];
    for (const position of candidates()) {
      const item = items[position];
      if (item && passes(item, needle)) result.push(item);
    }
    return result;
  }

  function rowHtml(item, position, active) {
    const flagged = Boolean(item.parse_error || item.missing);
    const confidence = Number(item.confidence || 0).toFixed(2);
    const label = sourceLabel(item.category_source);
    const name = item.name || t("common.unnamed");
    return `
      <article class="row vrow${item.id === selectedId ? " selected" : ""}${active ? " active" : ""}${flagged ? " bad" : ""}"
               style="top:${position * ROW_HEIGHT}px" data-id="${escapeHtml(item.id)}" tabindex="0"
               role="option" aria-selected="${item.id === selectedId}">
        <div class="row-head">
          <input class="check" type="checkbox" data-check="${escapeHtml(item.id)}"
                 ${isChecked(item.id) ? "checked" : ""} aria-label="${escapeHtml(t("list.toggle", { name }))}">
          <div class="row-main">
            <strong>${flagged ? `<span class="flag" title="${escapeHtml(t("list.bad"))}">!</span>` : ""}${escapeHtml(name)}</strong>
            <p>${escapeHtml(item.description || "")}</p>
          </div>
        </div>
        <div class="row-meta">
          <span class="pill" title="${escapeHtml(t("list.categoryHint", { source: label, confidence }))}">${escapeHtml(item.category || t("common.uncategorized"))}</span>
          <span class="cell">${escapeHtml(item.platform_origin || "unknown")}</span>
          <span class="cell">${formatSize(item.size_bytes)}</span>
          <span class="cell">${escapeHtml(t("list.quality", { score: item.quality_score ?? 0 }))}</span>
          <span class="cell">${escapeHtml(t("list.copies", { count: item.locations_count ?? 1 }))}</span>
          <span class="cell">${formatTime(item.mtime)}</span>
        </div>
      </article>`;
  }

  function skeletonHtml() {
    return `<div class="skeleton-list">${Array.from({ length: 6 })
      .map(() => '<div class="row skeleton" aria-hidden="true"></div>')
      .join("")}</div>`;
  }

  function emptyHtml() {
    return `<div class="empty"><h3>${escapeHtml(t("list.emptyTitle"))}</h3><p>${escapeHtml(t("list.emptyBody"))}</p></div>`;
  }

  function errorHtml() {
    const title = viewState === "permission_error" ? t("list.permission") : t("list.failed");
    const message = viewPayload.message || "";
    const fix = viewPayload.fix || "";
    const code = viewPayload.code || "";
    return `
      <div class="empty error-state">
        <h3>${escapeHtml(title)}</h3>
        ${message ? `<p>${escapeHtml(message)}</p>` : ""}
        ${fix ? `<p class="muted">${escapeHtml(fix)}</p>` : ""}
        ${code ? `<p class="muted">${escapeHtml(code)}</p>` : ""}
        <button type="button" class="secondary" data-retry>${escapeHtml(t("list.retry"))}</button>
      </div>`;
  }

  function render() {
    if (viewState === "loading") {
      container.innerHTML = skeletonHtml();
      return;
    }
    if (viewState === "permission_error" || viewState === "failed") {
      container.innerHTML = errorHtml();
      return;
    }
    const list = rows();
    if (!list.length) {
      container.innerHTML = emptyHtml();
      return;
    }
    const total = list.length;
    const viewport = container.clientHeight || 560;
    const start = Math.max(0, Math.floor(container.scrollTop / ROW_HEIGHT) - OVERSCAN);
    const end = Math.min(total, Math.ceil((container.scrollTop + viewport) / ROW_HEIGHT) + OVERSCAN);
    let html = `<div class="vlist-inner" style="height:${total * ROW_HEIGHT}px" role="listbox" aria-label="${escapeHtml(t("sidebar.title"))}">`;
    for (let position = start; position < end; position += 1) {
      html += rowHtml(list[position], position, position === activeIndex);
    }
    container.innerHTML = `${html}</div>`;
  }

  function schedule() {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      render();
    });
  }

  function focusIndex(list) {
    const top = activeIndex * ROW_HEIGHT;
    const bottom = top + ROW_HEIGHT;
    if (top < container.scrollTop) container.scrollTop = top;
    if (bottom > container.scrollTop + container.clientHeight) {
      container.scrollTop = bottom - container.clientHeight;
    }
    render();
  }

  container.addEventListener("scroll", schedule, { passive: true });
  container.addEventListener("click", (event) => {
    if (event.target.matches(".check")) return;
    if (event.target.closest("[data-retry]")) {
      if (onRetry) onRetry();
      return;
    }
    const row = event.target.closest(".row");
    if (row) onOpen(row.dataset.id);
  });
  container.addEventListener("change", (event) => {
    if (event.target.matches("[data-check]")) onToggle(event.target.dataset.check);
  });
  container.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea, select")) return;
    const list = rows();
    if (!list.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      activeIndex = Math.max(0, Math.min(list.length - 1, activeIndex + step));
      focusIndex(list);
      return;
    }
    if (event.key === " ") {
      event.preventDefault();
      const item = list[activeIndex >= 0 ? activeIndex : 0];
      if (item) onToggle(item.id);
      return;
    }
    if (event.key === "Enter") {
      const item = list[activeIndex >= 0 ? activeIndex : 0];
      if (item) {
        event.preventDefault();
        onOpen(item.id);
      }
    }
  });

  rebuildIndex();

  return {
    setItems(next) {
      items = Array.isArray(next) ? next : [];
      activeIndex = -1;
      rebuildIndex();
      if (viewState === "loading") viewState = "ready";
      render();
    },
    setFilters(next) {
      filters = { ...filters, ...(next || {}) };
      activeIndex = -1;
      container.scrollTop = 0;
      render();
    },
    setSelected(id) {
      selectedId = String(id || "");
      render();
    },
    setChecked(fn) {
      isChecked = typeof fn === "function" ? fn : () => false;
      render();
    },
    showState(kind, payload = {}) {
      viewState = kind;
      viewPayload = payload || {};
      render();
    },
    visible() {
      return rows();
    },
    visibleCount() {
      return rows().length;
    },
    render
  };
}