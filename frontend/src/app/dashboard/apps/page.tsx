"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { AppCard } from "@/components/app-card";
import { DeployZone } from "@/components/deploy-zone";
import { DockerStatusBanner } from "@/components/docker-status-banner";
import { LoadingState, PerfWarningBanner } from "@/components/loading-state";
import { App, User } from "@/types";

export default function AppsPage() {
  const { t } = useLang();
  const [apps, setApps] = useState<App[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [selectedApp, setSelectedApp] = useState<number | null>(null);
  const [logs, setLogs] = useState<string>("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [slowSec, setSlowSec] = useState<number | null>(null);

  const loadApps = useCallback(async () => {
    try { setApps(await api.getApps()); } catch (e) { console.error(e); }
    finally { setInitialLoading(false); }
  }, []);

  useEffect(() => {
    const start = Date.now();
    const t = setTimeout(() => {
      if (initialLoading) setSlowSec(Math.round((Date.now() - start) / 1000));
    }, 5000);
    return () => clearTimeout(t);
  }, [initialLoading]);

  useEffect(() => {
    const stored = localStorage.getItem("user");
    if (stored) setUser(JSON.parse(stored));
    loadApps();
  }, [loadApps]);

  const loadLogs = async (appId: number) => {
    setSelectedApp(appId);
    try { const data = await api.getAppLogs(appId); setLogs(data.logs); } catch (e: any) { setLogs(`Error: ${e.message}`); }
  };

  const filtered = apps.filter((app) => {
    if (filter !== "all" && app.status !== filter) return false;
    if (search && !app.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const canDeploy = user && (user.role === "admin" || user.role === "developer");
  const filterKeys: Record<string, string> = { all: "apps.filter.all", running: "apps.filter.running", stopped: "apps.filter.stopped", building: "apps.filter.building", error: "apps.filter.error" };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold text-gray-900">{t("apps.title")}</h1>
        <p className="text-gray-500 text-[10px] mt-0.5">{t("apps.subtitle")}</p>
      </div>

      <DockerStatusBanner onChange={(running) => running && loadApps()} />

      {canDeploy && <DeployZone onDeployed={loadApps} />}

      <div className="flex gap-2 items-center flex-wrap">
        <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder={t("apps.search")}
          className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs flex-1 min-w-[150px] focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
        <div className="flex gap-1">
          {Object.entries(filterKeys).map(([f, key]) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-2 py-1 text-[10px] rounded-full font-medium transition ${filter === f ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
              {t(key)}
            </button>
          ))}
        </div>
      </div>

      {initialLoading && slowSec !== null && <PerfWarningBanner seconds={slowSec} />}

      {initialLoading ? (
        <LoadingState variant="card" label={t("common.loading_apps")} />
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-400 text-xs">{t("apps.no_match")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filtered.map((app) => (
            <div key={app.id}>
              <AppCard app={app} userRole={user?.role || "viewer"} userId={user?.id} onRefresh={loadApps} />
              {canDeploy && (
                <button onClick={() => selectedApp === app.id ? setSelectedApp(null) : loadLogs(app.id)}
                  className="w-full mt-0.5 text-[9px] text-gray-400 hover:text-gray-600 py-0.5">
                  {selectedApp === app.id ? t("app.hide_logs") : t("app.logs")}
                </button>
              )}
              {selectedApp === app.id && (
                <div className="mt-1 bg-gray-900 text-green-400 rounded-md p-2 text-[10px] font-mono max-h-32 overflow-auto whitespace-pre-wrap">
                  {logs || t("app.no_logs")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
