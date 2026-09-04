import th from "./th";
import en from "./en";
import enEU from "./en-EU";
import ja from "./ja";

export type Locale = "th" | "en" | "en-EU" | "ja";

/**
 * `th` and `en` are full dictionaries. `en-EU` and `ja` are OVERLAYS that carry
 * only regulator-specific compliance strings; everything else falls back to
 * `en` via t().
 *
 * Regulatory mapping:
 *   th     — PDPA (พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562)
 *   en     — generic English, refers to PDPA by default
 *   en-EU  — GDPR (Regulation (EU) 2016/679, Privacy by Design Art. 25)
 *   ja     — APPI (個人情報の保護に関する法律, 2003 + 2022 amendments)
 *
 * One file per locale: the combined dictionary had grown past 3,000 lines, so
 * adding a single string meant opening all of it. Add new keys to `th` and `en`
 * together — the overlays only need an entry when the regulator's wording
 * actually differs.
 */
const translations: Record<Locale, Record<string, string>> = {
  th,
  en,
  "en-EU": enEU,
  ja,
};

/**
 * Resolution order: requested locale → en → key itself.
 * EU and JA are overlays — missing strings fall back to en.
 */
export function t(key: string, locale: Locale): string {
  return (
    translations[locale]?.[key] ||
    translations.en[key] ||
    key
  );
}

export function getStoredLocale(): Locale {
  if (typeof window === "undefined") return "th";
  return (localStorage.getItem("ivs_locale") as Locale) || "th";
}

export function setStoredLocale(locale: Locale) {
  if (typeof window !== "undefined") {
    localStorage.setItem("ivs_locale", locale);
  }
}
