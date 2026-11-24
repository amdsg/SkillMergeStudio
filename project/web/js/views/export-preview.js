import { escapeHtml, formatSize } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";
import { formatBadges, formatDescription } from "/js/views/platform-format.js";

export function createExportPreview({ root }) {
  function render(result) {
    if (!result || !Array.isArray(result.items) || !result.items.length) {
      root.classList.add("hidden");
      return;
    }
    const summary = result.summary || {};
    const items = result.items
      .map((item) => {
        const validation = (item.validation || [])
          .map((check) => `<li class="${escapeHtml(check.level || "")}">${escapeHtml(check.message || "")} ${check.fix ? `<em>${escapeHtml(check.fix)}</em>` : ""}</li>`)
          .join("");
        const files = (item.planned && item.planned.files ? item.planned.files : [])
          .map((file) => `<li><code>${escapeHtml(file.rel_path)}</code> <span class="muted">${formatSize(file.size_bytes)}</span></li>`)
          .join("");
        return `<section class="export-preview-item">
          <header>
            <strong>${escapeHtml(item.label || item.platform)}</strong>
            <span class="format-badges">${formatBadges(item.format)
              .map((badge) => `<span class="format-badge ${escapeHtml(badge.tone)}">${escapeHtml(badge.text)}</span>`)
              .join("")}</span>
          </header>
          <p class="muted">${escapeHtml(formatDescription(item.format, item.planned && item.planned.name))}</p>
          <p class="muted">${escapeHtml(t("export.previewSize", { size: formatSize((item.planned && item.planned.total_size_bytes) || 0) }))}</p>
          ${item.requires_confirm ? `<p class="export-warning">${escapeHtml(t("export.candidateWarning"))}</p>` : ""}
          <ul class="export-preview-files">${files}</ul>
          ${validation ? `<ul class="export-preview-checks">${validation}</ul>` : ""}
        </section>`;
      })
      .join("");
    root.innerHTML = `<div class="export-preview-summary">
        <strong>${escapeHtml(t("export.previewTitle"))}</strong>
        <span class="muted">${escapeHtml(t("export.previewSummary", {
          total: summary.total || result.items.length,
          verified: summary.verified || 0,
          candidate: summary.candidate || 0
        }))}</span>
      </div>
      <div class="export-preview-list">${items}</div>`;
    root.classList.remove("hidden");
  }

  function showError(message) {
    root.innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
    root.classList.remove("hidden");
  }

  function reset() {
    root.innerHTML = "";
    root.classList.add("hidden");
  }

  return { render, showError, reset };
}