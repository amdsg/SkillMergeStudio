import { BASE_LOCALE, LOCALES } from "./locales.js";

let missingCount = 0;
let currentLocale = "zh";

export function setLocale(locale) {
  if (LOCALES[locale]) {
    currentLocale = locale;
  }
  return currentLocale;
}

export function getLocale() {
  return currentLocale;
}

function resolve(key, locale) {
  const chain = [];
  let id = LOCALES[locale] ? locale : BASE_LOCALE;
  while (id && chain.length < 2 && !chain.includes(id)) {
    chain.push(id);
    id = LOCALES[id]?.fallback;
  }
  for (const candidate of chain) {
    const value = LOCALES[candidate]?.dict?.[key];
    if (typeof value === "string") {
      return value;
    }
  }
  return null;
}

export function t(key, params = {}, locale = currentLocale) {
  const value = resolve(key, locale);
  if (value === null) {
    missingCount += 1;
    return "Text unavailable";
  }
  return value.replace(/\{(\w+)\}/g, (match, name) => {
    if (params[name] === undefined) return match;
    return String(params[name]);
  });
}

export function missing() {
  return missingCount;
}

export function resetMissing() {
  missingCount = 0;
}

export function keys(locale = BASE_LOCALE) {
  return Object.keys(LOCALES[locale]?.dict || {});
}

export function availableLocales() {
  return Object.keys(LOCALES);
}