"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { useLang } from "@/components/lang-provider";
import { SystemHealthPanel } from "@/components/system-health";
import { OverviewCards } from "@/components/overview-cards";
import { AppOverviewCards } from "@/components/app-overview-cards";
import { DockerStatusBanner } from "@/components/docker-status-banner";
import { LoadingState, PerfWarningBanner } from "@/components/loading-state";
import { SystemHealth, User } from "@/types";
import { SystemOverview } from "@/lib/api";
import { PageHeader } from "@/components/ui";

export default function DashboardPage() {
  const { t } = useLang();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [overview, setOverview] = useState<SystemOverview | null>(null);
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
      // ไม่ดึงรายการแอปอีกแล้ว — การ์ดแอปย้ายไปหน้าแอปพลิเคชันทั้งหมด
      // หน้านี้ตอบว่า "มีอะไรที่ควรรู้" ไม่ใช่ "มีแอปอะไรบ้าง"
      const [h, o] = await Promise.all([api.getSystemHealth(), api.getSystemOverview()]);
      setHealth(h);
      setOverview(o);
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
          <PageHeader title={t("dash.title")} help={t("dash.subtitle")} />
        </div>
        <div className="flex items-center gap-2">
          {lastRefresh && !refreshError && (
            <span className="text-[10px] text-gray-400">
              {t("dash.last_updated")}: {formatTime(lastRefresh)}
            </span>
          )}
          {refreshError && (
            <span className="text-[10px] text-red-500" title={refreshError}>
               {t("dash.refresh_failed")}
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

      {/* สี่มุมมอง — ตอบว่ามีอะไรที่ควรรู้ แล้วส่งต่อไปหน้าที่แก้ได้จริง
          ไม่มีการ์ดแอปและไม่มีช่องดีพลอยที่นี่ ทั้งสองอย่างคือการลงมือ ซึ่งเป็น
          หน้าที่ของหน้าแอปพลิเคชัน หน้านี้มีไว้สังเกต */}
      {initialLoading ? (
        <LoadingState variant="card" label={t("common.loading")} />
      ) : overview ? (
        <OverviewCards data={overview} />
      ) : null}

      {/* การ์ดเฉพาะแอปที่ผู้ดูแลเลือกเอง — ต่อจากหกใบที่เป็นภาพรวมทั้งระบบ */}
      {!initialLoading && <AppOverviewCards canAdd={!!canDeploy} />}

      <p className="text-[10px] text-gray-400">
        {t("ov.apps_moved")}{" "}
        <Link href="/dashboard/apps" className="text-brand-600 hover:underline">
          {t("dash.applications")}
        </Link>
      </p>

    </div>
  );
}
