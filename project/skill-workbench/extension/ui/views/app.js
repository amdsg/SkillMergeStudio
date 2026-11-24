import { createTutorialOverlay } from "./tutorial-overlay.js";
import { renderTargetPicker } from "./convert-panel.js";
import { setLocale, t } from "../lib/i18n/index.js";

const root = document.getElementById("wb-root");
const localeSwitch = document.getElementById("locale-switch");
const tutorialButton = document.getElementById("tutorial-button");

function applyLocale(locale) {
  setLocale(locale);
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of document.querySelectorAll("[data-i18n-placeholder]")) {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  }
}

localeSwitch?.addEventListener("change", (event) => {
  applyLocale(event.target.value);
});

tutorialButton?.addEventListener("click", () => {
  const existing = document.querySelector(".tutorial-overlay");
  if (existing) {
    existing.remove();
    return;
  }
  createTutorialOverlay(root);
});

applyLocale("zh");

export { root, applyLocale, renderTargetPicker };