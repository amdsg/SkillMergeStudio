import { escapeHtml } from "../util/dom.js";
import { t } from "../i18n/index.js";

const STORAGE_KEY = "skillmerge.github.localRefs";

function loadLocalRefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY) || "{}";
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? data : {};
  } catch (error) {
    return {};
  }
}

function saveLocalRefs(refs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(refs));
  } catch (error) {
    /* 存储满或隐私模式下忽略 */
  }
}

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
  let localRefs = loadLocalRefs();

  function quotaText(quota) {
    if (!quota) return "";
    const remaining = quota.remaining ?? "?";
    return t("github.quota", { remaining });
  }

  async function checkUpdate(repo) {
    const localRef = localRefs[repo];
    if (!localRef) return null;
    try {
      return await request("/api/github/check-update", {
        method: "POST",
        body: JSON.stringify({ repo_full_name: repo, local_ref: localRef })
      });
    } catch (error) {
      return { state: "check_failed" };
    }
  }

  async function captureBaseline(repo) {
    try {
      const data = await request("/api/github/check-update", {
        method: "POST",
        body: JSON.stringify({ repo_full_name: repo, local_ref: {} })
      });
      const signals = data.signals || {};
      const ref = {};
      for (const key of ["commit_sha", "release_tag", "pushed_at"]) {
        ref[key] = (signals[key] || {}).new ?? "unknown";
      }
      return ref;
    } catch (error) {
      return null;
    }
  }

  async function refreshUpdateBadge(repo) {
    const row = resultsEl.querySelector(`.github-row[data-repo="${repo}"]`);
    if (!row) return;
    const badge = row.querySelector(".github-update-badge");
    const btn = row.querySelector(".github-download");
    const data = await checkUpdate(repo);
    const has = data && data.state === "has_update";
    if (badge) badge.classList.toggle("hidden", !has);
    if (btn) btn.textContent = t(has ? "github.update" : "github.download");
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
        const repo = item.full_name || "";
        return `
      <article class="github-row" data-repo="${escapeHtml(repo)}">
        <div class="github-row-main">
          <div class="github-row-title">
            <a href="${escapeHtml(item.html_url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(
              repo || item.name || ""
            )}</a>
            <span class="github-stars" title="stars">★ ${escapeHtml(stars)}</span>
          </div>
          <p class="muted">${escapeHtml(item.description || "")}</p>
          <div class="github-meta">
            ${item.language ? `<span class="github-lang">${escapeHtml(item.language)}</span>` : ""}
            ${topics.map((tp) => `<span class="github-topic">${escapeHtml(tp)}</span>`).join("")}
          </div>
        </div>
        <div class="github-row-actions">
          <span class="github-update-badge hidden">${escapeHtml(t("github.hasUpdate"))}</span>
          <button class="secondary github-download" data-repo="${escapeHtml(repo)}" type="button">${escapeHtml(
          t("github.download")
        )}</button>
        </div>
      </article>`;
      })
      .join("");

    resultsEl.querySelectorAll(".github-download").forEach((btn) => {
      btn.addEventListener("click", () => downloadRepo(btn.dataset.repo, btn));
    });

    items.forEach((item) => {
      const repo = item.full_name;
      if (repo && localRefs[repo]) refreshUpdateBadge(repo);
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
      const baseline = await captureBaseline(repo);
      if (baseline) {
        localRefs[repo] = baseline;
        saveLocalRefs(localRefs);
      }
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
