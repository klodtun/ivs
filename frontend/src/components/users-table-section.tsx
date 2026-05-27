"use client";
import { useLang } from "@/components/lang-provider";
import { cn, formatLegalTimestamp } from "@/lib/utils";
import { Pagination, usePagination } from "@/components/pagination";
import type { User } from "@/types";

interface Props {
  users: User[];
  roleBadge: Record<string, string>;
  editAccessId?: number;
  currentUserId?: number;
  onChangeRole: (user: User, role: string) => void;
  onOpenAccess: (user: User) => void;
  onToggleActive: (user: User) => void;
  onDelete?: (user: User) => void;
}

export function UsersTableSection({
  users,
  roleBadge,
  editAccessId,
  currentUserId,
  onChangeRole,
  onOpenAccess,
  onToggleActive,
  onDelete,
}: Props) {
  const { t } = useLang();
  const { paged, page, pageSize, setPage, setPageSize, total } = usePagination(users, 25);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase">
          <tr>
            <th className="px-3 py-2 text-left">{t("settings.col.user")}</th>
            <th className="px-3 py-2 text-left">{t("settings.col.email")}</th>
            <th className="px-3 py-2 text-left">{t("settings.col.role")}</th>
            <th className="px-3 py-2 text-left">{t("settings.col.app_access")}</th>
            <th className="px-3 py-2 text-left">{t("settings.col.status")}</th>
            <th className="px-3 py-2 text-left whitespace-nowrap">{t("settings.col.created")}</th>
            <th className="px-3 py-2 text-right">{t("settings.col.actions")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {paged.map((u) => (
            <tr key={u.id} className={cn("hover:bg-gray-50", editAccessId === u.id && "bg-brand-50")}>
              <td className="px-3 py-2 font-medium text-gray-900">{u.username}</td>
              <td className="px-3 py-2 text-gray-600">{u.email}</td>
              <td className="px-3 py-2">
                <select
                  value={u.role}
                  onChange={(e) => onChangeRole(u, e.target.value)}
                  className={cn(
                    "text-[9px] px-1.5 py-0.5 rounded-full font-medium border-0 cursor-pointer",
                    roleBadge[u.role] || "bg-gray-100"
                  )}
                >
                  <option value="viewer">{t("role.viewer")}</option>
                  <option value="developer">{t("role.developer")}</option>
                  <option value="admin">{t("role.admin")}</option>
                </select>
              </td>
              <td className="px-3 py-2">
                {u.role === "admin" ? (
                  <span className="text-[9px] px-1.5 py-px rounded-full bg-red-50 text-red-600 font-medium">
                    {t("settings.full_access")}
                  </span>
                ) : u.access_all_apps ? (
                  <span className="text-[9px] px-1.5 py-px rounded-full bg-green-100 text-green-700 font-medium">
                    {t("settings.access_all")}
                  </span>
                ) : (u.allowed_app_ids?.length || 0) > 0 ? (
                  <span className="text-[9px] px-1.5 py-px rounded-full bg-blue-100 text-blue-700 font-medium">
                    {u.allowed_app_ids?.length} {t("settings.apps_assigned")}
                  </span>
                ) : (
                  <span className="text-[9px] px-1.5 py-px rounded-full bg-gray-100 text-gray-500 font-medium">
                    {t("settings.no_access")}
                  </span>
                )}
              </td>
              <td className="px-3 py-2">
                <span
                  className={cn(
                    "text-[9px] px-1.5 py-px rounded-full font-medium",
                    u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"
                  )}
                >
                  {u.is_active ? t("settings.active") : t("settings.disabled")}
                </span>
              </td>
              <td className="px-3 py-2 text-gray-600 text-[9px] font-mono whitespace-nowrap">
                {formatLegalTimestamp(u.created_at)}
              </td>
              <td className="px-3 py-2 text-right space-x-2">
                {u.role !== "admin" && (
                  <button
                    onClick={() => onOpenAccess(u)}
                    className="text-[10px] text-brand-600 hover:text-brand-700 font-medium"
                  >
                    {t("settings.set_access")}
                  </button>
                )}
                <button
                  onClick={() => onToggleActive(u)}
                  className={cn(
                    "text-[10px] font-medium",
                    u.is_active ? "text-red-600 hover:text-red-700" : "text-green-600 hover:text-green-700"
                  )}
                >
                  {u.is_active ? t("settings.disable") : t("settings.enable")}
                </button>
                {onDelete && u.id !== currentUserId && (
                  <button
                    onClick={() => onDelete(u)}
                    className="text-[10px] font-medium text-red-700 hover:text-red-800 hover:bg-red-50 px-1.5 py-0.5 rounded"
                    title={t("settings.delete_user_tooltip")}
                  >
                    {t("settings.delete_user")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        itemLabel={t("settings.users_item_label")}
      />
    </div>
  );
}
