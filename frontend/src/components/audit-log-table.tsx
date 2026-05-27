"use client";
import { useState } from "react";
import { useLang } from "@/components/lang-provider";
import { cn, formatLegalTimestamp } from "@/lib/utils";
import { Pagination, usePagination } from "@/components/pagination";
import { AuditLogDetailModal } from "@/components/audit-log-detail-modal";
import type { AuditLog, User } from "@/types";

interface Props {
  logs: AuditLog[];
  users: User[];
}

export function AuditLogTable({ logs, users }: Props) {
  const { t } = useLang();
  const { paged, page, pageSize, setPage, setPageSize, total } = usePagination(logs, 25);
  const [selected, setSelected] = useState<AuditLog | null>(null);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <p className="text-[9px] text-gray-500 font-medium uppercase">
          {t("settings.log.title_compliance")}
        </p>
        <span className="text-[8px] px-1.5 py-px rounded bg-green-100 text-green-700 font-medium">
          {t("settings.log.compliance_badge")}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase">
            <tr>
              <th className="px-3 py-2 text-left">{t("settings.log.time")}</th>
              <th className="px-3 py-2 text-left">{t("settings.log.level")}</th>
              <th className="px-3 py-2 text-left">{t("settings.log.user")}</th>
              <th className="px-3 py-2 text-left">{t("settings.log.action")}</th>
              <th className="px-3 py-2 text-left">{t("settings.log.resource")}</th>
              <th className="px-3 py-2 text-left">{t("settings.log.details")}</th>
              <th className="px-3 py-2 text-left">IP</th>
              <th className="px-3 py-2 text-left">{t("settings.log.request_id")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {paged.map((log) => {
              const logUser = users.find((u) => u.id === log.user_id);
              const levelColor =
                log.log_level === "ERROR"
                  ? "bg-red-100 text-red-700"
                  : log.log_level === "WARNING"
                  ? "bg-amber-100 text-amber-700"
                  : log.log_level === "DEBUG"
                  ? "bg-purple-100 text-purple-700"
                  : "bg-blue-50 text-blue-700";
              const timeStr = formatLegalTimestamp(log.created_at);
              return (
                <tr
                  key={log.id}
                  className={cn(
                    "hover:bg-gray-50",
                    log.log_level === "ERROR" && "bg-red-50/50",
                    log.log_level === "WARNING" && "bg-amber-50/30"
                  )}
                >
                  <td
                    className="px-3 py-2 text-gray-600 text-[9px] font-mono whitespace-nowrap"
                    title={t("settings.log.time_tooltip")}
                  >
                    {timeStr}
                  </td>
                  <td className="px-3 py-2">
                    <span className={cn("text-[8px] px-1.5 py-px rounded font-bold", levelColor)}>
                      {log.log_level || "INFO"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "text-[9px] px-1.5 py-px rounded-full font-medium",
                        logUser?.role === "admin"
                          ? "bg-red-100 text-red-700"
                          : logUser?.role === "developer"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-gray-100 text-gray-600"
                      )}
                    >
                      {log.username || logUser?.username || (log.user_id ? `#${log.user_id}` : "-")}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-[9px] px-1.5 py-px rounded bg-gray-100 text-gray-700 font-mono">
                      {log.action}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-600 text-[9px]">
                    {log.resource_type}
                    {log.resource_id && <span className="text-gray-400">#{log.resource_id}</span>}
                  </td>
                  {/*
                    Clickable details cell — opens a richer modal with the
                    full record (User-Agent, NTP source, session id, etc.)
                    without changing the visible row size. Keyboard-
                    accessible via tabindex + Enter/Space.
                  */}
                  <td
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelected(log)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(log);
                      }
                    }}
                    className="px-3 py-2 text-gray-500 text-[9px] max-w-[200px] truncate cursor-pointer hover:text-brand-700 hover:underline focus:outline-none focus:ring-1 focus:ring-brand-400 rounded"
                    title={t("settings.log.details_click")}
                  >
                    {log.details || <span className="text-gray-300 italic">{t("settings.log.no_detail")}</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-400 text-[8px] font-mono">
                    {log.ip_address || "-"}
                  </td>
                  <td
                    className="px-3 py-2 text-gray-400 text-[8px] font-mono"
                    title={`Request: ${log.request_id || "-"}\nSession: ${log.session_id || "-"}\nUA: ${log.user_agent || "-"}`}
                  >
                    {log.request_id ? log.request_id.slice(0, 8) : "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Pagination
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        itemLabel={t("settings.log.item_label")}
      />

      {logs.length === 0 && (
        <div className="p-8 text-center text-gray-400 text-xs">{t("settings.no_logs")}</div>
      )}

      {/* Detail modal — full record on demand, table size unchanged */}
      {selected && (
        <AuditLogDetailModal
          log={selected}
          user={users.find((u) => u.id === selected.user_id)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
