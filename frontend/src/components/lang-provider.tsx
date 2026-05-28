"use client";
import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { Locale, t as translate, getStoredLocale, setStoredLocale } from "@/lib/i18n";

interface LangContextType {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const LangContext = createContext<LangContextType>({
  locale: "th",
  setLocale: () => {},
  t: (key) => key,
});

// Maps IVS internal locale → BCP-47 tag used by the browser's native
// widgets (date pickers, number formatting, weekday names, etc.).
// Setting `document.documentElement.lang` makes `<input type="date">`
// render its calendar in the matching language.
const BCP47: Record<Locale, string> = {
  th: "th-TH",
  en: "en",
  // Use en-GB so the date picker defaults to dd/mm/yyyy like most of
  // the EU — matches what GDPR users expect locally.
  "en-EU": "en-GB",
  ja: "ja-JP",
};

export function LangProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("th");

  useEffect(() => {
    setLocaleState(getStoredLocale());
  }, []);

  // Keep <html lang="..."> in sync with the selected locale so native
  // form widgets (date pickers, number inputs) render in the right
  // language. Server-side default is `th`; we overwrite client-side.
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = BCP47[locale] || "en";
    }
  }, [locale]);

  const setLocale = (l: Locale) => {
    setLocaleState(l);
    setStoredLocale(l);
  };

  const t = (key: string) => translate(key, locale);

  return (
    <LangContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  return useContext(LangContext);
}
