"use client";
import { useEffect, useState } from "react";
import { useLang } from "@/components/lang-provider";
import { api } from "@/lib/api";
import { App } from "@/types";

type ExportResult = Awaited<ReturnType<typeof api.exportApp>>;

interface Props {
  app: App;
  onClose: () => void;
}

// Use the same relative API_BASE as lib/api.ts so the Next.js proxy
// handles localhost-vs-LAN-IP routing for us. The backend's response
// `download_url` already includes the `/api/...` prefix, so we use it
// as-is — prepending another `/api` would produce `/api/api/...` and 404.
//
// (This was the bug behind the "Download failed" alert: the export modal
// previously had its own `http://localhost:8000/api` constant which it
// concatenated with download_url, doubling the prefix.)
export function ExportAppModal({ app, onClose }: Props) {
  const { t } = useLang();
  const [status, setStatus] = useState<"working" | "done" | "error">("working");
  const [result, setResult] = useState<ExportResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && status !== "working") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onClose, status]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.exportApp(app.id);
        if (cancelled) return;
        setResult(r);
        setStatus("done");
      } catch (e: any) {
        if (cancelled) return;
        setErrorMsg(e?.message || "Export failed");
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [app.id]);

  const handleDownload = async () => {
    if (!result) return;
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    try {
      // result.download_url already contains the full `/api/...` path from the
      // backend, so we fetch it directly — no prefix concatenation.
      const res = await fetch(result.download_url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        // Try to surface the backend's error JSON if any (e.g. {"detail": "..."}).
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) detail = body.detail;
        } catch {}
        throw new Error(detail);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e?.message || "Download failed");
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 z-40 backdrop-blur-sm"
        onClick={() => status !== "working" && onClose()}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden pointer-events-auto"
          role="dialog"
          aria-modal="true"
        >
          {/* Header */}
          <div
            className={`px-5 py-4 ${
              status === "error"
                ? "bg-gradient-to-r from-red-500 to-red-600"
                : "bg-gradient-to-r from-brand-600 to-brand-700"
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                {status === "working" ? (
                  <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                ) : status === "done" ? (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                )}
              </div>
              <div>
                <h2 className="text-white font-semibold text-base">
                  {status === "working"
                    ? t("export.title_working")
                    : status === "done"
                    ? t("export.title_done")
                    : t("export.title_error")}
                </h2>
                <p className="text-white/80 text-[11px] mt-0.5">
                  {status === "working"
                    ? t("export.subtitle_working")
                    : status === "done"
                    ? t("export.subtitle_done")
                    : t("export.subtitle_error")}
                </p>
              </div>
            </div>
          </div>

          {/* Body */}
          <div className="p-5 space-y-3">
            {/* App identity */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-[10px] uppercase text-gray-500 font-semibold tracking-wider mb-1">
                {t("export.target_app")}
              </p>
              <p className="font-mono text-sm font-bold text-gray-900 break-all">{app.name}</p>
              <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-500">
                <span>v{app.current_version}</span>
                {app.port && <span>:{app.port}</span>}
                <span className="capitalize">{app.app_type}</span>
              </div>
            </div>

            {status === "working" && (
              <div className="space-y-1.5 text-[11px] text-gray-600">
                <p>{t("export.step1")}</p>
                <p>{t("export.step2")}</p>
                <p>{t("export.step3")}</p>
                <p className="text-gray-400 italic mt-2">{t("export.please_wait")}</p>
              </div>
            )}

            {status === "done" && result && (
              <>
                <div className="bg-green-50 border border-green-200 rounded-lg p-3 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-600">{t("export.bundle_size")}</span>
                    <span className="font-bold text-green-700">{result.size_human}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-600">{t("export.data_paths_copied")}</span>
                    <span className="font-bold text-green-700">{result.data_paths_copied}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-600">{t("export.filename")}</span>
                    <code className="text-[10px] bg-white px-1.5 py-0.5 rounded border border-gray-200 font-mono text-gray-700 max-w-[200px] truncate">
                      {result.filename}
                    </code>
                  </div>
                </div>

                {result.data_paths_copied === 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 flex gap-2">
                    <svg className="w-4 h-4 text-amber-600 flex-shrink-0 mt-px" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <p className="text-[11px] text-amber-800">{t("export.no_data_warning")}</p>
                  </div>
                )}

                {result.errors.length > 0 && (
                  <details className="text-[10px]">
                    <summary className="text-gray-500 cursor-pointer hover:text-gray-700">
                      {t("export.warnings")} ({result.errors.length})
                    </summary>
                    <ul className="mt-1 space-y-0.5 ml-4 text-gray-500">
                      {result.errors.map((err, i) => (
                        <li key={i} className="list-disc">{err}</li>
                      ))}
                    </ul>
                  </details>
                )}

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-2.5 text-[11px] text-blue-800">
                  💡 {t("export.tip")}
                </div>
              </>
            )}

            {status === "error" && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-[11px] text-red-700">
                {errorMsg}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-5 py-3 flex items-center justify-end gap-2 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              disabled={status === "working"}
              className="px-4 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition disabled:opacity-50"
            >
              {status === "done" ? t("export.close") : t("export.cancel")}
            </button>
            {status === "done" && result && (
              <button
                type="button"
                onClick={handleDownload}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 rounded-md hover:bg-brand-700 transition"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                {t("export.download")}
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
