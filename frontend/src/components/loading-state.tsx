"use client";
import { useLang } from "@/components/lang-provider";

interface Props {
  /** Optional explicit label. Defaults to "Loading…" in current locale. */
  label?: string;
  /** "page" = full-page centered spinner; "inline" = small inline; "card" = full-width skeleton card */
  variant?: "page" | "inline" | "card";
}

export function LoadingState({ label, variant = "page" }: Props) {
  const { t } = useLang();
  const text = label ?? t("common.loading");

  if (variant === "inline") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-gray-500">
        <Spinner size="sm" />
        {text}
      </span>
    );
  }

  if (variant === "card") {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 flex items-center justify-center gap-2.5">
        <Spinner />
        <span className="text-xs text-gray-500">{text}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <Spinner size="lg" />
      <p className="text-xs text-gray-500">{text}</p>
    </div>
  );
}

export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dim = size === "sm" ? "w-3 h-3" : size === "lg" ? "w-6 h-6" : "w-4 h-4";
  return (
    <svg
      className={`${dim} animate-spin text-brand-600`}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

/** Pulse skeleton placeholder block — useful while waiting for data. */
export function SkeletonBlock({
  rows = 3,
  className = "",
}: { rows?: number; className?: string }) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-4 space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-3 bg-gray-100 rounded animate-pulse"
          style={{ width: `${100 - i * 12}%` }}
        />
      ))}
    </div>
  );
}

/** Performance-warning banner — shown when initial load exceeds threshold. */
export function PerfWarningBanner({ seconds }: { seconds: number }) {
  const { t } = useLang();
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 flex items-start gap-2">
      <span className="text-base flex-shrink-0">⏱</span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-medium text-amber-800">
          {t("perf.slow_title").replace("{n}", String(seconds))}
        </p>
        <p className="text-[10px] text-amber-700 mt-0.5">
          {t("perf.slow_desc")}
        </p>
      </div>
    </div>
  );
}
