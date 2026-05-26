"use client";
import { useState } from "react";
import { useLang } from "@/components/lang-provider";
import { cn } from "@/lib/utils";

const GITHUB_URL = "https://github.com/public-api-lists/public-api-lists";

const categories = [
  { icon: "🤖", key: "ai", name_th: "AI & Machine Learning", name_en: "AI & Machine Learning", desc_th: "วิเคราะห์ข้อความ, ภาพ, การทำนายข้อมูล", desc_en: "Text analysis, image recognition, predictions", count: 45, color: "bg-purple-50 text-purple-700 border-purple-200" },
  { icon: "🗺️", key: "maps", name_th: "แผนที่ & ตำแหน่ง", name_en: "Maps & Geo", desc_th: "พิกัด, แผนที่, คำนวณระยะทาง", desc_en: "Coordinates, maps, distance calculation", count: 30, color: "bg-blue-50 text-blue-700 border-blue-200" },
  { icon: "🌤️", key: "weather", name_th: "อากาศ & สิ่งแวดล้อม", name_en: "Weather & Environment", desc_th: "ข้อมูลอากาศเรียลไทม์ทั่วโลก", desc_en: "Real-time weather data worldwide", count: 20, color: "bg-cyan-50 text-cyan-700 border-cyan-200" },
  { icon: "💰", key: "finance", name_th: "การเงิน & คริปโต", name_en: "Finance & Crypto", desc_th: "ราคาหุ้น, คริปโต, ดัชนีตลาด", desc_en: "Stock prices, crypto, market indices", count: 35, color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { icon: "🐾", key: "animals", name_th: "สัตว์", name_en: "Animals", desc_th: "รูปภาพ, ข้อมูลพันธุ์, พฤติกรรมสัตว์", desc_en: "Images, breeds, animal behavior data", count: 15, color: "bg-orange-50 text-orange-700 border-orange-200" },
  { icon: "📚", key: "books", name_th: "หนังสือ", name_en: "Books", desc_th: "ค้นหาหนังสือจากคลังข้อมูลใหญ่", desc_en: "Search books from large databases", count: 12, color: "bg-amber-50 text-amber-700 border-amber-200" },
  { icon: "🎬", key: "media", name_th: "มีเดีย / เพลง / บันเทิง", name_en: "Media / Music / Entertainment", desc_th: "ข้อมูลหนัง, เพลง, ซีรีส์", desc_en: "Movies, music, series data", count: 40, color: "bg-pink-50 text-pink-700 border-pink-200" },
  { icon: "🏥", key: "health", name_th: "สุขภาพ & การแพทย์", name_en: "Health & Medical", desc_th: "ข้อมูลโรค, ยา, คำแนะนำสุขภาพ", desc_en: "Diseases, drugs, health advice", count: 18, color: "bg-red-50 text-red-700 border-red-200" },
  { icon: "🚚", key: "transport", name_th: "ขนส่ง & โลจิสติกส์", name_en: "Logistics / Transport", desc_th: "เส้นทาง, สถานะขนส่ง, ขนส่งสาธารณะ", desc_en: "Routes, shipping status, public transit", count: 22, color: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  { icon: "🎓", key: "education", name_th: "การศึกษา", name_en: "Education", desc_th: "ข้อมูลการเรียน, คอร์สเรียน, คำศัพท์", desc_en: "Learning data, courses, vocabulary", count: 14, color: "bg-teal-50 text-teal-700 border-teal-200" },
  { icon: "🛠️", key: "devtools", name_th: "เครื่องมือนักพัฒนา", name_en: "Dev Tools", desc_th: "GitHub, QR Code, Lorem Ipsum, JSON tools", desc_en: "GitHub, QR Code, Lorem Ipsum, JSON tools", count: 50, color: "bg-gray-50 text-gray-700 border-gray-200" },
  { icon: "🎮", key: "games", name_th: "เกม", name_en: "Games", desc_th: "ข้อมูลเกม, สถิติผู้เล่น, คะแนน", desc_en: "Game data, player stats, scores", count: 25, color: "bg-violet-50 text-violet-700 border-violet-200" },
];

const popularApis = [
  { name: "JSONPlaceholder", desc_th: "API ทดสอบ REST สำเร็จรูป (Users, Posts, Comments)", desc_en: "Ready-made REST test API (Users, Posts, Comments)", url: "https://jsonplaceholder.typicode.com", docs: "https://jsonplaceholder.typicode.com/guide/", free: true, noKey: true, cat: "devtools" },
  { name: "OpenWeatherMap", desc_th: "ข้อมูลอากาศเรียลไทม์ทั่วโลก", desc_en: "Real-time weather data worldwide", url: "https://api.openweathermap.org", docs: "https://openweathermap.org/api", free: true, noKey: false, cat: "weather" },
  { name: "REST Countries", desc_th: "ข้อมูลประเทศทั่วโลก (ธง, ประชากร, ภาษา)", desc_en: "World country data (flags, population, languages)", url: "https://restcountries.com/v3.1/all", docs: "https://restcountries.com", free: true, noKey: true, cat: "maps" },
  { name: "Dog CEO", desc_th: "รูปภาพสุนัขแบบสุ่มจากทุกสายพันธุ์", desc_en: "Random dog images from all breeds", url: "https://dog.ceo/api/breeds/image/random", docs: "https://dog.ceo/dog-api/", free: true, noKey: true, cat: "animals" },
  { name: "PokeAPI", desc_th: "ข้อมูล Pokemon ครบทุกตัว", desc_en: "Complete Pokemon data", url: "https://pokeapi.co/api/v2/pokemon/pikachu", docs: "https://pokeapi.co/docs/v2", free: true, noKey: true, cat: "games" },
  { name: "CoinGecko", desc_th: "ราคาคริปโตเรียลไทม์ ฟรีไม่ต้อง Key", desc_en: "Real-time crypto prices, free no key required", url: "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", docs: "https://docs.coingecko.com/reference/introduction", free: true, noKey: true, cat: "finance" },
  { name: "The Cat API", desc_th: "รูปภาพแมวสุ่ม พร้อมข้อมูลสายพันธุ์", desc_en: "Random cat images with breed info", url: "https://api.thecatapi.com/v1/images/search", docs: "https://docs.thecatapi.com", free: true, noKey: false, cat: "animals" },
  { name: "Open Library", desc_th: "ค้นหาหนังสือจากคลังข้อมูลนับล้านเล่ม", desc_en: "Search millions of books", url: "https://openlibrary.org/search.json?q=javascript", docs: "https://openlibrary.org/developers/api", free: true, noKey: true, cat: "books" },
  { name: "TMDB", desc_th: "ข้อมูลหนัง ซีรีส์ นักแสดง ครบถ้วน", desc_en: "Complete movies, series, actors data", url: "https://api.themoviedb.org/3", docs: "https://developer.themoviedb.org/docs", free: true, noKey: false, cat: "media" },
  { name: "Quotable", desc_th: "คำคมสุ่มจากบุคคลสำคัญ ไม่ต้อง Key", desc_en: "Random quotes from notable people, no key needed", url: "https://api.quotable.io/random", docs: "https://github.com/lukePeavey/quotable", free: true, noKey: true, cat: "devtools" },
  { name: "NASA APOD", desc_th: "ภาพดาราศาสตร์ประจำวันจาก NASA", desc_en: "NASA Astronomy Picture of the Day", url: "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY", docs: "https://api.nasa.gov", free: true, noKey: false, cat: "education" },
  { name: "JokeAPI", desc_th: "มุกตลก/เรื่องขำขัน แบบสุ่ม", desc_en: "Random jokes and humor", url: "https://v2.jokeapi.dev/joke/Any", docs: "https://jokeapi.dev", free: true, noKey: true, cat: "media" },
];

export default function ApiCatalogPage() {
  const { t, locale } = useLang();
  const [search, setSearch] = useState("");
  const [selectedCat, setSelectedCat] = useState<string | null>(null);

  const filteredCats = categories.filter(c => {
    const name = locale === "th" ? c.name_th : c.name_en;
    const desc = locale === "th" ? c.desc_th : c.desc_en;
    return !search || name.toLowerCase().includes(search.toLowerCase()) || desc.toLowerCase().includes(search.toLowerCase());
  });

  const filteredApis = popularApis.filter(api => {
    const desc = locale === "th" ? api.desc_th : api.desc_en;
    const matchSearch = !search || api.name.toLowerCase().includes(search.toLowerCase()) || desc.toLowerCase().includes(search.toLowerCase());
    const matchCat = !selectedCat || api.cat === selectedCat;
    return matchSearch && matchCat;
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{t("api_catalog.title")}</h1>
          <p className="text-gray-500 text-[10px] mt-0.5">{t("api_catalog.subtitle")}</p>
        </div>
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
          className="px-3 py-1 bg-gray-900 text-white text-[10px] font-medium rounded-md hover:bg-gray-800 transition flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
          {t("api_catalog.visit_github")}
        </a>
      </div>

      {/* Intro Box */}
      <div className="bg-gradient-to-r from-brand-50 to-indigo-50 rounded-lg border border-brand-200 p-4">
        <p className="text-xs text-gray-700 leading-relaxed">{t("api_catalog.intro")}</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
          {[
            { key: "h1", icon: "🌍" },
            { key: "h2", icon: "⭐" },
            { key: "h3", icon: "⚡" },
            { key: "h4", icon: "👥" },
          ].map(h => (
            <div key={h.key} className="bg-white/70 rounded-md p-2">
              <div className="text-sm mb-0.5">{h.icon}</div>
              <p className="text-[10px] font-semibold text-gray-900">{t(`api_catalog.${h.key}`)}</p>
              <p className="text-[9px] text-gray-500 leading-tight">{t(`api_catalog.${h.key}_desc`)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Search */}
      <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
        placeholder={t("api_catalog.search")}
        className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />

      {/* Categories */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-900">{t("api_catalog.categories_title")}</h2>
          {selectedCat && (
            <button onClick={() => setSelectedCat(null)} className="text-[10px] text-brand-600 hover:text-brand-700">
              {locale === "th" ? "แสดงทั้งหมด" : "Show all"}
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2">
          {filteredCats.map(cat => (
            <button key={cat.key} onClick={() => setSelectedCat(selectedCat === cat.key ? null : cat.key)}
              className={cn(
                "text-left rounded-lg border p-2.5 transition hover:shadow-sm",
                selectedCat === cat.key ? "ring-2 ring-brand-500 border-brand-300 bg-brand-50" : cat.color
              )}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">{cat.icon}</span>
                <span className="text-[11px] font-semibold truncate">{locale === "th" ? cat.name_th : cat.name_en}</span>
              </div>
              <p className="text-[9px] text-gray-500 leading-tight">{locale === "th" ? cat.desc_th : cat.desc_en}</p>
              <div className="mt-1.5 flex items-center gap-1">
                <span className="text-[9px] font-medium text-gray-400">{cat.count}+ {t("api_catalog.count_apis")}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Popular APIs */}
      <div>
        <h2 className="text-sm font-semibold text-gray-900 mb-2">{t("api_catalog.popular_title")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
          {filteredApis.map(api => (
            <div key={api.name} className="bg-white rounded-lg border border-gray-200 p-3 hover:shadow-md transition">
              <div className="flex items-center justify-between mb-1.5">
                <h4 className="font-semibold text-xs text-gray-900">{api.name}</h4>
                <div className="flex gap-1">
                  {api.free && (
                    <span className="text-[8px] px-1.5 py-px rounded-full bg-green-100 text-green-700 font-medium">
                      {t("api_catalog.free")}
                    </span>
                  )}
                  {api.noKey ? (
                    <span className="text-[8px] px-1.5 py-px rounded-full bg-blue-100 text-blue-700 font-medium">
                      {t("api_catalog.no_key")}
                    </span>
                  ) : (
                    <span className="text-[8px] px-1.5 py-px rounded-full bg-amber-100 text-amber-700 font-medium">
                      {t("api_catalog.key_required")}
                    </span>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-gray-500 mb-2">{locale === "th" ? api.desc_th : api.desc_en}</p>
              <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                <code className="text-[8px] text-gray-400 truncate max-w-[60%] font-mono">{api.url.replace("https://", "").split("/")[0]}</code>
                <div className="flex gap-2">
                  <a href={api.url} target="_blank" rel="noopener noreferrer"
                    className="text-[10px] text-brand-600 hover:text-brand-700 font-medium">
                    {t("api_catalog.try_it")} →
                  </a>
                  <a href={api.docs} target="_blank" rel="noopener noreferrer"
                    className="text-[10px] text-gray-500 hover:text-gray-700 font-medium">
                    {t("api_catalog.docs")}
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tips */}
      <div className="bg-amber-50 rounded-lg border border-amber-200 p-4">
        <h3 className="font-semibold text-amber-800 text-xs mb-2 flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          {t("api_catalog.tip_title")}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="flex items-start gap-1.5">
              <span className="text-amber-600 text-[10px] font-bold mt-px">{i}.</span>
              <p className="text-[10px] text-amber-800 leading-relaxed">{t(`api_catalog.tip_${i}`)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* GitHub CTA */}
      <div className="bg-gray-900 rounded-lg p-4 text-center">
        <p className="text-white text-xs mb-1">
          {locale === "th" ? "ดู API ทั้งหมดกว่า 300+ รายการ" : "Browse 300+ APIs and counting"}
        </p>
        <p className="text-gray-400 text-[10px] mb-3">
          {locale === "th" ? "อัปเดตอยู่เสมอโดยชุมชน Open Source" : "Constantly updated by the Open Source community"}
        </p>
        <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-1.5 bg-white text-gray-900 text-xs font-medium rounded-md hover:bg-gray-100 transition">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
          public-api-lists/public-api-lists
        </a>
      </div>
    </div>
  );
}
