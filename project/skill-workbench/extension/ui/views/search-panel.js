export function createSearchPanel(host, client) {
  const panel = document.createElement("section");
  panel.className = "search-panel";
  const input = document.createElement("input");
  input.type = "search";
  input.dataset.i18nPlaceholder = "wb.convert.search.placeholder";
  const state = document.createElement("p");
  state.dataset.i18n = "wb.state.empty";
  const list = document.createElement("div");
  list.className = "search-results";
  list.setAttribute("role", "list");
  panel.append(input, state, list);
  host.append(panel);

  function render(items) {
    list.replaceChildren();
    state.dataset.i18n = items.length ? "wb.state.ready" : "wb.state.empty";
    for (const item of items) {
      const row = document.createElement("article");
      row.dataset.repo = item.full_name;
      const title = document.createElement("h3");
      title.textContent = item.full_name;
      const meta = document.createElement("p");
      meta.textContent = `stars: ${item.stars ?? "unknown"} · pushed: ${item.pushed_at ?? "unknown"}`;
      const badge = document.createElement("p");
      badge.dataset.applicability = item.applicability?.mode || "unknown";
      badge.dataset.i18n = `wb.applicability.${item.applicability?.mode || "unknown"}`;
      row.append(title, meta, badge);
      list.append(row);
    }
  }

  input.addEventListener("change", async () => {
    state.dataset.i18n = "wb.state.loading";
    try {
      const data = await client.search({ query: input.value });
      render(data.items || []);
    } catch (error) {
      state.dataset.i18n = "wb.state.failed";
      state.dataset.errorCode = error.code || "E_INTERNAL";
    }
  });

  return { panel, render };
}