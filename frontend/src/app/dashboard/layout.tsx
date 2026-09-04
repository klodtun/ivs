"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
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
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  // หน้าที่กินความกว้างเต็ม — แผนที่ระบบวาดเส้นเชื่อมระหว่างการ์ด การบีบให้อยู่
  // ในคอลัมน์กลางทำให้ต้องเลื่อนแนวนอนเพื่อดูให้ครบ ซึ่งขัดกับจุดประสงค์ของ
  // แผนที่ หน้าอื่นเป็นข้อความและตาราง จึงยังอ่านง่ายกว่าเมื่อจำกัดความกว้าง
  const fullBleed = pathname?.startsWith("/dashboard/system-map");

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
        <div className={fullBleed ? "flex-1 w-full" : "p-4 max-w-6xl mx-auto flex-1 w-full"}>
          {children}
        </div>
        {!fullBleed && <CopyrightFooter />}
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
