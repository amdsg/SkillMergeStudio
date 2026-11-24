import { t, setLocale } from "../lib/i18n/index.js";

setLocale("zh");
document.getElementById("agent-state").textContent = t("wb.state.loading");

document.getElementById("open-app").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});