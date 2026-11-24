import { escapeHtml } from "../util/dom.js";
import { t } from "../i18n/index.js";

export function createCandidatePool({ button, modal, list, closeButton, getItems, onSelect }) {
  function render() {
    const items = (getItems() || []).filter((item) => item.verification_status === "unknown");
    if (!items.length) {
      list.innerHTML = `<p class="muted">${escapeHtml(t("candidate.empty"))}</p>`;
      return;
    }
    list.innerHTML = items
      .map(
        (item) => `
      <article class="candidate-row">
        <div>
          <strong>${escapeHtml(item.label)}</strong>
          <span class="platform-badge candidate">${escapeHtml(t("candidate.badge"))}</span>
          <p class="muted">${escapeHtml(item.group)} · ${escapeHtml(item.evidence_level || "candidate")} · ${escapeHtml(
          item.notes || t("candidate.noNotes")
        )}</p>
        </div>
        <button class="secondary" data-candidate="${item.id}" type="button">${escapeHtml(t("candidate.select"))}</button>
      </article>
    `
      )
      .join("");
    list.querySelectorAll("[data-candidate]").forEach((buttonEl) => {
      buttonEl.addEventListener("click", () => {
        const item = items.find((entry) => entry.id === buttonEl.dataset.candidate);
        if (!item) return;
        if (!window.confirm(t("candidate.confirm"))) return;
        onSelect(item);
        close();
      });
    });
  }

  function open() {
    modal.classList.remove("hidden");
    render();
  }

  function close() {
    modal.classList.add("hidden");
  }

  button.addEventListener("click", open);
  closeButton.addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  return { open, close, render };
}