const STATES = ["has_update", "up_to_date", "check_failed", "removed", "renamed", "inaccessible", "unknown"];

export function createUpgradePanel(host, client) {
  const panel = document.createElement("section");
  panel.className = "upgrade-panel";
  const repo = document.createElement("input");
  repo.type = "text";
  repo.dataset.i18nPlaceholder = "wb.convert.search.placeholder";
  const run = document.createElement("button");
  run.type = "button";
  run.dataset.i18n = "wb.button.upgrade";
  const list = document.createElement("div");
  const listId = "wb-upgrade-list";
  list.id = listId;
  panel.append(repo, run, list);
  host.append(panel);

  function render(items) {
    list.replaceChildren();
    for (const item of items) {
      const row = document.createElement("article");
      row.dataset.repo = item.repo_full_name;
      row.dataset.state = item.state;
      const title = document.createElement("h3");
      title.textContent = item.repo_full_name;
      const stateBadge = document.createElement("span");
      stateBadge.dataset.i18n = `wb.enums.upgrade_state.${item.state}`;
      const signals = document.createElement("dl");
      for (const [name, value] of Object.entries(item.signals || {})) {
        const term = document.createElement("dt");
        term.textContent = name;
        const detail = document.createElement("dd");
        detail.textContent = `${value.old} -> ${value.new}`;
        signals.append(term, detail);
      }
      const declaration = document.createElement("div");
      declaration.dataset.role = "declaration-diff";
      const diff = item.declaration_diff || {};
      declaration.dataset.legacyMissing = String(Boolean(diff.legacy_missing));
      declaration.dataset.unchanged = String(Boolean(diff.unchanged));
      row.append(title, stateBadge, signals, declaration);
      list.append(row);
    }
  }

  run.addEventListener("click", async () => {
    render([{ repo_full_name: repo.value, state: "check_failed", signals: {}, declaration_diff: {} }]);
    try {
      const data = await client.upgrade({ repo_full_name: repo.value, local_ref: {} });
      render([data]);
    } catch {
      render([{ repo_full_name: repo.value, state: "check_failed", signals: {}, declaration_diff: {} }]);
    }
  });

  return { panel, render, states: STATES, listId };
}
