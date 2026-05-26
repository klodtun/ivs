"use client";
import { useState } from "react";
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

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(username, password);
      localStorage.setItem("token", res.access_token);
      const user = await api.getMe();
      localStorage.setItem("user", JSON.stringify(user));
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 via-white to-brand-100">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-xl shadow-lg p-6 border border-brand-100">
          <div className="flex justify-end mb-2">
            <LangToggle />
          </div>
          <div className="text-center mb-5">
            <img src="/ivs-logo.png" alt="IVS" className="w-12 h-12 mx-auto mb-3 object-contain" />
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

          <p className="text-center text-[10px] text-gray-400 mt-4">
            {t("login.default")}
          </p>
        </div>
      </div>
    </div>
  );
}
