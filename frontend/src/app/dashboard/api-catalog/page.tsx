"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Legacy /dashboard/api-catalog route — preserved for deep links.
 * v1.0.2: API Catalog merged into the Vault page as a tab.
 */
export default function ApiCatalogRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard/vault?tab=programs");
  }, [router]);
  return (
    <div className="text-xs text-gray-400 p-8 text-center animate-pulse">
      Redirecting to Vault...
    </div>
  );
}
