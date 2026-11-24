import { t } from "/js/i18n/index.js";

export const PHASES = ["walk", "parse", "write", "build", "ai", "classify", "export"];

export function phaseLabel(phase) {
  const value = String(phase || "");
  if (PHASES.includes(value)) return t(`phase.${value}`);
  return t("phase.unknown", { phase: value || "?" });
}