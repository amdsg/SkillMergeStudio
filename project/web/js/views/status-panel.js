import { formatSize } from "/js/util/dom.js";
import { t } from "/js/i18n/index.js";

export function renderBasketBar({ summaryEl, previewButton, items, basket, platforms, platform }) {
  const count = basket.size;
  const selected = items.filter((item) => basket.has(item.id));
  const estimate = selected.reduce((sum, item) => sum + Number(item.size_bytes || 0) * 0.9, 0);
  const target = platforms.find((item) => item.id === platform);
  const limit = target && target.limits ? target.limits.bundle_max_mb : null;
  const limitText = !target
    ? t("basket.noPlatform")
    : limit === null
      ? t("basket.candidateLimit")
      : t("basket.limit", { mb: limit });
  summaryEl.textContent = t("basket.summary", { count, size: formatSize(estimate), limit: limitText });
  previewButton.disabled = count === 0;
}

export function renderPlatformCounts({ element, platforms, data }) {
  if (!element) return;
  const counts = (data && data.counts) || {};
  const lastVerified =
    platforms
      .map((item) => item.last_verified_at || item.verified_at)
      .filter(Boolean)
      .sort()
      .pop() || t("common.dash");
  const value = (item) => (item === null || item === undefined ? t("common.dash") : item);
  element.textContent = t("platform.counts", {
    verified: value(counts.verified),
    official: value(counts.verified_official),
    local: value(counts.local_contract),
    candidate: value(counts.candidate),
    evidence: value(counts.evidence_total),
    skill: value(counts.evidence_skill),
    rules: value(counts.evidence_rules),
    discovery: value(counts.evidence_discovery),
    last: lastVerified
  });
}