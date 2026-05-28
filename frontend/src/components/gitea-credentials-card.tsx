"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

export function GiteaCredentialsCard() {
  const { t } = useLang();
  const [creds, setCreds] = useState<{ username: string; password: string; is_default: boolean } | null>(null);
  const [editing, setEditing] = useState(false);
  const [editUser, setEditUser] = useState("");
  const [editPass, setEditPass] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  useEffect(() => {
    api.getGiteaCredentials().then(setCreds).catch(() => setCreds(null));
  }, []);

  const startEdit = () => {
    if (!creds) return;
    setEditUser(creds.username);
    setEditPass(creds.password);
    setError("");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setError("");
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const updated = await api.updateGiteaCredentials(editUser.trim(), editPass);
      setCreds(updated);
      setEditing(false);
    } catch (e: any) {
      setError(e?.message || t("gitea.creds.save_failed"));
    } finally {
      setSaving(false);
    }
  };

  const copy = (value: string, id: string) => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    navigator.clipboard.writeText(value).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(""), 1500);
    });
  };

  if (!creds) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-3 text-[10px] text-gray-400">
        {t("gitea.creds.loading")}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-xs font-semibold text-gray-900 flex items-center gap-1.5">
            🔑 {t("gitea.creds.title")}
          </h4>
          <p className="text-[10px] text-gray-500 mt-0.5">{t("gitea.creds.subtitle")}</p>
        </div>
        {!editing && (
          <button
            onClick={startEdit}
            className="px-2.5 py-1 text-[10px] font-medium text-brand-600 bg-brand-50 border border-brand-200 rounded-md hover:bg-brand-100 transition flex-shrink-0"
          >
            {t("gitea.creds.edit")}
          </button>
        )}
      </div>

      {/* Default credentials warning */}
      {creds.is_default && !editing && (
        <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 flex gap-2">
          <svg className="w-4 h-4 text-amber-600 flex-shrink-0 mt-px" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <p className="text-[11px] text-amber-800 leading-snug">{t("gitea.creds.default_warning")}</p>
        </div>
      )}

      {editing ? (
        <div className="space-y-2.5">
          <div>
            <label className="text-[10px] font-medium text-gray-600 block mb-1">
              {t("gitea.creds.username")}
            </label>
            <input
              type="text"
              value={editUser}
              onChange={(e) => setEditUser(e.target.value)}
              autoComplete="username"
              className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p className="text-[9px] text-gray-400 mt-0.5">{t("gitea.creds.username_hint")}</p>
          </div>

          <div>
            <label className="text-[10px] font-medium text-gray-600 block mb-1">
              {t("gitea.creds.password")}
            </label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                value={editPass}
                onChange={(e) => setEditPass(e.target.value)}
                autoComplete="new-password"
                className="w-full px-2.5 py-1.5 pr-9 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
              />
              <button
                type="button"
                onClick={() => setShowPass((v) => !v)}
                tabIndex={-1}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPass ? "🙈" : "👁"}
              </button>
            </div>
            <p className="text-[9px] text-gray-400 mt-0.5">{t("gitea.creds.password_hint")}</p>
          </div>

          {error && (
            <div className="text-[10px] text-red-600 bg-red-50 border border-red-200 rounded p-1.5">
              ⚠ {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              onClick={cancelEdit}
              disabled={saving}
              className="px-3 py-1 text-[10px] text-gray-600 hover:text-gray-800"
            >
              {t("gitea.creds.cancel")}
            </button>
            <button
              onClick={save}
              disabled={saving || !editUser.trim() || !editPass}
              className="px-3 py-1 text-[10px] font-semibold text-white bg-brand-600 rounded-md hover:bg-brand-700 disabled:bg-gray-300"
            >
              {saving ? t("gitea.creds.saving") : t("gitea.creds.save")}
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {/* Username */}
          <div className="bg-gray-50 border border-gray-200 rounded-md p-2.5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">
                {t("gitea.creds.username")}
              </span>
              <button
                onClick={() => copy(creds.username, "user")}
                className="text-[9px] text-brand-600 hover:text-brand-700 px-1 py-px rounded hover:bg-brand-50"
              >
                {copied === "user" ? `✓ ${t("gitea.creds.copied")}` : t("gitea.creds.copy")}
              </button>
            </div>
            <code className="text-xs font-mono font-semibold text-gray-900 break-all">
              {creds.username}
            </code>
          </div>

          {/* Password */}
          <div className="bg-gray-50 border border-gray-200 rounded-md p-2.5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-semibold text-gray-500 uppercase tracking-wider">
                {t("gitea.creds.password")}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setShowPass((v) => !v)}
                  className="text-[9px] text-gray-500 hover:text-gray-700 px-1 py-px rounded hover:bg-gray-100"
                >
                  {showPass ? `🙈 ${t("gitea.creds.hide")}` : `👁 ${t("gitea.creds.show")}`}
                </button>
                <button
                  onClick={() => copy(creds.password, "pass")}
                  className="text-[9px] text-brand-600 hover:text-brand-700 px-1 py-px rounded hover:bg-brand-50"
                >
                  {copied === "pass" ? `✓ ${t("gitea.creds.copied")}` : t("gitea.creds.copy")}
                </button>
              </div>
            </div>
            <code className="text-xs font-mono font-semibold text-gray-900 break-all">
              {showPass ? creds.password : "••••••••••••"}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}
