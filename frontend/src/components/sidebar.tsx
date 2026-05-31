"use client";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useLang } from "@/components/lang-provider";
import { LangToggle } from "@/components/lang-toggle";
import { User } from "@/types";
import { isEnabled } from "@/lib/features";
import { api } from "@/lib/api";

const navItems = [
  {
    labelKey: "nav.dashboard",
    href: "/dashboard",
    icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
    roles: ["admin", "developer"],
  },
  {
    labelKey: "nav.apps",
    href: "/dashboard/apps",
    icon: "M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4",
    roles: ["admin", "developer", "viewer"],
  },
  {
    labelKey: "nav.tunnels",
    href: "/dashboard/tunnels",
    icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
    roles: ["admin", "developer"],
  },
  {
    labelKey: "nav.vault",
    href: "/dashboard/vault",
    icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
    roles: ["admin", "developer"],
  },
  {
    labelKey: "nav.resources",
    href: "/dashboard/resources",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    roles: ["admin"],
  },
  {
    labelKey: "nav.api_catalog",
    href: "/dashboard/api-catalog",
    icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    roles: ["admin", "developer", "viewer"],
    featureFlag: "api_catalog" as const,
  },
  {
    labelKey: "nav.settings",
    href: "/dashboard/settings",
    icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
    roles: ["admin"],
  },
];

export function Sidebar({ user }: { user: User | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useLang();
  const [shutdownConfirm, setShutdownConfirm] = useState(false);
  const [shutdownWorking, setShutdownWorking] = useState(false);

  const handleShutdown = async () => {
    if (!shutdownConfirm) { setShutdownConfirm(true); return; }
    setShutdownWorking(true);
    try {
      await api.shutdownIvs();
      // Backend kills both ports 2s after returning; close tab.
      setTimeout(() => {
        try { window.close(); } catch {}
        // Fallback: navigate to about:blank so user sees something neutral
        // if the browser refuses to close a tab it didn't open via script.
        try { window.location.href = "about:blank"; } catch {}
      }, 2500);
    } catch (e: any) {
      alert(e?.message || "Shutdown failed");
      setShutdownWorking(false);
      setShutdownConfirm(false);
    }
  };

  const filteredNav = navItems.filter(
    (item) =>
      user &&
      item.roles.includes(user.role) &&
      // Hide entries gated behind a feature flag that's off in this release
      (!("featureFlag" in item) || isEnabled(item.featureFlag as any))
  );

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  const roleBadgeColor: Record<string, string> = {
    admin: "bg-red-100 text-red-700",
    developer: "bg-blue-100 text-blue-700",
    viewer: "bg-gray-100 text-gray-600",
  };

  const roleKey: Record<string, string> = {
    admin: "role.admin",
    developer: "role.developer",
    viewer: "role.viewer",
  };

  return (
    <aside className="w-52 bg-white border-r border-gray-200 flex flex-col min-h-screen text-xs">
      <div className="p-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <img src="/ivs-logo.png" alt="IVS" className="w-8 h-8 rounded-lg object-contain" />
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-gray-900 text-xs leading-tight">
              Vibe Server
            </h2>
            <p className="text-[10px] text-gray-400 leading-tight">
              {t("nav.subtitle")}
            </p>
          </div>
          <LangToggle compact />
        </div>
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {filteredNav.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <button
              key={item.href}
              onClick={() => router.push(item.href)}
              className={cn(
                "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs transition-all",
                active
                  ? "bg-brand-50 text-brand-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              )}
            >
              <svg
                className="w-3.5 h-3.5 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d={item.icon}
                />
              </svg>
              {t(item.labelKey)}
            </button>
          );
        })}
      </nav>

      {user && (
        <div className="p-3 border-t border-gray-100">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-[10px] font-medium">
              {user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-900 truncate">
                {user.username}
              </p>
              <span
                className={cn(
                  "text-[9px] px-1 py-px rounded-full font-medium",
                  roleBadgeColor[user.role] || "bg-gray-100 text-gray-600"
                )}
              >
                {t(roleKey[user.role] || "role.viewer")}
              </span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-left text-[10px] text-gray-500 hover:text-red-600 px-1.5 py-1 rounded hover:bg-red-50 transition"
          >
            {t("nav.signout")}
          </button>

          {/* Shutdown IVS — admin only. Confirm-then-fire pattern: first
              click flips the label to red "ยืนยันปิด IVS"; second click
              hits the endpoint and closes the tab. */}
          {user.role === "admin" && (
            <button
              onClick={handleShutdown}
              disabled={shutdownWorking}
              className={cn(
                "w-full text-left text-[10px] mt-1 px-1.5 py-1 rounded transition disabled:opacity-50",
                shutdownConfirm
                  ? "bg-red-600 text-white hover:bg-red-700 font-semibold"
                  : "text-gray-500 hover:text-red-600 hover:bg-red-50"
              )}
              title={t("nav.shutdown_tooltip")}
            >
              {shutdownWorking
                ? `⏻ ${t("nav.shutdown_working")}`
                : shutdownConfirm
                ? `⚠ ${t("nav.shutdown_confirm")}`
                : `⏻ ${t("nav.shutdown")}`}
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
