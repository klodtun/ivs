"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, timeRemaining } from "@/lib/utils";
import { Tunnel, App } from "@/types";
import { Pagination, usePagination } from "@/components/pagination";
import PrivacyNoticePopup from "@/components/privacy-notice-popup";
import { TunnelShareModal } from "@/components/tunnel-share-modal";

const durationOptions = [
  { value: 1, labelKey: "tunnel.dur.1m" },
  { value: 10, labelKey: "tunnel.dur.10m" },
  { value: 60, labelKey: "tunnel.dur.1h" },
  { value: 180, labelKey: "tunnel.dur.3h" },
  { value: 1440, labelKey: "tunnel.dur.24h" },
];

export default function TunnelsPage() {
  const { t } = useLang();
  const [tunnels, setTunnels] = useState<Tunnel[]>([]);
  const [apps, setApps] = useState<App[]>([]);
  const [selectedApp, setSelectedApp] = useState<number | null>(null);
  const [duration, setDuration] = useState(60);
  const [creating, setCreating] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  // PDPA — privacy notice review + tunnel-share-by-email modals
  const [privacyAppId, setPrivacyAppId] = useState<number | null>(null);
  const [shareTunnel, setShareTunnel] = useState<Tunnel | null>(null);
  const {
    paged: pagedTunnels,
    page: tunnelPage,
    pageSize: tunnelPageSize,
    setPage: setTunnelPage,
    setPageSize: setTunnelPageSize,
    total: tunnelTotal,
  } = usePagination(tunnels, 25);

  const loadData = useCallback(async () => {
    try {
      const [tu, ap] = await Promise.all([api.getTunnels(), api.getApps()]);
      setTunnels(tu);
      setApps(ap.filter((a: App) => a.status === "running"));
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadData(); const i = setInterval(loadData, 10000); return () => clearInterval(i); }, [loadData]);

  const handleCreate = async () => {
    if (!selectedApp) return;
    setCreating(true);
    try { await api.createTunnel(selectedApp, duration); await loadData(); } catch (e: any) { alert(e.message); } finally { setCreating(false); }
  };

  const handleRevoke = async (id: number) => {
    try { await api.revokeTunnel(id); await loadData(); } catch (e: any) { alert(e.message); }
  };

  const copyUrl = (tunnel: Tunnel) => {
    if (!tunnel.public_url) return;
    navigator.clipboard.writeText(tunnel.public_url).then(() => {
      setCopiedId(tunnel.id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  };

  const getAppName = (appId: number) => {
    const found = apps.find((a) => a.id === appId);
    if (found) return found.name;
    // If app not in running list, search all tunnels metadata
    return `App #${appId}`;
  };

  const getEffectiveStatus = (tunnel: Tunnel): string => {
    if (tunnel.status !== "active") return tunnel.status;
    // Check if time has actually expired
    const utcDate = tunnel.expires_at.endsWith("Z") || tunnel.expires_at.includes("+")
      ? tunnel.expires_at : tunnel.expires_at + "Z";
    if (new Date(utcDate).getTime() <= Date.now()) return "expired";
    return "active";
  };

  const statusStyles: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    expired: "bg-gray-100 text-gray-500",
    revoked: "bg-red-100 text-red-600",
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold text-gray-900">{t("tunnel.title")}</h1>
        <p className="text-gray-500 text-[10px] mt-0.5">{t("tunnel.subtitle")}</p>
      </div>

      {/* Create Tunnel */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 text-sm mb-3">{t("tunnel.create")}</h3>
        <div className="flex gap-2 items-end flex-wrap">
          <div className="flex-1 min-w-[150px]">
            <label className="block text-[10px] text-gray-600 mb-0.5">{t("tunnel.app_label")}</label>
            <select value={selectedApp || ""} onChange={(e) => setSelectedApp(Number(e.target.value) || null)}
              className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none">
              <option value="">{t("tunnel.app_select")}</option>
              {apps.map((app) => (<option key={app.id} value={app.id}>{app.name}</option>))}
            </select>
          </div>
          <div>
            <label className="block text-[10px] text-gray-600 mb-0.5">{t("tunnel.duration")}</label>
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}
              className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none">
              {durationOptions.map((d) => (<option key={d.value} value={d.value}>{t(d.labelKey)}</option>))}
            </select>
          </div>
          <button onClick={handleCreate} disabled={!selectedApp || creating}
            className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50">
            {creating ? t("tunnel.creating") : t("tunnel.open")}
          </button>
        </div>
      </div>

      {/* Tunnel List */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900 text-sm">{t("tunnel.active")}</h3>
        </div>
        {tunnels.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-xs">{t("tunnel.none")}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">{t("tunnel.col.app")}</th>
                  <th className="px-4 py-2 text-left">{t("tunnel.col.url")}</th>
                  <th className="px-4 py-2 text-center">{t("tunnel.col.status")}</th>
                  <th className="px-4 py-2 text-center">{t("tunnel.col.time")}</th>
                  <th className="px-4 py-2 text-right">{t("tunnel.col.action")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {pagedTunnels.map((tunnel) => {
                  const effectiveStatus = getEffectiveStatus(tunnel);
                  const isActive = effectiveStatus === "active";
                  const remaining = isActive ? timeRemaining(tunnel.expires_at) : "-";

                  return (
                    <tr key={tunnel.id} className={cn("hover:bg-gray-50", !isActive && "opacity-60")}>
                      <td className="px-4 py-2.5 font-medium text-gray-900">{getAppName(tunnel.app_id)}</td>
                      <td className="px-4 py-2.5">
                        {tunnel.public_url ? (
                          <div className="flex items-center gap-1.5">
                            <a href={tunnel.public_url} target="_blank" rel="noopener noreferrer"
                              className="text-brand-600 hover:underline truncate max-w-[300px]">
                              {tunnel.public_url}
                            </a>
                            {isActive && (
                              <button
                                onClick={() => copyUrl(tunnel)}
                                className={cn(
                                  "flex-shrink-0 p-1 rounded transition",
                                  copiedId === tunnel.id
                                    ? "bg-green-100 text-green-600"
                                    : "hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                                )}
                                title="Copy URL"
                              >
                                {copiedId === tunnel.id ? (
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                  </svg>
                                ) : (
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                  </svg>
                                )}
                              </button>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span className={cn("text-[9px] px-1.5 py-px rounded-full font-medium", statusStyles[effectiveStatus] || "bg-gray-100 text-gray-500")}>
                          {effectiveStatus}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center text-gray-600">
                        {isActive ? (
                          <span className="text-green-600 font-medium">{remaining}</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isActive && (
                          <div className="inline-flex items-center gap-1">
                            {/* 🛡️ Privacy notice — opens the same review popup
                                used by AppCard so the recipient (and sender)
                                can revisit their PDPA consent at any time. */}
                            <button
                              onClick={() => setPrivacyAppId(tunnel.app_id)}
                              title={t("tunnel.privacy_tooltip")}
                              className="text-[10px] text-gray-500 hover:text-purple-700 hover:bg-purple-50 px-1.5 py-0.5 rounded transition inline-flex items-center gap-0.5"
                            >
                              <span className="text-xs leading-none">🛡️</span>
                              <span className="hidden sm:inline">{t("tunnel.privacy")}</span>
                            </button>
                            {/* 📧 Share via email — opens TunnelShareModal
                                that pre-builds a PDPA-compliant message
                                (notice + URL + usage instructions + risk
                                warning) and hands it to the user's mail
                                client via mailto:. */}
                            <button
                              onClick={() => setShareTunnel(tunnel)}
                              title={t("tunnel.share_tooltip")}
                              className="text-[10px] text-gray-500 hover:text-brand-700 hover:bg-brand-50 px-1.5 py-0.5 rounded transition inline-flex items-center gap-0.5"
                            >
                              <span className="text-xs leading-none">📧</span>
                              <span className="hidden sm:inline">{t("tunnel.share")}</span>
                            </button>
                            <button
                              onClick={() => handleRevoke(tunnel.id)}
                              className="text-[10px] text-red-600 hover:text-red-700 font-medium hover:bg-red-50 px-2 py-0.5 rounded transition"
                            >
                              {t("tunnel.revoke")}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <Pagination
              total={tunnelTotal}
              page={tunnelPage}
              pageSize={tunnelPageSize}
              onPageChange={setTunnelPage}
              onPageSizeChange={setTunnelPageSize}
              itemLabel={t("tunnel.item_label")}
            />
          </div>
        )}
      </div>

      {/* 🛡️ Privacy Notice — review mode for the underlying app.
          Reuses the same popup AppCard uses, so consent flows through
          the same /api/pdpa/{id}/consent endpoint and the audit log. */}
      {privacyAppId !== null && (
        <PrivacyNoticePopup
          appId={privacyAppId}
          mode="review"
          onAccept={() => setPrivacyAppId(null)}
          onClose={() => setPrivacyAppId(null)}
        />
      )}

      {/* 📧 Share tunnel by email — composes the PDPA-compliant message
          and hands it to the user's mail client via mailto:. */}
      {shareTunnel && shareTunnel.public_url && (
        <TunnelShareModal
          tunnel={{
            id: shareTunnel.id,
            public_url: shareTunnel.public_url,
            expires_at: shareTunnel.expires_at,
            app_id: shareTunnel.app_id,
          }}
          appName={getAppName(shareTunnel.app_id)}
          onClose={() => setShareTunnel(null)}
        />
      )}
    </div>
  );
}
