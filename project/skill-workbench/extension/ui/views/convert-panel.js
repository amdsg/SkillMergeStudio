const GROUPS = ["recommended", "baseline", "all"];

export function renderTargetPicker(root, targets, options = {}) {
  const state = { query: "", expanded: new Set(), recent: [] };
  const warningKey = "wb.convert.unknown.warning";
  const container = document.createElement("div");
  container.className = "target-picker";
  const search = document.createElement("input");
  search.type = "search";
  search.dataset.i18nPlaceholder = "wb.convert.search.placeholder";
  const list = document.createElement("div");
  list.setAttribute("role", "listbox");
  container.append(search, list);
  root.append(container);

  function visible() {
    const query = state.query.trim().toLowerCase();
    if (!query) {
      return targets.filter((item) => item.enabled !== false);
    }
    return targets.filter((item) => {
      if (item.enabled === false) return false;
      const haystack = [item.id, item.label, item.group, ...(item.aliases || [])].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }

  function render() {
    list.replaceChildren();
    for (const [index, target] of visible().slice(0, 50).entries()) {
      const row = document.createElement("button");
      row.type = "button";
      row.setAttribute("role", "option");
      row.dataset.targetId = target.id;
      row.setAttribute("aria-selected", String(index === options.selectedIndex));
      row.textContent = target.label;
      if (target.evidence_level !== "verified") {
        row.dataset.warningKey = warningKey;
      }
      list.append(row);
    }
  }

  search.addEventListener("input", () => {
    state.query = search.value;
    render();
  });
  render();
  return { groups: GROUPS, state, refresh: render };
}