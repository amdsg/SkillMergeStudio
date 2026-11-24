export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
}

export function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${Math.round(value)} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function formatTime(value) {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  let ms = Number.isFinite(numeric) ? numeric : Date.parse(String(value));
  if (!Number.isFinite(ms)) return String(value);
  if (ms < 1e12) ms *= 1000;
  return new Date(ms).toLocaleString("zh-CN", { hour12: false });
}
export function isTyping(node) {
  return Boolean(node && node.closest && node.closest("input, textarea, select"));
}