"use client";
import { useMemo } from "react";
import { useLang } from "@/components/lang-provider";

interface Props {
  /** Total number of items (un-paginated). */
  total: number;
  /** Current 1-based page number. */
  page: number;
  /** How many items per page. */
  pageSize: number;
  /** Called when the user picks a new page. */
  onPageChange: (page: number) => void;
  /** Called when the user picks a new page size (optional — hides selector when omitted). */
  onPageSizeChange?: (size: number) => void;
  /** Available page-size options. Defaults to [10, 25, 50, 100]. */
  pageSizeOptions?: number[];
  /** Optional label for the items being paginated (e.g. "logs", "users"). */
  itemLabel?: string;
  /** Compact mode renders without the page-size selector and counts. */
  compact?: boolean;
}

/**
 * Build the list of page numbers to render, with ellipses around long ranges.
 * E.g. for current=7 of 20 → [1, '…', 5, 6, 7, 8, 9, '…', 20]
 */
function paginationRange(current: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const window = 1; // pages on each side of current
  const out: (number | "…")[] = [1];
  const start = Math.max(2, current - window);
  const end = Math.min(total - 1, current + window);
  if (start > 2) out.push("…");
  for (let i = start; i <= end; i++) out.push(i);
  if (end < total - 1) out.push("…");
  out.push(total);
  return out;
}

export function Pagination({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  itemLabel,
  compact = false,
}: Props) {
  const { t } = useLang();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(safePage * pageSize, total);
  const range = useMemo(() => paginationRange(safePage, totalPages), [safePage, totalPages]);

  // Don't render at all if there's nothing to paginate
  if (total === 0) return null;

  const btnBase =
    "min-w-[1.5rem] h-6 px-1.5 text-[10px] rounded-md transition flex items-center justify-center";
  const btnNum = "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50";
  const btnActive = "bg-brand-600 text-white border border-brand-600";
  const btnDisabled = "bg-gray-50 text-gray-300 cursor-not-allowed border border-gray-100";

  return (
    <div className="flex items-center justify-between gap-3 px-2 py-1.5 border-t border-gray-100 bg-gray-50/50">
      {!compact && (
        <div className="text-[10px] text-gray-500">
          {t("pagination.showing")} <span className="font-semibold text-gray-700">{start.toLocaleString()}</span>
          {" – "}
          <span className="font-semibold text-gray-700">{end.toLocaleString()}</span>
          {" "}{t("pagination.of")} <span className="font-semibold text-gray-700">{total.toLocaleString()}</span>
          {itemLabel ? ` ${itemLabel}` : ""}
        </div>
      )}

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={safePage <= 1}
          aria-label={t("pagination.first")}
          className={`${btnBase} ${safePage <= 1 ? btnDisabled : btnNum}`}
        >
          «
        </button>
        <button
          type="button"
          onClick={() => onPageChange(safePage - 1)}
          disabled={safePage <= 1}
          aria-label={t("pagination.prev")}
          className={`${btnBase} ${safePage <= 1 ? btnDisabled : btnNum}`}
        >
          ‹
        </button>

        {range.map((p, i) =>
          p === "…" ? (
            <span key={`gap-${i}`} className="text-[10px] text-gray-400 px-0.5">
              …
            </span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              className={`${btnBase} ${p === safePage ? btnActive : btnNum}`}
              aria-current={p === safePage ? "page" : undefined}
            >
              {p}
            </button>
          )
        )}

        <button
          type="button"
          onClick={() => onPageChange(safePage + 1)}
          disabled={safePage >= totalPages}
          aria-label={t("pagination.next")}
          className={`${btnBase} ${safePage >= totalPages ? btnDisabled : btnNum}`}
        >
          ›
        </button>
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={safePage >= totalPages}
          aria-label={t("pagination.last")}
          className={`${btnBase} ${safePage >= totalPages ? btnDisabled : btnNum}`}
        >
          »
        </button>
      </div>

      {!compact && onPageSizeChange && (
        <div className="flex items-center gap-1 text-[10px] text-gray-500">
          <span>{t("pagination.per_page")}:</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(parseInt(e.target.value))}
            className="border border-gray-200 rounded px-1 py-0.5 text-[10px] bg-white"
          >
            {pageSizeOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

/**
 * Convenience hook: keeps page state, clamps when the underlying array shrinks,
 * and returns the current slice plus everything the <Pagination/> component needs.
 */
import { useState, useEffect } from "react";

export function usePagination<T>(items: T[], defaultPageSize = 25) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  // Clamp page if the dataset shrinks (e.g. filter applied, items deleted)
  useEffect(() => {
    const total = items.length;
    const maxPage = Math.max(1, Math.ceil(total / pageSize));
    if (page > maxPage) setPage(maxPage);
  }, [items.length, pageSize, page]);

  const start = (page - 1) * pageSize;
  const paged = items.slice(start, start + pageSize);

  return {
    page,
    pageSize,
    setPage,
    setPageSize: (s: number) => {
      setPageSize(s);
      setPage(1);
    },
    paged,
    total: items.length,
  };
}
