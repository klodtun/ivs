"use client";
import { useEffect, useRef, useState } from "react";
import { useLang } from "@/components/lang-provider";

interface Props {
  /** Visible title — usually describes the action ("Purge expired logs?"). */
  title: string;
  /** Short explanation under the title. */
  description: string;
  /** Items the user is about to lose — rendered as a red bullet list. */
  consequences?: string[];
  /** Optional legal-reference block (e.g. "พ.ร.บ. คอมพิวเตอร์ §26 ..."). */
  legalNote?: string;
  /** Label for the destructive button (e.g. "Purge now"). */
  confirmLabel: string;
  /** Async handler — receives the typed password. Throw to surface an error. */
  onConfirm: (password: string) => Promise<void>;
  onCancel: () => void;
}

/**
 * Modal that re-prompts the caller for their OWN login password before
 * performing a destructive action. Designed for moments where a single
 * click on the underlying page could create legal liability.
 *
 * Why password (not just a typed-keyword like Delete-Modal)?
 *   - It proves the active session belongs to the person clicking, not
 *     someone walking past an unlocked laptop.
 *   - It re-establishes intent immediately before the destructive call.
 *   - Failed attempts are server-side audit-logged for forensics.
 */
export function PasswordConfirmModal({
  title,
  description,
  consequences,
  legalNote,
  confirmLabel,
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useLang();
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onCancel();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onCancel, submitting]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await onConfirm(password);
    } catch (err: any) {
      setError(err?.message || t("password_confirm.error_generic"));
      setSubmitting(false);
      // Clear the password so a wrong-attempt can't sit on screen unmasked
      setPassword("");
      inputRef.current?.focus();
      return;
    }
    setSubmitting(false);
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
        onClick={() => !submitting && onCancel()}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden pointer-events-auto"
          role="dialog"
          aria-modal="true"
          aria-labelledby="pwd-modal-title"
        >
          {/* Red header — destructive action signal */}
          <div className="bg-gradient-to-r from-red-500 to-red-600 px-5 py-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h2 id="pwd-modal-title" className="text-white font-semibold text-base">
                  {title}
                </h2>
                <p className="text-red-100 text-[11px] mt-0.5">
                  {t("password_confirm.subtitle")}
                </p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="p-5 space-y-3">
              {/* Action explanation */}
              <p className="text-[11px] text-gray-700 leading-relaxed">{description}</p>

              {/* Consequences */}
              {consequences && consequences.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-red-700 uppercase tracking-wider mb-1">
                    {t("password_confirm.consequences")}
                  </p>
                  <ul className="space-y-1 text-[11px] text-gray-700 ml-1">
                    {consequences.map((c, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-red-500 font-bold mt-px">•</span>
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Legal callout */}
              {legalNote && (
                <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 flex gap-2">
                  <svg className="w-4 h-4 text-amber-600 flex-shrink-0 mt-px" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <p className="text-[11px] text-amber-800 leading-snug">{legalNote}</p>
                </div>
              )}

              {/* Password input */}
              <div>
                <label className="text-[11px] font-medium text-gray-700 block mb-1.5">
                  {t("password_confirm.label")}
                </label>
                <div className="relative">
                  <input
                    ref={inputRef}
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={submitting}
                    placeholder={t("password_confirm.placeholder")}
                    autoComplete="current-password"
                    className="w-full px-3 py-2 pr-10 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 disabled:bg-gray-50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
                    aria-label={showPassword ? t("password_confirm.hide") : t("password_confirm.show")}
                  >
                    {showPassword ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                </div>
                {error && (
                  <p className="mt-1.5 text-[11px] text-red-600 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </p>
                )}
              </div>

              {/* Forensic notice */}
              <p className="text-[10px] text-gray-500 italic leading-snug">
                {t("password_confirm.forensic_note")}
              </p>
            </div>

            <div className="bg-gray-50 px-5 py-3 flex items-center justify-end gap-2 border-t border-gray-200">
              <button
                type="button"
                onClick={onCancel}
                disabled={submitting}
                className="px-4 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition disabled:opacity-50"
              >
                {t("password_confirm.cancel")}
              </button>
              <button
                type="submit"
                disabled={!password.trim() || submitting}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-red-600 rounded-md hover:bg-red-700 transition disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <>
                    <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {t("password_confirm.working")}
                  </>
                ) : (
                  confirmLabel
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
