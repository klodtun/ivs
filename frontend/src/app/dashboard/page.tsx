"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { SystemHealthPanel } from "@/components/system-health";
import { AppCard } from "@/components/app-card";
import { DeployZone } from "@/components/deploy-zone";
import { DockerStatusBanner } from "@/components/docker-status-banner";
import { LoadingState, PerfWarningBanner } from "@/components/loading-state";
import { App, SystemHealth, User } from "@/types";

export default function DashboardPage() {
  const { t } = useLang();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [apps, setApps] = useState<App[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadStartedAt] = useState<number>(() => Date.now());
  const [slowLoadSeconds, setSlowLoadSeconds] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    setRefreshError(null);
    try {
      const [h, a] = await Promise.all([api.getSystemHealth(), api.getApps()]);
      setHealth(h);
      setApps(a);
      setLastRefresh(new Date());
    } catch (e) {
      console.error("Failed to load dashboard data", e);
      setRefreshError(e instanceof Error ? e.message : "Failed to refresh");
    } finally {
      setIsRefreshing(false);
      setInitialLoading(false);
    }
  }, []);

  // Flag if the very first paint is slow (>5s) — likely Docker / NAS hw-bound
  useEffect(() => {
    if (!initialLoading) return;
    const t = setTimeout(() => {
      const elapsed = Math.round((Date.now() - loadStartedAt) / 1000);
      if (initialLoading) setSlowLoadSeconds(elapsed);
    }, 5000);
    return () => clearTimeout(t);
  }, [initialLoading, loadStartedAt]);

  useEffect(() => {
    const stored = localStorage.getItem("user");
    if (stored) {
      const u = JSON.parse(stored);
      setUser(u);
      if (u.role === "viewer") {
        window.location.href = "/dashboard/apps";
        return;
      }
    }
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const canDeploy = user && (user.role === "admin" || user.role === "developer");

  const formatTime = (d: Date) =>
    d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{t("dash.title")}</h1>
          <p className="text-gray-500 text-[10px] mt-0.5">{t("dash.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {lastRefresh && !refreshError && (
            <span className="text-[10px] text-gray-400">
              {t("dash.last_updated")}: {formatTime(lastRefresh)}
            </span>
          )}
          {refreshError && (
            <span className="text-[10px] text-red-500" title={refreshError}>
              ⚠ {t("dash.refresh_failed")}
            </span>
          )}
          <button
            onClick={() => {
              setIsRefreshing(true);
              // Full page reload — fetches latest data AND picks up any deployed front-end changes
              window.location.reload();
            }}
            disabled={isRefreshing}
            className="inline-flex items-center gap-1 px-3 py-1 text-[10px] bg-white border border-gray-200 rounded-md hover:bg-gray-50 transition text-gray-600 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <svg
              className={`w-3 h-3 ${isRefreshing ? "animate-spin" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {isRefreshing ? t("dash.refreshing") : t("dash.refresh")}
          </button>
        </div>
      </div>

      <DockerStatusBanner onChange={(running) => running && loadData()} />

      {initialLoading && slowLoadSeconds !== null && (
        <PerfWarningBanner seconds={slowLoadSeconds} />
      )}

      {initialLoading ? (
        <LoadingState variant="card" label={t("common.loading_health")} />
      ) : (
        <SystemHealthPanel health={health} />
      )}

      {canDeploy && <DeployZone onDeployed={loadData} />}

      <div>
        <h2 className="text-sm font-semibold text-gray-900 mb-3">
          {t("dash.applications")} ({apps.length})
        </h2>
        {apps.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <svg className="w-8 h-8 mx-auto text-gray-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <p className="text-gray-400 text-xs">{t("dash.no_apps")}</p>
            {canDeploy && <p className="text-[10px] text-gray-400 mt-0.5">{t("dash.no_apps_hint")}</p>}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {apps.map((app) => (
              <AppCard key={app.id} app={app} userRole={user?.role || "viewer"} userId={user?.id} onRefresh={loadData} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
