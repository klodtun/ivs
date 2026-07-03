"use client";

/**
 * IVS API Catalog (v1.0.1)
 *
 * Copyright (c) 2026 IVS Project. All Rights Reserved.
 * Licensed under the IVS Proprietary EULA.
 *
 * Managed catalog of APIs discovered from deployed apps.
 *   - Auto-scan running apps for /openapi.json
 *   - Test endpoint health from the UI
 *   - Replace base URL / API key / schema with versioned history
 *   - Restore prior versions
 */
import { useCallback, useEffect, useState } from "react";
import { api, CatalogEntry, CatalogVersion } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, formatLegalTimestamp } from "@/lib/utils";

type TestResult = {
  status: string;
  http_code: number | null;
  latency_ms: number;
  message: string;
  body_snippet: string;
};

export default function ApiCatalogView() {
  const { t } = useLang();
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanSummary, setScanSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState<Record<number, boolean>>({});
  const [testResults, setTestResults] = useState<Record<number, TestResult>>({});
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const [history, setHistory] = useState<CatalogVersion[]>([]);
  const [editFor, setEditFor] = useState<CatalogEntry | null>(null);
  const [revealedKeys, setRevealedKeys] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    try {
      const list = await api.listCatalog();
      setEntries(list);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const scan = async () => {
    setScanning(true);
    setScanSummary(null);
    try {
      const r = await api.scanCatalog();
      setScanSummary(`${t("catalog.scan_done")}: ${r.scanned} ${t("catalog.scanned")} · ${r.new} ${t("catalog.new")} · ${r.updated} ${t("catalog.updated")} · ${r.failed} ${t("catalog.failed")}`);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  const runTest = async (id: number) => {
    setTesting(s => ({ ...s, [id]: true }));
    try {
      const r = await api.testCatalogEntry(id);
      setTestResults(s => ({ ...s, [id]: r }));
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setTesting(s => ({ ...s, [id]: false }));
    }
  };

  const reveal = async (id: number) => {
    try {
      const r = await api.revealCatalogKey(id);
      if (r.api_key) {
        setRevealedKeys(s => ({ ...s, [id]: r.api_key as string }));
        navigator.clipboard.writeText(r.api_key).catch(() => {});
        setTimeout(() => {
          setRevealedKeys(s => { const next = { ...s }; delete next[id]; return next; });
        }, 10000);
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  const openHistory = async (id: number) => {
    setHistoryFor(id);
    try {
      const h = await api.getCatalogHistory(id);
      setHistory(h);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const restore = async (entryId: number, versionId: number) => {
    if (!confirm(t("catalog.restore_confirm"))) return;
    try {
      await api.restoreCatalogVersion(entryId, versionId);
      setHistoryFor(null);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const deleteEntry = async (id: number, name: string) => {
    if (!confirm(`${t("catalog.delete_confirm")}: "${name}"?`)) return;
    try {
      await api.deleteCatalogEntry(id);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const filtered = entries.filter(e =>
    !search ||
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.base_url.toLowerCase().includes(search.toLowerCase()) ||
    (e.description || "").toLowerCase().includes(search.toLowerCase())
  );

  const statusColor = (s: string) => {
    if (s === "OK") return "bg-green-50 text-green-700 border-green-200";
    if (s === "FAIL") return "bg-red-50 text-red-700 border-red-200";
    return "bg-gray-50 text-gray-600 border-gray-200";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{t("catalog.title")}</h1>
          <p className="text-gray-500 text-[10px] mt-0.5">{t("catalog.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={scan}
            disabled={scanning}
            className="px-3 py-1.5 text-xs bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {scanning ? t("catalog.scanning") : t("catalog.scan_now")}
          </button>
          <button
            onClick={() => setEditFor({} as CatalogEntry)}
            className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            {t("catalog.add_manual")}
          </button>
        </div>
      </div>

      {scanSummary && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-800">
          {scanSummary}
        </div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700">
          {error}
        </div>
      )}

      <input
        type="text"
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder={t("catalog.search")}
        className="w-full text-xs border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />

      {loading ? (
        <div className="text-xs text-gray-400 animate-pulse p-8 text-center">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-xs text-gray-400">
          {t("catalog.empty")}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(entry => {
            const isExpanded = expanded === entry.id;
            const result = testResults[entry.id];
            return (
              <div key={entry.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div className="p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-gray-900">{entry.name}</span>
                      <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                        {entry.method}
                      </span>
                      <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-medium", statusColor(entry.last_test_status))}>
                        {entry.last_test_status}
                      </span>
                      <span className="text-[10px] text-gray-400">v{entry.current_version}</span>
                      {entry.discovery_source === "auto" && (
                        <span className="text-[10px] bg-brand-50 text-brand-700 px-1.5 py-0.5 rounded">auto</span>
                      )}
                    </div>
                    <div className="font-mono text-[11px] text-gray-600 mt-1 break-all">
                      {entry.full_url}
                    </div>
                    {entry.description && (
                      <div className="text-[11px] text-gray-500 mt-1">{entry.description}</div>
                    )}
                    {entry.last_test_message && (
                      <div className="text-[10px] text-gray-400 mt-1">
                        {entry.last_test_message}
                        {entry.last_test_at && ` · ${formatLegalTimestamp((entry.last_test_at))}`}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <button
                      onClick={() => runTest(entry.id)}
                      disabled={testing[entry.id]}
                      className="px-2 py-1 text-[10px] bg-brand-600 text-white rounded hover:bg-brand-700 disabled:opacity-50"
                    >
                      {testing[entry.id] ? "..." : t("catalog.test")}
                    </button>
                    <button
                      onClick={() => setExpanded(isExpanded ? null : entry.id)}
                      className="px-2 py-1 text-[10px] border border-gray-300 rounded hover:bg-gray-50"
                    >
                      {isExpanded ? t("catalog.collapse") : t("catalog.details")}
                    </button>
                  </div>
                </div>

                {result && (
                  <div className="px-3 pb-3">
                    <div className={cn("text-[11px] rounded p-2 border", statusColor(result.status))}>
                      <div className="font-semibold mb-1">
                        {result.status} · HTTP {result.http_code ?? "?"} · {result.latency_ms} ms
                      </div>
                      <div className="opacity-80">{result.message}</div>
                      {result.body_snippet && (
                        <pre className="mt-2 text-[10px] font-mono bg-white/50 p-1.5 rounded overflow-auto max-h-32">{result.body_snippet}</pre>
                      )}
                    </div>
                  </div>
                )}

                {isExpanded && (
                  <div className="px-3 pb-3 border-t border-gray-100 pt-3 space-y-2 text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <div className="text-[10px] text-gray-400 uppercase">{t("catalog.base_url")}</div>
                        <div className="font-mono text-gray-700 break-all">{entry.base_url}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-gray-400 uppercase">{t("catalog.path")}</div>
                        <div className="font-mono text-gray-700">{entry.path}</div>
                      </div>
                      {entry.has_api_key && (
                        <div>
                          <div className="text-[10px] text-gray-400 uppercase">{t("catalog.api_key")}</div>
                          <div className="font-mono text-gray-700 flex items-center gap-2">
                            <span>{revealedKeys[entry.id] || entry.api_key}</span>
                            <button
                              onClick={() => reveal(entry.id)}
                              className="text-[10px] text-brand-600 underline"
                            >
                              {revealedKeys[entry.id] ? t("catalog.copied") : t("catalog.reveal_copy")}
                            </button>
                          </div>
                        </div>
                      )}
                      <div>
                        <div className="text-[10px] text-gray-400 uppercase">{t("catalog.schema_size")}</div>
                        <div className="text-gray-700">{entry.schema_size > 0 ? `${entry.schema_size} bytes` : "—"}</div>
                      </div>
                    </div>
                    {entry.schema_snippet && (
                      <details className="text-[10px]">
                        <summary className="cursor-pointer text-gray-500">{t("catalog.show_schema")}</summary>
                        <pre className="mt-1 font-mono bg-gray-50 p-2 rounded max-h-48 overflow-auto whitespace-pre-wrap">
                          {entry.schema_snippet}
                        </pre>
                      </details>
                    )}
                    <div className="flex gap-2 pt-2">
                      <button onClick={() => setEditFor(entry)}
                        className="px-2 py-1 text-[10px] bg-amber-600 text-white rounded hover:bg-amber-700">
                        {t("catalog.replace")}
                      </button>
                      <button onClick={() => openHistory(entry.id)}
                        className="px-2 py-1 text-[10px] border border-gray-300 rounded hover:bg-gray-50">
                        {t("catalog.history")} ({entry.current_version - 1})
                      </button>
                      <button onClick={() => deleteEntry(entry.id, entry.name)}
                        className="px-2 py-1 text-[10px] text-red-600 border border-red-200 rounded hover:bg-red-50 ml-auto">
                        {t("catalog.delete")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {editFor && (
        <EditModal
          entry={editFor}
          onClose={() => setEditFor(null)}
          onSaved={() => { setEditFor(null); load(); }}
          t={t}
        />
      )}

      {historyFor !== null && (
        <HistoryModal
          versions={history}
          entryId={historyFor}
          onClose={() => setHistoryFor(null)}
          onRestore={restore}
          t={t}
        />
      )}
    </div>
  );
}

function EditModal({ entry, onClose, onSaved, t }: {
  entry: CatalogEntry;
  onClose: () => void;
  onSaved: () => void;
  t: (k: string) => string;
}) {
  const isNew = !entry.id;
  const [form, setForm] = useState({
    name: entry.name || "",
    base_url: entry.base_url || "",
    method: entry.method || "GET",
    path: entry.path || "/",
    api_key: "",
    description: entry.description || "",
    reason: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      if (isNew) {
        await api.createCatalogEntry({
          name: form.name,
          base_url: form.base_url,
          method: form.method,
          path: form.path,
          api_key: form.api_key || undefined,
          description: form.description,
        });
      } else {
        await api.replaceCatalogEntry(entry.id, {
          base_url: form.base_url || undefined,
          api_key: form.api_key || undefined,
          method: form.method,
          path: form.path,
          reason: form.reason,
        });
      }
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-md w-full p-5 space-y-3">
        <h2 className="text-sm font-bold text-gray-900">
          {isNew ? t("catalog.add_manual") : `${t("catalog.replace")}: ${entry.name}`}
        </h2>
        {err && <div className="text-xs text-red-600 bg-red-50 p-2 rounded">{err}</div>}

        {isNew && (
          <input className="w-full text-xs border border-gray-300 rounded px-2 py-1.5"
            placeholder={t("catalog.name")}
            value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
        )}
        <div className="grid grid-cols-3 gap-2">
          <select className="text-xs border border-gray-300 rounded px-2 py-1.5"
            value={form.method} onChange={e => setForm({ ...form, method: e.target.value })}>
            {["GET", "POST", "PUT", "DELETE", "PATCH"].map(m => <option key={m}>{m}</option>)}
          </select>
          <input className="col-span-2 text-xs border border-gray-300 rounded px-2 py-1.5 font-mono"
            placeholder={t("catalog.path")}
            value={form.path} onChange={e => setForm({ ...form, path: e.target.value })} />
        </div>
        <input className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 font-mono"
          placeholder={t("catalog.base_url")}
          value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} />
        <input className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 font-mono"
          placeholder={t("catalog.api_key") + " (" + t("catalog.optional") + ")"}
          value={form.api_key} onChange={e => setForm({ ...form, api_key: e.target.value })} />
        {!isNew && (
          <input className="w-full text-xs border border-gray-300 rounded px-2 py-1.5"
            placeholder={t("catalog.reason")}
            value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} />
        )}
        <div className="flex gap-2 pt-2">
          <button onClick={save} disabled={saving}
            className="flex-1 px-3 py-1.5 text-xs bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
            {saving ? "..." : (isNew ? t("catalog.create") : t("catalog.replace"))}
          </button>
          <button onClick={onClose}
            className="px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function HistoryModal({ versions, entryId, onClose, onRestore, t }: {
  versions: CatalogVersion[];
  entryId: number;
  onClose: () => void;
  onRestore: (entryId: number, versionId: number) => void;
  t: (k: string) => string;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-2xl w-full p-5 space-y-3 max-h-[80vh] overflow-auto">
        <div className="flex justify-between items-center">
          <h2 className="text-sm font-bold text-gray-900">{t("catalog.history")}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-lg">✕</button>
        </div>
        {versions.length === 0 ? (
          <div className="text-xs text-gray-400 p-4 text-center">{t("catalog.no_history")}</div>
        ) : (
          <div className="space-y-2">
            {versions.map(v => (
              <div key={v.id} className="border border-gray-200 rounded p-3 text-xs">
                <div className="flex justify-between items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold">v{v.version_number}</div>
                    <div className="font-mono text-[11px] text-gray-600 break-all mt-0.5">
                      {v.method} {v.base_url}{v.path}
                    </div>
                    {v.reason && (
                      <div className="text-[10px] text-gray-500 mt-1 italic">{v.reason}</div>
                    )}
                    {v.created_at && (
                      <div className="text-[10px] text-gray-400 mt-1">
                        {formatLegalTimestamp((v.created_at))}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => onRestore(entryId, v.id)}
                    className="shrink-0 px-2 py-1 text-[10px] bg-amber-600 text-white rounded hover:bg-amber-700"
                  >
                    {t("catalog.restore")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
