import { t } from "/js/i18n/index.js";

const SIZE_OPTIONS = [
  ["", "filter.sizeAny"],
  ["small", "filter.sizeSmall"],
  ["medium", "filter.sizeMedium"],
  ["large", "filter.sizeLarge"]
];
const QUALITY_OPTIONS = [["", "filter.qualityAny"], ["60", "filter.quality60"], ["80", "filter.quality80"]];
const TIME_OPTIONS = [["", "filter.timeAny"], ["7", "filter.time7"], ["30", "filter.time30"]];
const COPIES_OPTIONS = [["", "filter.copiesAny"], ["2", "filter.copies2"]];

export function markQuickButtons(root, active) {
  root.querySelectorAll("[data-quick]").forEach((button) => {
    button.classList.toggle("active", button.dataset.quick === active);
  });
}

export function createFilters({ root, onChange, getItems }) {
  const platform = root.querySelector("#filter-platform");
  const size = root.querySelector("#filter-size");
  const quality = root.querySelector("#filter-quality");
  const time = root.querySelector("#filter-time");
  const copies = root.querySelector("#filter-copies");
  const reset = root.querySelector("#filter-reset");

  function option(value, key, current) {
    const selected = current === value ? "selected" : "";
    return `<option value="${value}" ${selected}>${t(key)}</option>`;
  }

  function fill(select, options, current) {
    select.innerHTML = options.map(([value, key]) => option(value, key, current)).join("");
    select.value = current;
  }

  function render() {
    const items = getItems();
    const names = Array.from(new Set(items.map((item) => item.platform_origin || "unknown"))).sort();
    const currentPlatform = platform.value || "";
    platform.innerHTML =
      option("", "filter.all", currentPlatform) +
      names.map((name) => `<option value="${name}" ${name === currentPlatform ? "selected" : ""}>${name}</option>`).join("");
    platform.value = currentPlatform;
    fill(size, SIZE_OPTIONS, size.value || "");
    fill(quality, QUALITY_OPTIONS, quality.value || "");
    fill(time, TIME_OPTIONS, time.value || "");
    fill(copies, COPIES_OPTIONS, copies.value || "");
  }

  function read() {
    const sizeValue = size.value;
    let sizeMin = null;
    let sizeMax = null;
    if (sizeValue === "small") sizeMax = 10 * 1024;
    if (sizeValue === "medium") {
      sizeMin = 10 * 1024;
      sizeMax = 100 * 1024;
    }
    if (sizeValue === "large") sizeMin = 100 * 1024;
    const days = Number(time.value || 0);
    return {
      platform: platform.value || "",
      sizeMin,
      sizeMax,
      qualityMin: quality.value ? Number(quality.value) : null,
      mtimeFrom: days ? Date.now() / 1000 - days * 86400 : null,
      copiesMin: copies.value ? Number(copies.value) : null
    };
  }

  function fire() {
    onChange(read());
  }

  [platform, size, quality, time, copies].forEach((node) => node.addEventListener("change", fire));
  reset.addEventListener("click", () => {
    platform.value = "";
    size.value = "";
    quality.value = "";
    time.value = "";
    copies.value = "";
    fire();
  });

  return {
    render,
    read,
    reset() {
      reset.click();
    }
  };
}