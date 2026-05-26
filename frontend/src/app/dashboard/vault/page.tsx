"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, timeAgo } from "@/lib/utils";
import { VaultKey, User } from "@/types";

const providerIcons: Record<string, string> = { openai: "AI", claude: "CL", anthropic: "AN", google: "GG", default: "KY" };
const categories = ["general", "ai", "maps", "weather", "finance", "other"];

export default function VaultPage() {
  const { t } = useLang();
  const [keys, setKeys] = useState<VaultKey[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", provider: "", category: "general", value: "", description: "" });
  const [search, setSearch] = useState("");
  const [saving, setSaving] = useState(false);

  const loadKeys = useCallback(async () => { try { setKeys(await api.getVaultKeys()); } catch (e) { console.error(e); } }, []);

  useEffect(() => {
    const stored = localStorage.getItem("user");
    if (stored) setUser(JSON.parse(stored));
    loadKeys();
  }, [loadKeys]);

  const handleAdd = async () => {
    if (!form.name || !form.provider || !form.value) return;
    setSaving(true);
    try { await api.createVaultKey(form); setForm({ name: "", provider: "", category: "general", value: "", description: "" }); setShowAdd(false); await loadKeys(); } catch (e: any) { alert(e.message); } finally { setSaving(false); }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`${t("vault.delete_confirm")} "${name}"?`)) return;
    try { await api.deleteVaultKey(id); await loadKeys(); } catch (e: any) { alert(e.message); }
  };

  const filtered = keys.filter((k) => k.name.toLowerCase().includes(search.toLowerCase()) || k.provider.toLowerCase().includes(search.toLowerCase()));
  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{t("vault.title")}</h1>
          <p className="text-gray-500 text-[10px] mt-0.5">{t("vault.subtitle")}</p>
        </div>
        {isAdmin && (
          <button onClick={() => setShowAdd(!showAdd)}
            className="px-3 py-1 bg-brand-600 text-white text-[10px] font-medium rounded-md hover:bg-brand-700 transition">
            {showAdd ? t("vault.cancel") : t("vault.add")}
          </button>
        )}
      </div>

      {showAdd && isAdmin && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
          <h3 className="font-semibold text-gray-900 text-sm">{t("vault.add_title")}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t("vault.key_name")} className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
            <input type="text" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}
              placeholder={t("vault.provider")} className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none">
              {categories.map((c) => (<option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>))}
            </select>
            <input type="password" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })}
              placeholder={t("vault.key_value")} className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
          </div>
          <input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder={t("vault.description")} className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
          <button onClick={handleAdd} disabled={saving || !form.name || !form.provider || !form.value}
            className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50">
            {saving ? t("vault.saving") : t("vault.save")}
          </button>
        </div>
      )}

      <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
        placeholder={t("vault.search")}
        className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />

      {filtered.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-400 text-xs">{t("vault.no_keys")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filtered.map((key) => {
            const icon = providerIcons[key.provider.toLowerCase()] || providerIcons.default;
            return (
              <div key={key.id} className="bg-white rounded-lg border border-gray-200 p-3 hover:shadow-md transition">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-7 h-7 rounded-md bg-brand-100 text-brand-700 flex items-center justify-center text-[9px] font-bold">{icon}</div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-gray-900 text-xs truncate">{key.name}</h4>
                    <p className="text-[9px] text-gray-400">{key.provider}</p>
                  </div>
                  <span className="text-[8px] px-1.5 py-px rounded-full bg-gray-100 text-gray-500">{key.category}</span>
                </div>
                {key.description && <p className="text-[9px] text-gray-500 mb-2">{key.description}</p>}
                <div className="flex items-center justify-between text-[9px] text-gray-400 pt-2 border-t border-gray-100">
                  <span>{timeAgo(key.created_at)}</span>
                  <div className="flex gap-2">
                    <span className="text-green-600 font-medium">{t("vault.encrypted")}</span>
                    {isAdmin && (<button onClick={() => handleDelete(key.id, key.name)} className="text-red-500 hover:text-red-700">{t("app.delete")}</button>)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
