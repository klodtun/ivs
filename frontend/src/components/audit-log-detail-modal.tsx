"use client";
import { useEffect, useState } from "react";
import { useLang } from "@/components/lang-provider";
import { cn, formatLegalTimestamp } from "@/lib/utils";
import type { AuditLog, User } from "@/types";

interface Props {
  log: AuditLog;
  user?: User;
  onClose: () => void;
}

const LEVEL_COLOR: Record<string, string> = {
  ERROR: "bg-red-100 text-red-700 border-red-200",
  WARNING: "bg-amber-100 text-amber-700 border-amber-200",
  INFO: "bg-blue-50 text-blue-700 border-blue-200",
  DEBUG: "bg-purple-100 text-purple-700 border-purple-200",
};

const ROLE_COLOR: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  developer: "bg-blue-100 text-blue-700",
  viewer: "bg-gray-100 text-gray-600",
};

/**
 * Read-only "tell me everything" view for one audit-log row. Opened by
 * clicking the truncated details cell in <AuditLogTable />. Keeps the
 * compact table compact while still giving the operator the full record
 * (including normally-hidden fields like User-Agent and NTP source) when
 * they need it for an investigation or evidence export.
 */
export function AuditLogDetailModal({ log, user, onClose }: Props) {
  const { t } = useLang();
  const [copied, setCopied] = useState<string>("");

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  const copy = (value: string, id: string) => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    navigator.clipboard.writeText(value).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(""), 1500);
    });
  };

  const level = log.log_level || "INFO";
  const levelClass = LEVEL_COLOR[level] || LEVEL_COLOR.INFO;
  const username =
    log.username || user?.username || (log.user_id ? `#${log.user_id}` : "—");
  const role = user?.role || "viewer";

  // Pretty-print JSON-looking details
  const detailsPretty = (() => {
    if (!log.details) return "";
    const trimmed = log.details.trim();
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch {}
    }
    return log.details;
  })();

  const Field = ({
    label,
    value,
    copyable,
    valueClass,
    mono,
    fullWidth,
  }: {
    label: string;
    value: React.ReactNode;
    copyable?: string;
    valueClass?: string;
    mono?: boolean;
    fullWidth?: boolean;
  }) => (
    <div className={fullWidth ? "col-span-2" : ""}>
      <div className="flex items-center justify-between gap-2 mb-0.5">
        <p className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">{label}</p>
        {copyable && (
          <button
            type="button"
            onClick={() => copy(copyable, label)}
            className="text-[9px] text-brand-600 hover:text-brand-700 px-1 py-px rounded hover:bg-brand-50"
            title={t("audit_detail.copy")}
          >
            {copied === label ? `✓ ${t("audit_detail.copied")}` : t("audit_detail.copy")}
          </button>
        )}
      </div>
      <div className={cn("text-[11px] text-gray-800", mono && "font-mono", valueClass)}>
        {value || <span className="text-gray-300 italic">—</span>}
      </div>
    </div>
  );

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col pointer-events-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="audit-detail-title"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-brand-600 to-brand-700 px-5 py-3 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div className="min-w-0">
                <h2 id="audit-detail-title" className="text-white font-semibold text-sm">
                  {t("audit_detail.title")} #{log.id}
                </h2>
                <p className="text-brand-100 text-[11px] mt-0.5">{t("audit_detail.subtitle")}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white/70 hover:text-white p-1 flex-shrink-0"
              aria-label={t("audit_detail.close")}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Body */}
          <div className="overflow-y-auto flex-1 p-5 space-y-4">
            {/* Top banner: action + level + time */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "text-[10px] font-bold px-2 py-0.5 rounded border",
                    levelClass
                  )}
                >
                  {level}
                </span>
                <code className="text-xs font-mono bg-white px-2 py-0.5 rounded border border-gray-200 text-gray-800">
                  {log.action}
                </code>
              </div>
              <div className="text-[11px] text-gray-600 font-mono">
                {formatLegalTimestamp(log.created_at)}
              </div>
            </div>

            {/* Field grid */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-3">
              <Field
                label={t("audit_detail.user")}
                value={
                  <span className="flex items-center gap-1.5">
                    <span className="font-medium">{username}</span>
                    {user && (
                      <span
                        className={cn(
                          "text-[9px] px-1.5 py-px rounded-full font-medium",
                          ROLE_COLOR[role] || "bg-gray-100 text-gray-600"
                        )}
                      >
                        {t(`role.${role}`)}
                      </span>
                    )}
                  </span>
                }
              />

              <Field
                label={t("audit_detail.user_id")}
                value={log.user_id ?? "—"}
                mono
              />

              <Field
                label={t("audit_detail.resource")}
                value={
                  <span>
                    <span className="font-medium">{log.resource_type}</span>
                    {log.resource_id && (
                      <span className="text-gray-400 ml-1">#{log.resource_id}</span>
                    )}
                  </span>
                }
              />

              <Field
                label={t("audit_detail.ip_address")}
                value={log.ip_address}
                copyable={log.ip_address || undefined}
                mono
              />

              <Field
                label={t("audit_detail.request_id")}
                value={log.request_id}
                copyable={log.request_id || undefined}
                mono
              />

              <Field
                label={t("audit_detail.session_id")}
                value={log.session_id}
                copyable={log.session_id || undefined}
                mono
              />

              <Field
                label={t("audit_detail.ntp_source")}
                value={log.ntp_server}
                mono
                fullWidth
              />

              <Field
                label={t("audit_detail.user_agent")}
                value={
                  log.user_agent ? (
                    <span className="break-all text-gray-700">{log.user_agent}</span>
                  ) : null
                }
                copyable={log.user_agent || undefined}
                mono
                fullWidth
              />
            </div>

            {/* Details — full text, JSON-prettified if possible */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  {t("audit_detail.details")}
                </p>
                {log.details && (
                  <button
                    type="button"
                    onClick={() => copy(log.details, "details")}
                    className="text-[9px] text-brand-600 hover:text-brand-700 px-1 py-px rounded hover:bg-brand-50"
                  >
                    {copied === "details" ? `✓ ${t("audit_detail.copied")}` : t("audit_detail.copy")}
                  </button>
                )}
              </div>
              <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-[11px] font-mono whitespace-pre-wrap break-words max-h-[300px] overflow-y-auto leading-relaxed">
                {detailsPretty || (
                  <span className="text-gray-500 italic">{t("audit_detail.no_details")}</span>
                )}
              </pre>
            </div>
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-5 py-3 flex items-center justify-between border-t border-gray-200 flex-shrink-0">
            <p className="text-[10px] text-gray-500">
              {t("audit_detail.legal_note")}
            </p>
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition"
            >
              {t("audit_detail.close")}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
