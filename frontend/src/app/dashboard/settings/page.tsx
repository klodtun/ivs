"use client";
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, formatDateTimeSeconds, timeAgo } from "@/lib/utils";
import { User, App, AuditLog, AuditLogExport } from "@/types";

type Tab = "users" | "logs" | "dns" | "network" | "pdpa" | "gitea" | "autostart";

interface NetworkInfo {
  server_ip: string;
  hostname: string;
  gateway: string | null;
  dns_servers: string[];
  interfaces: {
    name: string;
    ipv4: string | null;
    netmask: string | null;
    mac: string | null;
    is_up: boolean;
    speed: number;
  }[];
  internet: boolean;
  mdns_available: boolean;
  mdns_hostname: string | null;
  mdns_service: string | null;
  platform: string;
}

export default function SettingsPage() {
  const { t } = useLang();
  const [users, setUsers] = useState<User[]>([]);
  const [apps, setApps] = useState<App[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [tab, setTab] = useState<Tab>("users");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "viewer" });
  const [saving, setSaving] = useState(false);
  const [editAccess, setEditAccess] = useState<User | null>(null);
  const [accessAll, setAccessAll] = useState(false);
  const [selectedAppIds, setSelectedAppIds] = useState<number[]>([]);
  const [savingAccess, setSavingAccess] = useState(false);

  // Audit Export
  const [exports, setExports] = useState<AuditLogExport[]>([]);
  const [exporting, setExporting] = useState(false);

  // DNS Config
  const [dnsConfig, setDnsConfig] = useState({ domain_suffix: "", server_ip: "" });
  const [dnsDomain, setDnsDomain] = useState("");
  const [savingDns, setSavingDns] = useState(false);

  // Network Info
  const [networkInfo, setNetworkInfo] = useState<NetworkInfo | null>(null);
  const [loadingNetwork, setLoadingNetwork] = useState(false);

  // mDNS Config
  const [mdnsStatus, setMdnsStatus] = useState<{
    running: boolean; hostname: string; mdns_address: string;
    default_hostname: string; ip: string; port: number; saved_hostname: string;
  } | null>(null);
  const [mdnsInput, setMdnsInput] = useState("");
  const [savingMdns, setSavingMdns] = useState(false);
  const [resettingMdns, setResettingMdns] = useState(false);

  // PDPA
  const [pdpaRecords, setPdpaRecords] = useState<any[]>([]);
  const [loadingPdpa, setLoadingPdpa] = useState(false);
  const [scanningAll, setScanningAll] = useState(false);
  const [exportingRopa, setExportingRopa] = useState(false);
  const [editPdpa, setEditPdpa] = useState<any | null>(null);
  const [pdpaForm, setPdpaForm] = useState({ purpose: "", pii_fields: [] as string[], retention_period: "", security_notes: "" });
  const [savingPdpa, setSavingPdpa] = useState(false);
  const [scanResult, setScanResult] = useState<any | null>(null);
  const [piiInput, setPiiInput] = useState("");
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  // Privacy Notice
  const [editPN, setEditPN] = useState<any | null>(null);
  const [pnForm, setPnForm] = useState({ privacy_notice_enabled: false, privacy_notice_title: "", privacy_notice_detail: "", privacy_policy_url: "", privacy_notice_url: "" });
  const [savingPN, setSavingPN] = useState(false);
  const [previewPN, setPreviewPN] = useState<any | null>(null);

  // NTP Status
  const [ntpStatus, setNtpStatus] = useState<{
    synced: boolean; ntp_server: string | null; ntp_server_name: string | null;
    ntp_authority: string | null; ntp_stratum: number | null; offset_ms: number;
    last_sync: string | null; sync_count: number;
  } | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [u, l, a] = await Promise.all([api.getUsers(), api.getAuditLogs(), api.getApps()]);
      setUsers(u); setLogs(l); setApps(a);
    } catch (e) { console.error(e); }
  }, []);

  const loadExports = useCallback(async () => {
    try { const e = await api.getAuditLogExports(); setExports(e); } catch (e) { console.error(e); }
  }, []);

  const loadDnsConfig = useCallback(async () => {
    try {
      const c = await api.getDNSConfig();
      setDnsConfig(c);
      setDnsDomain(c.domain_suffix);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => {
    if (tab === "logs") {
      loadExports();
      api.getNtpStatus().then(setNtpStatus).catch(() => {});
    }
  }, [tab, loadExports]);
  useEffect(() => { if (tab === "dns") loadDnsConfig(); }, [tab, loadDnsConfig]);

  const loadNetworkInfo = useCallback(async () => {
    setLoadingNetwork(true);
    try { const n = await api.getNetworkInfo(); setNetworkInfo(n); } catch (e) { console.error(e); } finally { setLoadingNetwork(false); }
  }, []);
  const loadMdns = useCallback(async () => {
    try {
      const m = await api.getMdnsStatus();
      setMdnsStatus(m);
      setMdnsInput(m.hostname);
    } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { if (tab === "network") { loadNetworkInfo(); loadMdns(); } }, [tab, loadNetworkInfo, loadMdns]);

  const handleSaveMdns = async () => {
    if (!mdnsInput.trim()) return;
    setSavingMdns(true);
    try { await api.updateMdnsHostname(mdnsInput.trim()); await loadMdns(); } catch (e: any) { alert(e.message); } finally { setSavingMdns(false); }
  };

  const handleResetMdns = async () => {
    setResettingMdns(true);
    try { await api.resetMdnsHostname(); await loadMdns(); } catch (e: any) { alert(e.message); } finally { setResettingMdns(false); }
  };

  const handleAddUser = async () => {
    if (!form.username || !form.email || !form.password) return;
    setSaving(true);
    try { await api.createUser(form); setForm({ username: "", email: "", password: "", role: "viewer" }); setShowAdd(false); await loadData(); } catch (e: any) { alert(e.message); } finally { setSaving(false); }
  };

  const toggleActive = async (user: User) => {
    try { await api.updateUser(user.id, { is_active: !user.is_active }); await loadData(); } catch (e: any) { alert(e.message); }
  };

  const changeRole = async (user: User, role: string) => {
    try { await api.updateUser(user.id, { role }); await loadData(); } catch (e: any) { alert(e.message); }
  };

  const openAccessPanel = (user: User) => {
    setEditAccess(user);
    setAccessAll(user.access_all_apps || false);
    setSelectedAppIds(user.allowed_app_ids || []);
  };

  const saveAccess = async () => {
    if (!editAccess) return;
    setSavingAccess(true);
    try {
      await api.setUserAccess(editAccess.id, { user_id: editAccess.id, app_ids: accessAll ? [] : selectedAppIds, access_all: accessAll });
      setEditAccess(null);
      await loadData();
    } catch (e: any) { alert(e.message); } finally { setSavingAccess(false); }
  };

  const toggleAppId = (appId: number) => {
    setSelectedAppIds(prev => prev.includes(appId) ? prev.filter(id => id !== appId) : [...prev, appId]);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await api.exportAuditLogs();
      await loadExports();
      await loadData();
    } catch (e: any) { alert(e.message); } finally { setExporting(false); }
  };

  const handleDownloadExport = (id: number) => {
    const token = localStorage.getItem("token");
    const url = api.downloadAuditLogExport(id);
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", "");
    // Use fetch with auth header
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const blobUrl = URL.createObjectURL(blob);
        a.href = blobUrl;
        a.click();
        URL.revokeObjectURL(blobUrl);
      });
  };

  const handleSaveDns = async () => {
    if (!dnsDomain.trim()) return;
    setSavingDns(true);
    try {
      const c = await api.updateDNSConfig(dnsDomain.trim());
      setDnsConfig(c);
      await loadData();
    } catch (e: any) { alert(e.message); } finally { setSavingDns(false); }
  };

  // ── PDPA handlers ──
  const loadPdpa = useCallback(async () => {
    setLoadingPdpa(true);
    try { const r = await api.getPdpaRecords(); setPdpaRecords(r); } catch (e) { console.error(e); } finally { setLoadingPdpa(false); }
  }, []);

  useEffect(() => { if (tab === "pdpa") loadPdpa(); }, [tab, loadPdpa]);

  const handleScanAll = async () => {
    setScanningAll(true);
    try { await api.scanAllAppsPii(); await loadPdpa(); } catch (e: any) { alert(e.message); } finally { setScanningAll(false); }
  };

  const handleScanApp = async (appId: number) => {
    try {
      const result = await api.scanAppPii(appId);
      setScanResult(result);
      await loadPdpa();
    } catch (e: any) { alert(e.message); }
  };

  const handleExportRopa = async () => {
    setExportingRopa(true);
    try {
      const result = await api.exportRopa();
      const token = localStorage.getItem("token");
      const url = api.downloadRopaReport(result.filename);
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await r.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = result.filename;
      a.click();
      URL.revokeObjectURL(blobUrl);
      setToastMsg(`✅ Export สำเร็จ — ${result.filename} (${result.record_count} กิจกรรม, SHA-256: ${result.sha256_hash.substring(0, 16)}...)`);
      setTimeout(() => setToastMsg(null), 8000);
    } catch (e: any) { alert(e.message); } finally { setExportingRopa(false); }
  };

  const openPdpaEdit = (record: any) => {
    setEditPdpa(record);
    setPdpaForm({
      purpose: record.purpose || "",
      pii_fields: record.pii_fields || [],
      retention_period: record.retention_period || "",
      security_notes: record.security_notes || "",
    });
    setPiiInput("");
    setScanResult(null);
  };

  const handleSavePdpa = async () => {
    if (!editPdpa) return;
    setSavingPdpa(true);
    try {
      await api.updatePdpaRecord(editPdpa.app_id, pdpaForm);
      setEditPdpa(null);
      await loadPdpa();
    } catch (e: any) { alert(e.message); } finally { setSavingPdpa(false); }
  };

  const addPiiField = () => {
    const v = piiInput.trim();
    if (v && !pdpaForm.pii_fields.includes(v)) {
      setPdpaForm(prev => ({ ...prev, pii_fields: [...prev.pii_fields, v] }));
      setPiiInput("");
    }
  };

  const removePiiField = (field: string) => {
    setPdpaForm(prev => ({ ...prev, pii_fields: prev.pii_fields.filter(f => f !== field) }));
  };

  const addAutoDetectedPii = (fields: string[]) => {
    const merged = Array.from(new Set([...pdpaForm.pii_fields, ...fields]));
    setPdpaForm(prev => ({ ...prev, pii_fields: merged }));
  };

  // Privacy Notice handlers
  const openPNEdit = (record: any) => {
    setEditPN(record);
    setPnForm({
      privacy_notice_enabled: record.privacy_notice_enabled || false,
      privacy_notice_title: record.privacy_notice_title || "",
      privacy_notice_detail: record.privacy_notice_detail || "",
      privacy_policy_url: record.privacy_policy_url || "",
      privacy_notice_url: record.privacy_notice_url || "",
    });
  };

  const handleSavePN = async () => {
    if (!editPN) return;
    setSavingPN(true);
    try {
      await api.updatePrivacyNotice(editPN.app_id, pnForm);
      await loadPdpa();
      setEditPN(null);
      setToastMsg(`✅ บันทึก Privacy Notice สำเร็จ — ${editPN.app_name}`);
      setTimeout(() => setToastMsg(null), 5000);
    } catch (e: any) { alert(e.message); } finally { setSavingPN(false); }
  };

  const PII_CHECKLIST = [
    "ชื่อ-นามสกุล", "อีเมล", "เบอร์โทรศัพท์", "ที่อยู่",
    "บัตรประชาชน/Passport", "วันเกิด/อายุ", "LINE ID",
    "IP Address", "Cookie/Session", "Username/Password",
    "GPS/Location", "รูปภาพ/ไบโอเมตริก", "บัญชีธนาคาร/การเงิน",
    "MAC Address", "เลขประจำตัวผู้เสียภาษี", "ข้อมูลบริษัท/องค์กร",
  ];

  const pdpaStatusBadge: Record<string, string> = {
    not_started: "bg-red-100 text-red-700",
    partial: "bg-yellow-100 text-yellow-700",
    complete: "bg-green-100 text-green-700",
  };

  const roleBadge: Record<string, string> = { admin: "bg-red-100 text-red-700", developer: "bg-blue-100 text-blue-700", viewer: "bg-gray-100 text-gray-600" };
  const roleKey: Record<string, string> = { admin: "role.admin", developer: "role.developer", viewer: "role.viewer" };

  const tabs: { key: Tab; labelKey: string }[] = [
    { key: "users", labelKey: "settings.tab.users" },
    { key: "logs", labelKey: "settings.tab.logs" },
    { key: "dns", labelKey: "settings.tab.dns" },
    { key: "network", labelKey: "settings.tab.network" },
    { key: "pdpa", labelKey: "settings.tab.pdpa" },
    { key: "gitea", labelKey: "settings.tab.gitea" },
    { key: "autostart", labelKey: "settings.tab.autostart" },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold text-gray-900">{t("settings.title")}</h1>
        <p className="text-gray-500 text-[10px] mt-0.5">{t("settings.subtitle")}</p>
      </div>

      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {tabs.map((tb) => (
          <button key={tb.key} onClick={() => setTab(tb.key)}
            className={cn("px-3 py-1.5 text-xs font-medium border-b-2 transition whitespace-nowrap",
              tab === tb.key ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-700")}>
            {t(tb.labelKey)}
          </button>
        ))}
      </div>

      {/* ===== TAB: USERS ===== */}
      {tab === "users" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setShowAdd(!showAdd)}
              className="px-3 py-1 bg-brand-600 text-white text-[10px] font-medium rounded-md hover:bg-brand-700 transition">
              {showAdd ? t("vault.cancel") : t("settings.add_user")}
            </button>
          </div>

          {showAdd && (
            <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
              <h3 className="font-semibold text-gray-900 text-sm">{t("settings.create_user")}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder={t("settings.username")} className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder={t("settings.email")} className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
                <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder={t("settings.password")} className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none">
                  <option value="viewer">{t("role.viewer")}</option>
                  <option value="developer">{t("role.developer")}</option>
                  <option value="admin">{t("role.admin")}</option>
                </select>
              </div>
              <button onClick={handleAddUser} disabled={saving || !form.username || !form.email || !form.password}
                className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50">
                {saving ? t("settings.creating") : t("settings.create")}
              </button>
            </div>
          )}

          {editAccess && (
            <div className="bg-white rounded-lg border-2 border-brand-300 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 text-sm">
                  {t("settings.access_title")} — {editAccess.username}
                  <span className={cn("ml-2 text-[9px] px-1.5 py-0.5 rounded-full font-medium", roleBadge[editAccess.role])}>
                    {t(roleKey[editAccess.role])}
                  </span>
                </h3>
                <button onClick={() => setEditAccess(null)} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
              </div>
              <p className="text-[10px] text-gray-500">{t("settings.access_desc")}</p>
              <label className="flex items-center gap-2 p-2 rounded-md bg-gray-50 cursor-pointer">
                <input type="checkbox" checked={accessAll} onChange={(e) => setAccessAll(e.target.checked)}
                  className="rounded border-gray-300 text-brand-600 focus:ring-brand-500" />
                <span className="text-xs font-medium text-gray-700">{t("settings.access_all")}</span>
                <span className="text-[9px] text-gray-400 ml-1">{t("settings.access_all_desc")}</span>
              </label>
              {!accessAll && (
                <div className="space-y-2">
                  <p className="text-[10px] text-gray-600 font-medium">{t("settings.access_select")}:</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5 max-h-48 overflow-auto">
                    {apps.map(app => (
                      <label key={app.id}
                        className={cn("flex items-center gap-2 px-2 py-1.5 rounded-md border text-[10px] cursor-pointer transition",
                          selectedAppIds.includes(app.id) ? "border-brand-400 bg-brand-50 text-brand-700" : "border-gray-200 bg-white text-gray-600 hover:border-gray-300")}>
                        <input type="checkbox" checked={selectedAppIds.includes(app.id)} onChange={() => toggleAppId(app.id)}
                          className="rounded border-gray-300 text-brand-600 focus:ring-brand-500 w-3 h-3" />
                        <div className="flex-1 min-w-0">
                          <span className="font-medium truncate block">{app.name}</span>
                          <span className="text-[8px] text-gray-400">{app.app_type} • {app.status}</span>
                        </div>
                      </label>
                    ))}
                  </div>
                  {apps.length === 0 && <p className="text-[10px] text-gray-400 text-center py-2">{t("settings.no_apps_to_assign")}</p>}
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <button onClick={saveAccess} disabled={savingAccess}
                  className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50">
                  {savingAccess ? t("settings.saving_access") : t("settings.save_access")}
                </button>
                <button onClick={() => setEditAccess(null)}
                  className="px-4 py-1.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-md hover:bg-gray-200 transition">
                  {t("vault.cancel")}
                </button>
                <span className="text-[9px] text-gray-400 self-center ml-2">
                  {accessAll ? t("settings.access_all") : `${selectedAppIds.length} ${t("settings.apps_selected")}`}
                </span>
              </div>
            </div>
          )}

          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">{t("settings.col.user")}</th>
                  <th className="px-3 py-2 text-left">{t("settings.col.email")}</th>
                  <th className="px-3 py-2 text-left">{t("settings.col.role")}</th>
                  <th className="px-3 py-2 text-left">{t("settings.col.app_access")}</th>
                  <th className="px-3 py-2 text-left">{t("settings.col.status")}</th>
                  <th className="px-3 py-2 text-left">{t("settings.col.created")}</th>
                  <th className="px-3 py-2 text-right">{t("settings.col.actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((u) => (
                  <tr key={u.id} className={cn("hover:bg-gray-50", editAccess?.id === u.id && "bg-brand-50")}>
                    <td className="px-3 py-2 font-medium text-gray-900">{u.username}</td>
                    <td className="px-3 py-2 text-gray-600">{u.email}</td>
                    <td className="px-3 py-2">
                      <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}
                        className={cn("text-[9px] px-1.5 py-0.5 rounded-full font-medium border-0 cursor-pointer", roleBadge[u.role] || "bg-gray-100")}>
                        <option value="viewer">{t("role.viewer")}</option>
                        <option value="developer">{t("role.developer")}</option>
                        <option value="admin">{t("role.admin")}</option>
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      {u.role === "admin" ? (
                        <span className="text-[9px] px-1.5 py-px rounded-full bg-red-50 text-red-600 font-medium">{t("settings.full_access")}</span>
                      ) : u.access_all_apps ? (
                        <span className="text-[9px] px-1.5 py-px rounded-full bg-green-100 text-green-700 font-medium">{t("settings.access_all")}</span>
                      ) : (u.allowed_app_ids?.length || 0) > 0 ? (
                        <span className="text-[9px] px-1.5 py-px rounded-full bg-blue-100 text-blue-700 font-medium">
                          {u.allowed_app_ids?.length} {t("settings.apps_assigned")}
                        </span>
                      ) : (
                        <span className="text-[9px] px-1.5 py-px rounded-full bg-gray-100 text-gray-500 font-medium">{t("settings.no_access")}</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span className={cn("text-[9px] px-1.5 py-px rounded-full font-medium", u.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600")}>
                        {u.is_active ? t("settings.active") : t("settings.disabled")}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-400 text-[9px]">{timeAgo(u.created_at)}</td>
                    <td className="px-3 py-2 text-right space-x-2">
                      {u.role !== "admin" && (
                        <button onClick={() => openAccessPanel(u)} className="text-[10px] text-brand-600 hover:text-brand-700 font-medium">
                          {t("settings.set_access")}
                        </button>
                      )}
                      <button onClick={() => toggleActive(u)}
                        className={cn("text-[10px] font-medium", u.is_active ? "text-red-600 hover:text-red-700" : "text-green-600 hover:text-green-700")}>
                        {u.is_active ? t("settings.disable") : t("settings.enable")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ===== TAB: AUDIT LOGS ===== */}
      {tab === "logs" && (
        <div className="space-y-3">
          {/* NTP Status */}
          {ntpStatus && (
            <div className={cn("rounded-lg border p-3 flex items-center gap-3",
              ntpStatus.synced ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200")}>
              <div className={cn("w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                ntpStatus.synced ? "bg-green-100" : "bg-red-100")}>
                <svg className={cn("w-4 h-4", ntpStatus.synced ? "text-green-600" : "text-red-600")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={cn("text-xs font-semibold", ntpStatus.synced ? "text-green-800" : "text-red-800")}>
                    {t("settings.ntp.title")}
                  </p>
                  <span className={cn("text-[8px] px-1.5 py-px rounded font-bold",
                    ntpStatus.synced ? "bg-green-200 text-green-800" : "bg-red-200 text-red-800")}>
                    {ntpStatus.synced ? "SYNCED" : "NOT SYNCED"}
                  </span>
                </div>
                <p className="text-[9px] text-gray-600 mt-0.5">
                  <span className="font-medium">{ntpStatus.ntp_server}</span>
                  {" — "}{ntpStatus.ntp_server_name}
                </p>
                <p className="text-[8px] text-gray-400 mt-0.5">
                  {t("settings.ntp.authority")}: {ntpStatus.ntp_authority} | Stratum {ntpStatus.ntp_stratum} | Offset: {ntpStatus.offset_ms}ms | {t("settings.ntp.synced")} {ntpStatus.sync_count}x
                </p>
              </div>
            </div>
          )}

          {/* Export button & history */}
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{t("settings.export_history")}</h3>
                <p className="text-[9px] text-gray-400 mt-0.5">{t("settings.export_hash_note")}</p>
              </div>
              <button onClick={handleExport} disabled={exporting}
                className="px-3 py-1.5 bg-green-600 text-white text-[10px] font-medium rounded-md hover:bg-green-700 transition disabled:opacity-50 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {exporting ? t("settings.exporting") : t("settings.export_logs")}
              </button>
            </div>

            {exports.length > 0 ? (
              <div className="overflow-hidden rounded-md border border-gray-100">
                <table className="w-full text-[10px]">
                  <thead className="bg-gray-50 text-gray-500 text-[8px] uppercase">
                    <tr>
                      <th className="px-2 py-1.5 text-left">{t("settings.export_filename")}</th>
                      <th className="px-2 py-1.5 text-left">{t("settings.export_hash")}</th>
                      <th className="px-2 py-1.5 text-center">{t("settings.export_records")}</th>
                      <th className="px-2 py-1.5 text-left">{t("settings.export_date")}</th>
                      <th className="px-2 py-1.5 text-right"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {exports.map((exp) => (
                      <tr key={exp.id} className="hover:bg-gray-50">
                        <td className="px-2 py-1.5 font-mono text-gray-700">{exp.filename}</td>
                        <td className="px-2 py-1.5 font-mono text-gray-500 max-w-[200px] truncate" title={exp.sha256_hash}>{exp.sha256_hash}</td>
                        <td className="px-2 py-1.5 text-center text-gray-600">{exp.record_count}</td>
                        <td className="px-2 py-1.5 text-gray-400">{timeAgo(exp.created_at)}</td>
                        <td className="px-2 py-1.5 text-right">
                          <button onClick={() => handleDownloadExport(exp.id)}
                            className="text-brand-600 hover:text-brand-700 font-medium">
                            {t("settings.export_download")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-[10px] text-gray-400 text-center py-2">{t("settings.export_no_history")}</p>
            )}
          </div>

          {/* Audit log table — พ.ร.บ. คอมพิวเตอร์ compliant */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
              <p className="text-[9px] text-gray-500 font-medium uppercase">{t("settings.log.title_compliance")}</p>
              <span className="text-[8px] px-1.5 py-px rounded bg-green-100 text-green-700 font-medium">{t("settings.log.compliance_badge")}</span>
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
                {logs.map((log) => {
                  const logUser = users.find(u => u.id === log.user_id);
                  const levelColor = log.log_level === "ERROR" ? "bg-red-100 text-red-700" :
                    log.log_level === "WARNING" ? "bg-amber-100 text-amber-700" :
                    log.log_level === "DEBUG" ? "bg-purple-100 text-purple-700" :
                    "bg-blue-50 text-blue-700";
                  const timeStr = formatDateTimeSeconds(log.created_at);
                  return (
                  <tr key={log.id} className={cn("hover:bg-gray-50",
                    log.log_level === "ERROR" && "bg-red-50/50",
                    log.log_level === "WARNING" && "bg-amber-50/30")}>
                    <td className="px-3 py-2 text-gray-500 text-[8px] font-mono whitespace-nowrap" title={timeStr}>{timeStr}</td>
                    <td className="px-3 py-2">
                      <span className={cn("text-[8px] px-1.5 py-px rounded font-bold", levelColor)}>
                        {log.log_level || "INFO"}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className={cn("text-[9px] px-1.5 py-px rounded-full font-medium",
                        logUser?.role === "admin" ? "bg-red-100 text-red-700" :
                        logUser?.role === "developer" ? "bg-blue-100 text-blue-700" :
                        "bg-gray-100 text-gray-600")}>
                        {log.username || logUser?.username || (log.user_id ? `#${log.user_id}` : "-")}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-[9px] px-1.5 py-px rounded bg-gray-100 text-gray-700 font-mono">{log.action}</span>
                    </td>
                    <td className="px-3 py-2 text-gray-600 text-[9px]">{log.resource_type}{log.resource_id && <span className="text-gray-400">#{log.resource_id}</span>}</td>
                    <td className="px-3 py-2 text-gray-500 text-[9px] max-w-[200px] truncate" title={log.details}>{log.details}</td>
                    <td className="px-3 py-2 text-gray-400 text-[8px] font-mono">{log.ip_address || "-"}</td>
                    <td className="px-3 py-2 text-gray-400 text-[8px] font-mono" title={`Request: ${log.request_id || "-"}\nSession: ${log.session_id || "-"}\nUA: ${log.user_agent || "-"}`}>
                      {log.request_id ? log.request_id.slice(0, 8) : "-"}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
            {logs.length === 0 && <div className="p-8 text-center text-gray-400 text-xs">{t("settings.no_logs")}</div>}
          </div>
        </div>
      )}

      {/* ===== TAB: DNS CONFIG ===== */}
      {tab === "dns" && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
            <div>
              <h3 className="font-semibold text-gray-900 text-sm">{t("settings.dns_title")}</h3>
              <p className="text-[10px] text-gray-500 mt-0.5">{t("settings.dns_desc")}</p>
            </div>

            {/* Current config */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-brand-50 rounded-md p-3">
                <p className="text-[9px] text-brand-600 font-medium uppercase">{t("settings.dns_current")}</p>
                <p className="text-sm font-bold text-brand-700 mt-0.5">{dnsConfig.domain_suffix || "..."}</p>
              </div>
              <div className="bg-gray-50 rounded-md p-3">
                <p className="text-[9px] text-gray-500 font-medium uppercase">{t("settings.dns_server_ip")}</p>
                <p className="text-sm font-bold text-gray-700 mt-0.5 font-mono">{dnsConfig.server_ip || "..."}</p>
              </div>
            </div>

            {/* Change domain */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">{t("settings.dns_domain")}</label>
              <div className="flex gap-2">
                <input type="text" value={dnsDomain} onChange={(e) => setDnsDomain(e.target.value)}
                  placeholder={t("settings.dns_domain_hint")}
                  className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
                <button onClick={handleSaveDns} disabled={savingDns || !dnsDomain.trim() || dnsDomain === dnsConfig.domain_suffix}
                  className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50">
                  {savingDns ? t("settings.dns_saving") : t("settings.dns_save")}
                </button>
              </div>
            </div>

            {/* Example */}
            <div className="bg-blue-50 rounded-md p-3 text-[10px] text-blue-800">
              <p className="font-medium">💡 {t("settings.dns_example")} <code className="bg-blue-100 px-1 rounded">{dnsDomain || "vibe.local"}</code></p>
              <p className="mt-1">{t("settings.dns_example2")} <code className="bg-blue-100 px-1 rounded font-mono">http://myapp.{dnsDomain || "vibe.local"}</code></p>
            </div>

            {/* Warning */}
            <div className="bg-amber-50 rounded-md p-3 text-[10px] text-amber-800 flex items-start gap-2">
              <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <p>{t("settings.dns_warning")}</p>
            </div>
          </div>
        </div>
      )}

      {/* ===== TAB: NETWORK ===== */}
      {tab === "network" && (
        <div className="space-y-4">
          {/* Network Info Header */}
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-blue-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 text-sm">{t("settings.net_title")}</h3>
                  <p className="text-[10px] text-gray-500">{t("settings.net_desc")}</p>
                </div>
              </div>
              <button onClick={loadNetworkInfo} disabled={loadingNetwork}
                className="px-3 py-1.5 bg-blue-600 text-white text-[10px] font-medium rounded-md hover:bg-blue-700 transition disabled:opacity-50 flex items-center gap-1">
                <svg className={cn("w-3 h-3", loadingNetwork && "animate-spin")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {t("settings.net_refresh")}
              </button>
            </div>

            {networkInfo ? (
              <>
                {/* Status Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-blue-50 rounded-md p-3">
                    <p className="text-[9px] text-blue-600 font-medium uppercase">{t("settings.net_ip")}</p>
                    <p className="text-sm font-bold text-blue-700 mt-0.5 font-mono">{networkInfo.server_ip}</p>
                  </div>
                  <div className="bg-gray-50 rounded-md p-3">
                    <p className="text-[9px] text-gray-500 font-medium uppercase">{t("settings.net_gateway")}</p>
                    <p className="text-sm font-bold text-gray-700 mt-0.5 font-mono">{networkInfo.gateway || "-"}</p>
                  </div>
                  <div className="bg-gray-50 rounded-md p-3">
                    <p className="text-[9px] text-gray-500 font-medium uppercase">{t("settings.net_hostname")}</p>
                    <p className="text-sm font-bold text-gray-700 mt-0.5 font-mono truncate" title={networkInfo.hostname}>{networkInfo.hostname}</p>
                  </div>
                  <div className={cn("rounded-md p-3", networkInfo.internet ? "bg-green-50" : "bg-red-50")}>
                    <p className={cn("text-[9px] font-medium uppercase", networkInfo.internet ? "text-green-600" : "text-red-600")}>{t("settings.net_internet")}</p>
                    <p className={cn("text-sm font-bold mt-0.5", networkInfo.internet ? "text-green-700" : "text-red-700")}>
                      {networkInfo.internet ? t("settings.net_connected") : t("settings.net_disconnected")}
                    </p>
                  </div>
                </div>

                {/* DNS Servers */}
                {networkInfo.dns_servers.length > 0 && (
                  <div className="bg-gray-50 rounded-md p-3">
                    <p className="text-[9px] text-gray-500 font-medium uppercase mb-1">{t("settings.net_dns")}</p>
                    <div className="flex gap-2 flex-wrap">
                      {networkInfo.dns_servers.map((dns, i) => (
                        <span key={i} className="text-xs font-mono bg-white px-2 py-0.5 rounded border border-gray-200 text-gray-700">{dns}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Network Interfaces Table */}
                <div>
                  <h4 className="text-xs font-semibold text-gray-800 mb-2">{t("settings.net_interfaces")}</h4>
                  <div className="bg-white rounded-md border border-gray-200 overflow-hidden">
                    <table className="w-full text-[10px]">
                      <thead className="bg-gray-50 text-gray-500 text-[8px] uppercase">
                        <tr>
                          <th className="px-3 py-1.5 text-left">{t("settings.net_col_name")}</th>
                          <th className="px-3 py-1.5 text-left">{t("settings.net_col_ip")}</th>
                          <th className="px-3 py-1.5 text-left">{t("settings.net_col_mac")}</th>
                          <th className="px-3 py-1.5 text-center">{t("settings.net_col_status")}</th>
                          <th className="px-3 py-1.5 text-right">{t("settings.net_col_speed")}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {networkInfo.interfaces.map((iface) => (
                          <tr key={iface.name} className="hover:bg-gray-50">
                            <td className="px-3 py-1.5 font-medium text-gray-900 font-mono">{iface.name}</td>
                            <td className="px-3 py-1.5 font-mono text-gray-700">{iface.ipv4 || "-"}</td>
                            <td className="px-3 py-1.5 font-mono text-gray-500 text-[9px]">{iface.mac || "-"}</td>
                            <td className="px-3 py-1.5 text-center">
                              <span className={cn("text-[8px] px-1.5 py-px rounded font-bold",
                                iface.is_up ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600")}>
                                {iface.is_up ? t("settings.net_up") : t("settings.net_down")}
                              </span>
                            </td>
                            <td className="px-3 py-1.5 text-right text-gray-600">
                              {iface.speed > 0 ? `${iface.speed} Mbps` : "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-6 text-center text-gray-400 text-xs">
                {loadingNetwork ? (
                  <div className="flex items-center justify-center gap-2">
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Loading...
                  </div>
                ) : "..."}
              </div>
            )}
          </div>

          {/* Quick Setup — mDNS */}
          <div className="bg-white rounded-lg border-2 border-brand-200 p-4 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-brand-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-brand-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{t("settings.net_mdns_quick_title")}</h3>
                <p className="text-[10px] text-gray-500">{t("settings.net_mdns_quick_desc")}</p>
              </div>
            </div>

            {/* mDNS Status Banner */}
            {mdnsStatus && (
              <div className={cn("rounded-lg border p-3 flex items-center gap-3",
                mdnsStatus.running ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200")}>
                <div className={cn("w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                  mdnsStatus.running ? "bg-green-100" : "bg-amber-100")}>
                  <svg className={cn("w-4 h-4", mdnsStatus.running ? "text-green-600" : "text-amber-600")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className={cn("text-xs font-semibold", mdnsStatus.running ? "text-green-800" : "text-amber-800")}>
                      {t("settings.net_mdns_status")}
                    </p>
                    <span className={cn("text-[8px] px-1.5 py-px rounded font-bold",
                      mdnsStatus.running ? "bg-green-200 text-green-800" : "bg-amber-200 text-amber-800")}>
                      {mdnsStatus.running ? t("settings.net_mdns_active") : t("settings.net_mdns_inactive")}
                    </span>
                  </div>
                  <p className="text-[9px] text-gray-600 mt-0.5">
                    <span className="font-medium">{t("settings.net_mdns_hostname")}:</span>{" "}
                    <code className="bg-white px-1.5 py-px rounded font-mono text-brand-700 text-sm font-bold">{mdnsStatus.mdns_address}</code>
                    <span className="text-gray-400 ml-2">({mdnsStatus.ip}:{mdnsStatus.port})</span>
                  </p>
                </div>
              </div>
            )}

            {/* Quick Setup 3 Steps */}
            <div className="space-y-2">
              <div className="flex items-start gap-3 bg-brand-50 rounded-md p-3">
                <div className="w-7 h-7 rounded-full bg-brand-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">1</div>
                <div className="flex-1">
                  <p className="text-[11px] text-brand-900 font-medium">{t("settings.net_mdns_quick_step1")}</p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-brand-50 rounded-md p-3">
                <div className="w-7 h-7 rounded-full bg-brand-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">2</div>
                <div className="flex-1">
                  <p className="text-[11px] text-brand-900 font-medium">
                    {t("settings.net_mdns_quick_step2_pre")}:{" "}
                    <code className="bg-brand-100 px-2 py-0.5 rounded font-mono text-brand-800 text-sm font-bold">
                      http://{mdnsStatus?.mdns_address || "ivs.local"}:{mdnsStatus?.port || 3000}
                    </code>
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-amber-50 rounded-md p-3">
                <div className="w-7 h-7 rounded-full bg-amber-500 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">3</div>
                <div className="flex-1 space-y-2">
                  <p className="text-[11px] text-amber-900 font-medium">{t("settings.net_mdns_quick_step3")}</p>
                  <a href="https://support.apple.com/kb/DL999" target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-[10px] font-medium rounded-md hover:bg-blue-700 transition">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {t("settings.net_mdns_download_bonjour")}
                  </a>
                  <p className="text-[9px] text-gray-500">{t("settings.net_mdns_win_note")}</p>
                </div>
              </div>
            </div>

            {/* Linux note */}
            <div className="bg-gray-900 rounded-md p-3">
              <p className="text-[9px] text-gray-400 mb-1">Linux</p>
              <code className="text-[10px] text-green-400 font-mono block">{t("settings.net_mdns_linux")}</code>
            </div>
          </div>

          {/* mDNS Config — Editable */}
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-purple-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{t("settings.net_mdns_edit_title")}</h3>
                <p className="text-[10px] text-gray-500">{t("settings.net_mdns_edit_desc")}</p>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">{t("settings.net_mdns_input_label")}</label>
              <div className="relative">
                <input type="text" value={mdnsInput} onChange={(e) => setMdnsInput(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  placeholder={t("settings.net_mdns_input_hint")}
                  className="w-full px-2.5 py-1.5 pr-14 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none font-mono" />
                <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-gray-400">.local</span>
              </div>
              <p className="text-[9px] text-gray-400">{t("settings.net_mdns_default_note")}</p>
              <div className="flex gap-2">
                <button onClick={handleSaveMdns} disabled={savingMdns || !mdnsInput.trim() || mdnsInput === mdnsStatus?.hostname}
                  className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50">
                  {savingMdns ? t("settings.net_mdns_saving") : t("settings.net_mdns_save")}
                </button>
                <button onClick={handleResetMdns} disabled={resettingMdns || mdnsStatus?.hostname === mdnsStatus?.default_hostname}
                  className="px-3 py-1.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-md hover:bg-gray-200 transition disabled:opacity-50">
                  {resettingMdns ? t("settings.net_mdns_resetting") : t("settings.net_mdns_reset")}
                </button>
              </div>
            </div>

            {/* Preview */}
            {mdnsInput && (
              <div className="bg-blue-50 rounded-md p-3 text-[10px] text-blue-800">
                <p className="font-medium">
                  URL: <code className="bg-blue-100 px-1 rounded font-mono">http://{mdnsInput}.local:{mdnsStatus?.port || 3000}</code>
                </p>
              </div>
            )}
          </div>

          {/* Static IP Guide */}
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-amber-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{t("settings.net_static_title")}</h3>
                <p className="text-[10px] text-gray-500">{t("settings.net_static_desc")}</p>
              </div>
            </div>

            {/* Why Static IP */}
            <div className="bg-amber-50 rounded-md p-3 space-y-2">
              <p className="text-xs font-semibold text-amber-800">{t("settings.net_static_why")}</p>
              <ul className="space-y-1.5">
                {["reason1", "reason2", "reason3"].map((key) => (
                  <li key={key} className="flex items-start gap-2 text-[10px] text-amber-700">
                    <svg className="w-3.5 h-3.5 text-amber-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    {t(`settings.net_static_${key}`)}
                  </li>
                ))}
              </ul>
            </div>

            {/* Method 1: Ubuntu/Debian netplan */}
            <div>
              <h4 className="text-xs font-semibold text-gray-800 mb-2">{t("settings.net_static_ubuntu")}</h4>
              <div className="bg-gray-900 rounded-md p-3">
                <p className="text-[9px] text-gray-400 mb-1">/etc/netplan/01-static.yaml</p>
                <code className="text-[10px] text-green-400 font-mono block whitespace-pre">{`network:
  version: 2
  ethernets:
    ${networkInfo?.interfaces.find(i => i.is_up && i.ipv4)?.name || "eth0"}:
      dhcp4: no
      addresses:
        - ${networkInfo?.server_ip || "192.168.1.100"}/24
      routes:
        - to: default
          via: ${networkInfo?.gateway || "192.168.1.1"}
      nameservers:
        addresses: [${networkInfo?.dns_servers.join(", ") || "8.8.8.8, 1.1.1.1"}]`}</code>
                <p className="text-[9px] text-gray-400 mt-2">sudo netplan apply</p>
              </div>
            </div>

            {/* Method 2: macOS */}
            <div>
              <h4 className="text-xs font-semibold text-gray-800 mb-2">{t("settings.net_static_macos")}</h4>
              <div className="bg-gray-900 rounded-md p-3">
                <p className="text-[9px] text-gray-400 mb-1">System Settings &gt; Network &gt; Ethernet &gt; Details &gt; TCP/IP</p>
                <code className="text-[10px] text-green-400 font-mono block whitespace-pre">{`Configure IPv4: Manually
IP Address:    ${networkInfo?.server_ip || "192.168.1.100"}
Subnet Mask:   ${networkInfo?.interfaces.find(i => i.ipv4 === networkInfo?.server_ip)?.netmask || "255.255.255.0"}
Router:        ${networkInfo?.gateway || "192.168.1.1"}
DNS Servers:   ${networkInfo?.dns_servers.join(", ") || "8.8.8.8, 1.1.1.1"}`}</code>
              </div>
            </div>

            {/* Method 3: Router DHCP Reservation */}
            <div className="bg-blue-50 rounded-md p-3 space-y-1.5">
              <p className="text-xs font-semibold text-blue-800">{t("settings.net_static_router")}</p>
              <p className="text-[10px] text-blue-700">{t("settings.net_static_router_desc")}</p>
              {networkInfo && (
                <div className="bg-blue-100 rounded p-2 mt-1">
                  <code className="text-[10px] text-blue-900 font-mono block">
                    MAC: {networkInfo.interfaces.find(i => i.ipv4 === networkInfo.server_ip)?.mac || networkInfo.interfaces.find(i => i.is_up && i.mac)?.mac || "N/A"}
                  </code>
                  <code className="text-[10px] text-blue-900 font-mono block mt-0.5">
                    IP: {networkInfo.server_ip}
                  </code>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ===== TAB: PDPA ===== */}
      {tab === "pdpa" && (
        <div className="space-y-4">
          {/* Header + Actions */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                  <span className="text-lg">🛡️</span>
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 text-sm">{t("settings.pdpa_title")}</h3>
                  <p className="text-[10px] text-gray-500">{t("settings.pdpa_desc")}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleScanAll} disabled={scanningAll}
                  className="px-3 py-1.5 bg-blue-50 text-blue-700 text-xs font-medium rounded-md hover:bg-blue-100 transition disabled:opacity-50">
                  {scanningAll ? t("settings.pdpa_scanning") : t("settings.pdpa_scan_all")}
                </button>
                <button onClick={handleExportRopa} disabled={exportingRopa || pdpaRecords.length === 0}
                  className="px-3 py-1.5 bg-purple-600 text-white text-xs font-medium rounded-md hover:bg-purple-700 transition disabled:opacity-50">
                  {exportingRopa ? t("settings.pdpa_exporting") : t("settings.pdpa_export")}
                </button>
              </div>
            </div>
          </div>

          {/* Toast notification */}
          {toastMsg && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center justify-between">
              <span className="text-green-800 text-xs font-medium">{toastMsg}</span>
              <button onClick={() => setToastMsg(null)} className="text-green-600 hover:text-green-800 text-sm ml-3">✕</button>
            </div>
          )}

          {/* ROPA Table */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            {loadingPdpa ? (
              <div className="p-8 text-center text-gray-400 text-xs">Loading...</div>
            ) : pdpaRecords.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-xs">{t("settings.pdpa_no_apps")}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">#</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_app")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_purpose")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_pii")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_retention")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_masking")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pn_col")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_status")}</th>
                      <th className="px-3 py-2 text-left font-semibold text-gray-600">{t("settings.pdpa_col_action")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {pdpaRecords.map((r, i) => (
                      <tr key={r.app_id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-400">{i + 1}</td>
                        <td className="px-3 py-2 font-medium text-gray-900">{r.app_name}</td>
                        <td className="px-3 py-2 text-gray-600 max-w-[150px] truncate">{r.purpose || <span className="text-gray-300">—</span>}</td>
                        <td className="px-3 py-2 max-w-[200px]">
                          {(r.pii_fields?.length > 0 || r.pii_auto_detected?.length > 0) ? (
                            <div className="flex flex-wrap gap-0.5">
                              {(r.pii_fields?.length > 0 ? r.pii_fields : r.pii_auto_detected)?.slice(0, 3).map((f: string) => (
                                <span key={f} className="px-1 py-0.5 bg-orange-50 text-orange-700 rounded text-[9px]">{f}</span>
                              ))}
                              {((r.pii_fields?.length || r.pii_auto_detected?.length || 0) > 3) && (
                                <span className="px-1 py-0.5 text-gray-400 text-[9px]">+{(r.pii_fields?.length || r.pii_auto_detected?.length) - 3}</span>
                              )}
                            </div>
                          ) : <span className="text-gray-300">—</span>}
                        </td>
                        <td className="px-3 py-2 text-gray-600">{r.retention_period || <span className="text-gray-300">—</span>}</td>
                        <td className="px-3 py-2">
                          {r.has_masking ? (
                            <span className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded text-[9px]">✓ พบ</span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-red-50 text-red-600 rounded text-[9px]">✗ ไม่พบ</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {r.privacy_notice_enabled ? (
                            <span className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded text-[9px] cursor-pointer hover:bg-green-100" onClick={() => openPNEdit(r)}>✓ {t("settings.pn_enabled")}</span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-[9px] cursor-pointer hover:bg-gray-200" onClick={() => openPNEdit(r)}>{t("settings.pn_disabled")}</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <span className={cn("px-1.5 py-0.5 rounded text-[9px] font-medium", pdpaStatusBadge[r.status] || pdpaStatusBadge.not_started)}>
                            {t(`settings.pdpa_status_${r.status}`)}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-1">
                            <button onClick={() => openPdpaEdit(r)} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-[9px] hover:bg-blue-100">
                              {t("settings.pdpa_edit")}
                            </button>
                            <button onClick={() => handleScanApp(r.app_id)} className="px-2 py-0.5 bg-gray-50 text-gray-600 rounded text-[9px] hover:bg-gray-100">
                              {t("settings.pdpa_scan")}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Security Base Info */}
          <div className="bg-blue-50 rounded-lg border border-blue-200 p-3">
            <p className="text-[10px] text-blue-700 font-medium">🔒 {t("settings.pdpa_security_base")}</p>
          </div>

          {/* Scan Result Modal */}
          {scanResult && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setScanResult(null)}>
              <div className="bg-white rounded-lg shadow-xl p-5 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center mb-3">
                  <h3 className="font-semibold text-sm text-gray-900">{t("settings.pdpa_scan_result")}: {scanResult.app_name}</h3>
                  <button onClick={() => setScanResult(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div className="bg-gray-50 rounded p-2">
                    <p className="text-[9px] text-gray-500">{t("settings.pdpa_files_scanned")}</p>
                    <p className="text-sm font-bold text-gray-900">{scanResult.files_scanned}</p>
                  </div>
                  <div className={cn("rounded p-2", scanResult.masking_detected ? "bg-green-50" : "bg-red-50")}>
                    <p className="text-[9px] text-gray-500">{t("settings.pdpa_col_masking")}</p>
                    <p className={cn("text-sm font-bold", scanResult.masking_detected ? "text-green-700" : "text-red-600")}>
                      {scanResult.masking_detected ? t("settings.pdpa_found_masking") : t("settings.pdpa_no_masking")}
                    </p>
                  </div>
                </div>

                {scanResult.pii_fields_detected?.length > 0 && (
                  <div className="mb-3">
                    <p className="text-[10px] font-medium text-gray-700 mb-1">{t("settings.pdpa_found_pii")}:</p>
                    <div className="flex flex-wrap gap-1">
                      {scanResult.pii_fields_detected.map((f: string) => (
                        <span key={f} className="px-2 py-0.5 bg-orange-50 text-orange-700 rounded text-[10px]">{f}</span>
                      ))}
                    </div>
                  </div>
                )}

                {!scanResult.masking_detected && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-2 mb-3">
                    <p className="text-[10px] text-yellow-700">⚠️ {t("settings.pdpa_masking_warn")}</p>
                  </div>
                )}

                {scanResult.masking_patterns?.length > 0 && (
                  <div className="mb-3">
                    <p className="text-[10px] font-medium text-gray-700 mb-1">Masking patterns:</p>
                    <div className="bg-gray-50 rounded p-2 space-y-0.5 max-h-32 overflow-y-auto">
                      {scanResult.masking_patterns.map((p: string, i: number) => (
                        <p key={i} className="text-[9px] text-gray-600 font-mono">{p}</p>
                      ))}
                    </div>
                  </div>
                )}

                {scanResult.scan_details?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-medium text-gray-700 mb-1">Scan Details ({scanResult.scan_details.length} items):</p>
                    <div className="bg-gray-50 rounded p-2 max-h-40 overflow-y-auto">
                      <table className="w-full text-[9px]">
                        <thead><tr className="text-gray-500"><th className="text-left pr-2">File</th><th className="text-left pr-2">Line</th><th className="text-left pr-2">Field</th><th className="text-left">Category</th></tr></thead>
                        <tbody>
                          {scanResult.scan_details.slice(0, 20).map((d: any, i: number) => (
                            <tr key={i} className="border-t border-gray-100">
                              <td className="pr-2 py-0.5 font-mono text-blue-600">{d.file}</td>
                              <td className="pr-2 py-0.5">{d.line}</td>
                              <td className="pr-2 py-0.5 font-mono">{d.field}</td>
                              <td className="py-0.5">{d.category}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Edit PDPA Modal */}
          {editPdpa && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditPdpa(null)}>
              <div className="bg-white rounded-lg shadow-xl p-5 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-semibold text-sm text-gray-900">{t("settings.pdpa_modal_title")}: {editPdpa.app_name}</h3>
                  <button onClick={() => setEditPdpa(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
                </div>

                <div className="space-y-4">
                  {/* Purpose */}
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">{t("settings.pdpa_purpose_label")}</label>
                    <textarea value={pdpaForm.purpose} onChange={e => setPdpaForm(prev => ({ ...prev, purpose: e.target.value }))}
                      placeholder={t("settings.pdpa_purpose_hint")}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none resize-none h-16" />
                  </div>

                  {/* PII Fields */}
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">{t("settings.pdpa_pii_label")}</label>

                    {/* Auto-detected PII */}
                    {editPdpa.pii_auto_detected?.length > 0 && (
                      <div className="mb-2">
                        <p className="text-[9px] text-blue-600 font-medium mb-1">🔍 {t("settings.pdpa_pii_auto")}:</p>
                        <div className="flex flex-wrap gap-1 mb-1">
                          {editPdpa.pii_auto_detected.map((f: string) => (
                            <span key={f} className={cn("px-1.5 py-0.5 rounded text-[9px] cursor-pointer border",
                              pdpaForm.pii_fields.includes(f) ? "bg-blue-100 text-blue-700 border-blue-300" : "bg-gray-50 text-gray-500 border-gray-200 hover:bg-blue-50"
                            )} onClick={() => {
                              if (pdpaForm.pii_fields.includes(f)) removePiiField(f);
                              else setPdpaForm(prev => ({ ...prev, pii_fields: [...prev.pii_fields, f] }));
                            }}>{f}</span>
                          ))}
                        </div>
                        <button onClick={() => addAutoDetectedPii(editPdpa.pii_auto_detected)}
                          className="text-[9px] text-blue-600 hover:text-blue-800 underline">
                          เพิ่มทั้งหมดที่ตรวจพบ
                        </button>
                      </div>
                    )}

                    {/* Checklist */}
                    <div className="grid grid-cols-2 gap-1 mb-2">
                      {PII_CHECKLIST.map(field => (
                        <label key={field} className="flex items-center gap-1.5 text-[10px] text-gray-600 cursor-pointer hover:text-gray-900">
                          <input type="checkbox" checked={pdpaForm.pii_fields.includes(field)}
                            onChange={() => {
                              if (pdpaForm.pii_fields.includes(field)) removePiiField(field);
                              else setPdpaForm(prev => ({ ...prev, pii_fields: [...prev.pii_fields, field] }));
                            }}
                            className="w-3 h-3 rounded border-gray-300 text-purple-600 focus:ring-purple-500" />
                          {field}
                        </label>
                      ))}
                    </div>

                    {/* Manual add */}
                    <div className="flex gap-1">
                      <input type="text" value={piiInput} onChange={e => setPiiInput(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && addPiiField()}
                        placeholder={t("settings.pdpa_pii_manual")}
                        className="flex-1 px-2 py-1 border border-gray-300 rounded text-[10px] outline-none focus:ring-1 focus:ring-purple-500" />
                      <button onClick={addPiiField} className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-[10px] hover:bg-gray-200">+</button>
                    </div>

                    {/* Selected PII tags */}
                    {pdpaForm.pii_fields.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {pdpaForm.pii_fields.map(f => (
                          <span key={f} className="px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded text-[9px] flex items-center gap-1">
                            {f}
                            <button onClick={() => removePiiField(f)} className="text-purple-400 hover:text-purple-600">&times;</button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Retention Period */}
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">{t("settings.pdpa_retention_label")}</label>
                    <input type="text" value={pdpaForm.retention_period} onChange={e => setPdpaForm(prev => ({ ...prev, retention_period: e.target.value }))}
                      placeholder={t("settings.pdpa_retention_hint")}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none" />
                  </div>

                  {/* Security Notes */}
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">{t("settings.pdpa_security_label")}</label>
                    <textarea value={pdpaForm.security_notes} onChange={e => setPdpaForm(prev => ({ ...prev, security_notes: e.target.value }))}
                      placeholder={t("settings.pdpa_security_hint")}
                      className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none resize-none h-12" />
                    <p className="text-[9px] text-gray-400 mt-0.5">🔒 {t("settings.pdpa_security_base")}</p>
                  </div>

                  {/* Masking Status */}
                  {editPdpa.masking_details && (
                    <div className={cn("rounded p-2 text-[10px]", editPdpa.has_masking ? "bg-green-50 text-green-700" : "bg-yellow-50 text-yellow-700")}>
                      <p className="font-medium mb-1">{editPdpa.has_masking ? "✓ " + t("settings.pdpa_found_masking") : "⚠️ " + t("settings.pdpa_no_masking")}</p>
                      <p className="text-[9px] opacity-75 whitespace-pre-wrap">{editPdpa.masking_details}</p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
                    <button onClick={() => setEditPdpa(null)} className="px-4 py-1.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-md hover:bg-gray-200">
                      {t("settings.pdpa_cancel")}
                    </button>
                    <button onClick={handleSavePdpa} disabled={savingPdpa}
                      className="px-4 py-1.5 bg-purple-600 text-white text-xs font-medium rounded-md hover:bg-purple-700 transition disabled:opacity-50">
                      {savingPdpa ? t("settings.pdpa_saving") : t("settings.pdpa_save")}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Privacy Notice Edit Modal */}
          {editPN && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditPN(null)}>
              <div className="bg-white rounded-lg shadow-xl w-[560px] max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-semibold text-sm text-gray-900">{t("settings.pn_title")}: {editPN.app_name}</h3>
                  <button onClick={() => setEditPN(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
                </div>
                <div className="p-4 space-y-4">
                  <p className="text-[10px] text-gray-500">{t("settings.pn_desc")}</p>

                  {/* Toggle */}
                  <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-purple-900">{t("settings.pn_toggle")}</p>
                      <p className="text-[10px] text-purple-600">{t("settings.pn_toggle_hint")}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setPnForm(prev => ({ ...prev, privacy_notice_enabled: !prev.privacy_notice_enabled }))}
                      className={cn("relative inline-flex h-6 w-11 flex-shrink-0 rounded-full border-2 border-transparent cursor-pointer transition-colors", pnForm.privacy_notice_enabled ? "bg-purple-600" : "bg-gray-300")}
                    >
                      <span className={cn("pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform", pnForm.privacy_notice_enabled ? "translate-x-5" : "translate-x-0")} />
                    </button>
                  </div>

                  {/* Fields — shown when enabled */}
                  {pnForm.privacy_notice_enabled && (
                    <div className="space-y-3">
                      {/* Notice Title */}
                      <div>
                        <label className="block text-[10px] font-medium text-gray-700 mb-1">{t("settings.pn_notice_title")}</label>
                        <input
                          type="text"
                          value={pnForm.privacy_notice_title}
                          onChange={e => setPnForm(prev => ({ ...prev, privacy_notice_title: e.target.value }))}
                          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:ring-1 focus:ring-purple-500 focus:border-purple-500"
                          placeholder="ประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล"
                        />
                      </div>

                      {/* Notice Detail */}
                      <div>
                        <label className="block text-[10px] font-medium text-gray-700 mb-1">{t("settings.pn_notice_detail")}</label>
                        <p className="text-[9px] text-gray-400 mb-1">{t("settings.pn_notice_detail_hint")}</p>
                        <textarea
                          value={pnForm.privacy_notice_detail}
                          onChange={e => setPnForm(prev => ({ ...prev, privacy_notice_detail: e.target.value }))}
                          rows={4}
                          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:ring-1 focus:ring-purple-500 focus:border-purple-500"
                          placeholder="แอปพลิเคชันนี้มีการเก็บรวบรวม ใช้ หรือเปิดเผยข้อมูลส่วนบุคคลของท่าน เพื่อวัตถุประสงค์ในการให้บริการ..."
                        />
                      </div>

                      {/* Privacy Policy URL */}
                      <div>
                        <label className="block text-[10px] font-medium text-gray-700 mb-1">{t("settings.pn_policy_url")}</label>
                        <input
                          type="url"
                          value={pnForm.privacy_policy_url}
                          onChange={e => setPnForm(prev => ({ ...prev, privacy_policy_url: e.target.value }))}
                          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:ring-1 focus:ring-purple-500 focus:border-purple-500"
                          placeholder="https://example.com/privacy-policy"
                        />
                      </div>

                      {/* Privacy Notice URL */}
                      <div>
                        <label className="block text-[10px] font-medium text-gray-700 mb-1">{t("settings.pn_notice_url")}</label>
                        <input
                          type="url"
                          value={pnForm.privacy_notice_url}
                          onChange={e => setPnForm(prev => ({ ...prev, privacy_notice_url: e.target.value }))}
                          className="w-full border border-gray-300 rounded px-2 py-1.5 text-xs focus:ring-1 focus:ring-purple-500 focus:border-purple-500"
                          placeholder="https://example.com/privacy-notice"
                        />
                      </div>

                      {/* Preview */}
                      <div className="border border-dashed border-purple-300 rounded-lg p-3 bg-purple-50/50">
                        <p className="text-[10px] font-medium text-purple-700 mb-2">👁️ {t("settings.pn_preview")}</p>
                        <div className="bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-lg">🛡️</span>
                            <h4 className="text-xs font-bold text-gray-900">{pnForm.privacy_notice_title || "ประกาศแจ้งเตือน"}</h4>
                          </div>
                          <p className="text-[10px] text-gray-600 mb-2 whitespace-pre-wrap">{pnForm.privacy_notice_detail || "รายละเอียดจะแสดงที่นี่..."}</p>
                          <div className="flex gap-2 text-[9px]">
                            {pnForm.privacy_policy_url && <span className="text-blue-600 underline">Privacy Policy ↗</span>}
                            {pnForm.privacy_notice_url && <span className="text-blue-600 underline">รายละเอียดเพิ่มเติม ↗</span>}
                          </div>
                          <div className="mt-3 flex justify-end">
                            <span className="px-3 py-1 bg-purple-600 text-white text-[10px] rounded">ยอมรับและเข้าใช้งาน</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Save/Cancel */}
                  <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                    <button onClick={() => setEditPN(null)} className="px-4 py-1.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-md hover:bg-gray-200">
                      {t("settings.pdpa_cancel")}
                    </button>
                    <button onClick={handleSavePN} disabled={savingPN}
                      className="px-4 py-1.5 bg-purple-600 text-white text-xs font-medium rounded-md hover:bg-purple-700 transition disabled:opacity-50">
                      {savingPN ? t("settings.pn_saving") : t("settings.pn_save")}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===== TAB: GITEA ===== */}
      {tab === "gitea" && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-green-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{t("settings.gitea_title")}</h3>
                <p className="text-[10px] text-gray-500">{t("settings.gitea_desc")}</p>
              </div>
            </div>

            {/* URL & Open button */}
            <div className="bg-gray-50 rounded-md p-3 flex items-center justify-between">
              <div>
                <p className="text-[9px] text-gray-500 font-medium uppercase">{t("settings.gitea_url")}</p>
                <p className="text-sm font-mono text-gray-700 mt-0.5">http://git.{dnsConfig.domain_suffix || "vibe.local"}:3001</p>
              </div>
              <a href={`http://git.${dnsConfig.domain_suffix || "vibe.local"}:3001`} target="_blank" rel="noopener noreferrer"
                className="px-3 py-1.5 bg-green-600 text-white text-[10px] font-medium rounded-md hover:bg-green-700 transition flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                {t("settings.gitea_open")}
              </a>
            </div>

            {/* Features */}
            <div>
              <h4 className="text-xs font-semibold text-gray-800 mb-2">{t("settings.gitea_features_title")}</h4>
              <div className="grid grid-cols-2 gap-2">
                {["gitea_f1", "gitea_f2", "gitea_f3", "gitea_f4"].map((key) => (
                  <div key={key} className="flex items-start gap-2 bg-green-50 rounded-md p-2.5">
                    <svg className="w-3.5 h-3.5 text-green-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <p className="text-[10px] text-green-800">{t(`settings.${key}`)}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Backup & Restore */}
            <div>
              <h4 className="text-xs font-semibold text-gray-800 mb-2">{t("settings.gitea_backup_title")}</h4>
              <div className="space-y-2">
                <div className="bg-gray-900 rounded-md p-3">
                  <p className="text-[9px] text-gray-400 mb-1">{t("settings.gitea_backup_cmd")}</p>
                  <code className="text-[10px] text-green-400 font-mono block">docker exec -u git gitea gitea dump -c /data/gitea/conf/app.ini</code>
                </div>
                <div className="bg-gray-900 rounded-md p-3">
                  <p className="text-[9px] text-gray-400 mb-1">{t("settings.gitea_restore_cmd")}</p>
                  <code className="text-[10px] text-green-400 font-mono block">unzip gitea-dump-*.zip -d /data/gitea-restore/</code>
                </div>
              </div>
            </div>

            {/* External Backup */}
            <div className="bg-amber-50 rounded-md p-3 space-y-1.5">
              <p className="text-xs font-semibold text-amber-800">{t("settings.gitea_backup_external")}</p>
              <p className="text-[10px] text-amber-700">{t("settings.gitea_backup_ext_desc")}</p>
              <div className="bg-amber-100 rounded p-2">
                <code className="text-[10px] text-amber-900 font-mono block">cp gitea-dump-*.zip /mnt/usb-backup/</code>
                <code className="text-[10px] text-amber-900 font-mono block mt-0.5">rclone copy gitea-dump-*.zip remote:backup/gitea/</code>
              </div>
              <p className="text-[9px] text-amber-600 mt-1">{t("settings.gitea_backup_note")}</p>
            </div>
          </div>
        </div>
      )}

      {/* ===== TAB: AUTO-START ===== */}
      {tab === "autostart" && (
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                <svg className="w-6 h-6 text-orange-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{t("settings.autostart_title")}</h3>
                <p className="text-[10px] text-gray-500">{t("settings.autostart_desc")}</p>
              </div>
            </div>

            {/* Steps */}
            <div className="space-y-2">
              {[
                { step: "1", key: "step1", icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
                { step: "2", key: "step2", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
                { step: "3", key: "step3", icon: "M5 13l4 4L19 7" },
              ].map(({ step, key, icon }) => (
                <div key={step} className="flex items-start gap-3 bg-orange-50 rounded-md p-3">
                  <div className="w-6 h-6 rounded-full bg-orange-500 text-white flex items-center justify-center text-[10px] font-bold flex-shrink-0">{step}</div>
                  <div>
                    <p className="text-xs font-semibold text-orange-900">{t(`settings.autostart_${key}`)}</p>
                    <p className="text-[10px] text-orange-700 mt-0.5">{t(`settings.autostart_${key}_desc`)}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Brand table */}
            <div>
              <h4 className="text-xs font-semibold text-gray-800 mb-2">{t("settings.autostart_keywords")}</h4>
              <div className="bg-white rounded-md border border-gray-200 overflow-hidden">
                <table className="w-full text-[10px]">
                  <thead className="bg-gray-50 text-gray-500 text-[8px] uppercase">
                    <tr>
                      <th className="px-3 py-1.5 text-left">{t("settings.autostart_brand")}</th>
                      <th className="px-3 py-1.5 text-left">{t("settings.autostart_setting_name")}</th>
                      <th className="px-3 py-1.5 text-left">{t("settings.autostart_location")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {[
                      { brand: "ASUS", setting: "Restore on AC Power Loss", location: "Advanced > APM Configuration" },
                      { brand: "Dell", setting: "AC Recovery", location: "Power Management" },
                      { brand: "HP", setting: "After Power Loss", location: "Advanced > Power-On Options" },
                      { brand: "Lenovo", setting: "After Power Loss", location: "Power > Automatic Power On" },
                      { brand: "Gigabyte", setting: "AC Back", location: "Power Management" },
                      { brand: "MSI", setting: "Restore on AC Power Loss", location: "Settings > Advanced" },
                      { brand: "ASRock", setting: "Restore on AC/Power Loss", location: "Advanced > Chipset Configuration" },
                      { brand: "Intel NUC", setting: "After Power Failure", location: "Power > Secondary Power Settings" },
                      { brand: "Supermicro", setting: "State after G3", location: "Advanced > Chipset Configuration" },
                    ].map((row) => (
                      <tr key={row.brand} className="hover:bg-gray-50">
                        <td className="px-3 py-1.5 font-medium text-gray-900">{row.brand}</td>
                        <td className="px-3 py-1.5 font-mono text-brand-700">{row.setting}</td>
                        <td className="px-3 py-1.5 text-gray-500">{row.location}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Docker Auto-Start */}
            <div className="bg-blue-50 rounded-md p-3 space-y-1.5">
              <p className="text-xs font-semibold text-blue-800">{t("settings.autostart_docker_title")}</p>
              <p className="text-[10px] text-blue-700">{t("settings.autostart_docker_desc")}</p>
            </div>

            {/* IVS Auto-Start */}
            <div className="bg-green-50 rounded-md p-3 space-y-1.5">
              <p className="text-xs font-semibold text-green-800">{t("settings.autostart_ivs_title")}</p>
              <p className="text-[10px] text-green-700">{t("settings.autostart_ivs_desc")}</p>
              <div className="bg-gray-900 rounded p-2 mt-1">
                <code className="text-[10px] text-green-400 font-mono block whitespace-pre">{`# docker-compose.yml
services:
  backend:
    restart: always
  frontend:
    restart: always
  caddy:
    restart: always
  coredns:
    restart: always
  gitea:
    restart: always`}</code>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
