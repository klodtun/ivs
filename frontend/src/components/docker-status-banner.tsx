"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

/**
 * Polls /system/docker/status periodically; when Docker is down it shows
 * a red banner with a "Start Docker" button. Admin-only — clicking the
 * button hits /system/docker/start which boots Docker Desktop / systemd
 * and waits up to 90s for the daemon to answer ping.
 */
export function DockerStatusBanner({ onChange }: { onChange?: (running: boolean) => void }) {
  const { t } = useLang();
  const [running, setRunning] = useState<boolean | null>(null);
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const u = localStorage.getItem("user");
      if (u) setIsAdmin(JSON.parse(u).role === "admin");
    } catch {}
  }, []);

  // Stable callback ref — parents pass inline arrow functions for
  // `onChange`, which get a new identity every render. Without a ref,
  // each parent re-render triggers useEffect cleanup + re-schedule +
  // an immediate `check()` call → API hammer at parent-render rate
  // instead of every 30s.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const check = useCallback(async () => {
    try {
      const r = await api.dockerStatus();
      setRunning(r.running);
      onChangeRef.current?.(r.running);
    } catch {
      setRunning(false);
      onChangeRef.current?.(false);
    }
  }, []); // empty deps — check is stable forever

  useEffect(() => {
    check();
    // Poll every 30s — Docker daemon status changes rarely; faster
    // polling just wastes API calls and CPU.
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, [check]);

  const handleStart = async () => {
    setStarting(true);
    setMessage(t("docker.starting"));
    try {
      const r = await api.dockerStart();
      setMessage(r.message || (r.ready ? t("docker.ready") : t("docker.start_failed")));
      if (r.ready) {
        setRunning(true);
        onChange?.(true);
      }
    } catch (e: any) {
      setMessage(e?.message || t("docker.start_failed"));
    } finally {
      setStarting(false);
      // Re-poll after attempt
      setTimeout(check, 2000);
    }
  };

  if (running === null || running === true) return null;

  return (
    <div className="bg-red-50 border border-red-300 rounded-lg p-3 flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
        <span className="text-base">🐳</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-red-800">{t("docker.banner_title")}</p>
        <p className="text-[10px] text-red-700 mt-0.5">
          {message || t("docker.banner_desc")}
        </p>
      </div>
      {isAdmin && (
        <button
          onClick={handleStart}
          disabled={starting}
          className="flex-shrink-0 px-3 py-1.5 bg-red-600 text-white text-[11px] font-semibold rounded-md hover:bg-red-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {starting ? t("docker.starting_btn") : t("docker.start_btn")}
        </button>
      )}
    </div>
  );
}
