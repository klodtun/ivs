"use client";
import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, timeAgo } from "@/lib/utils";
import { VaultKey, User } from "@/types";
import { PasswordConfirmModal } from "@/components/password-confirm-modal";
import ApiCatalogView from "@/components/api-catalog-view";

type VaultTab = "keys" | "programs";

const providerIcons: Record<string, string> = { openai: "AI", claude: "CL", anthropic: "AN", google: "GG", default: "KY" };
const categories = ["general", "ai", "maps", "weather", "finance", "other"];

export default function VaultPage() {
  const { t } = useLang();
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialTab: VaultTab = searchParams.get("tab") === "programs" ? "programs" : "keys";
  const [tab, setTab] = useState<VaultTab>(initialTab);
  const switchTab = (next: VaultTab) => {
    setTab(next);
    const url = next === "keys" ? "/dashboard/vault" : "/dashboard/vault?tab=programs";
    router.replace(url);
  };
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

  const [pendingDeleteKey, setPendingDeleteKey] = useState<VaultKey | null>(null);

  const handleDelete = (key: VaultKey) => {
    setPendingDeleteKey(key);
  };

  const handleDeleteConfirmed = async (password: string) => {
    if (!pendingDeleteKey) return;
    try {
      await api.deleteVaultKey(pendingDeleteKey.id, password);
      setPendingDeleteKey(null);
      await loadKeys();
    } catch (e: any) {
      throw e;
    }
  };

  // Reveal-and-copy: backend audit-logs the reveal at WARNING level.
  // The plaintext stays out of React state (one-shot copy then forgotten)
  // and the "Copied ✓" indicator clears after 2s.
  const [copiedKeyId, setCopiedKeyId] = useState<number | null>(null);
  const [copyError, setCopyError] = useState<number | null>(null);
  const handleCopy = async (id: number) => {
    setCopyError(null);
    try {
      const { value } = await api.revealVaultKey(id);
      await navigator.clipboard.writeText(value);
      setCopiedKeyId(id);
      setTimeout(() => setCopiedKeyId((curr) => (curr === id ? null : curr)), 2000);
    } catch (e: any) {
      setCopyError(id);
      setTimeout(() => setCopyError((curr) => (curr === id ? null : curr)), 3000);
    }
  };

  const filtered = keys.filter((k) => k.name.toLowerCase().includes(search.toLowerCase()) || k.provider.toLowerCase().includes(search.toLowerCase()));
  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold text-gray-900">{t("vault.title")}</h1>
        <p className="text-gray-500 text-[10px] mt-0.5">{t("vault.subtitle")}</p>
      </div>

      {/* Tab strip */}
      <div className="flex border-b border-gray-200 -mb-px">
        <button
          onClick={() => switchTab("keys")}
          className={cn(
            "px-4 py-2 text-xs font-medium border-b-2 transition-colors",
            tab === "keys"
              ? "border-brand-600 text-brand-700"
              : "border-transparent text-gray-500 hover:text-gray-700"
          )}
        >
          {t("vault.tab.keys")}
        </button>
        <button
          onClick={() => switchTab("programs")}
          className={cn(
            "px-4 py-2 text-xs font-medium border-b-2 transition-colors",
            tab === "programs"
              ? "border-brand-600 text-brand-700"
              : "border-transparent text-gray-500 hover:text-gray-700"
          )}
        >
          {t("vault.tab.programs")}
        </button>
      </div>

      {tab === "programs" && <ApiCatalogView />}

      {tab === "keys" && <>
      <div className="flex items-center justify-end">
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
                  <div className="flex items-center gap-2">
                    <span className="text-green-600 font-medium">{t("vault.encrypted")}</span>
                    <button
                      onClick={() => handleCopy(key.id)}
                      title={t("vault.copy_tooltip")}
                      className={cn(
                        "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded transition font-medium",
                        copiedKeyId === key.id
                          ? "bg-green-100 text-green-700"
                          : copyError === key.id
                          ? "bg-red-100 text-red-700"
                          : "bg-brand-50 text-brand-700 hover:bg-brand-100"
                      )}
                    >
                      <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      {copiedKeyId === key.id ? t("vault.copied") : copyError === key.id ? t("vault.copy_failed") : t("vault.copy")}
                    </button>
                    {isAdmin && (<button onClick={() => handleDelete(key)} className="text-red-500 hover:text-red-700">{t("app.delete")}</button>)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {pendingDeleteKey && (
        <PasswordConfirmModal
          title={`${t("vault.delete_modal.title")} — ${pendingDeleteKey.name}`}
          description={`${t("vault.delete_modal.desc_prefix")} "${pendingDeleteKey.name}" (${pendingDeleteKey.provider}). ${t("vault.delete_modal.desc_suffix")}`}
          consequences={[
            t("vault.delete_modal.consequence_1"),
            t("vault.delete_modal.consequence_2"),
            t("vault.delete_modal.consequence_3"),
          ]}
          legalNote={t("vault.delete_modal.legal_note")}
          confirmLabel={t("vault.delete_modal.confirm")}
          onConfirm={handleDeleteConfirmed}
          onCancel={() => setPendingDeleteKey(null)}
        />
      )}
      </>}
    </div>
  );
}
