import { escapeHtml } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";

const TYPE_KEYS = { dir: "format.dir", zip: "format.zip", prompt: "format.prompt" };

export function formatTypeLabel(format) {
  const type = format && format.package_type;
  return t(TYPE_KEYS[type] || "format.unknown");
}

export function formatBadges(format) {
  if (!format || !format.package_type) {
    return [{ text: t("format.unknown"), tone: "unknown" }];
  }
  const installable = Array.isArray(format.install_scopes) && format.install_scopes.length > 0;
  const verified = format.rule_status === "verified";
  const badges = [
    { text: formatTypeLabel(format), tone: "type" },
    { text: installable ? t("format.installable") : t("format.notInstallable"), tone: installable ? "ok" : "muted" },
    { text: verified ? t("format.verified") : t("format.candidate"), tone: verified ? "verified" : "candidate" }
  ];
  if (format.wrap) badges.push({ text: t("format.wrapped"), tone: "wrap" });
  return badges;
}

export function formatBadgeHtml(format) {
  return formatBadges(format)
    .map((badge) => `<span class="format-badge ${escapeHtml(badge.tone)}">${escapeHtml(badge.text)}</span>`)
    .join("");
}

export function formatSkillMdPath(format, name) {
  const path = format && format.skill_md_path ? String(format.skill_md_path) : "";
  if (!path) return t("format.unknown");
  return path.replace("<name>", name || "<name>");
}

export function formatDescription(format, name) {
  const parts = [];
  if (format && format.skill_md_path) {
    parts.push(t("format.skillMd", { path: formatSkillMdPath(format, name) }));
  } else {
    parts.push(t("format.unknown"));
  }
  if (format && format.wrap) parts.push(t("format.wrapped"));
  return parts.join(" · ");
}