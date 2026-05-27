"use client";
import { useState, useEffect, useRef } from "react";
import { useLang } from "@/components/lang-provider";
import { App } from "@/types";

interface Props {
  app: App;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  /** Optional handler: switch user to the export flow before deleting. */
  onExportFirst?: () => void;
}

export function DeleteAppModal({ app, onConfirm, onCancel, onExportFirst }: Props) {
  const { t } = useLang();
  const [typedName, setTypedName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on mount and bind Escape key
  useEffect(() => {
    inputRef.current?.focus();
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onCancel();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onCancel, submitting]);

  const canDelete = typedName.trim() === app.name && !submitting;

  const handleDelete = async () => {
    if (!canDelete) return;
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
        onClick={() => !submitting && onCancel()}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden pointer-events-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-red-500 to-red-600 px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h2 id="delete-modal-title" className="text-white font-semibold text-base">
                  {t("delete.title")}
                </h2>
                <p className="text-red-100 text-[11px] mt-0.5">{t("delete.subtitle")}</p>
              </div>
            </div>
          </div>

          {/* Body */}
          <div className="p-5 space-y-4">
            {/* App identity card */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-[10px] uppercase text-gray-500 font-semibold tracking-wider mb-1">
                {t("delete.target_app")}
              </p>
              <p className="font-mono text-sm font-bold text-gray-900 break-all">{app.name}</p>
              <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-500">
                <span>v{app.current_version}</span>
                {app.port && <span>:{app.port}</span>}
                <span className="capitalize">{app.app_type}</span>
              </div>
            </div>

            {/* What will be lost */}
            <div>
              <p className="text-xs font-semibold text-gray-800 mb-2 flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {t("delete.what_lost_title")}
              </p>
              <ul className="space-y-1.5 text-[11px] text-gray-600 ml-1">
                <li className="flex gap-2">
                  <span className="text-red-500 font-bold mt-px">•</span>
                  <span>{t("delete.lost.container")}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-red-500 font-bold mt-px">•</span>
                  <span>{t("delete.lost.data")}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-red-500 font-bold mt-px">•</span>
                  <span>{t("delete.lost.logs")}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-red-500 font-bold mt-px">•</span>
                  <span>{t("delete.lost.port")}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-red-500 font-bold mt-px">•</span>
                  <span>{t("delete.lost.access")}</span>
                </li>
              </ul>
            </div>

            {/* Irreversible warning */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 flex gap-2">
              <svg className="w-4 h-4 text-amber-600 flex-shrink-0 mt-px" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <p className="text-[11px] text-amber-800">{t("delete.irreversible")}</p>
            </div>

            {/* Export first suggestion */}
            {onExportFirst && (
              <div className="bg-brand-50 border border-brand-200 rounded-lg p-2.5">
                <div className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-brand-600 flex-shrink-0 mt-px" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  <div className="flex-1">
                    <p className="text-[11px] text-brand-900 font-medium">{t("delete.export_first_title")}</p>
                    <p className="text-[10px] text-brand-700 mt-0.5">{t("delete.export_first_desc")}</p>
                    <button
                      type="button"
                      onClick={onExportFirst}
                      disabled={submitting}
                      className="mt-2 inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold text-white bg-brand-600 rounded hover:bg-brand-700 transition disabled:opacity-50"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      {t("delete.export_first_button")}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Type-to-confirm */}
            <div>
              <label className="text-[11px] font-medium text-gray-700 block mb-1.5">
                {t("delete.type_to_confirm")}{" "}
                <code className="bg-gray-100 px-1.5 py-0.5 rounded text-red-600 font-mono text-[10px]">
                  {app.name}
                </code>
              </label>
              <input
                ref={inputRef}
                type="text"
                value={typedName}
                onChange={(e) => setTypedName(e.target.value)}
                disabled={submitting}
                placeholder={app.name}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 font-mono disabled:bg-gray-50 disabled:cursor-not-allowed"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-5 py-3 flex items-center justify-end gap-2 border-t border-gray-200">
            <button
              type="button"
              onClick={onCancel}
              disabled={submitting}
              className="px-4 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition disabled:opacity-50"
            >
              {t("delete.cancel")}
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={!canDelete}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-red-600 rounded-md hover:bg-red-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <>
                  <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  {t("delete.deleting")}
                </>
              ) : (
                <>
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  {t("delete.confirm")}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
