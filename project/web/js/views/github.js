import { escapeHtml } from "../util/dom.js";
import { t } from "../i18n/index.js";

export function createGithub({
  modal,
  closeButton,
  request,
  statusEl,
  resultsEl,
  queryInput,
  searchBtn,
  modeButtons,
  windowButtons,
  searchRow,
  windowRow
}) {
  let mode = "trending";
  let window = "week";
  let loading = false;

  function quotaText(quota) {
    if (!quota) return "";
    const remaining = quota.remaining ?? "?";
    return t("github.quota", { remaining });
  }

  function render(items) {
    if (!items || !items.length) {
      resultsEl.innerHTML = `<p class="muted">${escapeHtml(t("github.empty"))}</p>`;
      return;
    }
    resultsEl.innerHTML = items
      .map((item) => {
        const stars = item.stars ?? 0;
        const topics = (item.topics || []).slice(0, 4);
        return `
      <article class="github-row">
        <div class="github-row-main">
          <div class="github-row-title">
            <a href="${escapeHtml(item.html_url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(
              item.full_name || item.name || ""
            )}</a>
            <span class="github-stars" title="stars">★ ${escapeHtml(stars)}</span>
          </div>
          <p class="muted">${escapeHtml(item.description || "")}</p>
          <div class="github-meta">
            ${item.language ? `<span class="github-lang">${escapeHtml(item.language)}</span>` : ""}
            ${topics.map((tp) => `<span class="github-topic">${escapeHtml(tp)}</span>`).join("")}
          </div>
        </div>
        <button class="secondary github-download" data-repo="${escapeHtml(item.full_name)}" type="button">${escapeHtml(
          t("github.download")
        )}</button>
      </article>`;
      })
      .join("");

    resultsEl.querySelectorAll(".github-download").forEach((btn) => {
      btn.addEventListener("click", () => downloadRepo(btn.dataset.repo, btn));
    });
  }

  async function load() {
    if (loading) return;
    loading = true;
    statusEl.textContent = t("list.loading");
    try {
      const data =
        mode === "search"
          ? await request("/api/github/search", {
              method: "POST",
              body: JSON.stringify({ query: queryInput.value.trim() })
            })
          : await request("/api/github/trending", {
              method: "POST",
              body: JSON.stringify({ window })
            });
      render(data.items || []);
      statusEl.textContent = quotaText(data.quota);
    } catch (error) {
      statusEl.textContent = error.message;
      resultsEl.innerHTML = "";
    } finally {
      loading = false;
    }
  }

  async function downloadRepo(repo, btn) {
    btn.disabled = true;
    btn.textContent = t("list.loading");
    try {
      const data = await request("/api/github/download", {
        method: "POST",
        body: JSON.stringify({ repo_full_name: repo })
      });
      btn.textContent = t("github.downloaded");
      statusEl.textContent = t("github.downloadDone", {
        dir: data.dir_path || "",
        files: (data.files || []).length
      });
    } catch (error) {
      btn.textContent = t("github.download");
      statusEl.textContent = error.message;
    } finally {
      btn.disabled = false;
    }
  }

  function setMode(next) {
    mode = next;
    modeButtons.forEach((b) => b.classList.toggle("active", b.dataset.mode === next));
    searchRow.classList.toggle("hidden", next !== "search");
    windowRow.classList.toggle("hidden", next !== "trending");
    load();
  }

  function setWindow(next) {
    window = next;
    windowButtons.forEach((b) => b.classList.toggle("active", b.dataset.window === next));
    load();
  }

  function open() {
    modal.classList.remove("hidden");
    load();
  }

  function close() {
    modal.classList.add("hidden");
  }

  closeButton.addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  modeButtons.forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  windowButtons.forEach((b) => b.addEventListener("click", () => setWindow(b.dataset.window)));
  searchBtn.addEventListener("click", load);
  queryInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") load();
  });

  return { open, close, reload: load };
}
