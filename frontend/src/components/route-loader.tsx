"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

/**
 * Slim top progress bar that animates on every route change. Picks up
 * the perceived gap between clicking a sidebar item and the new page
 * finishing its initial data fetch. Pure CSS — no external lib.
 */
export function RouteLoader() {
  const pathname = usePathname();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    setVisible(true);
    setProgress(15);
    // Climb steeply, then crawl — fakes network progress
    const t1 = window.setTimeout(() => setProgress(45), 100);
    const t2 = window.setTimeout(() => setProgress(75), 400);
    const t3 = window.setTimeout(() => setProgress(92), 1200);
    // Finalize after page should have settled
    const t4 = window.setTimeout(() => setProgress(100), 1800);
    const t5 = window.setTimeout(() => { setVisible(false); setProgress(0); }, 2100);

    return () => {
      [t1, t2, t3, t4, t5].forEach(clearTimeout);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [pathname]);

  if (!visible) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] h-0.5 bg-transparent pointer-events-none">
      <div
        className="h-full bg-gradient-to-r from-brand-500 to-brand-700 shadow-[0_0_8px_rgba(109,92,184,0.6)] transition-all duration-300 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
