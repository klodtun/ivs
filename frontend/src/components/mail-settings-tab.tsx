"use client";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  MailConfig,
  MailOutboxRow,
  MailRopa,
  MailBasisOption,
  MailTestResult,
} from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, formatDateTimeSeconds } from "@/lib/utils";

/**
 * แถบ "จดหมาย" ในหน้าตั้งค่า — โมดูลจดหมาย ระยะที่ 0
 *
 * สามส่วนบนหน้าเดียว: ตั้งค่าตัวรีเลย์ (พร้อมส่งทดสอบที่คืนข้อความจริงจาก
 * เซิร์ฟเวอร์), ทะเบียน ROPA ของกิจกรรมนี้ (ระบบกรอกให้ มนุษย์ยืนยัน), และคิว
 * จดหมายล่าสุด เหตุที่อยู่ในไฟล์เดียวแยกจากหน้าตั้งค่า เพราะหน้านั้นยาวเกิน
 * สองพันบรรทัดแล้ว และสามส่วนนี้แชร์สถานะกัน (บันทึกการตั้งค่าแล้ว ROPA ต้องรีเฟรช)
 */

const inputCls =
  "w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500";
const labelCls = "block text-xs font-medium text-gray-700 mb-1";

const STATUS_STYLE: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  sending: "bg-blue-100 text-blue-700",
  sent: "bg-green-100 text-green-700",
  failed: "bg-amber-100 text-amber-800",
  dead: "bg-red-100 text-red-700",
};

export function MailSettingsTab() {
  const { t, locale } = useLang();
  const th = locale === "th";

  const [cfg, setCfg] = useState<MailConfig | null>(null);
  const [form, setForm] = useState({
    enabled: false, preset: "custom", host: "", port: 587, security: "starttls",
    username: "", password: "", from_address: "", from_name: "iVS", locale: "th",
    recipients: "", dashboard_url: "",
  });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<MailTestResult | null>(null);

  const [ropa, setRopa] = useState<MailRopa | null>(null);
  const [bases, setBases] = useState<MailBasisOption[]>([]);
  const [ropaBasis, setRopaBasis] = useState("legitimate_interest");
  const [dpaUrl, setDpaUrl] = useState("");
  const [dpaNote, setDpaNote] = useState("");
  const [confirming, setConfirming] = useState(false);

  const [outbox, setOutbox] = useState<MailOutboxRow[]>([]);
  const [processing, setProcessing] = useState(false);

  const load = useCallback(async () => {
    try {
      const c = await api.getMailConfig();
      setCfg(c);
      setForm({
        enabled: c.enabled, preset: c.preset, host: c.host, port: c.port, security: c.security,
        username: c.username, password: "", from_address: c.from_address, from_name: c.from_name,
        locale: c.locale, recipients: c.recipients_raw, dashboard_url: c.dashboard_url,
      });
    } catch (e) { console.error("load mail cfg", e); }
    try {
      const r = await api.getMailRopa();
      setRopa(r.record);
      setBases(r.basis_options);
      setRopaBasis(r.record.legal_basis || "legitimate_interest");
      setDpaUrl(r.record.dpa_url || "");
      setDpaNote(r.record.dpa_note || "");
    } catch (e) { console.error("load mail ropa", e); }
    try { setOutbox(await api.getMailOutbox(30)); } catch (e) { console.error("load outbox", e); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const applyPreset = (key: string) => {
    const p = cfg?.presets?.[key];
    setForm((f) => ({
      ...f, preset: key,
      ...(p && p.host ? { host: p.host, port: p.port, security: p.security } : {}),
    }));
  };

  const save = async () => {
    setSaving(true); setMsg("");
    try {
      const body: Record<string, unknown> = { ...form, port: Number(form.port) };
      // รหัสผ่าน: ว่าง = ไม่เปลี่ยน · พิมพ์ช่องว่างหนึ่งตัว = ล้าง (แบบเดียวกับโทเคนอุโมงค์)
      if (!form.password) delete body.password;
      else body.password = form.password === " " ? "" : form.password;
      await api.updateMailConfig(body);
      setMsg(t("settings.mail.saved"));
      await load();
    } catch (e: any) {
      setMsg(e?.message || t("settings.mail.save_failed"));
    } finally { setSaving(false); }
  };

  const sendTest = async () => {
    if (!testTo.trim()) return;
    setTesting(true); setTestResult(null);
    try { setTestResult(await api.sendMailTest(testTo.trim())); }
    catch (e: any) { setTestResult({ ok: false, message: e?.message || "error", elapsed_ms: 0 }); }
    finally { setTesting(false); }
  };

  const confirmRopa = async () => {
    setConfirming(true);
    try {
      const r = await api.confirmMailRopa({ legal_basis: ropaBasis, dpa_url: dpaUrl, dpa_note: dpaNote });
      setRopa(r);
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setConfirming(false); }
  };

  const processNow = async () => {
    setProcessing(true);
    try { await api.processMailNow(); setOutbox(await api.getMailOutbox(30)); }
    catch (e: any) { alert(e?.message || "error"); }
    finally { setProcessing(false); }
  };

  const retry = async (id: number) => {
    try { await api.retryMail(id); setOutbox(await api.getMailOutbox(30)); }
    catch (e: any) { alert(e?.message || "error"); }
  };

  const preset = cfg?.presets?.[form.preset];
  const relayRecipient = ropa?.recipients.find((r) => r.role === "relay");

  return (
    <div className="space-y-4">
      {/* ── ตัวรีเลย์ ─────────────────────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{t("settings.mail.title")}</h3>
            <p className="text-[10px] text-gray-500">{t("settings.mail.desc")}</p>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-700 whitespace-nowrap">
            <input type="checkbox" checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            {t("settings.mail.enabled")}
          </label>
        </div>

        {cfg && !cfg.configured && (
          <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 text-[10px] text-amber-800">
            {t("settings.mail.not_configured")}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className={labelCls}>{t("settings.mail.preset")}</label>
            <select value={form.preset} onChange={(e) => applyPreset(e.target.value)} className={inputCls}>
              {Object.entries(cfg?.presets || {}).map(([k, p]) => (
                <option key={k} value={k}>{k === "custom" ? t("settings.mail.preset_custom") : p.label}</option>
              ))}
            </select>
            {preset && (
              <p className="text-[9px] text-gray-400 mt-1">{th ? preset.hint_th : preset.hint_en}</p>
            )}
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.security")}</label>
            <select value={form.security} onChange={(e) => setForm({ ...form, security: e.target.value })} className={inputCls}>
              <option value="starttls">STARTTLS (587)</option>
              <option value="ssl">SSL/TLS (465)</option>
              <option value="none">{t("settings.mail.security_none")}</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.host")}</label>
            <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })}
              placeholder="smtp.example.com" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.port")}</label>
            <input type="number" min={1} max={65535} value={form.port}
              onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.username")}</label>
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
              autoComplete="off" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>
              {t("settings.mail.password")}
              {cfg?.password_configured && (
                <span className="ml-2 text-[9px] text-green-600">✓ {t("settings.mail.password_set")}</span>
              )}
            </label>
            <input type="password" value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder={cfg?.password_configured ? t("settings.mail.keep_placeholder") : ""}
              autoComplete="new-password" className={inputCls} />
            <p className="text-[9px] text-gray-400 mt-1">{t("settings.mail.password_hint")}</p>
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.from_address")}</label>
            <input value={form.from_address} onChange={(e) => setForm({ ...form, from_address: e.target.value })}
              placeholder="ivs@your-domain.co.th" className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.from_name")}</label>
            <input value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.locale")}</label>
            <select value={form.locale} onChange={(e) => setForm({ ...form, locale: e.target.value })} className={inputCls}>
              <option value="th">ไทย</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>{t("settings.mail.dashboard_url")}</label>
            <input value={form.dashboard_url} onChange={(e) => setForm({ ...form, dashboard_url: e.target.value })}
              placeholder={cfg?.dashboard_url_effective || ""} className={inputCls} />
          </div>
          <div className="md:col-span-2">
            <label className={labelCls}>{t("settings.mail.recipients")}</label>
            <textarea value={form.recipients} rows={2}
              onChange={(e) => setForm({ ...form, recipients: e.target.value })}
              placeholder={t("settings.mail.recipients_placeholder")} className={inputCls} />
            {cfg && (
              <p className="text-[9px] text-gray-400 mt-1">
                {t("settings.mail.recipients_effective")}: {cfg.recipients_effective.length
                  ? cfg.recipients_effective.join(", ")
                  : t("settings.mail.recipients_none")}
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button onClick={save} disabled={saving}
            className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
            {saving ? t("settings.mail.saving") : t("settings.mail.save")}
          </button>
          {msg && <span className="text-[10px] text-gray-600">{msg}</span>}
        </div>

        {/* ส่งทดสอบ */}
        <div className="border-t border-gray-100 pt-3">
          <label className={labelCls}>{t("settings.mail.test_title")}</label>
          <div className="flex flex-wrap gap-2">
            <input value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="you@example.com"
              className={cn(inputCls, "md:max-w-xs")} />
            <button onClick={sendTest} disabled={testing || !testTo.trim() || !cfg?.configured}
              className="px-4 py-1.5 bg-gray-800 text-white text-xs font-medium rounded-md hover:bg-gray-900 disabled:opacity-50 whitespace-nowrap">
              {testing ? t("settings.mail.testing") : t("settings.mail.test_send")}
            </button>
          </div>
          <p className="text-[9px] text-gray-400 mt-1">{t("settings.mail.test_hint")}</p>
          {testResult && (
            <div className={cn("mt-2 rounded-md p-2.5 text-[10px] font-mono break-all border",
              testResult.ok ? "bg-green-50 border-green-200 text-green-800" : "bg-red-50 border-red-200 text-red-800")}>
              {testResult.ok ? "✓ " : "✗ "}{testResult.message}
              {testResult.host && ` · ${testResult.host}:${testResult.port} (${testResult.security})`}
              {` · ${testResult.elapsed_ms} ms`}
            </div>
          )}
        </div>

        <div className="bg-indigo-50 border border-indigo-200 rounded-md p-2.5">
          <p className="text-[10px] text-indigo-800">{t("settings.mail.note")}</p>
        </div>
      </div>

      {/* ── ROPA ของกิจกรรมนี้ ─────────────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{t("settings.mail.ropa_title")}</h3>
            <p className="text-[10px] text-gray-500">{t("settings.mail.ropa_desc")}</p>
          </div>
          {ropa && (
            <span className={cn("text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap",
              ropa.status === "confirmed" && !ropa.needs_review
                ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-800")}>
              {ropa.status === "confirmed" && !ropa.needs_review
                ? t("settings.mail.ropa_confirmed")
                : ropa.status === "confirmed" ? t("settings.mail.ropa_needs_review") : t("settings.mail.ropa_draft")}
            </span>
          )}
        </div>

        {ropa && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="md:col-span-2">
              <span className="text-gray-500">{t("settings.mail.ropa_activity")}:</span>{" "}
              <span className="text-gray-900">{th ? ropa.activity_th : ropa.activity_en}</span>
            </div>
            <div className="md:col-span-2">
              <span className="text-gray-500">{t("settings.mail.ropa_purpose")}:</span>{" "}
              <span className="text-gray-900">{ropa.purpose}</span>
            </div>
            <div>
              <span className="text-gray-500">{t("settings.mail.ropa_categories")}:</span>{" "}
              <span className="text-gray-900">{ropa.data_categories.join(", ")}</span>
            </div>
            <div>
              <span className="text-gray-500">{t("settings.mail.ropa_retention")}:</span>{" "}
              <span className="text-gray-900">{ropa.retention}</span>
            </div>
            <div className="md:col-span-2">
              <span className="text-gray-500">{t("settings.mail.ropa_recipients")}:</span>{" "}
              {relayRecipient ? (
                <span className="text-gray-900">{relayRecipient.name} — {t("settings.mail.ropa_processor")}</span>
              ) : (
                <span className="text-gray-400">{t("settings.mail.ropa_no_relay")}</span>
              )}
            </div>
            <div>
              <label className={labelCls}>{t("settings.mail.ropa_basis")}</label>
              <select value={ropaBasis} onChange={(e) => setRopaBasis(e.target.value)} className={inputCls}>
                {bases.map((b) => (
                  <option key={b.value} value={b.value}>{th ? b.label_th : b.label_en}</option>
                ))}
              </select>
              {bases.find((b) => b.value === ropaBasis) && (
                <p className="text-[9px] text-gray-400 mt-1">{bases.find((b) => b.value === ropaBasis)!.why}</p>
              )}
            </div>
            <div>
              <label className={labelCls}>{t("settings.mail.ropa_dpa")}</label>
              <input value={dpaUrl} onChange={(e) => setDpaUrl(e.target.value)}
                placeholder="https://..." className={inputCls} />
              <p className="text-[9px] text-gray-400 mt-1">{t("settings.mail.ropa_dpa_hint")}</p>
            </div>
            <div className="md:col-span-2">
              <label className={labelCls}>{t("settings.mail.ropa_note")}</label>
              <input value={dpaNote} onChange={(e) => setDpaNote(e.target.value)} className={inputCls} />
            </div>
            <div className="md:col-span-2 flex flex-wrap items-center gap-3">
              <button onClick={confirmRopa} disabled={confirming}
                className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
                {confirming ? t("settings.mail.ropa_confirming") : t("settings.mail.ropa_confirm")}
              </button>
              {ropa.confirmed_at && (
                <span className="text-[10px] text-gray-500">
                  {t("settings.mail.ropa_confirmed_by")} {ropa.confirmed_by} · {formatDateTimeSeconds(ropa.confirmed_at)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── คิวจดหมาย ─────────────────────────────────────────────────── */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{t("settings.mail.outbox_title")}</h3>
            <p className="text-[10px] text-gray-500">{t("settings.mail.outbox_desc")}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => api.getMailOutbox(30).then(setOutbox).catch(() => {})}
              className="px-3 py-1 text-[10px] border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">
              {t("settings.mail.refresh")}
            </button>
            <button onClick={processNow} disabled={processing}
              className="px-3 py-1 text-[10px] bg-gray-800 text-white rounded-md hover:bg-gray-900 disabled:opacity-50">
              {processing ? t("settings.mail.processing") : t("settings.mail.process_now")}
            </button>
          </div>
        </div>
        {outbox.length === 0 ? (
          <p className="text-[10px] text-gray-400 text-center py-2">{t("settings.mail.outbox_empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead className="bg-gray-50 text-gray-500 text-[8px] uppercase">
                <tr>
                  <th className="px-2 py-1.5 text-left">{t("settings.mail.col_time")}</th>
                  <th className="px-2 py-1.5 text-left">{t("settings.mail.col_to")}</th>
                  <th className="px-2 py-1.5 text-left">{t("settings.mail.col_subject")}</th>
                  <th className="px-2 py-1.5 text-left">{t("settings.mail.col_status")}</th>
                  <th className="px-2 py-1.5 text-left">{t("settings.mail.col_error")}</th>
                  <th className="px-2 py-1.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {outbox.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-2 py-1.5 whitespace-nowrap text-gray-500">
                      {r.created_at ? formatDateTimeSeconds(r.created_at) : "-"}
                    </td>
                    <td className="px-2 py-1.5 font-mono">{r.to_email}</td>
                    <td className="px-2 py-1.5 text-gray-900 max-w-[260px] truncate" title={r.subject}>{r.subject}</td>
                    <td className="px-2 py-1.5">
                      <span className={cn("px-1.5 py-0.5 rounded-full", STATUS_STYLE[r.status] || "bg-gray-100")}>
                        {t(`settings.mail.status_${r.status}`)}
                        {r.attempts > 0 && ` (${r.attempts})`}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-red-700 font-mono max-w-[260px] truncate" title={r.last_error}>
                      {r.last_error || ""}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      {(r.status === "failed" || r.status === "dead") && (
                        <button onClick={() => retry(r.id)}
                          className="px-2 py-0.5 border border-gray-300 rounded text-gray-700 hover:bg-gray-50">
                          {t("settings.mail.retry")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
