import zh from "./zh.js";
import en from "./en.js";

export const BASE_LOCALE = "en";

export const LOCALES = {
  en: { id: "en", fallback: null, dict: en },
  zh: { id: "zh", fallback: "en", dict: zh }
};