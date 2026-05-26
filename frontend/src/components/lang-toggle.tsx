"use client";
import { useLang } from "@/components/lang-provider";
import { cn } from "@/lib/utils";

export function LangToggle({ compact }: { compact?: boolean }) {
  const { locale, setLocale, t } = useLang();

  if (compact) {
    return (
      <button
        onClick={() => setLocale(locale === "th" ? "en" : "th")}
        className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded bg-gray-100 hover:bg-gray-200 text-gray-600 transition"
        title={locale === "th" ? "Switch to English" : "เปลี่ยนเป็นภาษาไทย"}
      >
        <span>{locale === "th" ? "🇹🇭" : "🇬🇧"}</span>
        <span>{locale === "th" ? "TH" : "EN"}</span>
      </button>
    );
  }

  return (
    <div className="flex rounded-md border border-gray-200 overflow-hidden text-[10px]">
      <button
        onClick={() => setLocale("th")}
        className={cn(
          "px-2 py-0.5 transition font-medium",
          locale === "th"
            ? "bg-brand-600 text-white"
            : "bg-white text-gray-500 hover:bg-gray-50"
        )}
      >
        🇹🇭 {t("lang.th")}
      </button>
      <button
        onClick={() => setLocale("en")}
        className={cn(
          "px-2 py-0.5 transition font-medium",
          locale === "en"
            ? "bg-brand-600 text-white"
            : "bg-white text-gray-500 hover:bg-gray-50"
        )}
      >
        🇬🇧 {t("lang.en")}
      </button>
    </div>
  );
}
