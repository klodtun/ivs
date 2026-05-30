"use client";
import { cn, formatDateTime } from "@/lib/utils";
import { useLang } from "@/components/lang-provider";
import { App } from "@/types";
import { api } from "@/lib/api";
import { useState } from "react";
import PrivacyNoticePopup from "@/components/privacy-notice-popup";
import { DeleteAppModal } from "@/components/delete-app-modal";
import { ExportAppModal } from "@/components/export-app-modal";

const typeColors: Record<string, string> = {
  nodejs: "bg-green-100 text-green-700",
  python: "bg-yellow-100 text-yellow-700",
  fullstack: "bg-purple-100 text-purple-700",
  static: "bg-blue-100 text-blue-700",
  unknown: "bg-gray-100 text-gray-600",
};

export function AppCard({
  app,
  userRole,
  userId,
  onRefresh,
}: {
  app: App;
  userRole: string;
  /** Current user's id — used to enforce the "only deployer can export" rule. */
  userId?: number;
  onRefresh: () => void;
}) {
  const { t } = useLang();
  const [loading, setLoading] = useState("");
  const [showPrivacyNotice, setShowPrivacyNotice] = useState(false);
  const [showPrivacyReview, setShowPrivacyReview] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const canManage = userRole === "admin" || userRole === "developer";
  // Copyright protection: only the original deployer of an app can export
  // its source + data. Admins are deliberately not granted an override.
  // Current owner can always export. Admins also get export rights so
  // backup/migration still works after the original deployer is deleted.
  const canExport =
    (userId !== undefined && app.owner_id === userId) || userRole === "admin";

  const appUrl = app.port
    ? `http://${typeof window !== "undefined" ? window.location.hostname : "localhost"}:${app.port}`
    : null;

  const handleOpenApp = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowPrivacyNotice(true);
  };

  const handlePrivacyAccepted = () => {
    setShowPrivacyNotice(false);
    if (appUrl) window.open(appUrl, "_blank");
  };

  const statusKey = `app.status.${app.status}` as string;
  const statusDot: Record<string, string> = {
    running: "bg-green-500",
    stopped: "bg-gray-400",
    building: "bg-yellow-500",
    error: "bg-red-500",
  };
  const statusColor: Record<string, string> = {
    running: "text-green-600",
    stopped: "text-gray-500",
    building: "text-yellow-600",
    error: "text-red-600",
  };

  const action = async (fn: () => Promise<any>, name: string) => {
    setLoading(name);
    try {
      await fn();
      onRefresh();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setLoading("");
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-3 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className={cn("w-2 h-2 rounded-full flex-shrink-0", statusDot[app.status] || "bg-gray-400", app.status === "running" && "animate-pulse")} />
          <h3 className="font-semibold text-gray-900 text-xs">{app.name}</h3>
        </div>
        <span className={cn("text-[9px] px-1.5 py-px rounded-full font-medium", typeColors[app.app_type] || typeColors.unknown)}>
          {app.app_type}
        </span>
      </div>

      {app.description && (
        <p className="text-[10px] text-gray-500 mb-2 line-clamp-2">{app.description}</p>
      )}

      {appUrl && (
        <div className="flex items-center justify-between mb-2 gap-2">
          <a href={appUrl} onClick={handleOpenApp}
            className="inline-flex items-center gap-1 text-[10px] text-brand-600 hover:text-brand-700">
            <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            {typeof window !== "undefined" ? window.location.hostname : "localhost"}:{app.port}
          </a>
          {/*
            Privacy-notice review link — clicking opens the popup in
            "review" mode so the user can see their current accept/decline
            decision and switch it whenever they want (PDPA §19 — withdraw
            must be as easy as consent).
          */}
          <button
            type="button"
            onClick={() => setShowPrivacyReview(true)}
            title={t("app.privacy_review_tooltip")}
            className="inline-flex items-center gap-0.5 text-[10px] text-gray-500 hover:text-purple-700 transition"
          >
            <span className="text-xs leading-none">🛡️</span>
            <span className="hidden sm:inline">{t("app.privacy_review")}</span>
          </button>
        </div>
      )}

      <div className="flex items-center justify-between text-[9px] text-gray-400 mb-2">
        <span className={cn("font-medium", statusColor[app.status])}>{t(statusKey)}</span>
        <span>v{app.current_version}</span>
        <span>{formatDateTime(app.created_at)}</span>
      </div>

      {canManage && (
        <div className="flex gap-1.5 pt-2 border-t border-gray-100">
          {app.status === "stopped" ? (
            <button onClick={() => action(() => api.startApp(app.id), "start")} disabled={!!loading}
              className="flex-1 text-[10px] py-1 bg-green-50 text-green-700 rounded-md hover:bg-green-100 transition disabled:opacity-50">
              {loading === "start" ? "..." : t("app.start")}
            </button>
          ) : (
            <button onClick={() => action(() => api.stopApp(app.id), "stop")} disabled={!!loading}
              className="flex-1 text-[10px] py-1 bg-gray-50 text-gray-600 rounded-md hover:bg-gray-100 transition disabled:opacity-50">
              {loading === "stop" ? "..." : t("app.stop")}
            </button>
          )}
          <button onClick={() => action(() => api.restartApp(app.id), "restart")} disabled={!!loading}
            className="flex-1 text-[10px] py-1 bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition disabled:opacity-50">
            {loading === "restart" ? "..." : t("app.restart")}
          </button>
          {canExport ? (
            <button
              onClick={() => setShowExportModal(true)}
              disabled={!!loading}
              title={t("app.export_tooltip")}
              className="inline-flex items-center text-[10px] py-1 px-2 bg-brand-50 text-brand-700 rounded-md hover:bg-brand-100 transition disabled:opacity-50"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span className="ml-1 hidden sm:inline">{t("app.export")}</span>
            </button>
          ) : (
            // Non-owners still see the affordance, but disabled with a
            // tooltip explaining why — clearer than silently hiding it.
            <button
              type="button"
              disabled
              title={t("app.export_owner_only_tooltip")}
              className="inline-flex items-center text-[10px] py-1 px-2 bg-gray-100 text-gray-400 rounded-md cursor-not-allowed"
              aria-disabled="true"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              <span className="ml-1 hidden sm:inline">{t("app.export")}</span>
            </button>
          )}
          {userRole === "admin" && (
            <button onClick={() => setShowDeleteModal(true)}
              disabled={!!loading}
              className="text-[10px] py-1 px-2 bg-red-50 text-red-600 rounded-md hover:bg-red-100 transition disabled:opacity-50">
              {loading === "delete" ? "..." : t("app.delete")}
            </button>
          )}
        </div>
      )}

      {/* Privacy Notice Popup — gate mode (blocks app entry) */}
      {showPrivacyNotice && (
        <PrivacyNoticePopup
          appId={app.id}
          mode="gate"
          onAccept={handlePrivacyAccepted}
          onDecline={() => setShowPrivacyNotice(false)}
          onAlreadyAccepted={() => setShowPrivacyNotice(false)}
        />
      )}

      {/* Privacy Notice Popup — review mode (user explicitly clicked
          the 🛡️ link to view / change their decision) */}
      {showPrivacyReview && (
        <PrivacyNoticePopup
          appId={app.id}
          mode="review"
          onAccept={() => setShowPrivacyReview(false)}
          onClose={() => setShowPrivacyReview(false)}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <DeleteAppModal
          app={app}
          onCancel={() => setShowDeleteModal(false)}
          onConfirm={async () => {
            await action(() => api.deleteApp(app.id), "delete");
            setShowDeleteModal(false);
          }}
          // Only suggest "Export first" if the user is allowed to export
          // (i.e. they're the original deployer). Otherwise the button would
          // dead-end at a 403.
          onExportFirst={
            canExport
              ? () => {
                  setShowDeleteModal(false);
                  setShowExportModal(true);
                }
              : undefined
          }
        />
      )}

      {/* Export Modal */}
      {showExportModal && (
        <ExportAppModal app={app} onClose={() => setShowExportModal(false)} />
      )}
    </div>
  );
}
