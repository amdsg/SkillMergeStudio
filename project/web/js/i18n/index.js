import { zh } from "./zh.js";
import { en } from "./en.js";

const DICTS = { zh, en };
const listeners = new Set();
let lang = "zh";

export function t(key, params = {}) {
  const dict = DICTS[lang] || zh;
  const template = dict[key] ?? zh[key] ?? key;
  return String(template).replace(/\{(\w+)\}/g, (_match, name) => String(params[name] ?? ""));
}

export function getLang() {
  return lang;
}

export function setLang(next) {
  lang = next === "en" ? "en" : "zh";
  try {
    localStorage.setItem("sms.lang", lang);
  } catch (error) {
    /* ignore storage failures */
  }
  document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
  applyDom();
  listeners.forEach((listener) => listener(lang));
}

export function onLang(listener) {
  listeners.add(listener);
}

export function applyDom(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    const target = node.dataset.i18nAttr;
    if (target) {
      node.setAttribute(target, t(key));
    } else if (node.tagName === "INPUT" && node.hasAttribute("placeholder")) {
      node.placeholder = t(key);
    } else {
      node.textContent = t(key);
    }
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
}

export function initLang() {
  let saved = "zh";
  try {
    saved = localStorage.getItem("sms.lang") || "zh";
  } catch (error) {
    saved = "zh";
  }
  lang = saved === "en" ? "en" : "zh";
  document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
  applyDom();
}