"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { ResourceData, ResourceHistory } from "@/types";
import { Pagination, usePagination } from "@/components/pagination";

/* ─── SVG Mini-Chart (no external deps) ─── */
function MiniChart({
  data,
  color,
  height = 80,
  maxVal,
  label,
}: {
  data: number[];
  color: string;
  height?: number;
  maxVal?: number;
  label: string;
}) {
  if (data.length < 2) return null;
  const max = maxVal ?? Math.max(...data, 1);
  const w = 100;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = height - (v / max) * (height - 8) - 4;
    return `${x},${y}`;
  });
  const line = pts.join(" ");
  const area = `0,${height} ${line} ${w},${height}`;

  return (
    <div className="flex-1 min-w-[200px]">
      <p className="text-[10px] text-gray-500 mb-1 font-medium">{label}</p>
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="none">
        <polygon points={area} fill={color} opacity="0.15" />
        <polyline points={line} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
      <div className="flex justify-between text-[9px] text-gray-400 mt-0.5">
        <span>{data.length > 0 ? data[0] : 0}</span>
        <span>{data.length > 0 ? data[data.length - 1] : 0}</span>
      </div>
    </div>
  );
}

/* ─── Usage Bar ─── */
function UsageBar({ percent, label, used, total, unit, colorClass }: {
  percent: number;
  label: string;
  used: string;
  total: string;
  unit: string;
  colorClass: string;
}) {
  const barColor =
    percent >= 90 ? "bg-red-500" : percent >= 70 ? "bg-amber-500" : "bg-green-500";

  return (
    <div className={`p-3 rounded-lg border ${colorClass}`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-semibold text-gray-700">{label}</span>
        <span className={`text-xs font-bold ${
          percent >= 90 ? "text-red-600" : percent >= 70 ? "text-amber-600" : "text-green-600"
        }`}>
          {percent.toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-1.5">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-gray-500">
        <span>{used} {unit}</span>
        <span>{total} {unit}</span>
      </div>
    </div>
  );
}

/* ─── Main Page ─── */
export default function ResourcesPage() {
  const { t } = useLang();
  const [data, setData] = useState<ResourceData | null>(null);
  const [history, setHistory] = useState<ResourceHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{ filename: string; download_url: string } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const fetchData = useCallback(async () => {
    try {
      const [res, hist] = await Promise.all([
        api.getResources(),
        api.getResourceHistory(24),
      ]);
      setData(res);
      setHistory(hist);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      console.error("Failed to load resources:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // refresh every 15s
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const result = await api.exportResourceReport();
      setExportResult(result);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setExporting(false);
    }
  };

  // IMPORTANT: hooks must be called in the same order on every render,
  // so `usePagination` has to run BEFORE any conditional `return`. The
  // first render has data=null; we feed it an empty array — the hook
  // returns sensible empty defaults and we re-render once data arrives.
  const perAppPagination = usePagination(data?.per_app ?? [], 10);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <svg className="w-6 h-6 animate-spin text-brand-500" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (!data) return null;

  const sys = data.system;
  const cap = data.capacity;

  // Prepare chart data
  const cpuHistory = history.map((h) => h.cpu);
  const ramHistory = history.map((h) => h.mem_used);
  const appsHistory = history.map((h) => h.apps_running);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{t("res.title")}</h1>
          <p className="text-xs text-gray-500">{t("res.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-[10px] text-gray-400">{t("res.last_updated")}: {lastUpdated}</span>
          )}
          <button
            onClick={fetchData}
            className="px-2.5 py-1 text-[10px] bg-gray-100 text-gray-600 rounded-md hover:bg-gray-200 transition"
          >
            {t("res.refresh")}
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="px-2.5 py-1 text-[10px] bg-brand-600 text-white rounded-md hover:bg-brand-700 transition disabled:opacity-50"
          >
            {exporting ? t("res.exporting") : t("res.export")}
          </button>
        </div>
      </div>

      {/* Export success */}
      {exportResult && (
        <div className="flex items-center gap-2 p-2.5 bg-green-50 border border-green-200 rounded-lg">
          <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-xs text-green-700 flex-1">{t("res.export_success")}: {exportResult.filename}</span>
          <a
            href={exportResult.download_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 py-0.5 text-[10px] bg-green-600 text-white rounded hover:bg-green-700 transition"
          >
            {t("res.export_download")}
          </a>
        </div>
      )}

      {/* Alerts */}
      {data.alerts.length > 0 && (
        <div className="space-y-1.5">
          <h2 className="text-xs font-semibold text-gray-700">{t("res.alerts")}</h2>
          {data.alerts.map((alert, i) => (
            <div
              key={i}
              className={`flex items-center gap-2 p-2.5 rounded-lg border ${
                alert.level === "critical"
                  ? "bg-red-50 border-red-200"
                  : "bg-amber-50 border-amber-200"
              }`}
            >
              <span className="text-sm">
                {alert.level === "critical" ? "🔴" : "🟡"}
              </span>
              <span
                className={`text-xs font-medium ${
                  alert.level === "critical" ? "text-red-700" : "text-amber-700"
                }`}
              >
                {alert.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {data.alerts.length === 0 && (
        <div className="flex items-center gap-2 p-2.5 bg-green-50 border border-green-200 rounded-lg">
          <span className="text-sm">🟢</span>
          <span className="text-xs text-green-700">{t("res.no_alerts")}</span>
        </div>
      )}

      {/* System Hardware Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <UsageBar
          percent={sys.cpu_percent}
          label={`${t("res.cpu")} (${sys.cpu_cores} ${t("res.cores")})`}
          used={sys.cpu_percent.toFixed(1) + "%"}
          total={"100%"}
          unit=""
          colorClass="bg-white border-gray-200"
        />
        <UsageBar
          percent={sys.memory_percent}
          label={t("res.ram")}
          used={formatMB(sys.memory_used_mb)}
          total={formatMB(sys.memory_total_mb)}
          unit=""
          colorClass="bg-white border-gray-200"
        />
        <UsageBar
          percent={sys.disk_percent}
          label={t("res.storage")}
          used={sys.disk_used_gb + " GB"}
          total={sys.disk_total_gb + " GB"}
          unit=""
          colorClass="bg-white border-gray-200"
        />
        {/* GPU Card */}
        <div className="p-3 rounded-lg border bg-white border-gray-200">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold text-gray-700">{t("res.gpu")}</span>
            <span className="text-[10px] text-gray-500">
              {sys.gpu_type === "nvidia" ? "NVIDIA" : sys.gpu_type === "apple_silicon" ? "Apple Silicon" : "—"}
            </span>
          </div>
          {sys.gpu_type !== "none" ? (
            <>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden mb-1.5">
                <div
                  className="h-full rounded-full bg-purple-500 transition-all"
                  style={{ width: `${sys.gpu_total_mb ? ((sys.gpu_used_mb || 0) / sys.gpu_total_mb * 100) : 0}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-gray-500">
                <span>{sys.gpu_used_mb ? formatMB(sys.gpu_used_mb) : "N/A"}</span>
                <span>{sys.gpu_total_mb ? formatMB(sys.gpu_total_mb) : "N/A"}</span>
              </div>
            </>
          ) : (
            <p className="text-[10px] text-gray-400 mt-2">{t("res.gpu_none")}</p>
          )}
        </div>
      </div>

      {/* Capacity Analysis */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-xs font-semibold text-gray-700 mb-3">{t("res.capacity")}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-brand-600">{cap.apps_running}</p>
            <p className="text-[10px] text-gray-500">{t("res.apps_running")}</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-700">{cap.apps_total}</p>
            <p className="text-[10px] text-gray-500">{t("res.total")}</p>
          </div>
          <div className="text-center">
            <p className={`text-2xl font-bold ${cap.estimated_apps_can_add <= 2 ? "text-red-600" : cap.estimated_apps_can_add <= 5 ? "text-amber-600" : "text-green-600"}`}>
              ~{cap.estimated_apps_can_add}
            </p>
            <p className="text-[10px] text-gray-500">{t("res.apps_can_add")}</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-500">{formatMB(cap.ram_free_mb)}</p>
            <p className="text-[10px] text-gray-500">{t("res.free")} RAM</p>
          </div>
        </div>
        <p className="text-[10px] text-gray-400 text-center mt-2">
          {t("res.ram_per_app")}{cap.estimated_ram_per_app_mb} MB
        </p>
      </div>

      {/* Per-App Resource Usage */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h2 className="text-xs font-semibold text-gray-700 mb-3">{t("res.per_app")}</h2>
        {data.per_app.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-1.5 px-2 text-gray-500 font-medium">{t("res.col_app")}</th>
                  <th className="text-left py-1.5 px-2 text-gray-500 font-medium">{t("res.col_type")}</th>
                  <th className="text-right py-1.5 px-2 text-gray-500 font-medium">{t("res.col_cpu")}</th>
                  <th className="text-right py-1.5 px-2 text-gray-500 font-medium">{t("res.col_ram")}</th>
                  <th className="text-right py-1.5 px-2 text-gray-500 font-medium">{t("res.col_port")}</th>
                </tr>
              </thead>
              <tbody>
                {perAppPagination.paged.map((app) => (
                  <tr key={app.slug} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-1.5 px-2 font-medium text-gray-900">{app.name}</td>
                    <td className="py-1.5 px-2">
                      <span className="px-1.5 py-px rounded-full text-[9px] bg-gray-100 text-gray-600">{app.app_type}</span>
                    </td>
                    <td className="py-1.5 px-2 text-right">
                      <span className={app.cpu_percent > 80 ? "text-red-600 font-semibold" : "text-gray-700"}>
                        {app.cpu_percent.toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-right">
                      <span className="text-gray-700">{app.memory_mb}</span>
                      {app.memory_limit_mb > 0 && (
                        <span className="text-gray-400 text-[9px]"> / {app.memory_limit_mb}</span>
                      )}
                    </td>
                    <td className="py-1.5 px-2 text-right text-gray-500">{app.port || "—"}</td>
                  </tr>
                ))}
                {/* Total row — always reflects the FULL dataset, not just current page */}
                <tr className="border-t border-gray-200 font-semibold">
                  <td className="py-1.5 px-2 text-gray-700" colSpan={2}>{t("res.total")}</td>
                  <td className="py-1.5 px-2 text-right text-gray-700">
                    {data.per_app.reduce((s, a) => s + a.cpu_percent, 0).toFixed(1)}%
                  </td>
                  <td className="py-1.5 px-2 text-right text-gray-700">
                    {data.per_app.reduce((s, a) => s + a.memory_mb, 0).toFixed(1)}
                  </td>
                  <td className="py-1.5 px-2"></td>
                </tr>
              </tbody>
            </table>
            <Pagination
              total={perAppPagination.total}
              page={perAppPagination.page}
              pageSize={perAppPagination.pageSize}
              onPageChange={perAppPagination.setPage}
              onPageSizeChange={perAppPagination.setPageSize}
              itemLabel={t("res.per_app_item_label")}
            />
          </div>
        ) : (
          <p className="text-[10px] text-gray-400 text-center py-4">{t("res.no_apps")}</p>
        )}
      </div>

      {/* Historical Charts */}
      {history.length >= 2 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-xs font-semibold text-gray-700 mb-3">{t("res.history")}</h2>
          <div className="flex flex-wrap gap-4">
            <MiniChart data={cpuHistory} color="#3b82f6" maxVal={100} label={t("res.history_cpu")} />
            <MiniChart data={ramHistory} color="#8b5cf6" maxVal={sys.memory_total_mb} label={t("res.history_ram")} />
            <MiniChart data={appsHistory} color="#10b981" maxVal={Math.max(...appsHistory, 5)} label={t("res.history_apps")} />
          </div>
          <p className="text-[9px] text-gray-400 text-center mt-2">
            {history.length} data points — {new Date(history[0].time).toLocaleString()} → {new Date(history[history.length - 1].time).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}

/* ─── Helpers ─── */
function formatMB(mb: number): string {
  if (mb >= 1024) return (mb / 1024).toFixed(1) + " GB";
  return mb.toLocaleString() + " MB";
}
