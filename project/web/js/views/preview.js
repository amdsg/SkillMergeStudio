import { escapeHtml, formatSize } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";

export function renderPreview(options) {
  const { content, status, mergeButton, preview, activeTab, decisions, onDecide, onRePreview } = options;
  if (!preview) return { unresolved: 0, hasError: false };
  const data = preview;

  if (activeTab === "chapters") {
    content.innerHTML = `<ul class="preview-list">${data.chapters
      .map((item) => `
        <li class="preview-item">
          <div class="preview-item-head">
            <strong>${escapeHtml(item.title)}</strong>
            <span class="badge ${escapeHtml(item.decision)}">${escapeHtml(item.decision)} · ${
              item.sim === null ? "NA" : Number(item.sim).toFixed(3)
            }</span>
          </div>
        </li>`)
      .join("")}</ul>`;
  } else if (activeTab === "conflicts") {
    if (!data.conflicts.length) {
      content.innerHTML = `<p class="muted">${escapeHtml(t("preview.noConflicts"))}</p>`;
    } else {
      content.innerHTML = data.conflicts
        .map((item) => `
          <div class="preview-item">
            <div class="preview-item-head">
              <strong>${escapeHtml(item.title)}</strong>
              <span class="badge conflict">sim ${item.sim === null ? "NA" : Number(item.sim).toFixed(3)}</span>
            </div>
            <div class="conflict-text">
              <pre>${escapeHtml(item.text_a)}</pre>
              <pre>${escapeHtml(item.text_b)}</pre>
            </div>
            <div class="conflict-actions" data-key="${escapeHtml(item.key)}">
              ${["keepA", "keepB", "keepBoth", "manual"]
                .map(
                  (action) =>
                    `<button data-action="${action}" class="${decisions[item.key] === action ? "chosen" : ""}">${action}</button>`
                )
                .join("")}
            </div>
          </div>`)
        .join("");
      content.querySelectorAll(".conflict-actions button").forEach((button) => {
        button.addEventListener("click", () => {
          const key = button.parentElement.dataset.key;
          if (onDecide) onDecide(key, button.dataset.action);
          if (onRePreview) onRePreview();
        });
      });
    }
  } else if (activeTab === "diff") {
    content.innerHTML = `<ul class="preview-list">${
      data.diff
        .map(
          (item) =>
            `<li class="preview-item"><span class="badge">${escapeHtml(item.op)}</span> ${escapeHtml(item.title)}</li>`
        )
        .join("") || `<li class="muted">${escapeHtml(t("common.none"))}</li>`
    }</ul>`;
  } else if (activeTab === "size") {
    const suggestions = data.size_estimate.suggestions;
    content.innerHTML = `
      <p>${escapeHtml(
        t("preview.estimate", {
          size: formatSize(data.size_estimate.bytes),
          method: data.size_estimate.method
        })
      )}</p>
      ${
        suggestions.length
          ? `<h3>${escapeHtml(t("preview.suggestions"))}</h3><ul class="suggestions">${suggestions
              .map((item) => `<li>${escapeHtml(item.chapter)}: ${formatSize(item.bytes)} (${item.priority})</li>`)
              .join("")}</ul>`
          : `<p class="muted">${escapeHtml(t("preview.none"))}</p>`
      }`;
  } else {
    content.innerHTML = `<ul class="preview-list">${
      data.validation
        .map(
          (item) => `
          <li class="validation-item ${escapeHtml(item.level)}">
            <strong>${escapeHtml(item.id)}</strong> ${escapeHtml(item.message)}
            <span class="fix">${escapeHtml(item.fix)}</span>
          </li>`
        )
        .join("") || `<li class="muted">${escapeHtml(t("preview.noValidation"))}</li>`
    }</ul>`;
  }

  const unresolved = data.chapters.filter(
    (item) => ["suggest", "conflict"].includes(item.decision) && !decisions[item.key]
  );
  const hasError = data.validation.some((item) => item.level === "error");
  mergeButton.disabled = unresolved.length > 0 || hasError;
  if (unresolved.length) {
    status.textContent = t("preview.unresolved", { count: unresolved.length });
  }
  return { unresolved: unresolved.length, hasError };
}