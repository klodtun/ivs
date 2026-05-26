"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { SystemHealthPanel } from "@/components/system-health";
import { AppCard } from "@/components/app-card";
import { DeployZone } from "@/components/deploy-zone";
import { App, SystemHealth, User } from "@/types";

export default function DashboardPage() {
  const { t } = useLang();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [apps, setApps] = useState<App[]>([]);
  const [user, setUser] = useState<User | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [h, a] = await Promise.all([api.getSystemHealth(), api.getApps()]);
      setHealth(h);
      setApps(a);
    } catch (e) {
      console.error("Failed to load dashboard data", e);
    }
  }, []);

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{t("dash.title")}</h1>
          <p className="text-gray-500 text-[10px] mt-0.5">{t("dash.subtitle")}</p>
        </div>
        <button onClick={loadData}
          className="px-3 py-1 text-[10px] bg-white border border-gray-200 rounded-md hover:bg-gray-50 transition text-gray-600">
          {t("dash.refresh")}
        </button>
      </div>

      <SystemHealthPanel health={health} />

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
              <AppCard key={app.id} app={app} userRole={user?.role || "viewer"} onRefresh={loadData} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
