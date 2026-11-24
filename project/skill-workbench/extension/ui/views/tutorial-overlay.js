export const STEPS = ["search", "download", "merge", "convert", "config_preview", "write", "upgrade_export"];

export function createTutorialOverlay(host) {
  const overlay = document.createElement("section");
  overlay.className = "tutorial-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "false");
  overlay.setAttribute("aria-labelledby", "wb-tutorial-title");
  const title = document.createElement("h2");
  title.id = "wb-tutorial-title";
  title.dataset.i18n = "wb.tutorial.title";
  const body = document.createElement("div");
  body.className = "tutorial-body";
  const nav = document.createElement("div");
  nav.className = "tutorial-nav";
  for (const action of ["prev", "next", "skip", "restart", "close"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.i18n = `wb.tutorial.action.${action}`;
    nav.append(button);
  }
  overlay.append(title, body, nav);
  host.append(overlay);

  overlay.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.i18n === "wb.tutorial.action.next") {
      const step = Number(overlay.dataset.step || 0);
      const next = Math.min(step + 1, STEPS.length - 1);
      overlay.dataset.step = String(next);
      overlay.dispatchEvent(new CustomEvent("ui.focusTarget", { detail: { step: STEPS[next] }, bubbles: true }));
    }
  });

  overlay.dataset.step = "0";
  return { overlay, steps: STEPS };
}