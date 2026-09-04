"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { App } from "@/types";

type Token = {
  id: number;
  prefix: string;
  label: string;
  caller_kind: string;
  caller_name: string;
  target_app_id: number;
  target_app_name: string;
  scope: "read" | "write";
  allowed_paths: string[];
  expires_at: string | null;
  revoked_at: string | null;
  rate_limit_per_hour: number;
  use_count: number;
  last_used_at: string | null;
  state: "active" | "expired" | "revoked";
};

const KIND_ICON: Record<string, string>= { app: "", external: "", ai: "" };

/**
 * Credentials that let one system call an app's API through iVS.
 *
 * The plaintext exists once, in the response to issuing it. That shapes the
 * whole screen: the new token is shown in a panel that has to be dismissed
 * deliberately, with a copy button, rather than a toast that can vanish while
 * someone is looking elsewhere.
 */
export function ExchangeTokenView() {
  const { t } = useLang();
  const [apps, setApps] = useState<App[]>([]);
  const [appId, setAppId] = useState<number | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [issued, setIssued] = useState<{ token: string; scope: string; caller: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState<number | null>(null);
  // Endpoints the API catalog already discovered for the target app, so the
  // paths can be picked instead of remembered.
  const [catalog, setCatalog] = useState<{ app_id: number | null; method: string; path: string }[]>([]);
  const [pathChips, setPathChips] = useState<string[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState("");
  // ทดลองเรียกจริงผ่าน gateway — ผู้ตรวจต้องเห็นว่าโทเคนทำอะไรได้จริง
  // ไม่ใช่เชื่อจากรายการสิทธิ์ที่พิมพ์ไว้
  const [tryToken, setTryToken] = useState("");
  const [tryMethod, setTryMethod] = useState("GET");
  const [tryPath, setTryPath] = useState("/health");
  const [tryResult, setTryResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [trying, setTrying] = useState(false);

  const [form, setForm] = useState({
    caller_name: "",
    caller_kind: "app",
    scope: "read" as "read" | "write",
    paths: "",
    ttl_hours: "",
    rate_limit_per_hour: "1000",
    label: "",
  });

  useEffect(() => {
    api.getApps()
      .then((list) => {
        setApps(list);
        if (list.length && appId === null) setAppId(list[0].id);
      })
      .catch((e: any) => setError(e.message));
    // Not fatal if it fails — the paths can still be typed.
    loadCatalog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(async () => {
    if (appId === null) return;
    setLoading(true);
    setError("");
    try {
      const r = await api.listExchangeTokens(appId);
      setTokens(r.tokens);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [appId]);

  useEffect(() => { load(); }, [load]);

  const loadCatalog = useCallback(async () => {
    try {
      const rows = await api.listCatalog();
      setCatalog(rows.map((r: any) => ({ app_id: r.app_id, method: r.method, path: r.path })));
    } catch {
      setCatalog([]);
    }
  }, []);

  /**
   * Discover this app's endpoints without leaving the form.
   *
   * The scan covers every running app, which is what the catalog endpoint
   * does — but the count reported back is for this app only, since that is the
   * question the user is actually asking here.
   */
  const scanNow = async () => {
    setScanning(true);
    setScanResult("");
    setError("");
    try {
      await api.scanCatalog();
      const rows = await api.listCatalog();
      setCatalog(rows.map((r: any) => ({ app_id: r.app_id, method: r.method, path: r.path })));
      const mine = rows.filter((r: any) => r.app_id === appId).length;
      setScanResult(
        mine > 0
          ? t("xt.scan_found").replace("{n}", String(mine))
          : t("xt.scan_none")
      );
      // The scan runs against every app and holds the backend while it does,
      // so a token list requested mid-scan can come back empty or fail. Reload
      // it once the scan is done rather than leaving the screen claiming this
      // app has no tokens.
      await load();
      setError("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  const create = async () => {
    if (appId === null || !form.caller_name.trim()) return;
    setLoading(true);
    setError("");
    try {
      const typed = form.paths.split(",").map((p) => p.trim()).filter(Boolean);
      const paths = Array.from(new Set([...pathChips, ...typed]));
      const r = await api.createExchangeToken(appId, {
        caller_name: form.caller_name.trim(),
        caller_kind: form.caller_kind,
        scope: form.scope,
        allowed_paths: paths.length ? paths : ["*"],
        ttl_hours: form.ttl_hours ? Number(form.ttl_hours) : null,
        rate_limit_per_hour: Number(form.rate_limit_per_hour) || 1000,
        label: form.label.trim(),
      });
      setIssued({ token: r.token, scope: r.scope, caller: r.caller_name });
      setCopied(false);
      setShowForm(false);
      setForm({ ...form, caller_name: "", paths: "", label: "", ttl_hours: "" });
      setPathChips([]);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const revoke = async (id: number) => {
    setLoading(true);
    try {
      await api.revokeExchangeToken(id);
      setConfirmRevoke(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const tryCall = async () => {
    if (!tryToken.trim() || appId === null) return;
    setTrying(true);
    setTryResult(null);
    try {
      const r = await api.verifyExchangeToken(tryToken.trim(), tryMethod, tryPath.trim() || "/");
      if (!r.allowed) {
        setTryResult({ ok: false, text: r.reason });
      } else {
        // Allowed is only half the answer. Make the real call so the reviewer
        // sees the response the caller would get, with the field rules already
        // applied — that is what "opening this API" actually discloses.
        const app = apps.find((a) => a.id === appId);
        const res = await fetch(
          `/api/exchange/call/${app?.slug || appId}${tryPath.trim() || "/"}`,
          { method: tryMethod, headers: { Authorization: `Bearer ${tryToken.trim()}` } }
        );
        const body = await res.text();
        setTryResult({
          ok: res.ok,
          text: `HTTP ${res.status}\n\n${body.slice(0, 4000)}`,
        });
      }
    } catch (e: any) {
      setTryResult({ ok: false, text: e.message });
    } finally {
      setTrying(false);
    }
  };

  const copy = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setError(t("xt.copy_failed"));
    }
  };

  const stateStyle: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    expired: "bg-gray-100 text-gray-500",
    revoked: "bg-red-100 text-red-600",
  };

  // A write token with no expiry is refused by the backend; say so before the
  // user fills the rest of the form and gets a surprise.
  const writeNeedsTtl = form.scope === "write" && !form.ttl_hours;

  // Who could plausibly be calling: every other app, plus anyone already
  // issued a token before. Nobody should have to remember an app's exact slug.
  const appCallers = apps.filter((a) => a.id !== appId).map((a) => a.slug || a.name);
  const pastCallers = Array.from(new Set(tokens.map((tk) => tk.caller_name)));
  const callerChoices =
    form.caller_kind === "app"
      ? Array.from(new Set([...appCallers, ...pastCallers]))
      : form.caller_kind === "ai"
        ? Array.from(new Set(["local-model", "openrouter", "claude", ...pastCallers]))
        : pastCallers;

  // Paths the API catalog already found for this app, filtered to the scope —
  // offering POST on a read token would only produce a token that fails.
  const discovered = catalog
    .filter((c) => c.app_id === appId)
    .map((c) => `${(c.method || "GET").toUpperCase()} ${c.path || "/"}`)
    .filter((e) => (form.scope === "read" ? e.startsWith("GET") : true));
  const suggestedPaths = Array.from(new Set([
    ...discovered,
    ...(form.scope === "read" ? ["GET /api/*"] : ["POST /api/*"]),
  ]));

  const toggleChip = (v: string) =>
    setPathChips((prev) => (prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v]));

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-gray-900">{t("xt.title")}</h3>
          <p className="text-[11px] text-gray-500 mt-0.5 max-w-2xl leading-snug">{t("xt.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={appId ?? ""}
            onChange={(e) => setAppId(Number(e.target.value))}
            className="px-2 py-1.5 border border-gray-300 rounded-md text-xs bg-white outline-none focus:ring-2 focus:ring-brand-500"
          >
            {apps.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-3 py-1.5 text-xs font-medium bg-brand-600 text-white rounded-md hover:bg-brand-700 transition"
          >
            {showForm ? t("xt.cancel") : t("xt.new")}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">{error}</div>
      )}

      {/* The one time this secret exists */}
      {issued && (
        <div className="border-2 border-amber-300 bg-amber-50 rounded-lg p-3">
          <p className="text-xs font-semibold text-amber-900 flex items-center gap-1.5">
            {t("xt.issued_title")}
          </p>
          <p className="text-[11px] text-amber-800 mt-0.5">{t("xt.issued_once")}</p>
          <div className="flex items-center gap-2 mt-2">
            <code className="flex-1 min-w-0 px-2 py-1.5 bg-white border border-amber-200 rounded font-mono text-[11px] break-all">
              {issued.token}
            </code>
            <button
              onClick={copy}
              className={`px-3 py-1.5 text-[11px] font-medium rounded-md transition whitespace-nowrap ${
                copied ? "bg-gray-100 text-brand-700" : "bg-brand-600 text-white hover:bg-brand-700"
              }`}
            >
              {copied ? t("xt.copied") : t("xt.copy")}
            </button>
          </div>
          <button
            onClick={() => setIssued(null)}
            className="mt-2 text-[11px] text-amber-800 underline hover:text-amber-900"
          >
            {t("xt.issued_done")}
          </button>
        </div>
      )}

      {/* New token */}
      {showForm && (
        <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/60 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("xt.caller")}</label>
              <div className="flex gap-1.5">
                <select
                  value={form.caller_kind}
                  onChange={(e) => setForm({ ...form, caller_kind: e.target.value })}
                  className="px-1.5 py-1.5 border border-gray-300 rounded text-[11px] bg-white outline-none"
                >
                  <option value="app">{t("xt.kind_app")}</option>
                  <option value="ai">{t("xt.kind_ai")}</option>
                  <option value="external">{t("xt.kind_external")}</option>
                </select>
                <input
                  list="xt-caller-options"
                  value={form.caller_name}
                  onChange={(e) => setForm({ ...form, caller_name: e.target.value })}
                  placeholder={callerChoices.length ? t("xt.caller_pick") : t("xt.caller_ph")}
                  className="flex-1 min-w-0 px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
                />
                {/* A datalist keeps both options open: pick a known caller, or
                    type a name that does not exist in iVS yet. */}
                <datalist id="xt-caller-options">
                  {callerChoices.map((c) => <option key={c} value={c} />)}
                </datalist>
              </div>
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("xt.scope")}</label>
              <div className="flex gap-1.5">
                {(["read", "write"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setForm({ ...form, scope: s })}
                    className={`flex-1 px-2 py-1.5 text-[11px] font-medium rounded-md border transition ${
                      form.scope === s
                        ? s === "write"
                          ? "bg-red-100 text-red-700 border-red-300"
                          : "bg-gray-100 text-brand-700 border-green-300"
                        : "bg-white text-gray-500 border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    {t(`xt.scope_${s}`)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <label className="text-[10px] font-semibold text-gray-700">{t("xt.paths")}</label>
              <button
                type="button"
                onClick={scanNow}
                disabled={scanning}
                className="text-[10px] px-2 py-0.5 rounded-md bg-gray-200 text-gray-700 hover:bg-gray-300 transition disabled:opacity-50"
              >
                {scanning ? t("xt.scanning") : t("xt.scan")}
              </button>
            </div>
            {scanResult && <p className="text-[9.5px] text-green-700 mb-1">{scanResult}</p>}
            <div className="flex flex-wrap gap-1 mb-1.5">
              {suggestedPaths.map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => toggleChip(v)}
                  className={`px-1.5 py-0.5 rounded-md border font-mono text-[10px] transition ${
                    pathChips.includes(v)
                      ? "bg-brand-600 text-white border-brand-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-brand-300"
                  }`}
                >
                  {v}
                </button>
              ))}
              {pathChips.filter((c) => !suggestedPaths.includes(c)).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => toggleChip(v)}
                  className="px-1.5 py-0.5 rounded-md border font-mono text-[10px] bg-brand-600 text-white border-brand-600"
                >
                  {v} ✕
                </button>
              ))}
            </div>
            {discovered.length === 0 && !scanResult && (
              <p className="text-[9.5px] text-amber-700 mb-1">{t("xt.paths_none_found")}</p>
            )}
            <input
              value={form.paths}
              onChange={(e) => setForm({ ...form, paths: e.target.value })}
              placeholder={t("xt.paths_ph")}
              className="w-full px-2 py-1.5 border border-gray-300 rounded font-mono text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p className="text-[9.5px] text-gray-500 mt-0.5">
              {pathChips.length === 0 && !form.paths.trim()
                ? t("xt.paths_empty_means_all")
                : t("xt.paths_hint")}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("xt.ttl")}</label>
              <input
                type="number"
                min={1}
                value={form.ttl_hours}
                onChange={(e) => setForm({ ...form, ttl_hours: e.target.value })}
                placeholder={form.scope === "write" ? t("xt.ttl_required") : t("xt.ttl_never")}
                className={`w-full px-2 py-1.5 border rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500 ${
                  writeNeedsTtl ? "border-red-300 bg-red-50" : "border-gray-300"
                }`}
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("xt.rate")}</label>
              <input
                type="number"
                min={1}
                value={form.rate_limit_per_hour}
                onChange={(e) => setForm({ ...form, rate_limit_per_hour: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("xt.label")}</label>
              <input
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder={t("xt.label_ph")}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          {writeNeedsTtl && (
            <p className="text-[10px] text-red-700 bg-red-50 border border-red-200 rounded p-1.5">
              {t("xt.write_needs_ttl")}
            </p>
          )}
          <p className="text-[10px] text-gray-500 leading-snug">{t("xt.ropa_note")}</p>

          <button
            onClick={create}
            disabled={loading || !form.caller_name.trim() || writeNeedsTtl}
            className="w-full py-1.5 text-xs font-medium bg-brand-600 text-white rounded-md hover:bg-brand-700 transition disabled:opacity-50"
          >
            {loading ? t("xt.working") : t("xt.issue")}
          </button>
        </div>
      )}

      {/* Existing tokens */}
      {tokens.length === 0 && !loading ? (
        <p className="text-xs text-gray-500 italic py-4 text-center">{t("xt.empty")}</p>
      ) : (
        <div className="space-y-1.5">
          {tokens.map((tk) => (
            <div
              key={tk.id}
              className={`border rounded-lg p-2.5 ${
                tk.state === "active" ? "border-gray-200 bg-white" : "border-gray-200 bg-gray-50 opacity-75"
              }`}
            >
              <div className="flex items-start justify-between gap-2 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs">{KIND_ICON[tk.caller_kind] || "•"}</span>
                    <span className="text-xs font-medium text-gray-900 break-all">{tk.caller_name}</span>
                    <span className={`text-[9.5px] px-1.5 py-px rounded font-medium ${
                      tk.scope === "write" ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                    }`}>
                      {t(`xt.scope_${tk.scope}`)}
                    </span>
                    <span className={`text-[9.5px] px-1.5 py-px rounded ${stateStyle[tk.state]}`}>
                      {t(`xt.state_${tk.state}`)}
                    </span>
                  </div>
                  {tk.label && <p className="text-[10px] text-gray-500 mt-0.5">{tk.label}</p>}
                  <p className="text-[10px] text-gray-400 font-mono mt-0.5 break-all">
                    {tk.prefix}… · {tk.allowed_paths.join(", ")}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    {t("xt.expires")}: {tk.expires_at ? tk.expires_at.slice(0, 16).replace("T", " ") : t("xt.never")}
                    {" · "}{t("xt.rate_short")}: {tk.rate_limit_per_hour}/h
                    {" · "}{t("xt.used")}: {tk.use_count}
                  </p>
                </div>
                {tk.state === "active" && (
                  confirmRevoke === tk.id ? (
                    <div className="flex gap-1">
                      <button
                        onClick={() => revoke(tk.id)}
                        disabled={loading}
                        className="px-2 py-1 text-[10px] bg-red-600 text-white rounded-md hover:bg-red-700 transition disabled:opacity-50"
                      >
                        {t("xt.revoke_confirm")}
                      </button>
                      <button
                        onClick={() => setConfirmRevoke(null)}
                        className="px-2 py-1 text-[10px] bg-gray-100 text-gray-600 rounded-md hover:bg-gray-200 transition"
                      >
                        {t("xt.cancel")}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmRevoke(tk.id)}
                      className="px-2 py-1 text-[10px] text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition"
                    >
                      {t("xt.revoke")}
                    </button>
                  )
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ทดลองเรียกจริง */}
      <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/60">
        <p className="text-[11px] font-semibold text-gray-800 flex items-center gap-1.5">
          {t("xt.try_title")}
        </p>
        <p className="text-[10px] text-gray-500 mb-2 leading-snug">{t("xt.try_subtitle")}</p>
        <div className="flex flex-wrap gap-1.5">
          <input
            value={tryToken}
            onChange={(e) => setTryToken(e.target.value)}
            placeholder={t("xt.try_token_ph")}
            className="flex-1 min-w-[200px] px-2 py-1.5 border border-gray-300 rounded font-mono text-[10.5px] outline-none focus:ring-2 focus:ring-brand-500"
          />
          <select
            value={tryMethod}
            onChange={(e) => setTryMethod(e.target.value)}
            className="px-1.5 py-1.5 border border-gray-300 rounded text-[11px] bg-white outline-none"
          >
            {["GET", "POST", "PUT", "DELETE"].map((m) => <option key={m}>{m}</option>)}
          </select>
          <input
            value={tryPath}
            onChange={(e) => setTryPath(e.target.value)}
            placeholder="/health"
            className="w-40 px-2 py-1.5 border border-gray-300 rounded font-mono text-[10.5px] outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            onClick={tryCall}
            disabled={trying || !tryToken.trim()}
            className="px-3 py-1.5 text-[11px] font-medium bg-gray-800 text-white rounded-md hover:bg-gray-900 transition disabled:opacity-50"
          >
            {trying ? t("xt.try_running") : t("xt.try_run")}
          </button>
        </div>
        {tryResult && (
          <pre className={`mt-2 rounded p-2 text-[10px] font-mono overflow-x-auto max-h-52 overflow-y-auto ${
            tryResult.ok ? "bg-gray-900 text-green-300" : "bg-red-50 text-red-700 border border-red-200"
          }`}>
{tryResult.text}
          </pre>
        )}
      </div>
    </div>
  );
}
