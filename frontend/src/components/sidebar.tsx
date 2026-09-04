"use client";
import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useLang } from "@/components/lang-provider";
import { LangToggle } from "@/components/lang-toggle";
import { User } from "@/types";
import { isEnabled } from "@/lib/features";
import { api } from "@/lib/api";
import { customPages } from "@/custom/pages";

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
    labelKey: "nav.settings",
    href: "/dashboard/settings",
    icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
    roles: ["admin"],
  },
  {
    labelKey: "nav.consulting",
    href: "/dashboard/consulting",
    icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
    roles: ["admin", "developer", "viewer"],
  },
];

export function Sidebar({ user }: { user: User | null }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale } = useLang();
  const [shutdownConfirm, setShutdownConfirm] = useState(false);
  const [shutdownWorking, setShutdownWorking] = useState(false);
  // Current LAN IP shown top-left so people always have the right address
  // even when DHCP changes it and mDNS is off.
  const [lanIp, setLanIp] = useState<string>("");
  // โมดูลที่เป็นการสาธิต — รุ่นย่อยมี แต่ใบอนุญาตยังไม่ถึง
  const [demoModules, setDemoModules] = useState<string[]>([]);
  // เมนูที่กล่องนี้ควรแสดง มาจากหลังบ้าน ไม่ใช่หน้าจอตัดสินเอง
  //
  // ผลิตภัณฑ์สามตัว (iVS ฟรี · โรงพยาบาล · e-Contract) ต่างกันที่ชุดเมนู
  // ทางเลือกอีกทางคือแยกสาขาโค้ดแล้วตัดเมนูด้วยมือ ซึ่งจะได้หลายสายที่ต้องซิงก์
  // กันเอง และทำให้ file_baselines วัดอะไรไม่ได้ เพราะมันวัดจากรุ่นที่ปล่อยซึ่ง
  // ต้องมีสายเดียว
  //
  // null = ยังไม่รู้ → แสดงตามสิทธิ์ไปก่อน ไม่ใช่ซ่อนทั้งหมด เพราะแถบเมนูที่ว่าง
  // เปล่าตอนโหลดอ่านเหมือนระบบพัง
  const [visibleMenus, setVisibleMenus] = useState<string[] | null>(null);
  const [menuLabels, setMenuLabels] = useState<Record<string, { th: string; en: string }>>({});
  const [lanUrl, setLanUrl] = useState<string>("");
  const [ipChanged, setIpChanged] = useState(false);
  const [ipCopied, setIpCopied] = useState(false);

  useEffect(() => {
    if (!user) return;
    let stop = false;
    const check = async () => {
      try {
        api.getModules()
        .then((m) => {
          setDemoModules(m.demo_only || []);
          setVisibleMenus(m.visible_menus || null);
          setMenuLabels(m.menu_labels || {});
        })
        .catch(() => setDemoModules([]));
      const r = await api.getLanIp();
        if (stop) return;
        setLanIp(r.ip);
        setLanUrl(r.url);
        const prev = localStorage.getItem("ivs_last_lan_ip");
        if (prev && prev !== r.ip) setIpChanged(true);
        localStorage.setItem("ivs_last_lan_ip", r.ip);
      } catch {}
    };
    check();
    const id = setInterval(check, 60000); // re-check every 60s
    return () => { stop = true; clearInterval(id); };
  }, [user]);

  const copyIp = () => {
    navigator.clipboard?.writeText(lanUrl || lanIp).then(() => {
      setIpCopied(true);
      setIpChanged(false);
      setTimeout(() => setIpCopied(false), 1500);
    }).catch(() => {});
  };

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

  // เมนูไหนคือโมดูลไหน — ใช้ตัดสินว่าต้องติดป้ายสาธิตหรือไม่
  const MODULE_OF_HREF: Record<string, string> = {
    "/dashboard/bridge": "opencli",
    "/dashboard/econtract": "econtract",
    "/dashboard/system-map": "system_map",
    "/dashboard/flows": "flows",
    "/dashboard/design-controls": "iso13485",
  };

  const filteredNav = navItems.filter(
    (item) =>
      user &&
      item.roles.includes(user.role) &&
      // Hide entries gated behind a feature flag that's off in this release
      (!("featureFlag" in item) || isEnabled(item.featureFlag as any)) &&
      // และเมนูที่รุ่นย่อยนี้ไม่มี
      (visibleMenus === null || visibleMenus.includes(item.href))
  );

  // เมนูที่ลูกค้าประกาศไว้ในเขตของตัวเอง — ต่อท้ายของแกนเสมอ
  //
  // ก่อนหน้านี้การเพิ่มเมนูต้องแก้ไฟล์นี้ ซึ่งการอัปเกรดเขียนทับ ทำให้งานที่
  // ลูกค้าเพิ่มหายทุกครั้งที่อัปเดต แล้วบทเรียนที่เขาได้คือ "อย่าอัปเดต" ซึ่ง
  // อันตรายกว่าเมนูหาย เพราะเครื่องที่ไม่อัปเดตคือเครื่องที่ไม่ได้รับการแก้
  // ช่องโหว่ รายการจึงมาจาก custom/pages.ts ที่การอัปเกรดไม่แตะ
  //
  // roles ที่นี่ซ่อนเมนูเท่านั้น ไม่ใช่การกันสิทธิ์ — หน้าที่ซ่อนไว้ยังเปิดตรง
  // ด้วย URL ได้ การกันจริงต้องอยู่ที่ router ฝั่งหลังบ้าน
  const customNav = (user
    ? customPages.filter((p) => p.roles.includes(user.role as any))
    : []
  ).map((p) => ({
    labelKey: "",
    label: locale === "th" ? p.labelTh : p.labelEn,
    href: `/dashboard/custom/${p.slug}`,
    icon:
      p.icon ||
      "M11 4a1 1 0 011-1h.01a1 1 0 010 2H12a1 1 0 01-1-1zM4 7h16M4 12h16M4 17h10",
    roles: p.roles,
  }));

  // แกนกับเขตลูกค้าใช้รูปเดียวกันตอน render — ปุ่มไม่ต้องรู้ว่าเมนูมาจากไหน
  const allNav = [
    ...filteredNav.map((i) => ({
      href: i.href,
      icon: i.icon,
      label:
        menuLabels[i.href]?.[locale === "th" ? "th" : "en"] || t(i.labelKey),
      demo: demoModules.includes(MODULE_OF_HREF[i.href] || ""),
    })),
    ...customNav.map((i) => ({ href: i.href, icon: i.icon, label: i.label, demo: false })),
  ];

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
          <img src="/ivs-logo.png" alt="iVS" className="w-8 h-8 rounded-lg object-contain" />
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

        {/* Current LAN IP — click to copy. Highlights if it changed since
            last seen (DHCP moved it) so users update their bookmark. */}
        {lanIp && (
          <button
            onClick={copyIp}
            title={t("nav.lan_ip_tooltip")}
            className={cn(
              "mt-2 w-full flex items-center gap-1.5 px-2 py-1 rounded-md border transition text-left",
              ipChanged
                ? "bg-amber-50 border-amber-300 hover:bg-amber-100"
                : "bg-gray-50 border-gray-200 hover:bg-gray-100"
            )}
          >
            <svg className="w-3 h-3 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z" />
            </svg>
            <span className="flex-1 min-w-0">
              <span className="block text-[9px] text-gray-400 leading-none">
                {ipChanged ? t("nav.lan_ip_changed") : t("nav.lan_ip")}
              </span>
              <span className="block font-mono text-[11px] text-gray-800 truncate leading-tight">{lanIp}</span>
            </span>
            <span className="text-[9px] text-gray-400 flex-shrink-0">
              {ipCopied ? "✓" : "⧉"}
            </span>
          </button>
        )}
      </div>

      <nav className="flex-1 p-2 space-y-0.5">
        {allNav.map((item) => {
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
              <span className="flex-1 text-left truncate">{item.label}</span>
              {item.demo && (
                <span
                  title={
                    locale === "th"
                      ? "โมดูลสาธิต — ต้องมีใบอนุญาต Pro ขึ้นไปจึงใช้งานจริงได้"
                      : "Demonstration module — needs a Pro licence to run for real"
                  }
                  className="text-[8px] font-medium px-1 py-px rounded bg-amber-100 text-amber-700 flex-shrink-0"
                >
                  {locale === "th" ? "สาธิต" : "DEMO"}
                </span>
              )}
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
            className="w-full text-left text-[10px] text-gray-500 hover:text-red-600 px-1.5 py-1 rounded-md hover:bg-red-50 transition"
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
                "w-full text-left text-[10px] mt-1 px-1.5 py-1 rounded-md transition disabled:opacity-50",
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
