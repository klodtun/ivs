import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export function timeAgo(date: string): string {
  const seconds = Math.floor(
    (new Date().getTime() - new Date(date).getTime()) / 1000
  );
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatDateTime(date: string): string {
  const d = new Date(date);
  const day = d.getDate().toString().padStart(2, "0");
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  const year = d.getFullYear();
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

export function formatDateTimeSeconds(date: string): string {
  if (!date) return "-";

  const match = date.match(
    /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2}):(\d{2})/
  );

  if (match) {
    const [, year, month, day, hours, minutes, seconds] = match;
    return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
  }

  const d = new Date(date);
  if (Number.isNaN(d.getTime())) return "-";

  const day = d.getDate().toString().padStart(2, "0");
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  const year = d.getFullYear();
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  const seconds = d.getSeconds().toString().padStart(2, "0");
  return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
}

/**
 * Format a timestamp for legal / audit records.
 *
 * Output: `YYYY-MM-DD HH:mm:ss (UTC+TZ)` — unambiguous, ISO-style, with the
 * absolute timezone offset spelled out so it can't be misread in a different
 * locale. Use this anywhere the timestamp may end up in a compliance export,
 * dispute, or printed audit document.
 *
 * Example: "2026-05-27 20:09:03 (UTC+07:00)"
 *
 * Backend stores UTC; we render in the browser's local timezone so the user
 * sees real wall-clock time but the offset suffix makes it convertible.
 */
export function formatLegalTimestamp(date: string | null | undefined): string {
  if (!date) return "—";
  // Backend often returns naive UTC ("2026-05-27T13:09:03.387627" with no
  // suffix). The browser would otherwise interpret it as local time and
  // skew the result by the offset. Normalize to UTC explicitly.
  const normalized =
    typeof date === "string" && !date.endsWith("Z") && !date.includes("+") && !/-\d{2}:\d{2}$/.test(date)
      ? date + "Z"
      : date;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return "—";

  const pad = (n: number) => n.toString().padStart(2, "0");
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  const seconds = pad(d.getSeconds());

  // Build the UTC offset suffix, e.g. "UTC+07:00"
  const tzMin = -d.getTimezoneOffset(); // getTimezoneOffset is negated
  const tzSign = tzMin >= 0 ? "+" : "-";
  const tzAbs = Math.abs(tzMin);
  const tzHours = pad(Math.floor(tzAbs / 60));
  const tzMinutes = pad(tzAbs % 60);

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} (UTC${tzSign}${tzHours}:${tzMinutes})`;
}

export function timeRemaining(date: string): string {
  // Backend stores UTC — ensure browser interprets as UTC (append Z if no timezone)
  const utcDate = date.endsWith("Z") || date.includes("+") ? date : date + "Z";
  const diff = new Date(utcDate).getTime() - new Date().getTime();
  if (diff <= 0) return "Expired";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    const h = hours % 24;
    return `${days}d ${h}h`;
  }
  return `${hours}h ${mins}m`;
}
