import { escapeHtml, formatSize, formatTime } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";

function sourceLabel(source) {
  if (source === "manual") return t("source.manualLong");
  if (source === "ai") return t("source.aiLong");
  return t("source.keywordLong");
}

function statusLabel(status) {
  const key = `state.${status}`;
  const value = t(key);
  return value === key ? status : value;
}

function keywordHtml(skill) {
  const keyword = skill.keyword || {};
  const hits = keyword.hits || [];
  const suggested = keyword.category
    ? `<p class="muted">${escapeHtml(t("detail.keywordSuggested", {
        category: keyword.category,
        confidence: Number(keyword.confidence || 0).toFixed(2)
      }))}</p>`
    : "";
  if (!hits.length) return `${suggested}<p class="muted">${escapeHtml(t("detail.noHits"))}</p>`;
  return `${suggested}<ul class="hit-list">${hits
    .slice(0, 12)
    .map((hit) => `
      <li>
        <span class="hit-word">${escapeHtml(hit.word)}</span>
        <span class="hit-meta">${escapeHtml(t("detail.hitMeta", {
          field: hit.field === "description" ? t("detail.hitDescription") : t("detail.hitName"),
          weight: hit.weight,
          category: hit.category
        }))}</span>
      </li>`)
    .join("")}</ul>`;
}

function artifactsHtml(artifacts) {
  if (!artifacts.length) return `<p class="muted">${escapeHtml(t("detail.noArtifacts"))}</p>`;
  return `<ul class="artifact-list">${artifacts
    .map((item) => `
      <li>
        <div class="artifact-head">
          <strong>${escapeHtml(item.name || t("common.unnamed"))}</strong>
          <span class="tag">${escapeHtml(statusLabel(item.status))}</span>
        </div>
        <div class="artifact-meta">
          <span>${escapeHtml(item.platform || "generic")}</span>
          <span>${formatTime(item.created_at)}</span>
          <span>${formatSize(item.size_bytes)}</span>
        </div>
      </li>`)
    .join("")}</ul>`;
}

export function detailHtml(skill, artifacts, inBasket) {
  const source = sourceLabel(skill.category_source);
  const confidence = Number(skill.confidence || 0).toFixed(2);
  const warnings = (skill.warnings || [])
    .map((item) => `<li class="warn">${escapeHtml(item.message || item.code)}</li>`)
    .join("") || `<li class="muted">${escapeHtml(t("detail.none"))}</li>`;
  const locations = (skill.locations || [])
    .map((location) => `<li class="path">${escapeHtml(location.path)}</li>`)
    .join("") || `<li class="muted">${escapeHtml(t("detail.none"))}</li>`;
  const headings = (skill.headings || [])
    .slice(0, 20)
    .map((item) => `<li>${"#".repeat(item.level)} ${escapeHtml(item.text)}</li>`)
    .join("") || `<li class="muted">${escapeHtml(t("detail.none"))}</li>`;
  return `
    <h2>${escapeHtml(skill.name || t("common.unnamed"))}</h2>
    <dl>
      <dt>${escapeHtml(t("detail.category"))}</dt>
      <dd>${escapeHtml(skill.category || t("common.uncategorized"))} <span class="tag">${escapeHtml(source)}</span>
        <span class="muted">${escapeHtml(t("detail.confidence", { confidence }))}</span></dd>
      <dt>${escapeHtml(t("detail.source"))}</dt><dd>${escapeHtml(skill.platform_origin || "unknown")}</dd>
      <dt>${escapeHtml(t("detail.quality"))}</dt><dd>${skill.quality_score ?? 0}</dd>
      <dt>${escapeHtml(t("detail.size"))}</dt><dd>${formatSize(skill.size_bytes)}</dd>
      <dt>${escapeHtml(t("detail.updated"))}</dt><dd>${formatTime(skill.mtime)}</dd>
      <dt>${escapeHtml(t("detail.path"))}</dt><dd class="path">${escapeHtml(skill.path)}</dd>
    </dl>
    <button id="add-basket" class="primary" type="button">${escapeHtml(
      t(inBasket ? "detail.removeBasket" : "detail.addBasket")
    )}</button>
    <h3>${escapeHtml(t("detail.keywordBasis"))}</h3>
    ${keywordHtml(skill)}
    <h3>${escapeHtml(t("detail.artifacts"))}</h3>
    ${artifactsHtml(artifacts)}
    <h3>${escapeHtml(t("detail.headings"))}</h3>
    <ul>${headings}</ul>
    <h3>${escapeHtml(t("detail.warnings"))}</h3>
    <ul>${warnings}</ul>
    <h3>${escapeHtml(t("detail.locations"))}</h3>
    <ul>${locations}</ul>`;
}