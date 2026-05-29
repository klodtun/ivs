"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { formatLegalTimestamp } from "@/lib/utils";
import { PasswordConfirmModal } from "@/components/password-confirm-modal";

type TargetType = "email" | "ip" | "username" | "user_id";

interface ErasureHistoryRow {
  id: number;
  target_type: string;
  target_hash: string;
  reason: string;
  legal_basis: string;
  rows_affected: Record<string, number>;
  sha256_proof: string;
  created_at: string | null;
}

export function GdprErasurePanel() {
  const { t } = useLang();
  const [collapsed, setCollapsed] = useState(true);
  const COLLAPSED_KEY = "ivs.gdpr_panel.collapsed";

  const [targetType, setTargetType] = useState<TargetType>("email");
  const [targetValue, setTargetValue] = useState("");
  const [reason, setReason] = useState("");
  const [legalBasis, setLegalBasis] = useState("GDPR Art. 17(1)(a)");
  const [previewCounts, setPreviewCounts] = useState<Record<string, number> | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [certificate, setCertificate] = useState<{ text: string; sha256: string; id: number } | null>(null);
  const [history, setHistory] = useState<ErasureHistoryRow[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setCollapsed(localStorage.getItem(COLLAPSED_KEY) !== "false");
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem(COLLAPSED_KEY, String(next)); } catch {}
      if (!next) loadHistory();
      return next;
    });
  };

  const loadHistory = useCallback(async () => {
    try {
      const h = await api.listGdprErasures();
      setHistory(h);
    } catch {
      // ignore
    }
  }, []);

  const runPreview = async () => {
    if (!targetValue.trim()) return;
    setPreviewLoading(true);
    setPreviewCounts(null);
    try {
      const res = await api.previewGdprErasure(targetType, targetValue.trim());
      setPreviewCounts(res.rows_affected);
    } catch (e: any) {
      alert(e?.message || "Preview failed");
    } finally {
      setPreviewLoading(false);
    }
  };

  const runErasure = async (password: string) => {
    try {
      const res = await api.executeGdprErasure(
        targetType, targetValue.trim(), reason.trim(), legalBasis.trim(), password
      );
      setCertificate({ text: res.certificate, sha256: res.sha256_proof, id: res.id });
      setShowConfirm(false);
      setPreviewCounts(null);
      setTargetValue("");
      setReason("");
      await loadHistory();
    } catch (e: any) {
      throw e;
    }
  };

  const downloadCertificate = () => {
    if (!certificate) return;
    const blob = new Blob([certificate.text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gdpr-erasure-${certificate.id}-${certificate.sha256.substring(0, 8)}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // Collapsed view
  if (collapsed) {
    return (
      <div className="bg-white rounded-lg border border-gray-200">
        <button
          type="button"
          onClick={toggleCollapsed}
          className="w-full flex items-center justify-between gap-3 p-3 hover:bg-gray-50 transition rounded-lg group"
        >
          <div className="flex items-center gap-2 min-w-0">
            <svg className="w-4 h-4 text-red-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22" />
            </svg>
            <div className="text-left min-w-0">
              <h3 className="font-semibold text-gray-900 text-sm leading-tight">{t("gdpr.title")}</h3>
              <p className="text-[10px] text-gray-500 mt-0.5 truncate">{t("gdpr.subtitle_short")}</p>
            </div>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <span className="text-[9px] px-1.5 py-px rounded-full bg-gray-100 text-gray-500 font-medium hidden sm:inline">
              {t("retention.click_to_expand")}
            </span>
            <svg className="w-4 h-4 text-gray-400 group-hover:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={toggleCollapsed}
          className="flex items-start gap-2 text-left flex-1 min-w-0 hover:opacity-80 transition group"
          title={t("retention.click_to_collapse")}
        >
          <svg className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22" />
          </svg>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-1.5">
              {t("gdpr.title")}
              <svg className="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
              </svg>
            </h3>
            <p className="text-[10px] text-gray-500 mt-0.5">{t("gdpr.subtitle")}</p>
          </div>
        </button>
      </div>

      {/* Legal note */}
      <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 flex gap-2 text-[10px] text-amber-800">
        <svg className="w-3.5 h-3.5 flex-shrink-0 mt-px" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        <span>{t("gdpr.legal_note")}</span>
      </div>

      {/* Form */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        <div>
          <label className="text-[10px] font-medium text-gray-600 block mb-1">{t("gdpr.target_type")}</label>
          <select
            value={targetType}
            onChange={(e) => { setTargetType(e.target.value as TargetType); setPreviewCounts(null); }}
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded-md"
          >
            <option value="email">{t("gdpr.tt.email")}</option>
            <option value="username">{t("gdpr.tt.username")}</option>
            <option value="user_id">{t("gdpr.tt.user_id")}</option>
            <option value="ip">{t("gdpr.tt.ip")}</option>
          </select>
        </div>
        <div>
          <label className="text-[10px] font-medium text-gray-600 block mb-1">{t("gdpr.target_value")}</label>
          <input
            type="text"
            value={targetValue}
            onChange={(e) => { setTargetValue(e.target.value); setPreviewCounts(null); }}
            placeholder={t("gdpr.target_value_ph")}
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded-md font-mono"
          />
        </div>
        <div>
          <label className="text-[10px] font-medium text-gray-600 block mb-1">{t("gdpr.legal_basis_label")}</label>
          <input
            type="text"
            value={legalBasis}
            onChange={(e) => setLegalBasis(e.target.value)}
            placeholder="GDPR Art. 17(1)(a)"
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded-md"
          />
        </div>
        <div>
          <label className="text-[10px] font-medium text-gray-600 block mb-1">{t("gdpr.reason_label")}</label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("gdpr.reason_ph")}
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded-md"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-1">
        <button
          onClick={runPreview}
          disabled={!targetValue.trim() || previewLoading}
          className="px-3 py-1 text-[10px] font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40"
        >
          {previewLoading ? t("gdpr.previewing") : t("gdpr.preview")}
        </button>
        <button
          onClick={() => setShowConfirm(true)}
          disabled={!targetValue.trim() || !previewCounts}
          className="px-3 py-1 text-[10px] font-semibold text-white bg-red-600 rounded-md hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          {t("gdpr.execute")}
        </button>
      </div>

      {/* Preview result */}
      {previewCounts && (
        <div className="bg-gray-50 border border-gray-200 rounded-md p-2.5">
          <p className="text-[10px] font-semibold text-gray-700 mb-1.5">{t("gdpr.preview_title")}</p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px]">
            {Object.entries(previewCounts).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-gray-500 font-mono">{k}</span>
                <span className={`font-bold ${v > 0 ? "text-amber-700" : "text-gray-400"}`}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Certificate result */}
      {certificate && (
        <div className="bg-green-50 border border-green-300 rounded-md p-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-green-800">✓ {t("gdpr.cert_issued")} #{certificate.id}</p>
            <button onClick={downloadCertificate} className="text-[10px] text-green-700 hover:text-green-900 underline font-medium">
              ⬇ {t("gdpr.cert_download")}
            </button>
          </div>
          <p className="text-[10px] text-green-700">
            <span className="font-mono">SHA-256: {certificate.sha256.substring(0, 32)}…</span>
          </p>
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="border-t border-gray-100 pt-2">
          <p className="text-[10px] font-semibold text-gray-700 mb-1">{t("gdpr.history_title")} ({history.length})</p>
          <div className="bg-gray-50 rounded-md max-h-40 overflow-y-auto">
            <table className="w-full text-[9px]">
              <thead className="text-gray-500 sticky top-0 bg-gray-50">
                <tr>
                  <th className="text-left px-2 py-1">{t("gdpr.col_when")}</th>
                  <th className="text-left px-2 py-1">{t("gdpr.col_target")}</th>
                  <th className="text-left px-2 py-1">{t("gdpr.col_hash")}</th>
                  <th className="text-left px-2 py-1">{t("gdpr.col_rows")}</th>
                  <th className="text-left px-2 py-1">{t("gdpr.col_basis")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {history.map((h) => (
                  <tr key={h.id} className="hover:bg-white">
                    <td className="px-2 py-1 text-gray-600 font-mono whitespace-nowrap">{h.created_at ? formatLegalTimestamp(h.created_at) : "—"}</td>
                    <td className="px-2 py-1 text-gray-700">{h.target_type}</td>
                    <td className="px-2 py-1 font-mono text-gray-500" title={h.target_hash}>{h.target_hash.substring(0, 12)}…</td>
                    <td className="px-2 py-1 text-amber-700 font-semibold">{Object.values(h.rows_affected).reduce((a, b) => a + b, 0)}</td>
                    <td className="px-2 py-1 text-gray-600">{h.legal_basis || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Password modal */}
      {showConfirm && (
        <PasswordConfirmModal
          title={t("gdpr.modal_title")}
          description={t("gdpr.modal_desc")}
          consequences={[
            t("gdpr.modal_consequence_1"),
            t("gdpr.modal_consequence_2"),
            t("gdpr.modal_consequence_3"),
            t("gdpr.modal_consequence_4"),
          ]}
          legalNote={t("gdpr.modal_legal")}
          confirmLabel={t("gdpr.modal_confirm")}
          onConfirm={runErasure}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}
