"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

type RetentionEntry = {
  days: number;
  default: number;
  min: number;
  max_recommended: number;
  max_allowed: number;
};

type Settings = Record<string, RetentionEntry>;

const ORDER = ["audit_logs", "app_logs", "resource_metrics", "exports"] as const;

export function RetentionPolicyPanel() {
  const { t } = useLang();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [edits, setEdits] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [purging, setPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState<Record<string, number> | null>(null);
  const [toast, setToast] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const s = await api.getRetentionSettings();
      setSettings(s);
      // initialize edit buffer with current values
      const init: Record<string, number> = {};
      for (const k of Object.keys(s)) init[k] = s[k].days;
      setEdits(init);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!settings) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4 text-[10px] text-gray-400">
        {t("retention.loading")}
      </div>
    );
  }

  const hasChanges = ORDER.some((k) => edits[k] !== settings[k]?.days);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await api.updateRetentionSettings(edits);
      setSettings(updated);
      const init: Record<string, number> = {};
      for (const k of Object.keys(updated)) init[k] = updated[k].days;
      setEdits(init);
      setToast(t("retention.saved"));
      setTimeout(() => setToast(""), 3000);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handlePurge = async () => {
    if (!confirm(t("retention.purge_confirm"))) return;
    setPurging(true);
    try {
      const result = await api.triggerRetentionPurge();
      setPurgeResult(result);
      setToast(t("retention.purge_done"));
      setTimeout(() => setToast(""), 5000);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setPurging(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-1.5">
            <svg className="w-4 h-4 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {t("retention.title")}
          </h3>
          <p className="text-[10px] text-gray-500 mt-0.5">{t("retention.subtitle")}</p>
        </div>
        <button
          onClick={handlePurge}
          disabled={purging}
          title={t("retention.purge_tooltip")}
          className="px-2.5 py-1 text-[10px] font-medium text-red-600 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 transition disabled:opacity-50 flex-shrink-0"
        >
          {purging ? t("retention.purging") : t("retention.purge_now")}
        </button>
      </div>

      {/* Legal note */}
      <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 flex gap-2 text-[10px] text-amber-800">
        <svg className="w-3.5 h-3.5 flex-shrink-0 mt-px" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        <span>{t("retention.legal_note")}</span>
      </div>

      {/* Per-type controls */}
      <div className="space-y-2.5">
        {ORDER.map((key) => {
          const entry = settings[key];
          if (!entry) return null;
          const value = edits[key] ?? entry.days;
          const overRecommended = value > entry.max_recommended;
          const isMinimum = value === entry.min;
          return (
            <div key={key} className="border border-gray-100 rounded-md p-2.5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-gray-800">
                      {t(`retention.type.${key}`)}
                    </span>
                    {isMinimum && (
                      <span className="text-[8px] px-1 py-px rounded bg-blue-50 text-blue-700 font-medium">
                        {t("retention.at_minimum")}
                      </span>
                    )}
                  </div>
                  <p className="text-[9px] text-gray-500 mt-0.5">{t(`retention.desc.${key}`)}</p>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <input
                    type="number"
                    min={entry.min}
                    max={entry.max_allowed}
                    value={value}
                    onChange={(e) =>
                      setEdits((prev) => ({
                        ...prev,
                        [key]: parseInt(e.target.value) || entry.min,
                      }))
                    }
                    className="w-20 border border-gray-300 rounded px-1.5 py-0.5 text-[10px] text-right font-mono"
                  />
                  <span className="text-[10px] text-gray-500">{t("retention.days")}</span>
                </div>
              </div>
              <div className="mt-1.5 flex items-center justify-between text-[9px] text-gray-400">
                <span>
                  {t("retention.range")}: {entry.min}–{entry.max_allowed} {t("retention.days")}
                  {" · "}
                  {t("retention.default")}: {entry.default}
                </span>
                {overRecommended && (
                  <span className="text-amber-600 font-medium">
                    ⚠ {t("retention.over_recommended")}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <div className="text-[10px]">
          {toast && <span className="text-green-600 font-medium">{toast}</span>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const init: Record<string, number> = {};
              for (const k of Object.keys(settings)) init[k] = settings[k].days;
              setEdits(init);
            }}
            disabled={!hasChanges || saving}
            className="px-3 py-1 text-[10px] text-gray-600 hover:text-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {t("retention.reset")}
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges || saving}
            className="px-3 py-1 text-[10px] font-semibold text-white bg-brand-600 rounded-md hover:bg-brand-700 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? t("retention.saving") : t("retention.save")}
          </button>
        </div>
      </div>

      {/* Purge result detail */}
      {purgeResult && (
        <div className="bg-gray-50 border border-gray-100 rounded-md p-2.5">
          <p className="text-[10px] font-medium text-gray-700 mb-1">{t("retention.purge_result")}</p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
            {Object.entries(purgeResult).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-gray-500">{t(`retention.type.${k}`) || k}</span>
                <span className={`font-mono font-semibold ${v > 0 ? "text-amber-700" : "text-gray-400"}`}>
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
