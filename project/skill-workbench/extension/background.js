import { createAgentClient } from "./lib/agent-client.js";

const DEFAULT_PORT = 8788;

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ "wb.installed_at": new Date().toISOString() });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "wb.agent") {
    return false;
  }
  const client = createAgentClient(`http://127.0.0.1:${message.port || DEFAULT_PORT}`, message.token || "");
  client.health().then(
    (data) => sendResponse({ ok: true, data }),
    (error) => sendResponse({ ok: false, code: error.code || "E_INTERNAL" }),
  );
  return true;
});