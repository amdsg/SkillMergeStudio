import { escapeHtml, formatSize, formatTime } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";

function statusLabel(status) {
  const key = `state.${status}`;
  const value = t(key);
  return value === key ? status : value;
}

export function createHistory(options) {
  const { modal, body, message, closeButton, request, onChanged, platformSelect, platforms } = options;
  let items = [];
  let selectedPlatform = "";

  function close() {
    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
  }

  function setMessage(html, tone = "") {
    message.innerHTML = html;
    message.className = `history-message ${tone}`;
  }

  function rowHtml(item) {
    const id = escapeHtml(item.id);
    const updated = item.source_updated
      ? `<span class="tag warn">${escapeHtml(t("history.sourceUpdated"))}</span>`
      : "";
    const actions = [
      item.status === "active"
        ? `<button class="secondary" data-undo="${id}" type="button">${escapeHtml(t("history.undo"))}</button>`
        : "",
      item.status === "active"
        ? `<button class="secondary" data-rebuild="${id}" type="button">${escapeHtml(t("history.rebuild"))}</button>`
        : "",
      `<button class="secondary" data-copy="${id}" type="button">${escapeHtml(t("history.copy"))}</button>`
    ]
      .filter(Boolean)
      .join("");
    return `
      <tr class="${item.status === "active" ? "" : "dim"}">
        <td>${formatTime(item.created_at)}</td>
        <td class="name">${escapeHtml(item.name || t("common.unnamed"))} ${updated}</td>
        <td>${escapeHtml(item.platform || "generic")}</td>
        <td>${item.source_count ?? 0}</td>
        <td>${formatSize(item.size_bytes)}</td>
        <td>${escapeHtml(statusLabel(item.status))}</td>
        <td class="actions">${actions}</td>
      </tr>`;
  }

  function render() {
    if (!items.length) {
      body.innerHTML = `<p class="muted">${escapeHtml(t("history.empty"))}</p>`;
      return;
    }
    body.innerHTML = `
      <table class="history-table">
        <thead><tr>
          <th>${escapeHtml(t("history.time"))}</th>
          <th>${escapeHtml(t("history.name"))}</th>
          <th>${escapeHtml(t("history.platform"))}</th>
          <th>${escapeHtml(t("history.sources"))}</th>
          <th>${escapeHtml(t("history.size"))}</th>
          <th>${escapeHtml(t("history.status"))}</th>
          <th>${escapeHtml(t("history.actions"))}</th>
        </tr></thead>
        <tbody>${items.map(rowHtml).join("")}</tbody>
      </table>`;
  }

  function fillPlatforms() {
    if (!platformSelect) return;
    const list = typeof platforms === "function" ? platforms() : platforms || [];
    const entries = [`<option value="">${escapeHtml(t("history.allPlatforms"))}</option>`].concat(
      list.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`)
    );
    platformSelect.innerHTML = entries.join("");
    platformSelect.value = selectedPlatform;
  }

  async function load() {
    setMessage("");
    body.innerHTML = `<p class="muted">${escapeHtml(t("history.loading"))}</p>`;
    try {
      const suffix = selectedPlatform ? `&platform=${encodeURIComponent(selectedPlatform)}` : "";
      const data = await request(`/api/history?limit=100${suffix}`);
      items = data.items || [];
      render();
    } catch (error) {
      body.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    }
  }

  function showVerification(error) {
    const details = error.details || {};
    const verification = details.verification || details;
    const files = []
      .concat(verification.modified || [], verification.hash_mismatch || [], verification.missing || [], verification.extra || [])
      .map((entry) => (typeof entry === "string" ? entry : entry.path || entry.file || JSON.stringify(entry)));
    const list = files.length
      ? `<p class="muted">${escapeHtml(t("history.diffFiles"))}</p><ul class="diff-files">${files
          .slice(0, 20)
          .map((file) => `<li>${escapeHtml(file)}</li>`)
          .join("")}</ul>`
      : "";
    setMessage(`<p><strong>${escapeHtml(error.message)}</strong></p>${list}`, "error");
  }

  async function undo(id) {
    const item = items.find((entry) => entry.id === id);
    if (!window.confirm(t("history.undoConfirm", { name: item ? item.name : id }))) return;
    try {
      const result = await request(`/api/artifacts/${encodeURIComponent(id)}/undo`, { method: "POST" });
      setMessage(`<p class="ok">${escapeHtml(t("history.undoDone", { path: result.trash_path }))}</p>`, "ok");
      await load();
      if (onChanged) onChanged();
    } catch (error) {
      showVerification(error);
    }
  }

  async function waitJob(jobId) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      const job = await request(`/api/jobs/${encodeURIComponent(jobId)}`);
      if (job.status === "succeeded") return job.result;
      if (job.status === "failed" || job.status === "cancelled") {
        throw new Error(t(job.status === "failed" ? "history.taskFailed" : "history.taskCancelled"));
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw new Error(t("history.timeout"));
  }

  async function rebuild(id) {
    if (!window.confirm(t("history.rebuildConfirm"))) return;
    setMessage(`<p class="muted">${escapeHtml(t("history.rebuilding"))}</p>`);
    try {
      const data = await request(`/api/artifacts/${encodeURIComponent(id)}/rebuild`, {
        method: "POST",
        body: JSON.stringify({})
      });
      const result = await waitJob(data.job_id);
      setMessage(`<p class="ok">${escapeHtml(t("history.rebuildDone", { path: result.dir_path || "" }))}</p>`, "ok");
      await load();
      if (onChanged) onChanged();
    } catch (error) {
      setMessage(`<p class="error">${escapeHtml(error.message)}</p>`, "error");
    }
  }

  async function copyPath(id) {
    const item = items.find((entry) => entry.id === id);
    if (!item) return;
    try {
      await navigator.clipboard.writeText(item.dir_path || "");
      setMessage(`<p class="ok">${escapeHtml(t("history.copied", { path: item.dir_path || "" }))}</p>`, "ok");
    } catch (error) {
      setMessage(`<p class="muted">${escapeHtml(t("history.copyFailed", { path: item.dir_path || "" }))}</p>`);
    }
  }

  body.addEventListener("click", (event) => {
    const undoButton = event.target.closest("[data-undo]");
    if (undoButton) return undo(undoButton.dataset.undo);
    const rebuildButton = event.target.closest("[data-rebuild]");
    if (rebuildButton) return rebuild(rebuildButton.dataset.rebuild);
    const copyButton = event.target.closest("[data-copy]");
    if (copyButton) return copyPath(copyButton.dataset.copy);
    return undefined;
  });
  if (platformSelect) {
    platformSelect.addEventListener("change", () => {
      selectedPlatform = platformSelect.value;
      load();
    });
  }
  closeButton.addEventListener("click", close);

  return {
    open() {
      modal.classList.remove("hidden");
      document.body.classList.add("modal-open");
      setMessage("");
      fillPlatforms();
      load();
    },
    close
  };
}