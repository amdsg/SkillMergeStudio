import { escapeHtml, formatSize } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";
import { formatBadges } from "/js/views/platform-format.js";

function statusLabel(status) {
  if (status === "succeeded") return t("export.item.succeeded");
  if (status === "cancelled") return t("export.item.cancelled");
  return t("export.item.failed");
}

function pathLine(item) {
  const paths = [];
  if (item.dir_path) paths.push(`<code>${escapeHtml(item.dir_path)}</code>`);
  if (item.zip_path) paths.push(`<code>${escapeHtml(item.zip_path)}</code>`);
  if (item.installed_path) paths.push(`<code>${escapeHtml(item.installed_path)}</code>`);
  return paths.join("<br>");
}

export function createExportResults({ root }) {
  function render(result) {
    if (!result || result.batch !== true) {
      root.classList.add("hidden");
      return;
    }
    const items = Array.isArray(result.items) ? result.items : [];
    const summary = result.summary || {};
    const total = summary.total != null ? summary.total : items.length;
    const rows = items
      .map((item) => {
        const error = item.error
          ? `<div class="export-error"><strong>${escapeHtml(item.error.code || item.error.message || "")}</strong>
               <span>${escapeHtml(item.error.message || "")}</span>
               ${item.error.fix ? `<em>${escapeHtml(item.error.fix)}</em>` : ""}
             </div>`
          : "";
        const download = item.download_url
          ? `<a class="download-link" href="${escapeHtml(item.download_url)}">${escapeHtml(t("export.download"))}</a>`
          : "";
        return `<tr class="export-result-row ${escapeHtml(item.status || "")}">
          <td><span class="export-status-badge ${escapeHtml(item.status || "")}">${escapeHtml(statusLabel(item.status))}</span></td>
          <td>${escapeHtml(item.label || item.platform)}</td>
          <td><span class="format-badges">${formatBadges(item.format)
            .map((badge) => `<span class="format-badge ${escapeHtml(badge.tone)}">${escapeHtml(badge.text)}</span>`)
            .join("")}</span></td>
          <td>${pathLine(item)}${download}</td>
          <td>${item.size_bytes != null ? formatSize(item.size_bytes) : "—"}</td>
          <td>${error}</td>
        </tr>`;
      })
      .join("");
    root.innerHTML = `<div class="export-results-head">
        <strong>${escapeHtml(t("export.results"))}</strong>
        <span class="muted">${escapeHtml(t("export.summary", {
          ok: summary.succeeded || 0,
          failed: summary.failed || 0,
          cancelled: summary.cancelled || 0
        }))}</span>
        ${total !== items.length ? `<span class="export-warning">${escapeHtml(t("export.itemsMismatch", { total, items: items.length }))}</span>` : ""}
      </div>
      <table class="export-results-table">
        <thead><tr>
          <th>${escapeHtml(t("history.status"))}</th>
          <th>${escapeHtml(t("history.platform"))}</th>
          <th>${escapeHtml(t("export.format"))}</th>
          <th>${escapeHtml(t("export.paths"))}</th>
          <th>${escapeHtml(t("history.size"))}</th>
          <th>${escapeHtml(t("export.error"))}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
    root.classList.remove("hidden");
  }

  function reset() {
    root.innerHTML = "";
    root.classList.add("hidden");
  }

  return { render, reset };
}