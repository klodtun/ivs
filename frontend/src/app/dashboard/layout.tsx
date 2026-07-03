"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { RouteLoader } from "@/components/route-loader";
import { api } from "@/lib/api";
import { User } from "@/types";
import { useLang } from "@/components/lang-provider";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.replace("/login");
      return;
    }
    const stored = localStorage.getItem("user");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
        return;
      } catch {}
    }
    // Token present but user cache missing/corrupt — repopulate from /me.
    // Without this the sidebar renders empty because navItems are
    // filtered by user.role.
    api.getMe()
      .then((u) => {
        localStorage.setItem("user", JSON.stringify(u));
        setUser(u);
      })
      .catch(() => {
        localStorage.removeItem("token");
        router.replace("/login");
      });
  }, [router]);

  return (
    <div className="flex min-h-screen">
      <RouteLoader />
      <Sidebar user={user} />
      <main className="flex-1 overflow-auto flex flex-col">
        <div className="p-4 max-w-6xl mx-auto flex-1 w-full">{children}</div>
        <CopyrightFooter />
      </main>
    </div>
  );
}

function CopyrightFooter() {
  const { t } = useLang();
  return (
    <footer className="text-center text-[10px] text-gray-400 py-3 border-t border-gray-100 mt-4 select-none">
      {t("copyright.footer")}
    </footer>
  );
}
