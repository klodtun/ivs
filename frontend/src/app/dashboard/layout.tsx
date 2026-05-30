"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { RouteLoader } from "@/components/route-loader";
import { User } from "@/types";

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
    if (stored) setUser(JSON.parse(stored));
  }, [router]);

  return (
    <div className="flex min-h-screen">
      <RouteLoader />
      <Sidebar user={user} />
      <main className="flex-1 overflow-auto">
        <div className="p-4 max-w-6xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
