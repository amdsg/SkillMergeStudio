import { t } from "/js/i18n/index.js";

export function createSettings(options) {
  const { modal, form, status, closeButton, saveButton, testButton, request, onSaved } = options;
  let loaded = null;

  function field(id) {
    return form.querySelector(id);
  }

  function setStatus(text, tone = "") {
    status.textContent = text;
    status.className = `settings-status ${tone}`;
  }

  function lines(id) {
    return field(id).value.split("\n").map((line) => line.trim()).filter(Boolean);
  }

  function close() {
    modal.classList.add("hidden");
    document.body.classList.remove("modal-open");
  }

  async function open() {
    modal.classList.remove("hidden");
    document.body.classList.add("modal-open");
    setStatus("");
    try {
      loaded = await request("/api/config");
      field("#settings-roots").value = (loaded.roots || []).join("\n");
      field("#settings-save-dir").value = loaded.save_dir || "";
      field("#settings-depth").value = loaded.scan_depth || 10;
      field("#settings-ignore").value = (loaded.ignore_rules || []).join("\n");
      field("#settings-ai-enabled").checked = Boolean(loaded.ai && loaded.ai.enabled);
      field("#settings-ai-base").value = (loaded.ai && loaded.ai.base_url) || "";
      field("#settings-ai-model").value = (loaded.ai && loaded.ai.model) || "";
      field("#settings-ai-key").value = "";
      field("#settings-ai-key").placeholder = loaded.ai && loaded.ai.api_key_set ? t("settings.aiKeySet") : "";
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  async function save() {
    const payload = {
      roots: lines("#settings-roots"),
      save_dir: field("#settings-save-dir").value.trim(),
      scan_depth: Number(field("#settings-depth").value || 10),
      ignore_rules: lines("#settings-ignore"),
      ai: {
        enabled: field("#settings-ai-enabled").checked,
        base_url: field("#settings-ai-base").value.trim(),
        model: field("#settings-ai-model").value.trim()
      }
    };
    const key = field("#settings-ai-key").value.trim();
    if (key) payload.ai.api_key = key;
    try {
      const data = await request("/api/config", { method: "POST", body: JSON.stringify(payload) });
      setStatus(t("settings.saved"), "ok");
      if (onSaved) onSaved(data.config);
    } catch (error) {
      setStatus(`${t("settings.error")}: ${error.message}`, "error");
    }
  }

  async function test() {
    setStatus(t("settings.aiTesting"));
    try {
      const data = await request("/api/ai/test", { method: "POST", body: JSON.stringify({}) });
      if (data.reachable) {
        setStatus(t("settings.aiReachable"), "ok");
      } else {
        setStatus(t("settings.aiUnreachable", { reason: data.reason || "" }), "error");
      }
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  closeButton.addEventListener("click", close);
  saveButton.addEventListener("click", save);
  testButton.addEventListener("click", test);

  return { open, close };
}