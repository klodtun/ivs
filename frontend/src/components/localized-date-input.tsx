"use client";
import { useEffect, useRef, useState } from "react";
import { useLang } from "@/components/lang-provider";

/**
 * Locale-aware date input. The native `<input type="date">` picker on
 * Chrome/macOS ignores `<html lang>` and follows the OS UI language,
 * so we render our own popup calendar that uses `Intl.DateTimeFormat`
 * keyed off the IVS-selected locale.
 *
 * Internal value format is ISO yyyy-mm-dd (same as the native input),
 * so call sites don't need to change.
 */

const BCP47: Record<string, string> = {
  th: "th-TH",
  en: "en",
  "en-EU": "en-GB",
  ja: "ja-JP",
};

interface Props {
  value: string; // yyyy-mm-dd or ""
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function toIso(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function parseIso(v: string): Date | null {
  if (!v) return null;
  const m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const d = new Date(parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]));
  return Number.isNaN(d.getTime()) ? null : d;
}

export function LocalizedDateInput({ value, onChange, placeholder, className }: Props) {
  const { locale, t } = useLang();
  const bcp = BCP47[locale] || "en";

  const [open, setOpen] = useState(false);
  const [view, setView] = useState<Date>(parseIso(value) || new Date());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (parseIso(value)) setView(parseIso(value) as Date);
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Localized display string for the input itself (dd Mon yyyy etc.)
  const displayValue = (() => {
    const d = parseIso(value);
    if (!d) return "";
    return new Intl.DateTimeFormat(bcp, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(d);
  })();

  // Month + year header — "May 2026" / "พฤษภาคม 2569" / "2026年5月"
  const headerLabel = new Intl.DateTimeFormat(bcp, {
    month: "long",
    year: "numeric",
  }).format(view);

  // Weekday header row — locale-correct (Sun-start or Mon-start by locale)
  // Use a reference week and Intl.DateTimeFormat to grab short names.
  // First day of week: EU + JA = Monday (1), TH + EN = Sunday (0).
  const startOnMonday = locale === "en-EU" || locale === "ja";
  const weekdayLabels = (() => {
    // Use a known week (Jan 4 2026 = Sunday).
    const base = new Date(2026, 0, 4);
    const fmt = new Intl.DateTimeFormat(bcp, { weekday: "narrow" });
    const out: string[] = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(base);
      const offset = startOnMonday ? i + 1 : i;
      d.setDate(base.getDate() + offset);
      out.push(fmt.format(d));
    }
    return out;
  })();

  // Build the visible 6x7 grid for the current view month
  const grid: { date: Date; inMonth: boolean }[] = (() => {
    const firstOfMonth = new Date(view.getFullYear(), view.getMonth(), 1);
    const firstDay = firstOfMonth.getDay(); // 0=Sun
    const leadingBlank = startOnMonday ? (firstDay + 6) % 7 : firstDay;
    const start = new Date(firstOfMonth);
    start.setDate(start.getDate() - leadingBlank);
    const cells: { date: Date; inMonth: boolean }[] = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      cells.push({ date: d, inMonth: d.getMonth() === view.getMonth() });
    }
    return cells;
  })();

  const todayIso = toIso(new Date());
  const selectedIso = value;

  const pick = (d: Date) => {
    onChange(toIso(d));
    setOpen(false);
  };

  const prevMonth = () => setView((v) => new Date(v.getFullYear(), v.getMonth() - 1, 1));
  const nextMonth = () => setView((v) => new Date(v.getFullYear(), v.getMonth() + 1, 1));

  return (
    <div ref={ref} className="relative inline-block">
      <input
        type="text"
        readOnly
        value={displayValue}
        placeholder={placeholder || ""}
        onClick={() => setOpen((v) => !v)}
        className={className || "border border-gray-300 rounded px-1.5 py-0.5 text-[10px] cursor-pointer bg-white"}
      />
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-2 w-64">
          {/* Header */}
          <div className="flex items-center justify-between mb-2">
            <button
              type="button"
              onClick={prevMonth}
              className="p-1 hover:bg-gray-100 rounded text-gray-600"
              aria-label="Previous month"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <span className="text-xs font-semibold text-gray-800">{headerLabel}</span>
            <button
              type="button"
              onClick={nextMonth}
              className="p-1 hover:bg-gray-100 rounded text-gray-600"
              aria-label="Next month"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          {/* Weekday header */}
          <div className="grid grid-cols-7 gap-0.5 mb-1">
            {weekdayLabels.map((w, i) => (
              <div key={i} className="text-[9px] text-gray-400 text-center font-medium uppercase">
                {w}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7 gap-0.5">
            {grid.map(({ date, inMonth }, i) => {
              const iso = toIso(date);
              const isSelected = iso === selectedIso;
              const isToday = iso === todayIso;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => pick(date)}
                  className={`text-[10px] py-1 rounded transition ${
                    isSelected
                      ? "bg-brand-600 text-white font-semibold"
                      : isToday
                      ? "bg-brand-50 text-brand-700 font-medium"
                      : inMonth
                      ? "text-gray-700 hover:bg-gray-100"
                      : "text-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {date.getDate()}
                </button>
              );
            })}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
            <button
              type="button"
              onClick={() => onChange("")}
              className="text-[10px] text-gray-500 hover:text-gray-700 px-1.5 py-0.5"
            >
              {t("datepicker.clear")}
            </button>
            <button
              type="button"
              onClick={() => pick(new Date())}
              className="text-[10px] text-brand-600 hover:text-brand-700 font-medium px-1.5 py-0.5"
            >
              {t("datepicker.today")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
