"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { LangToggle } from "@/components/lang-toggle";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useLang();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showDefaultHint, setShowDefaultHint] = useState(false);
  const [isLastAdmin, setIsLastAdmin] = useState(false);
  const [failedCount, setFailedCount] = useState(0);
  const [resetConfirm, setResetConfirm] = useState(false);
  const [resetWorking, setResetWorking] = useState(false);
  const [resetMessage, setResetMessage] = useState("");
  const [shutdownOpen, setShutdownOpen] = useState(false);
  const [shutdownUser, setShutdownUser] = useState("");
  const [shutdownPass, setShutdownPass] = useState("");
  const [shutdownBusy, setShutdownBusy] = useState(false);
  const [shutdownErr, setShutdownErr] = useState("");

  const FAILED_KEY = "ivs_login_failed";
  const FAILED_THRESHOLD = 10;

  // Show the default admin hint only while the seeded admin account
  // still exists. Once an admin deletes it (after creating a real admin
  // user), the hint disappears for everyone on the next page load.
  useEffect(() => {
    api.hasDefaultAdmin()
      .then((r) => setShowDefaultHint(!!r.exists))
      .catch(() => setShowDefaultHint(false));
    api.adminCount()
      .then((r) => setIsLastAdmin(r.count === 1))
      .catch(() => setIsLastAdmin(false));
    // Persist failed-login counter across page reloads so the recovery
    // button is gated by accumulated mistakes, not just the current session.
    if (typeof window !== "undefined") {
      const stored = parseInt(localStorage.getItem(FAILED_KEY) || "0", 10);
      setFailedCount(Number.isFinite(stored) ? stored : 0);
    }
  }, []);

  const showRecovery = isLastAdmin && failedCount >= FAILED_THRESHOLD;

  const handleShutdown = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shutdownUser || !shutdownPass) return;
    setShutdownBusy(true);
    setShutdownErr("");
    try {
      // Login first to obtain admin token (endpoint is admin-only)
      const r = await api.login(shutdownUser, shutdownPass);
      localStorage.setItem("token", r.access_token);
      const me = await api.getMe();
      if (me.role !== "admin") {
        throw new Error(t("login.shutdown_admin_only"));
      }
      await api.shutdownIvs();
      // Backend kills both ports 2s after returning
      setTimeout(() => {
        try { window.close(); } catch {}
        try { window.location.href = "about:blank"; } catch {}
      }, 2500);
      setShutdownErr(t("login.shutdown_started"));
    } catch (err: any) {
      setShutdownErr(err?.message || t("login.shutdown_failed"));
      localStorage.removeItem("token");
    } finally {
      setShutdownBusy(false);
    }
  };

  const handleFactoryReset = async () => {
    if (!resetConfirm) {
      setResetConfirm(true);
      return;
    }
    setResetWorking(true);
    setResetMessage("");
    try {
      await api.factoryResetLastAdmin();
      setResetMessage(t("login.reset_done"));
      setShowDefaultHint(true);
      setIsLastAdmin(false);
      setResetConfirm(false);
      setUsername("admin");
      setPassword("admin123");
      // Clear failure counter so the recovery prompt doesn't show
      // again immediately after a successful reset.
      localStorage.removeItem(FAILED_KEY);
      setFailedCount(0);
    } catch (e: any) {
      setResetMessage(e?.message || t("login.reset_failed"));
    } finally {
      setResetWorking(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(username, password);
      localStorage.setItem("token", res.access_token);
      const user = await api.getMe();
      localStorage.setItem("user", JSON.stringify(user));
      // Reset failure counter on successful login
      localStorage.removeItem(FAILED_KEY);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Login failed");
      // Increment persistent failed-attempt counter (gates the
      // last-admin recovery button — appears after 10 mistakes).
      if (typeof window !== "undefined") {
        const next = failedCount + 1;
        setFailedCount(next);
        try { localStorage.setItem(FAILED_KEY, String(next)); } catch {}
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-brand-50 via-white to-brand-100 py-8">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-lg p-6 border border-brand-100">
          <div className="flex justify-end mb-2">
            <LangToggle />
          </div>
          <div className="text-center mb-5">
            {/* Logo enlarged 200% (was w-12 h-12) */}
            <img src="/ivs-logo.png" alt="iVS" className="w-24 h-24 mx-auto mb-3 object-contain" />
            <h1 className="text-lg font-bold text-gray-900">
              {t("login.title")}
            </h1>
            <p className="text-gray-500 mt-0.5 text-xs">
              {t("login.subtitle")}
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-3">
            {error && (
              <div className="bg-red-50 text-red-600 text-xs px-3 py-2 rounded-lg border border-red-200">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-0.5">
                {t("login.username")}
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none transition"
                placeholder={t("login.username_placeholder")}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-0.5">
                {t("login.password")}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none transition"
                placeholder={t("login.password_placeholder")}
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-1.5 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 focus:ring-4 focus:ring-brand-200 transition disabled:opacity-50"
            >
              {loading ? t("login.signing_in") : t("login.submit")}
            </button>
          </form>

          {showDefaultHint && (
            <div className="text-center mt-4">
              <p className="text-[10px] text-gray-400">
                {t("login.default")}
              </p>
              {/* 50% smaller hint — disappears once default admin is deleted */}
              <p className="text-[5px] text-gray-400 mt-0.5 leading-tight">
                {t("login.default_disappears_note")}
              </p>
            </div>
          )}

          {showRecovery && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              {!resetConfirm ? (
                <button
                  type="button"
                  onClick={handleFactoryReset}
                  className="w-full text-[10px] text-gray-400 hover:text-red-600 transition py-1"
                >
                  {t("login.reset_link")}
                </button>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-lg p-2.5 space-y-2">
                  <p className="text-[10px] text-red-700 leading-snug">
                    {t("login.reset_confirm")}
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => { setResetConfirm(false); setResetMessage(""); }}
                      disabled={resetWorking}
                      className="flex-1 text-[10px] py-1.5 bg-white text-gray-700 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                    >
                      {t("login.reset_cancel")}
                    </button>
                    <button
                      type="button"
                      onClick={handleFactoryReset}
                      disabled={resetWorking}
                      className="flex-1 text-[10px] py-1.5 bg-red-600 text-white font-semibold rounded hover:bg-red-700 disabled:opacity-50"
                    >
                      {resetWorking ? t("login.reset_working") : t("login.reset_confirm_btn")}
                    </button>
                  </div>
                </div>
              )}
              {resetMessage && (
                <p className="mt-2 text-[10px] text-green-700 text-center">{resetMessage}</p>
              )}
            </div>
          )}

          {/* Shutdown IVS — toggle expanded form. Requires admin credentials
              because the underlying endpoint is admin-only. */}
          <div className="mt-3 pt-2 border-t border-gray-100">
            {!shutdownOpen ? (
              <button
                type="button"
                onClick={() => setShutdownOpen(true)}
                className="w-full text-[10px] text-gray-400 hover:text-red-600 transition py-1"
              >
                ⏻ {t("login.shutdown")}
              </button>
            ) : (
              <form onSubmit={handleShutdown} className="bg-red-50 border border-red-200 rounded-lg p-2.5 space-y-2">
                <p className="text-[10px] text-red-700 leading-snug">
                  {t("login.shutdown_desc")}
                </p>
                <input
                  type="text"
                  value={shutdownUser}
                  onChange={(e) => setShutdownUser(e.target.value)}
                  placeholder={t("login.username")}
                  autoComplete="username"
                  className="w-full px-2 py-1 text-[11px] border border-red-300 rounded outline-none focus:ring-2 focus:ring-red-300"
                />
                <input
                  type="password"
                  value={shutdownPass}
                  onChange={(e) => setShutdownPass(e.target.value)}
                  placeholder={t("login.password")}
                  autoComplete="current-password"
                  className="w-full px-2 py-1 text-[11px] border border-red-300 rounded outline-none focus:ring-2 focus:ring-red-300"
                />
                {shutdownErr && (
                  <p className="text-[10px] text-red-700">{shutdownErr}</p>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => { setShutdownOpen(false); setShutdownErr(""); setShutdownUser(""); setShutdownPass(""); }}
                    disabled={shutdownBusy}
                    className="flex-1 text-[10px] py-1.5 bg-white text-gray-700 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                  >
                    {t("login.reset_cancel")}
                  </button>
                  <button
                    type="submit"
                    disabled={shutdownBusy || !shutdownUser || !shutdownPass}
                    className="flex-1 text-[10px] py-1.5 bg-red-600 text-white font-semibold rounded hover:bg-red-700 disabled:opacity-50"
                  >
                    {shutdownBusy ? `⏻ ${t("login.shutdown_working")}` : `⏻ ${t("login.shutdown_confirm")}`}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
        <LoginFooter t={t} />
      </div>
    </div>
  );
}

function LoginFooter({ t }: { t: (k: string) => string }) {
  const [version, setVersion] = useState<{ version: string; edition: string } | null>(null);
  useEffect(() => {
    fetch("/api/system/version")
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setVersion({ version: d.version, edition: d.edition }))
      .catch(() => {});
  }, []);
  return (
    <div className="mt-4 text-center text-[10px] text-gray-400 leading-relaxed select-none">
      {version && (
        <div className="text-gray-500 font-medium mb-1">
          iVS v{version.version} · {version.edition} Edition
        </div>
      )}
      © 2026 IVS Project · {t("copyright.all_rights")}<br />
      {t("copyright.eula_notice")}
    </div>
  );
}
