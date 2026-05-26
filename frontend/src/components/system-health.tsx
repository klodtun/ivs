"use client";
import { cn, formatBytes } from "@/lib/utils";
import { useLang } from "@/components/lang-provider";
import { SystemHealth } from "@/types";

function CircularGauge({
  value,
  label,
  detail,
  color,
}: {
  value: number;
  label: string;
  detail: string;
  color: string;
}) {
  const circumference = 2 * Math.PI * 40;
  const strokeDashoffset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-16 h-16">
        <svg className="w-16 h-16 -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="40" fill="none" stroke={color} strokeWidth="8"
            strokeLinecap="round" strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset} className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold text-gray-900">{Math.round(value)}%</span>
        </div>
      </div>
      <p className="mt-1 text-xs font-medium text-gray-700">{label}</p>
      <p className="text-[10px] text-gray-400">{detail}</p>
    </div>
  );
}

function StatusDot({ active, label }: { active: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1">
      <span className={cn("w-1.5 h-1.5 rounded-full", active ? "bg-green-500 animate-pulse" : "bg-red-400")} />
      <span className="text-[10px] text-gray-600">{label}</span>
    </div>
  );
}

export function SystemHealthPanel({ health }: { health: SystemHealth | null }) {
  const { t } = useLang();

  if (!health) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="animate-pulse flex gap-6 justify-center">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-16 h-16 bg-gray-100 rounded-full" />
          ))}
        </div>
      </div>
    );
  }

  const cpuColor = health.cpu_percent > 80 ? "#ef4444" : health.cpu_percent > 50 ? "#f59e0b" : "#22c55e";
  const memColor = health.memory_percent > 80 ? "#ef4444" : health.memory_percent > 50 ? "#f59e0b" : "#22c55e";
  const diskColor = health.disk_percent > 80 ? "#ef4444" : health.disk_percent > 50 ? "#f59e0b" : "#22c55e";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 text-sm">{t("dash.health")}</h3>
        <div className="flex gap-3">
          <StatusDot active={health.docker_running} label={t("health.docker")} />
          <StatusDot active={health.dns_running} label={t("health.dns")} />
          <div className="text-[10px] text-gray-500">
            {t("dash.apps_count")}: {health.apps_running}/{health.apps_total}
          </div>
        </div>
      </div>
      <div className="flex justify-around">
        <CircularGauge value={health.cpu_percent} label={t("health.cpu")} detail={`${health.cpu_percent.toFixed(1)}%`} color={cpuColor} />
        <CircularGauge value={health.memory_percent} label={t("health.ram")} detail={`${formatBytes(health.memory_used)} / ${formatBytes(health.memory_total)}`} color={memColor} />
        <CircularGauge value={health.disk_percent} label={t("health.storage")} detail={`${formatBytes(health.disk_used)} / ${formatBytes(health.disk_total)}`} color={diskColor} />
      </div>
    </div>
  );
}
