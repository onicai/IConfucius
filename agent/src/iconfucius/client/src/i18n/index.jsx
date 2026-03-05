import { createContext, useContext, useState, useCallback, useMemo } from "react";
import en from "./en";
import zh from "./zh";

const LOCALES = { en, zh };
const STORAGE_KEY = "iconfucius_locale";
const DEFAULT_LOCALE = "en";

function loadLocale() {
  try { return localStorage.getItem(STORAGE_KEY) || DEFAULT_LOCALE; }
  catch { return DEFAULT_LOCALE; }
}

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [locale, setLocaleState] = useState(loadLocale);

  const setLocale = useCallback((l) => {
    setLocaleState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch {}
  }, []);

  const t = useCallback((key, params) => {
    const dict = LOCALES[locale] || LOCALES[DEFAULT_LOCALE];
    let val = dict[key] ?? LOCALES[DEFAULT_LOCALE][key] ?? key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        val = val.replaceAll(`{${k}}`, v);
      });
    }
    return val;
  }, [locale]);

  const tArray = useCallback((prefix) => {
    const dict = LOCALES[locale] || LOCALES[DEFAULT_LOCALE];
    const items = [];
    for (let i = 1; ; i++) {
      const key = `${prefix}.${i}`;
      if (!(key in dict)) break;
      items.push(dict[key]);
    }
    return items;
  }, [locale]);

  const ctx = useMemo(() => ({ locale, setLocale, t, tArray }), [locale, setLocale, t, tArray]);

  return <I18nContext.Provider value={ctx}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}

export const AVAILABLE_LOCALES = [
  { code: "en", label: "EN" },
  { code: "zh", label: "中文" },
];
