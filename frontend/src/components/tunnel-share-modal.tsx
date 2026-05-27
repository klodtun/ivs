"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { formatLegalTimestamp } from "@/lib/utils";

interface Props {
  tunnel: {
    id: number;
    public_url: string;
    expires_at: string;
    app_id: number;
  };
  appName: string;
  onClose: () => void;
}

interface NoticeData {
  app_name: string;
  privacy_notice_enabled: boolean;
  privacy_notice_title: string;
  privacy_notice_detail: string;
  privacy_policy_url: string;
  privacy_notice_url: string;
}

/**
 * Compose-and-send modal for tunnel URLs.
 *
 * A tunnel grants external access to an otherwise internal app — that's
 * exactly the moment where PDPA §19 demands the data subject be informed
 * BEFORE they're given a URL that may collect their personal data. So
 * sharing a tunnel by email shouldn't be a bare link; it should include:
 *
 *   1) The app's Privacy Notice (verbatim from PDPA settings)
 *   2) The tunnel URL + expiry
 *   3) Usage instructions so the recipient knows what to expect
 *   4) Pointers to the organization's privacy policy / full notice
 *
 * This modal builds that message client-side, shows a preview the
 * sender can review, and opens the user's mail client via `mailto:`.
 */
export function TunnelShareModal({ tunnel, appName, onClose }: Props) {
  const { t } = useLang();
  const [notice, setNotice] = useState<NoticeData | null>(null);
  const [recipient, setRecipient] = useState("");
  const [extraNote, setExtraNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.getPrivacyNotice(tunnel.app_id);
        if (!cancelled) setNotice(data);
      } catch {
        // Even if PDPA settings are missing we still send a usable email
        // — just without the notice block. Don't block the share flow.
        if (!cancelled) setNotice(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tunnel.app_id]);

  // Build the message body that becomes the email's plain-text content.
  // Plain text only — mailto: has no MIME format, and many recipients'
  // clients render whatever they get as monospace anyway. We use
  // unicode box-drawing characters for section separators because they
  // survive every mail client we care about.
  const body = (() => {
    const lines: string[] = [];
    lines.push("สวัสดีครับ/ค่ะ,");
    lines.push("");
    lines.push(`ขอเรียนเชิญใช้งานแอปพลิเคชัน "${appName}" ผ่านลิงก์อุโมงค์ชั่วคราว`);
    lines.push("กรุณาอ่านประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล (PDPA) ก่อนเข้าใช้งาน");
    lines.push("");

    // 1) Privacy notice
    if (notice && notice.privacy_notice_enabled) {
      lines.push("═══════════════════════════════════════════");
      lines.push("⚠️  ประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล");
      lines.push("═══════════════════════════════════════════");
      if (notice.privacy_notice_title) {
        lines.push(notice.privacy_notice_title);
        lines.push("");
      }
      if (notice.privacy_notice_detail) {
        lines.push(notice.privacy_notice_detail);
        lines.push("");
      }
      if (notice.privacy_policy_url) {
        lines.push(`📄 นโยบายคุ้มครองข้อมูลส่วนบุคคล: ${notice.privacy_policy_url}`);
      }
      if (notice.privacy_notice_url) {
        lines.push(`📋 ประกาศแจ้งเตือนฉบับเต็ม: ${notice.privacy_notice_url}`);
      }
      lines.push("");
    } else {
      lines.push("(แอปนี้ยังไม่ได้ตั้งค่าประกาศแจ้งเตือน PDPA — แนะนำให้ผู้ดูแลตั้งค่าก่อนเปิดให้บุคคลภายนอก)");
      lines.push("");
    }

    // 2) Tunnel link + expiry
    lines.push("═══════════════════════════════════════════");
    lines.push("🔗  ลิงก์เข้าใช้งาน (Tunnel)");
    lines.push("═══════════════════════════════════════════");
    lines.push(tunnel.public_url);
    lines.push("");
    lines.push(`⏱  ลิงก์นี้จะหมดอายุ: ${formatLegalTimestamp(tunnel.expires_at)}`);
    lines.push("");

    // 3) Usage instructions
    lines.push("═══════════════════════════════════════════");
    lines.push("📖  วิธีใช้งาน");
    lines.push("═══════════════════════════════════════════");
    lines.push("1. คลิกลิงก์ข้างต้นเพื่อเปิดแอป");
    lines.push("2. หากแอปแสดงประกาศแจ้งเตือน PDPA — กรุณาอ่านและพิจารณาก่อนกดยอมรับ");
    lines.push("3. การยอมรับ/ปฏิเสธของท่านจะถูกบันทึกในระบบตาม PDPA §19");
    lines.push("4. ท่านสามารถเปลี่ยนการยอมรับได้ทุกเมื่อโดยกลับมาที่ลิงก์นี้");
    lines.push("");

    // 4) Risk / policy warning
    lines.push("═══════════════════════════════════════════");
    lines.push("🔒  ข้อควรระวังด้านความปลอดภัย");
    lines.push("═══════════════════════════════════════════");
    lines.push("• ลิงก์นี้เป็นการเข้าถึงระบบภายในผ่านเครือข่ายภายนอก");
    lines.push("• มีความเสี่ยงที่ข้อมูลอาจรั่วไหลหากใช้งานไม่เหมาะสม");
    lines.push("• กรุณาใช้งานตามนโยบายของหน่วยงานท่าน");
    lines.push("• หากพบพฤติกรรมผิดปกติ กรุณาแจ้งผู้ดูแลระบบทันที");
    lines.push("");

    if (extraNote.trim()) {
      lines.push("═══════════════════════════════════════════");
      lines.push("💬  หมายเหตุจากผู้ส่ง");
      lines.push("═══════════════════════════════════════════");
      lines.push(extraNote);
      lines.push("");
    }

    lines.push("───────────────────────────────────────────");
    lines.push(`ส่งจาก IVS — Internal Vibe Server`);
    return lines.join("\r\n");
  })();

  const subject = `[IVS Tunnel] ${appName} — ลิงก์เข้าใช้งานพร้อมประกาศ PDPA`;

  const mailtoUrl = `mailto:${encodeURIComponent(recipient)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  const handleOpenMail = () => {
    // Browsers cap mailto: URLs at around 2000 chars on Windows clients.
    // Our body is ~1500-2000 chars depending on the notice — if we go over
    // we still try; worst case some clients truncate. The Copy button is
    // the safety net.
    window.location.href = mailtoUrl;
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(`${subject}\n\n${body}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col pointer-events-auto"
          role="dialog"
          aria-modal="true"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-brand-600 to-brand-700 px-5 py-3 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <span className="text-lg">📧</span>
              </div>
              <div>
                <h2 className="text-white font-semibold text-sm">{t("tunnel.share.title")}</h2>
                <p className="text-brand-100 text-[11px] mt-0.5">{t("tunnel.share.subtitle")}</p>
              </div>
            </div>
            <button onClick={onClose} className="text-white/70 hover:text-white p-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Body */}
          <div className="overflow-y-auto flex-1 p-5 space-y-3">
            {/* Recipient + note inputs */}
            <div className="grid grid-cols-1 gap-2">
              <div>
                <label className="text-[10px] font-medium text-gray-600 block mb-0.5">
                  {t("tunnel.share.recipient")}
                </label>
                <input
                  type="email"
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                  placeholder={t("tunnel.share.recipient_placeholder")}
                  className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                />
                <p className="text-[9px] text-gray-400 mt-0.5">{t("tunnel.share.recipient_hint")}</p>
              </div>
              <div>
                <label className="text-[10px] font-medium text-gray-600 block mb-0.5">
                  {t("tunnel.share.extra_note")}
                </label>
                <textarea
                  value={extraNote}
                  onChange={(e) => setExtraNote(e.target.value)}
                  rows={2}
                  placeholder={t("tunnel.share.extra_note_placeholder")}
                  className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 resize-none"
                />
              </div>
            </div>

            {/* Preview */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                  {t("tunnel.share.preview")}
                </p>
                {loading && <span className="text-[10px] text-gray-400">{t("tunnel.share.loading_notice")}</span>}
              </div>
              <div className="bg-gray-50 border border-gray-200 rounded-md text-[10.5px] leading-relaxed">
                <div className="px-3 py-2 border-b border-gray-200 bg-white">
                  <span className="text-gray-500 mr-1">{t("tunnel.share.subject_label")}:</span>
                  <span className="font-medium text-gray-800">{subject}</span>
                </div>
                <pre className="px-3 py-3 max-h-[280px] overflow-y-auto whitespace-pre-wrap font-mono text-gray-700">
                  {body}
                </pre>
              </div>
            </div>

            {/* Tip */}
            <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 text-[11px] text-amber-800">
              💡 {t("tunnel.share.tip")}
            </div>
          </div>

          {/* Footer */}
          <div className="bg-gray-50 px-5 py-3 flex items-center justify-between border-t border-gray-200 flex-shrink-0">
            <button
              onClick={handleCopy}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border transition ${
                copied
                  ? "bg-green-50 border-green-200 text-green-700"
                  : "bg-white border-gray-300 text-gray-700 hover:bg-gray-100"
              }`}
            >
              {copied ? `✓ ${t("tunnel.share.copied")}` : t("tunnel.share.copy")}
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition"
              >
                {t("tunnel.share.cancel")}
              </button>
              <button
                onClick={handleOpenMail}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-brand-600 rounded-md hover:bg-brand-700 transition"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                {t("tunnel.share.open_mail")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
