import { escapeHtml } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";
import { formatBadgeHtml } from "/js/views/platform-format.js";

const MAX_PLATFORMS = 28;

export function createExportPlatforms({ root, getItems, getDefault, onSelectionChange }) {
  const selected = new Set();
  let mode = "zip";
  let message = "";
  let initialized = false;

  function items() {
    return getItems() || [];
  }

  function installable(item) {
    return Array.isArray(item.format && item.format.install_scopes) && item.format.install_scopes.length > 0;
  }

  function selectedItems() {
    return items().filter((item) => selected.has(item.id));
  }

  function pruneSelection() {
    const available = new Set(items().map((item) => item.id));
    Array.from(selected).forEach((id) => {
      if (!available.has(id)) selected.delete(id);
    });
    if (mode === "install") {
      selectedItems().forEach((item) => {
        if (!installable(item)) selected.delete(item.id);
      });
    }
  }

  function notify() {
    if (onSelectionChange) onSelectionChange(selectedItems(), message);
  }

  function toggle(id, checked) {
    if (checked && selected.size >= MAX_PLATFORMS) {
      message = t("export.tooMany", { max: MAX_PLATFORMS });
      return false;
    }
    message = "";
    if (checked) selected.add(id);
    else selected.delete(id);
    return true;
  }

  function render() {
    if (!initialized && !selected.size) {
      const fallback = getDefault && getDefault();
      if (fallback) selected.add(fallback);
      initialized = true;
    }
    pruneSelection();
    const list = items();
    if (!list.length) {
      root.innerHTML = `<p class="muted">${escapeHtml(t("platform.loading"))}</p>`;
      return;
    }
    const groups = {};
    list.forEach((item) => {
      const key = item.verification_status === "verified" ? item.group || "verified" : t("candidate.header");
      (groups[key] = groups[key] || []).push(item);
    });
    const rows = Object.keys(groups)
      .sort()
      .map((group) => {
        const groupItems = groups[group]
          .map((item) => {
            const disabled = mode === "install" && !installable(item);
            const checked = selected.has(item.id);
            const reason = disabled ? `<span class="export-platform-note">${escapeHtml(t("export.installDisabled"))}</span>` : "";
            return `<label class="export-platform-row ${disabled ? "disabled" : ""}">
              <input type="checkbox" data-platform="${escapeHtml(item.id)}" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}>
              <span class="export-platform-label">${escapeHtml(item.label)}</span>
              <span class="export-platform-format">${formatBadgeHtml(item.format)}</span>
              ${reason}
            </label>`;
          })
          .join("");
        return `<fieldset class="export-platform-group"><legend>${escapeHtml(group)} <span>${groups[group].length}</span></legend>${groupItems}</fieldset>`;
      })
      .join("");
    root.innerHTML = `<div class="export-platform-head">
        <strong>${escapeHtml(t("export.platforms"))}</strong>
        <span class="muted">${escapeHtml(t("export.selected", { count: selected.size, max: MAX_PLATFORMS }))}</span>
      </div>
      ${message ? `<p class="export-platform-message" role="status">${escapeHtml(message)}</p>` : ""}
      <div class="export-platform-list">${rows}</div>`;
    notify();
  }

  root.addEventListener("change", (event) => {
    const input = event.target.closest("input[data-platform]");
    if (!input) return;
    const allowed = toggle(input.dataset.platform, input.checked);
    if (!allowed) input.checked = false;
    render();
  });

  return {
    render,
    getSelected() {
      return selectedItems().map((item) => item.id);
    },
    getSelectedItems() {
      return selectedItems();
    },
    setMode(next) {
      mode = next;
      render();
    },
    setDefault(id) {
      if (!initialized && id) {
        selected.add(id);
        initialized = true;
      }
    },
    count() {
      return selected.size;
    }
  };
}