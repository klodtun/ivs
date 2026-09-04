"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

type Source = {
  id: number;
  name: string;
  description: string;
  url: string;
  method: string;
  vault_key_name: string;
  fetch_interval_minutes: number;
  retention_days: number;
  is_active: boolean;
  last_fetch_at: string | null;
  last_status: string;
  last_message: string;
  pii_found: string[];
  record_count: number;
};

/**
 * Outside data, fetched once and shared with the apps.
 *
 * The screen leads with what the PII scan found, not with the record count.
 * A source quietly carrying personal data is the thing that changes what the
 * operator has to do — it needs a lawful basis and a retention decision — and
 * it is the thing nobody goes looking for on their own.
 */
export function DataMartView() {
  const { t } = useLang();
  const [sources, setSources] = useState<Source[]>([]);
  const [vaultKeys, setVaultKeys] = useState<{ id: number; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [preview, setPreview] = useState<{ id: number; data: any } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const [form, setForm] = useState({
    name: "",
    url: "",
    method: "GET",
    vault_key_name: "",
    description: "",
    fetch_interval_minutes: "60",
    retention_days: "30",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await api.listDataMartSources();
      setSources(r.sources);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // The credential is picked from the Vault by name — nobody should be
    // pasting a secret into this form.
    api.getVaultKeys()
      .then((k) => setVaultKeys(k.map((x: any) => ({ id: x.id, name: x.name }))))
      .catch(() => setVaultKeys([]));
  }, [load]);

  const create = async () => {
    if (!form.name.trim() || !form.url.trim()) return;
    setLoading(true);
    setError("");
    try {
      await api.createDataMartSource({
        name: form.name.trim(),
        url: form.url.trim(),
        method: form.method,
        vault_key_name: form.vault_key_name,
        description: form.description.trim(),
        fetch_interval_minutes: Number(form.fetch_interval_minutes) || 60,
        retention_days: Number(form.retention_days) || 30,
      });
      setForm({ ...form, name: "", url: "", description: "" });
      setShowForm(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchNow = async (id: number) => {
    setBusyId(id);
    setError("");
    try {
      await api.fetchDataMartSource(id);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const showLatest = async (id: number) => {
    setBusyId(id);
    setError("");
    try {
      const d = await api.getDataMartLatest(id);
      setPreview({ id, data: d });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (id: number) => {
    setBusyId(id);
    try {
      await api.deleteDataMartSource(id);
      setConfirmDelete(null);
      if (preview?.id === id) setPreview(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const statusStyle: Record<string, string> = {
    ok: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    never: "bg-gray-100 text-gray-500",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-gray-900">{t("dm.title")}</h3>
          <p className="text-[11px] text-gray-500 mt-0.5 max-w-2xl leading-snug">{t("dm.subtitle")}</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="px-3 py-1.5 text-xs font-medium bg-brand-600 text-white rounded-md hover:bg-brand-700 transition whitespace-nowrap"
        >
          {showForm ? t("dm.cancel") : t("dm.new")}
        </button>
      </div>

      {error && (
        <div className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">{error}</div>
      )}

      {showForm && (
        <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/60 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("dm.name")}</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t("dm.name_ph")}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("dm.key")}</label>
              <select
                value={form.vault_key_name}
                onChange={(e) => setForm({ ...form, vault_key_name: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] bg-white outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">{t("dm.key_none")}</option>
                {vaultKeys.map((k) => <option key={k.id} value={k.name}>{k.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("dm.url")}</label>
            <div className="flex gap-1.5">
              <select
                value={form.method}
                onChange={(e) => setForm({ ...form, method: e.target.value })}
                className="px-1.5 py-1.5 border border-gray-300 rounded text-[11px] bg-white outline-none"
              >
                <option>GET</option>
                <option>POST</option>
              </select>
              <input
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://example.org/api/data"
                className="flex-1 min-w-0 px-2 py-1.5 border border-gray-300 rounded font-mono text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("dm.interval")}</label>
              <input
                type="number" min={1}
                value={form.fetch_interval_minutes}
                onChange={(e) => setForm({ ...form, fetch_interval_minutes: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("dm.retention")}</label>
              <input
                type="number" min={0}
                value={form.retention_days}
                onChange={(e) => setForm({ ...form, retention_days: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("dm.desc")}</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder={t("dm.desc_ph")}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          <p className="text-[10px] text-gray-500 leading-snug">{t("dm.pii_note")}</p>
          <button
            onClick={create}
            disabled={loading || !form.name.trim() || !form.url.trim()}
            className="w-full py-1.5 text-xs font-medium bg-brand-600 text-white rounded-md hover:bg-brand-700 transition disabled:opacity-50"
          >
            {loading ? t("dm.working") : t("dm.add")}
          </button>
        </div>
      )}

      {sources.length === 0 && !loading ? (
        <p className="text-xs text-gray-500 italic py-4 text-center">{t("dm.empty")}</p>
      ) : (
        <div className="space-y-1.5">
          {sources.map((s) => (
            <div key={s.id} className="border border-gray-200 rounded-lg p-2.5 bg-white">
              <div className="flex items-start justify-between gap-2 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs font-medium text-gray-900">{s.name}</span>
                    <span className={`text-[9.5px] px-1.5 py-px rounded ${statusStyle[s.last_status] || statusStyle.never}`}>
                      {t(`dm.status_${s.last_status}`)}
                    </span>
                    {/* The finding that changes what the operator must do */}
                    {s.pii_found.length > 0 && (
                      <span className="text-[9.5px] px-1.5 py-px rounded bg-amber-100 text-amber-800 font-medium">
                         {t("dm.pii_found")}: {s.pii_found.join(", ")}
                      </span>
                    )}
                  </div>
                  {s.description && <p className="text-[10px] text-gray-500 mt-0.5">{s.description}</p>}
                  <p className="text-[10px] text-gray-400 font-mono mt-0.5 break-all">
                    {s.method} {s.url}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    {t("dm.every")} {s.fetch_interval_minutes} {t("dm.minutes")}
                    {" · "}{t("dm.keep")} {s.retention_days} {t("dm.days")}
                    {" · "}{t("dm.records")}: {s.record_count}
                    {s.vault_key_name && ` ·  ${s.vault_key_name}`}
                  </p>
                  {s.last_status === "failed" && s.last_message && (
                    <p className="text-[10px] text-red-600 mt-0.5">{s.last_message}</p>
                  )}
                </div>
                <div className="flex gap-1 flex-wrap">
                  <button
                    onClick={() => fetchNow(s.id)}
                    disabled={busyId === s.id}
                    className="px-2 py-1 text-[10px] bg-brand-600 text-white rounded-md hover:bg-brand-700 transition disabled:opacity-50"
                  >
                    {busyId === s.id ? t("dm.working") : t("dm.fetch_now")}
                  </button>
                  {s.record_count > 0 && (
                    <button
                      onClick={() => showLatest(s.id)}
                      disabled={busyId === s.id}
                      className="px-2 py-1 text-[10px] bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition disabled:opacity-50"
                    >
                      {t("dm.view")}
                    </button>
                  )}
                  {confirmDelete === s.id ? (
                    <>
                      <button
                        onClick={() => remove(s.id)}
                        disabled={busyId === s.id}
                        className="px-2 py-1 text-[10px] bg-red-600 text-white rounded-md hover:bg-red-700 transition disabled:opacity-50"
                      >
                        {t("dm.delete_confirm")}
                      </button>
                      <button
                        onClick={() => setConfirmDelete(null)}
                        className="px-2 py-1 text-[10px] bg-gray-100 text-gray-600 rounded-md hover:bg-gray-200 transition"
                      >
                        {t("dm.cancel")}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setConfirmDelete(s.id)}
                      className="px-2 py-1 text-[10px] text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition"
                    >
                      {t("dm.delete")}
                    </button>
                  )}
                </div>
              </div>

              {preview?.id === s.id && (
                <div className="mt-2 border-t border-gray-100 pt-2">
                  <p className="text-[10px] text-gray-500 mb-1">
                    {t("dm.fetched")}: {(preview.data.fetched_at || "").slice(0, 19).replace("T", " ")}
                    {" · "}{t("dm.expires")}: {preview.data.expires_at
                      ? preview.data.expires_at.slice(0, 10)
                      : t("dm.no_expiry")}
                    {" · "}hash {String(preview.data.content_hash || "").slice(0, 12)}…
                  </p>
                  <pre className="bg-gray-900 text-green-300 rounded p-2 text-[10px] font-mono overflow-x-auto max-h-52 overflow-y-auto">
{JSON.stringify(preview.data.data, null, 1).slice(0, 6000)}
                  </pre>
                  <button
                    onClick={() => setPreview(null)}
                    className="mt-1 text-[10px] text-gray-500 hover:text-gray-700"
                  >
                    {t("dm.close")}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
