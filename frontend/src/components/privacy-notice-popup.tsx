"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { formatLegalTimestamp } from "@/lib/utils";
import { useLang } from "@/components/lang-provider";

interface PrivacyNoticeData {
  app_id: number;
  app_name: string;
  app_slug: string;
  privacy_notice_enabled: boolean;
  privacy_notice_title: string;
  privacy_notice_detail: string;
  privacy_policy_url: string;
  privacy_notice_url: string;
}

interface Props {
  appId?: number;
  appSlug?: string;
  /**
   * "gate"   – the popup blocks app entry until the user accepts; if
   *            they've already accepted, we skip the popup and call
   *            onAccept immediately.
   * "review" – the user explicitly clicked "ดูประกาศแจ้งเตือน" from
   *            the AppCard to review/change their decision. Always
   *            opens, shows current decision, lets them switch.
   */
  mode?: "gate" | "review";
  onAccept: () => void;
  onDecline?: () => void;
  onAlreadyAccepted?: () => void;
  onClose?: () => void;
}

const CONSENT_KEY_PREFIX = "ivs_pn_consent_";

function getCurrentUserId(): string {
  if (typeof window === "undefined") return "unknown";
  try {
    const user = localStorage.getItem("user");
    if (user) {
      const parsed = JSON.parse(user);
      return String(parsed.id || parsed.username || "unknown");
    }
  } catch {}
  return "unknown";
}

function getConsentKey(appId: number): string {
  return `${CONSENT_KEY_PREFIX}${getCurrentUserId()}_${appId}`;
}

function readLocalConsent(appId: number): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(getConsentKey(appId));
  if (!stored) return false;
  try {
    const data = JSON.parse(stored);
    const thirtyDays = 30 * 24 * 60 * 60 * 1000;
    return data.accepted === true && Date.now() - data.timestamp < thirtyDays;
  } catch {
    return false;
  }
}

function writeLocalConsent(appId: number, accepted: boolean) {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    getConsentKey(appId),
    JSON.stringify({ timestamp: Date.now(), accepted })
  );
}

export default function PrivacyNoticePopup({
  appId,
  appSlug,
  mode = "gate",
  onAccept,
  onDecline,
  onAlreadyAccepted,
  onClose,
}: Props) {
  const { t } = useLang();
  const [notice, setNotice] = useState<PrivacyNoticeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [show, setShow] = useState(false);
  const [currentDecision, setCurrentDecision] = useState<"accepted" | "declined" | null>(null);
  const [decisionAt, setDecisionAt] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const loadNotice = async () => {
      try {
        let data: PrivacyNoticeData;
        if (appId) {
          data = await api.getPrivacyNotice(appId);
        } else if (appSlug) {
          data = await api.getPrivacyNoticeBySlug(appSlug);
        } else {
          onAlreadyAccepted?.();
          return;
        }
        if (cancelled) return;

        setNotice(data);

        // Notice disabled → bypass for gate mode, but allow review mode
        // to show "this app doesn't have a privacy notice configured".
        if (!data.privacy_notice_enabled && mode === "gate") {
          onAlreadyAccepted?.();
          onAccept();
          return;
        }

        // Fetch the user's server-side decision (authoritative).
        // Fallback to localStorage if the server call fails.
        let serverDecision: "accepted" | "declined" | null = null;
        let serverCreatedAt: string | null = null;
        try {
          const c = await api.getMyPdpaConsent(data.app_id);
          if (!cancelled) {
            serverDecision = c.decision;
            serverCreatedAt = c.created_at;
            setCurrentDecision(c.decision);
            setDecisionAt(c.created_at);
          }
        } catch {
          // Server unreachable — degrade gracefully to localStorage
          if (readLocalConsent(data.app_id)) {
            serverDecision = "accepted";
          }
          if (!cancelled) setCurrentDecision(serverDecision);
        }

        if (mode === "gate") {
          // If they've already accepted, skip the popup entirely.
          // (A "declined" decision still blocks them — they have to
          // re-engage with the popup to change it.)
          if (serverDecision === "accepted") {
            onAlreadyAccepted?.();
            onAccept();
            return;
          }
          if (!cancelled) setShow(true);
        } else {
          // Review mode — always show, regardless of prior decision
          if (!cancelled) setShow(true);
        }
      } catch {
        // If the whole notice fetch fails, fall through (don't block app entry)
        if (mode === "gate") {
          onAlreadyAccepted?.();
          onAccept();
        } else {
          onClose?.();
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadNotice();
    return () => {
      cancelled = true;
    };
  }, [appId, appSlug, mode]);

  const recordDecision = async (decision: "accepted" | "declined") => {
    if (!notice || submitting) return;
    setSubmitting(true);
    try {
      const res = await api.recordPdpaConsent(notice.app_id, decision);
      writeLocalConsent(notice.app_id, decision === "accepted");
      setCurrentDecision(decision);
      setDecisionAt(res.created_at);
    } catch {
      // Even if server recording fails we still record locally so the
      // user isn't stuck in an infinite popup loop. The server-side
      // audit trail is the legal record though, so log a console hint.
      writeLocalConsent(notice.app_id, decision === "accepted");
      console.warn("Failed to record consent on server; recorded locally only");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAccept = async () => {
    await recordDecision("accepted");
    setShow(false);
    onAccept();
  };

  const handleDecline = async () => {
    await recordDecision("declined");
    setShow(false);
    if (mode === "review") {
      onClose?.();
    } else {
      onDecline?.();
    }
  };

  const handleClose = () => {
    setShow(false);
    onClose?.();
  };

  useEffect(() => {
    if (!show) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (mode === "review") handleClose();
        else handleDecline();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [show, mode]);

  if (loading || !show || !notice) return null;

  const isReview = mode === "review";
  const noticeDisabled = !notice.privacy_notice_enabled;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[9999] backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-[480px] max-w-[90vw] max-h-[85vh] overflow-y-auto animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="px-6 pt-6 pb-3 text-center relative">
          {isReview && (
            <button
              onClick={handleClose}
              className="absolute right-4 top-4 text-gray-400 hover:text-gray-600 p-1"
              aria-label="Close"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <div className="w-14 h-14 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <span className="text-2xl">🛡️</span>
          </div>
          <h2 className="text-base font-bold text-gray-900">
            {notice.privacy_notice_title || t("pn.default_title")}
          </h2>
          <p className="text-[10px] text-gray-400 mt-1">{notice.app_name}</p>
          {isReview && (
            <span className="inline-block mt-2 text-[10px] px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full font-medium">
              {t("pn.review_badge")}
            </span>
          )}
        </div>

        {/* Notice disabled banner (only shown in review mode if the admin turned it off) */}
        {noticeDisabled && (
          <div className="mx-6 mb-2 p-3 bg-gray-50 border border-gray-200 rounded-lg text-[11px] text-gray-600">
            {t("pn.disabled_banner")}
          </div>
        )}

        {/* Current decision banner (review mode only) */}
        {isReview && currentDecision && (
          <div
            className={`mx-6 mb-2 p-3 rounded-lg border ${
              currentDecision === "accepted"
                ? "bg-green-50 border-green-200"
                : "bg-red-50 border-red-200"
            }`}
          >
            <p className={`text-[11px] font-semibold ${
              currentDecision === "accepted" ? "text-green-800" : "text-red-800"
            }`}>
              {t("pn.current_status")}: {currentDecision === "accepted" ? t("pn.status_accepted") : t("pn.status_declined")}
            </p>
            {decisionAt && (
              <p className="text-[10px] text-gray-500 mt-0.5 font-mono">
                {t("pn.recorded_at")}: {formatLegalTimestamp(decisionAt)}
              </p>
            )}
          </div>
        )}

        {/* Body */}
        <div className="px-6 py-3">
          <div className="bg-gray-50 rounded-lg p-4 text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
            {notice.privacy_notice_detail || t("pn.default_detail")}
          </div>

          {(notice.privacy_policy_url || notice.privacy_notice_url) && (
            <div className="mt-3 flex flex-wrap gap-3 justify-center">
              {notice.privacy_policy_url && (
                <a
                  href={notice.privacy_policy_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
                >
                  📄 {t("pn.link_policy")}
                  <span className="text-[9px]">↗</span>
                </a>
              )}
              {notice.privacy_notice_url && (
                <a
                  href={notice.privacy_notice_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
                >
                  📋 {t("pn.link_full_notice")}
                  <span className="text-[9px]">↗</span>
                </a>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 pt-3">
          {/* In review mode, show buttons matching the user's current choice differently */}
          {isReview ? (
            <>
              <button
                onClick={handleAccept}
                disabled={submitting || currentDecision === "accepted"}
                className="w-full py-2.5 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 transition shadow-md disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {currentDecision === "accepted" ? t("pn.accept_current") : t("pn.switch_to_accept")}
              </button>
              <button
                onClick={handleDecline}
                disabled={submitting || currentDecision === "declined"}
                className="w-full py-2 mt-2 bg-red-50 text-red-700 border border-red-200 text-sm font-medium rounded-lg hover:bg-red-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {currentDecision === "declined" ? t("pn.decline_current") : t("pn.switch_to_decline")}
              </button>
              <button
                onClick={handleClose}
                className="w-full py-2 mt-2 text-xs text-gray-500 hover:text-gray-700 rounded-lg transition"
              >
                {t("pn.close")}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleAccept}
                disabled={submitting}
                className="w-full py-2.5 bg-purple-600 text-white text-sm font-semibold rounded-lg hover:bg-purple-700 transition shadow-md disabled:opacity-50"
              >
                {submitting ? t("pn.saving") : t("pn.accept_and_enter")}
              </button>
              <button
                onClick={handleDecline}
                disabled={submitting}
                className="w-full py-2 mt-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition disabled:opacity-50"
              >
                {t("pn.decline")}
              </button>
            </>
          )}
          <p className="text-[9px] text-gray-400 text-center mt-2">
            {t("pn.legal_footer")}
          </p>
        </div>
      </div>
    </div>
  );
}
