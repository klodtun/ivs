"use client";
import { useState, useEffect, useRef } from "react";
import { useLang } from "@/components/lang-provider";
import type { Locale } from "@/lib/i18n";

interface LocaleMeta {
  code: Locale;
  flag: string;
  label: string;
  short: string;
  regulator: string;
}

const LOCALES: LocaleMeta[] = [
  { code: "th",    flag: "🇹🇭", label: "ไทย",            short: "TH",    regulator: "PDPA" },
  { code: "en",    flag: "🇬🇧", label: "English",        short: "EN",    regulator: "Generic" },
  { code: "en-EU", flag: "🇪🇺", label: "English (EU)",   short: "EN-EU", regulator: "GDPR" },
  { code: "ja",    flag: "🇯🇵", label: "日本語",          short: "JA",    regulator: "APPI" },
];

export function LangToggle({ compact }: { compact?: boolean }) {
  const { locale, setLocale } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LOCALES.find((l) => l.code === locale) || LOCALES[0];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded bg-gray-100 hover:bg-gray-200 text-gray-700 transition"
        title={`Current: ${current.label} (${current.regulator})`}
      >
        <span>{current.flag}</span>
        {!compact && <span className="font-medium">{current.short}</span>}
        <svg className="w-2.5 h-2.5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-44 bg-white border border-gray-200 rounded-md shadow-lg z-50 overflow-hidden">
          {LOCALES.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                setLocale(l.code);
                setOpen(false);
              }}
              className={`w-full flex items-center justify-between gap-2 px-2 py-1.5 text-[11px] transition ${
                l.code === locale
                  ? "bg-brand-50 text-brand-700 font-semibold"
                  : "hover:bg-gray-50 text-gray-700"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <span>{l.flag}</span>
                <span>{l.label}</span>
              </span>
              <span className="text-[9px] text-gray-400 font-mono">{l.regulator}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
