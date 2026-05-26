"use client";
import { useState, useRef, useEffect } from "react";
import { useLang } from "@/components/lang-provider";

const APP_TYPES = [
  { key: "static", icon: "🌐", color: "bg-blue-50 border-blue-200 text-blue-700" },
  { key: "nodejs", icon: "🟢", color: "bg-green-50 border-green-200 text-green-700" },
  { key: "fastapi", icon: "⚡", color: "bg-yellow-50 border-yellow-200 text-yellow-700" },
  { key: "streamlit", icon: "📊", color: "bg-red-50 border-red-200 text-red-700" },
  { key: "fullstack", icon: "🔮", color: "bg-purple-50 border-purple-200 text-purple-700" },
] as const;

export function DeployGuide() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("static");
  const [viewMode, setViewMode] = useState<"prompts" | "template" | "cases">("prompts");
  const [copied, setCopied] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    if (open) document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [open]);

  const copyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(""), 2000);
    });
  };

  const prompt = t(`guide.prompt.${activeTab}`);
  const structure = t(`guide.structure.${activeTab}`);
  const templateContent = t("guide.template");

  return (
    <div className="relative inline-block" ref={panelRef}>
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 ml-2 px-1.5 py-0.5 text-[10px] font-medium text-brand-600 bg-brand-50 border border-brand-200 rounded-full hover:bg-brand-100 transition-colors"
        title={t("guide.tooltip")}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        {t("guide.button")}
      </button>

      {open && (
        <>
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setOpen(false)} />
        <div className="fixed inset-4 sm:inset-auto sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 z-50 w-auto sm:w-[520px] max-h-[calc(100vh-2rem)] sm:max-h-[80vh] bg-white rounded-xl border border-gray-200 shadow-2xl overflow-hidden flex flex-col">
          {/* Header */}
          <div className="bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-3 flex items-center justify-between flex-shrink-0">
            <div>
              <h3 className="text-white font-semibold text-sm">{t("guide.title")}</h3>
              <p className="text-brand-100 text-[10px] mt-0.5">{t("guide.subtitle")}</p>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white p-0.5">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Tab Toggle: Prompts / Template / Cases */}
          <div className="flex border-b border-gray-100 flex-shrink-0">
            {(["prompts", "template", "cases"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`flex-1 py-2 text-[11px] font-medium transition-colors ${viewMode === mode ? "text-brand-600 border-b-2 border-brand-500 bg-brand-50/50" : "text-gray-500 hover:text-gray-700"}`}
              >
                {t(`guide.tab_${mode}`)}
              </button>
            ))}
          </div>

          <div className="overflow-y-auto flex-1 min-h-0">
            {viewMode === "prompts" ? (
              <div className="p-3">
                {/* App Type Tabs */}
                <div className="flex gap-1 mb-3">
                  {APP_TYPES.map(({ key, icon, color }) => (
                    <button
                      key={key}
                      onClick={() => setActiveTab(key)}
                      className={`flex items-center gap-0.5 px-2 py-1 text-[10px] font-medium rounded-md border transition-all flex-1 justify-center ${
                        activeTab === key
                          ? `${color} ring-1 ring-offset-1 ring-brand-300`
                          : "bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100"
                      }`}
                    >
                      <span className="text-xs">{icon}</span>
                      {t(`guide.type.${key}`)}
                    </button>
                  ))}
                </div>

                {/* File Structure */}
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                      {t("guide.file_structure")}
                    </span>
                  </div>
                  <div className="bg-gray-900 text-gray-300 rounded-lg p-3 text-[11px] font-mono leading-relaxed whitespace-pre">
                    {structure}
                  </div>
                </div>

                {/* AI Prompt */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                      {t("guide.ai_prompt")}
                    </span>
                    <button
                      onClick={() => copyText(prompt, `prompt-${activeTab}`)}
                      className={`flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-md transition-all ${
                        copied === `prompt-${activeTab}`
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-600 hover:bg-brand-100 hover:text-brand-700"
                      }`}
                    >
                      {copied === `prompt-${activeTab}` ? (
                        <>
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                          {t("guide.copied")}
                        </>
                      ) : (
                        <>
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                          {t("guide.copy")}
                        </>
                      )}
                    </button>
                  </div>
                  <div className="relative bg-brand-50 border border-brand-200 rounded-lg p-3 text-[11px] text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {prompt}
                  </div>
                </div>

                {/* Tip */}
                <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-2.5 flex gap-2">
                  <span className="text-amber-500 mt-0.5 flex-shrink-0">
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </span>
                  <p className="text-[10px] text-amber-800">{t(`guide.tip.${activeTab}`)}</p>
                </div>
              </div>
            ) : viewMode === "template" ? (
              /* ivs-app.md Template */
              <div className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-xs font-semibold text-gray-800">{t("guide.template_title")}</p>
                    <p className="text-[10px] text-gray-500 mt-0.5">{t("guide.template_desc")}</p>
                  </div>
                  <button
                    onClick={() => copyText(templateContent, "template")}
                    className={`flex items-center gap-1 px-2.5 py-1 text-[10px] rounded-md transition-all ${
                      copied === "template"
                        ? "bg-green-100 text-green-700"
                        : "bg-brand-600 text-white hover:bg-brand-700"
                    }`}
                  >
                    {copied === "template" ? (
                      <>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        {t("guide.copied")}
                      </>
                    ) : (
                      <>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        {t("guide.copy_template")}
                      </>
                    )}
                  </button>
                </div>
                <div className="bg-gray-900 text-gray-300 rounded-lg p-3 text-[11px] font-mono leading-relaxed whitespace-pre overflow-x-auto">
                  {templateContent}
                </div>
              </div>
            ) : (
              /* Case Studies */
              <div className="p-3 space-y-3">
                <div>
                  <p className="text-xs font-semibold text-gray-800">{t("guide.cases_title")}</p>
                  <p className="text-[10px] text-gray-500 mt-0.5">{t("guide.cases_subtitle")}</p>
                </div>
                {["line_oa", "ngrok", "db_deploy"].map((caseKey) => (
                  <div key={caseKey} className="border border-gray-200 rounded-lg overflow-hidden">
                    {/* Case Header */}
                    <div className="bg-gray-50 px-3 py-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          caseKey === "line_oa" ? "bg-green-500" : caseKey === "ngrok" ? "bg-orange-500" : "bg-red-500"
                        }`} />
                        <span className="text-[11px] font-semibold text-gray-800">{t(`guide.case.${caseKey}.title`)}</span>
                      </div>
                    </div>
                    <div className="px-3 py-2 space-y-2">
                      {/* Problem */}
                      <div>
                        <span className="text-[9px] font-bold text-red-600 uppercase tracking-wider">Problem</span>
                        <p className="text-[10px] text-gray-700 mt-0.5">{t(`guide.case.${caseKey}.problem`)}</p>
                      </div>
                      {/* Cause */}
                      <div>
                        <span className="text-[9px] font-bold text-amber-600 uppercase tracking-wider">Cause</span>
                        <p className="text-[10px] text-gray-600 mt-0.5 whitespace-pre-line">{t(`guide.case.${caseKey}.cause`)}</p>
                      </div>
                      {/* Fix */}
                      <div>
                        <span className="text-[9px] font-bold text-green-600 uppercase tracking-wider">Solution</span>
                        <p className="text-[10px] text-gray-700 mt-0.5 whitespace-pre-line bg-green-50 rounded-md p-2">{t(`guide.case.${caseKey}.fix`)}</p>
                      </div>
                      {/* Tags */}
                      <div className="flex flex-wrap gap-1 pt-1">
                        {t(`guide.case.${caseKey}.tag`).split(" · ").map((tag: string) => (
                          <span key={tag} className="px-1.5 py-0.5 text-[8px] font-medium bg-gray-100 text-gray-500 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        </>
      )}
    </div>
  );
}
