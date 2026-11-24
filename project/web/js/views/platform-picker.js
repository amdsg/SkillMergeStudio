import { filterPlatforms } from "../util/fuzzy.js";
import { escapeHtml } from "../util/dom.js";
import { t } from "../i18n/index.js";
import { ROW_HEIGHT, windowSlice } from "../util/platform-window.js";

const GROUP_STORAGE = "sms.platform.groups";
const RECENT_STORAGE = "sms.platform.recent";

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch (error) {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    return;
  }
}

function badge(item) {
  if (item.requires_confirm) {
    return `<span class="platform-badge candidate">${escapeHtml(t("candidate.requiresConfirm"))}</span>`;
  }
  return `<span class="platform-badge verified">${escapeHtml(t("picker.verified"))}</span>`;
}

function formatChip(item) {
  const format = item.format || {};
  if (!format.package_type) {
    return `<span class="picker-format muted">${escapeHtml(t("format.unknown"))}</span>`;
  }
  const suffix = format.wrap ? " · wrap" : "";
  return `<span class="picker-format">${escapeHtml(format.package_type + suffix)}</span>`;
}

export function createPlatformPicker({ input, listbox, getItems, getSelected, onSelect }) {
  const spacer = document.createElement("div");
  spacer.className = "picker-spacer";
  const rowsBox = document.createElement("div");
  rowsBox.className = "picker-rows";
  listbox.appendChild(spacer);
  listbox.appendChild(rowsBox);
  let rows = [];
  let active = -1;
  let open = false;
  let query = "";
  let collapsed = readJson(GROUP_STORAGE, {});
  if (!("__candidate__" in collapsed)) collapsed.__candidate__ = true;
  let recent = readJson(RECENT_STORAGE, []);
  let selectedId = getSelected ? getSelected() : "";

  function selectableIndices() {
    return rows.map((row, index) => (row.type === "item" ? index : -1)).filter((index) => index >= 0);
  }

  function buildRows() {
    const items = getItems() || [];
    if (query) {
      return filterPlatforms(items, query).map((item) => ({ type: "item", item }));
    }
    const result = [];
    const recentItems = recent.map((id) => items.find((item) => item.id === id)).filter(Boolean);
    if (recentItems.length) {
      result.push({ type: "header", label: t("picker.recent"), key: "__recent__", count: recentItems.length });
      if (!collapsed.__recent__) recentItems.forEach((item) => result.push({ type: "item", item }));
    }
    const groups = {};
    items
      .filter((item) => item.verification_status === "verified" && !recentItems.some((recentItem) => recentItem.id === item.id))
      .forEach((item) => {
        (groups[item.group] = groups[item.group] || []).push(item);
      });
    Object.keys(groups).sort().forEach((group) => {
      const key = `verified:${group}`;
      result.push({ type: "header", label: group, key, count: groups[group].length });
      if (!collapsed[key]) groups[group].forEach((item) => result.push({ type: "item", item }));
    });
    const candidates = items.filter((item) => item.verification_status === "unknown");
    if (candidates.length) {
      result.push({ type: "header", label: t("candidate.header"), key: "__candidate__", count: candidates.length });
      if (!collapsed.__candidate__) candidates.forEach((item) => result.push({ type: "item", item }));
    }
    return result;
  }

  function rowHtml(row, index) {
    if (row.type === "header") {
      const arrow = collapsed[row.key] ? "▸" : "▾";
      return `<div class="picker-row picker-header" data-index="${index}" data-header="${row.key}">${arrow} ${escapeHtml(row.label)}（${row.count}）</div>`;
    }
    const item = row.item;
    return `<div class="picker-row ${index === active ? "active" : ""}" role="option" id="platform-opt-${index}" data-index="${index}" aria-selected="${item.id === selectedId}">
      <span class="picker-label">${escapeHtml(item.label)}</span>${formatChip(item)}${badge(item)}<span class="picker-meta">${escapeHtml(item.group)}</span>
    </div>`;
  }

  function render() {
    rows = buildRows();
    const box = listbox.getBoundingClientRect();
    const height = box.height || 280;
    const windowed = windowSlice(rows.length, listbox.scrollTop, height);
    spacer.style.height = `${windowed.totalHeight}px`;
    rowsBox.style.transform = `translateY(${windowed.offset}px)`;
    rowsBox.innerHTML = rows.slice(windowed.start, windowed.end).map((row, offset) => rowHtml(row, windowed.start + offset)).join("");
    const selected = rows[active];
    input.setAttribute("aria-expanded", open ? "true" : "false");
    if (open && selected && selected.type === "item") {
      input.setAttribute("aria-activedescendant", `platform-opt-${active}`);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
    const items = selectableIndices();
    if (!items.includes(active)) active = items.length ? items[0] : -1;
  }

  function positionActive(step) {
    const indices = selectableIndices();
    if (!indices.length) return;
    const current = indices.indexOf(active);
    const next = current < 0 ? 0 : (current + step + indices.length) % indices.length;
    active = indices[next];
    const rowTop = active * ROW_HEIGHT;
    if (rowTop < listbox.scrollTop) listbox.scrollTop = rowTop;
    if (rowTop + ROW_HEIGHT > listbox.scrollTop + listbox.clientHeight) {
      listbox.scrollTop = rowTop + ROW_HEIGHT - listbox.clientHeight;
    }
    render();
  }

  function choose(index) {
    const row = rows[index];
    if (!row || row.type !== "item") return;
    selectedId = row.item.id;
    recent = [selectedId, ...recent.filter((id) => id !== selectedId)].slice(0, 5);
    writeJson(RECENT_STORAGE, recent);
    input.value = row.item.label;
    close();
    onSelect(row.item);
  }

  function openList() {
    open = true;
    render();
  }

  function close() {
    open = false;
    input.setAttribute("aria-expanded", "false");
    const selected = (getItems() || []).find((item) => item.id === selectedId);
    if (selected) input.value = selected.label;
  }

  listbox.addEventListener("click", (event) => {
    const row = event.target.closest("[data-index]");
    if (!row) return;
    const index = Number(row.dataset.index);
    const data = rows[index];
    if (!data) return;
    if (data.type === "header") {
      collapsed[data.header] = !collapsed[data.header];
      writeJson(GROUP_STORAGE, collapsed);
      render();
      return;
    }
    choose(index);
  });

  listbox.addEventListener("scroll", () => {
    if (open) render();
  });

  input.addEventListener("focus", openList);
  input.addEventListener("input", (event) => {
    query = event.target.value;
    active = -1;
    openList();
  });
  input.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (!listbox.contains(document.activeElement)) close();
    }, 120);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) openList();
      positionActive(1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) openList();
      positionActive(-1);
      return;
    }
    if (event.key === "Enter" && open && active >= 0) {
      event.preventDefault();
      choose(active);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key === "Home" && open) {
      event.preventDefault();
      active = selectableIndices()[0] ?? -1;
      render();
    }
    if (event.key === "End" && open) {
      event.preventDefault();
      active = selectableIndices().slice(-1)[0] ?? -1;
      render();
    }
    if (event.key === "Tab") close();
  });

  const selected = (getItems() || []).find((item) => item.id === selectedId);
  if (selected) input.value = selected.label;

  return {
    setItems() {
      const item = (getItems() || []).find((entry) => entry.id === selectedId);
      if (item) input.value = item.label;
      if (open) render();
    },
    setValue(platformId) {
      selectedId = platformId;
      const item = (getItems() || []).find((entry) => entry.id === platformId);
      if (item) input.value = item.label;
      render();
    },
    getValue() {
      return selectedId;
    },
    open: openList,
    close,
  };
}