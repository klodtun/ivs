"use client";
import { useLang } from "@/components/lang-provider";
import { formatLegalTimestamp } from "@/lib/utils";
import { Pagination, usePagination } from "@/components/pagination";
import type { AuditLogExport } from "@/types";

interface Props {
  exports: AuditLogExport[];
  onDownload: (id: number) => void;
}

export function ExportHistoryTable({ exports, onDownload }: Props) {
  const { t } = useLang();
  const { paged, page, pageSize, setPage, setPageSize, total } = usePagination(exports, 10);

  if (exports.length === 0) {
    return (
      <p className="text-[10px] text-gray-400 text-center py-2">
        {t("settings.export_no_history")}
      </p>
    );
  }

  const fmtRangeBound = (s: string | null) =>
    s
      ? new Date(s).toLocaleDateString(undefined, {
          day: "2-digit",
          month: "short",
          year: "numeric",
        })
      : "—";

  return (
    <div className="overflow-hidden rounded-md border border-gray-100">
      <table className="w-full text-[10px]">
        <thead className="bg-gray-50 text-gray-500 text-[8px] uppercase">
          <tr>
            <th className="px-2 py-1.5 text-left">{t("settings.export_filename")}</th>
            <th className="px-2 py-1.5 text-left">{t("settings.export_range_col")}</th>
            <th className="px-2 py-1.5 text-center">{t("settings.export_records")}</th>
            <th className="px-2 py-1.5 text-center">{t("settings.export_files_col")}</th>
            <th className="px-2 py-1.5 text-left">{t("settings.export_hash")}</th>
            <th className="px-2 py-1.5 text-left whitespace-nowrap">{t("settings.export_date")}</th>
            <th className="px-2 py-1.5 text-right"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {paged.map((exp) => {
            const rangeLabel =
              !exp.start_date && !exp.end_date
                ? t("settings.export_range_all_label")
                : `${fmtRangeBound(exp.start_date)} → ${fmtRangeBound(exp.end_date)}`;
            return (
              <tr key={exp.id} className="hover:bg-gray-50">
                <td className="px-2 py-1.5 font-mono text-gray-700 max-w-[180px] truncate" title={exp.filename}>
                  {exp.filename}
                </td>
                <td className="px-2 py-1.5 text-gray-600">{rangeLabel}</td>
                <td className="px-2 py-1.5 text-center text-gray-600">{exp.record_count.toLocaleString()}</td>
                <td className="px-2 py-1.5 text-center text-gray-600">{exp.file_count || 1}</td>
                <td
                  className="px-2 py-1.5 font-mono text-gray-500 max-w-[140px] truncate"
                  title={exp.sha256_hash}
                >
                  {exp.sha256_hash.substring(0, 16)}…
                </td>
                {/* Legal-grade timestamp — full ISO + UTC offset, no relative time */}
                <td
                  className="px-2 py-1.5 text-gray-600 font-mono text-[9px] whitespace-nowrap"
                  title={t("settings.export_date_tooltip")}
                >
                  {formatLegalTimestamp(exp.created_at)}
                </td>
                <td className="px-2 py-1.5 text-right">
                  <button
                    onClick={() => onDownload(exp.id)}
                    className="text-brand-600 hover:text-brand-700 font-medium"
                  >
                    {t("settings.export_download")}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Pagination
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        itemLabel={t("settings.export_history_item_label")}
      />
    </div>
  );
}
