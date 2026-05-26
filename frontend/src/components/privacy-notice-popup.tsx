"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

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
  onAccept: () => void;
  onDecline?: () => void;
  onAlreadyAccepted?: () => void;
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
  const userId = getCurrentUserId();
  return `${CONSENT_KEY_PREFIX}${userId}_${appId}`;
}

function hasConsent(appId: number): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(getConsentKey(appId));
  if (!stored) return false;
  try {
    const data = JSON.parse(stored);
    // Consent valid for 30 days
    const thirtyDays = 30 * 24 * 60 * 60 * 1000;
    return Date.now() - data.timestamp < thirtyDays;
  } catch {
    return false;
  }
}

function setConsent(appId: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    getConsentKey(appId),
    JSON.stringify({ timestamp: Date.now(), accepted: true })
  );
}

export default function PrivacyNoticePopup({ appId, appSlug, onAccept, onDecline, onAlreadyAccepted }: Props) {
  const [notice, setNotice] = useState<PrivacyNoticeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [show, setShow] = useState(false);

  useEffect(() => {
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

        setNotice(data);

        if (!data.privacy_notice_enabled) {
          // Privacy Notice disabled — proceed directly
          onAlreadyAccepted?.();
          onAccept();
          return;
        }

        // Check if user already accepted
        if (hasConsent(data.app_id)) {
          onAlreadyAccepted?.();
          onAccept();
          return;
        }

        // Show the popup
        setShow(true);
      } catch {
        // If API fails, proceed anyway
        onAlreadyAccepted?.();
        onAccept();
      } finally {
        setLoading(false);
      }
    };

    loadNotice();
  }, [appId, appSlug]);

  const handleAccept = () => {
    if (notice) {
      setConsent(notice.app_id);
    }
    setShow(false);
    onAccept();
  };

  const handleDecline = () => {
    setShow(false);
    onDecline?.();
  };

  // Escape key handler
  useEffect(() => {
    if (!show) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleDecline();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [show]);

  if (loading || !show || !notice) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[9999] backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-[480px] max-w-[90vw] max-h-[85vh] overflow-y-auto animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="px-6 pt-6 pb-3 text-center">
          <div className="w-14 h-14 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <span className="text-2xl">🛡️</span>
          </div>
          <h2 className="text-base font-bold text-gray-900">
            {notice.privacy_notice_title || "ประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล"}
          </h2>
          <p className="text-[10px] text-gray-400 mt-1">{notice.app_name}</p>
        </div>

        {/* Body */}
        <div className="px-6 py-3">
          <div className="bg-gray-50 rounded-lg p-4 text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
            {notice.privacy_notice_detail || "แอปพลิเคชันนี้มีการเก็บรวบรวม ใช้ หรือเปิดเผยข้อมูลส่วนบุคคลของท่าน"}
          </div>

          {/* Links */}
          {(notice.privacy_policy_url || notice.privacy_notice_url) && (
            <div className="mt-3 flex flex-wrap gap-3 justify-center">
              {notice.privacy_policy_url && (
                <a
                  href={notice.privacy_policy_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
                >
                  📄 นโยบายคุ้มครองข้อมูลส่วนบุคคล (Privacy Policy)
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
                  📋 ประกาศแจ้งเตือนฉบับเต็ม
                  <span className="text-[9px]">↗</span>
                </a>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 pb-6 pt-3">
          <button
            onClick={handleAccept}
            className="w-full py-2.5 bg-purple-600 text-white text-sm font-semibold rounded-lg hover:bg-purple-700 transition shadow-md hover:shadow-lg"
          >
            ยอมรับและเข้าใช้งาน
          </button>
          <button
            onClick={handleDecline}
            className="w-full py-2 mt-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition"
          >
            ปฏิเสธ
          </button>
          <p className="text-[9px] text-gray-400 text-center mt-2">
            ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 (PDPA)
          </p>
        </div>
      </div>
    </div>
  );
}
