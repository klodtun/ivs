"use client";
import { useState, useEffect, useCallback } from "react";
import { api, VaultScopeOverview, VaultScopeKey, VaultGrantRow } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { SectionHeader } from "@/components/ui";

/**
 * ขอบเขตของคลังกุญแจ — ตัวตน / กลุ่ม / ความสามารถ
 *
 * เดิม iVS ส่งกุญแจทุกใบเข้าทุกคอนเทนเนอร์ หน้านี้คือที่ที่คนตัดสินใจว่าใบไหน
 * ไปที่ไหน สิทธิ์เริ่มต้นคือไม่มี ไม่มีแถวที่ตรง = ไม่ได้กุญแจ
 *
 * ตัวเลขที่ต้องเห็นก่อนอย่างอื่นคือส่วนต่างจากพฤติกรรมเดิม เพราะการเปลี่ยนไป
 * ปฏิเสธไว้ก่อนจะทำให้แอปที่เคยพึ่งกุญแจไม่ได้รับมันอีกเมื่อ deploy ครั้งถัดไป
 * ถ้าไม่บอกตรงนี้ ความเปลี่ยนแปลงนี้จะไปโผล่ตอนแอปพัง
 */
export function VaultScopeView() {
  const { t } = useLang();
  const [data, setData] = useState<VaultScopeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [guide, setGuide] = useState(false);
  const [error, setError] = useState("");
  const [openKey, setOpenKey] = useState<number | null>(null);
  const [grantApp, setGrantApp] = useState<Record<number, string>>({});
  const [nsDraft, setNsDraft] = useState<Record<number, string>>({});
  const [envDraft, setEnvDraft] = useState<Record<number, string>>({});
  // ชื่อตัวแปรที่จะติดไปกับสิทธิ์ใบใหม่ ว่างไว้ = ใช้ชื่อของกุญแจ
  const [grantEnv, setGrantEnv] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    try {
      setData(await api.getVaultScope());
      setError("");
    } catch (e: any) {
      setError(e?.message || t("vscope.load_failed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  async function act(fn: () => Promise<any>) {
    setBusy(true);
    try { await fn(); await load(); }
    catch (e: any) { setError(e?.message || t("vscope.action_failed")); }
    finally { setBusy(false); }
  }

  if (loading) {
    return <div className="p-6 text-center text-[11px] text-gray-400 animate-pulse">{t("vscope.loading")}</div>;
  }
  if (!data) {
    return <div className="p-6 text-center text-[11px] text-red-600">{error || t("vscope.load_failed")}</div>;
  }

  const T = data.totals;
  const losing = data.migration.apps;

  return (
    <div className="space-y-3">
      {/* หัวข้อสั้น คำอธิบายยาวอยู่ในคู่มือ
        *
        * ของเดิมอัดสามแกนของแบบจำลองสิทธิ์ไว้ในบรรทัดเดียวใต้หัวข้อ ยาวเกินกว่า
        * จะอ่านผ่าน ๆ และสั้นเกินกว่าจะเข้าใจถ้าตั้งใจอ่าน — ได้ที่บนหน้าจอไป
        * โดยไม่ช่วยใคร ย้ายมาไว้ในคู่มือที่เขียนได้ยาวพอจะอธิบายจริง
        */}
      <SectionHeader
        title={t("vscope.title")}
        help={t("vscope.subtitle")}
        right={
          <button
            onClick={() => setGuide((v) => !v)}
            className="px-2 py-0.5 text-[10px] rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50"
          >
            {guide ? t("vscope.guide_close") : t("vscope.guide")}
          </button>
        }
      />

      {guide && (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3 space-y-2.5">
          {([1, 2, 3, 4] as const).map((n) => (
            <div key={n}>
              <p className="text-[11px] font-medium text-gray-800">{t(`vscope.g${n}_t`)}</p>
              <p className="text-[10.5px] text-gray-600 mt-0.5 leading-relaxed">
                {t(`vscope.g${n}_b`)}
              </p>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11px] text-red-700">
          {error}
        </div>
      )}

      <div className="flex gap-1.5 flex-wrap text-[10px]">
        <Stat n={T.keys} label={t("vscope.stat_keys")} />
        <Stat n={T.keys_ungranted} label={t("vscope.stat_ungranted")} tone={T.keys_ungranted ? "amber" : "plain"} />
        <Stat n={T.keys_no_reveal} label={t("vscope.stat_no_reveal")} />
        <Stat n={T.keys_bad_env} label={t("vscope.stat_bad_env")} tone={T.keys_bad_env ? "amber" : "plain"} />
        <Stat n={T.grants_bad_env ?? 0} label={t("vscope.stat_bad_grant_env")}
              tone={T.grants_bad_env ? "amber" : "plain"} />
        <Stat n={T.apps_without_keys} label={t("vscope.stat_apps_empty")} />
      </div>

      {/* ชื่อที่โปรแกรมอ่านไม่ได้ ทำให้กุญแจถูกส่งไปโดยไม่มีใครใช้ — ได้ความเสี่ยง
          โดยไม่ได้ประโยชน์ ต้องรู้ก่อนจะไปให้สิทธิ์อะไร */}
      {T.keys_bad_env > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 px-2.5 py-2">
          <p className="text-[11px] font-medium text-amber-900">{t("vscope.bad_env_title")}</p>
          <p className="text-[10px] text-amber-800 mt-0.5 leading-relaxed">{t("vscope.bad_env_desc")}</p>
        </div>
      )}

      {/* ความเปลี่ยนแปลงที่จะเกิดตอน deploy ครั้งถัดไป ต้องอยู่บนสุด ไม่ใช่ท้ายหน้า */}
      {losing.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 px-2.5 py-2">
          <p className="text-[11px] font-medium text-amber-900">{t("vscope.migration_title")}</p>
          <p className="text-[10px] text-amber-800 mt-0.5 leading-relaxed">
            {t("vscope.migration_desc")}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {losing.slice(0, 20).map((a) => (
              <span key={a.slug} className="text-[9.5px] px-1.5 py-px rounded bg-white border border-amber-200 text-amber-900">
                {a.slug} <span className="text-amber-700">{a.has_now}/{a.had_before}</span>
              </span>
            ))}
            {losing.length > 20 && (
              <span className="text-[9.5px] text-amber-700">+{losing.length - 20}</span>
            )}
          </div>
        </div>
      )}

      {/* แกนที่ 2 — กลุ่ม */}
      <div className="rounded border border-gray-200 bg-white p-2.5">
        <h3 className="text-[11px] font-medium text-gray-800">{t("vscope.ns_title")}</h3>
        <p className="text-[10px] text-gray-500">{t("vscope.ns_desc")}</p>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {data.namespaces.map((n) => (
            <span key={n.namespace} className="text-[9.5px] px-1.5 py-px rounded bg-gray-100 text-gray-700 font-mono">
              {n.namespace} · {n.keys}
            </span>
          ))}
        </div>
      </div>

      {/* แกนที่ 1 และ 3 — ตัวตนและความสามารถ รายกุญแจ */}
      <div className="space-y-1.5">
        {data.keys.map((k) => (
          <KeyRow
            key={k.id} k={k} apps={data.apps} t={t} busy={busy}
            open={openKey === k.id}
            onToggle={() => setOpenKey(openKey === k.id ? null : k.id)}
            grantAppId={grantApp[k.id] || ""}
            setGrantAppId={(v) => setGrantApp({ ...grantApp, [k.id]: v })}
            nsValue={nsDraft[k.id] ?? k.namespace}
            setNsValue={(v) => setNsDraft({ ...nsDraft, [k.id]: v })}
            envValue={envDraft[k.id] ?? (k.env_overridden ? k.env_name : "")}
            setEnvValue={(v) => setEnvDraft({ ...envDraft, [k.id]: v })}
            grantEnvValue={grantEnv[k.id] || ""}
            setGrantEnvValue={(v) => setGrantEnv({ ...grantEnv, [k.id]: v })}
            onGrant={() => act(async () => {
              const r = await api.grantVaultKey(
                k.id, Number(grantApp[k.id]), "", grantEnv[k.id] || "");
              setGrantEnv({ ...grantEnv, [k.id]: "" });
              return r;
            })}
            onSetGrantEnv={(gid, name) => act(() => api.updateGrantEnvName(gid, name))}
            onRevoke={(gid) => act(() => api.revokeVaultGrant(gid))}
            onSaveScope={(patch) => act(() => api.updateVaultKeyScope(k.id, patch))}
            onGrantNs={(appId) => act(() => api.grantVaultNamespace(k.id, k.namespace, appId))}
          />
        ))}
      </div>
    </div>
  );
}

/** สิทธิ์หนึ่งบรรทัด พร้อมชื่อตัวแปรที่แอปตัวนั้นจะได้รับจริง
 *
 * ชื่ออยู่ตรงนี้ ไม่ใช่ที่กุญแจ เพราะความลับใบเดียวอาจถูกอ่านคนละชื่อสองฝั่ง
 * แสดงคู่กับชื่อแอปเสมอ เพื่อให้ตอบได้ทันทีว่า "แอปนี้จะเห็นตัวแปรชื่ออะไร"
 * โดยไม่ต้องเดาจากชื่อกุญแจ
 */
function GrantRow({ g, t, busy, onSetEnv, onRevoke }: {
  g: VaultGrantRow; t: (s: string) => string; busy: boolean;
  onSetEnv: (name: string) => void; onRevoke: () => void;
}) {
  const [draft, setDraft] = useState(g.env_overridden ? g.env_name : "");
  const dirty = draft.trim() !== (g.env_overridden ? g.env_name : "");
  return (
    <div className="flex items-center gap-1 flex-wrap text-[9.5px]
                    px-1.5 py-1 rounded border border-gray-200 bg-gray-50">
      <span className="font-medium text-gray-800">{g.slug}</span>
      <span className="text-gray-400">→</span>
      <input value={draft} onChange={(e) => setDraft(e.target.value)}
             placeholder={g.env_name}
             className={`font-mono border rounded px-1 py-px w-40 ${
               g.env_valid ? "border-gray-300" : "border-amber-400 bg-amber-50"
             }`} />
      {g.env_overridden && (
        <span className="px-1 py-px rounded bg-slate-100 text-slate-700">
          {t("vscope.per_app_name")}
        </span>
      )}
      {!g.env_valid && (
        <span className="px-1 py-px rounded bg-amber-100 text-amber-800">
          {t("vscope.bad_env_tag")}
        </span>
      )}
      {dirty && (
        <button onClick={() => onSetEnv(draft.trim())} disabled={busy}
                className="px-1.5 py-px rounded-md bg-brand-600 text-white
                           hover:bg-brand-700 disabled:opacity-40">
          {t("vscope.save_env")}
        </button>
      )}
      <button onClick={onRevoke} disabled={busy}
              className="ml-auto text-red-600 hover:underline disabled:opacity-40">
        {t("vscope.revoke")}
      </button>
    </div>
  );
}

function Stat({ n, label, tone = "plain" }: { n: number; label: string; tone?: "plain" | "amber" }) {
  return (
    <span className={`px-2 py-1 rounded border ${
      tone === "amber" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-gray-200 bg-white text-gray-600"
    }`}>
      {label}: <span className="font-semibold">{n}</span>
    </span>
  );
}

function KeyRow({
  k, apps, t, busy, open, onToggle, grantAppId, setGrantAppId,
  nsValue, setNsValue, envValue, setEnvValue,
  grantEnvValue, setGrantEnvValue, onGrant, onSetGrantEnv,
  onRevoke, onSaveScope, onGrantNs,
}: {
  k: VaultScopeKey;
  apps: VaultScopeOverview["apps"];
  t: (s: string) => string;
  busy: boolean; open: boolean; onToggle: () => void;
  grantAppId: string; setGrantAppId: (v: string) => void;
  nsValue: string; setNsValue: (v: string) => void;
  envValue: string; setEnvValue: (v: string) => void;
  grantEnvValue: string; setGrantEnvValue: (v: string) => void;
  onGrant: () => void; onSetGrantEnv: (grantId: number, name: string) => void;
  onRevoke: (grantId: number) => void;
  onSaveScope: (patch: Record<string, any>) => void;
  onGrantNs: (appId: number) => void;
}) {
  const held = new Set(k.granted_to.map((g) => g.app_id));
  return (
    <div className="rounded border border-gray-200 bg-white">
      <button onClick={onToggle} className="w-full text-left px-2.5 py-2 hover:bg-gray-50">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="min-w-0">
            <span className="text-xs text-gray-900">{k.name}</span>
            <span className={`ml-1.5 font-mono text-[10px] ${
              k.env_valid ? "text-gray-500" : "text-amber-700 line-through decoration-amber-400"
            }`}>{k.env_name}</span>
            {!k.env_valid && (
              <span className="ml-1 text-[9px] px-1 py-px rounded bg-amber-100 text-amber-800">
                {t("vscope.bad_env_tag")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-[9px] px-1.5 py-px rounded bg-gray-100 text-gray-600 font-mono">
              {k.namespace}
            </span>
            {!k.allow_reveal && (
              <span className="text-[9px] px-1.5 py-px rounded bg-slate-100 text-slate-700">
                {t("vscope.inject_only")}
              </span>
            )}
            <span className={`text-[9px] px-1.5 py-px rounded ${
              k.grant_count ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-800"
            }`}>
              {k.grant_count ? `${t("vscope.held_by")}: ${k.grant_count}` : t("vscope.no_grant")}
            </span>
          </div>
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-2.5 py-2 space-y-2">
          {/* ตัวตน */}
          <div>
            <h4 className="text-[10.5px] font-medium text-gray-700">{t("vscope.identity")}</h4>
            {k.granted_to.length === 0 ? (
              <p className="text-[10px] text-gray-400 mt-0.5">{t("vscope.identity_none")}</p>
            ) : (
              <div className="mt-1 space-y-1">
                {k.granted_to.map((g) => (
                  <GrantRow key={g.grant_id} g={g} t={t} busy={busy}
                            onSetEnv={(name) => onSetGrantEnv(g.grant_id, name)}
                            onRevoke={() => onRevoke(g.grant_id)} />
                ))}
              </div>
            )}
            <div className="mt-1.5 flex gap-1 flex-wrap items-center">
              <select value={grantAppId} onChange={(e) => setGrantAppId(e.target.value)}
                      className="text-[10.5px] border border-gray-300 rounded px-1.5 py-1">
                <option value="">{t("vscope.pick_app")}</option>
                {apps.filter((a) => !held.has(a.app_id)).map((a) => (
                  <option key={a.app_id} value={a.app_id}>{a.slug}</option>
                ))}
              </select>
              {/* ชื่อเฉพาะแอปตัวนี้ — ว่างไว้ก็ได้ชื่อของกุญแจตามเดิม */}
              <input value={grantEnvValue} onChange={(e) => setGrantEnvValue(e.target.value)}
                     placeholder={k.env_name}
                     className="text-[10.5px] font-mono border border-gray-300 rounded px-1.5 py-1 w-44" />
              <button onClick={onGrant} disabled={busy || !grantAppId}
                      className="text-[10px] px-2 py-1 rounded-md bg-brand-600 text-white
                                 hover:bg-brand-700 disabled:opacity-40">
                {t("vscope.grant")}
              </button>
              <button onClick={() => grantAppId && onGrantNs(Number(grantAppId))}
                      disabled={busy || !grantAppId}
                      className="text-[10px] px-2 py-1 rounded-md border border-gray-300
                                 text-gray-700 hover:bg-gray-50 disabled:opacity-40">
                {t("vscope.grant_ns")} {k.namespace}
              </button>
            </div>
          </div>

          {/* กลุ่ม + ความสามารถ */}
          <div className="border-t border-gray-100 pt-2">
            <label className="block text-[10px] text-gray-600">{t("vscope.env_name")}</label>
            <div className="flex gap-1.5 items-center flex-wrap mt-0.5">
              <input
                value={envValue}
                onChange={(e) => setEnvValue(e.target.value)}
                placeholder={k.env_derived}
                className="text-[10.5px] font-mono border border-gray-300 rounded px-1.5 py-1 w-64"
              />
              <button onClick={() => onSaveScope({ env_override: envValue })}
                      disabled={busy}
                      className="text-[10px] px-2 py-1 rounded-md border border-gray-300
                                 text-gray-700 hover:bg-gray-50 disabled:opacity-40">
                {t("vscope.save_env")}
              </button>
            </div>
            <p className="text-[9.5px] text-gray-500 mt-0.5">
              {t("vscope.env_note")} <span className="font-mono">{k.env_derived}</span>
            </p>
          </div>

          <div className="flex gap-2 flex-wrap items-end border-t border-gray-100 pt-2">
            <div>
              <label className="block text-[10px] text-gray-600">{t("vscope.namespace")}</label>
              <input value={nsValue} onChange={(e) => setNsValue(e.target.value)}
                     placeholder={k.namespace}
                     className="text-[10.5px] font-mono border border-gray-300 rounded px-1.5 py-1 w-40" />
            </div>
            <button onClick={() => onSaveScope({ namespace: nsValue })} disabled={busy}
                    className="text-[10px] px-2 py-1 rounded-md border border-gray-300
                               text-gray-700 hover:bg-gray-50 disabled:opacity-40">
              {t("vscope.save_ns")}
            </button>
            {/* หมวดเคยตั้งได้ตอนสร้างเท่านั้น กุญแจที่จัดผิดจึงแก้ไม่ได้เลยนอกจาก
                ลบแล้วสร้างใหม่ ซึ่งต้องรู้ค่าความลับเดิม — เป็นเหตุผลที่ผิดในการ
                บังคับให้คนเปิดดูค่ากุญแจ */}
            <div>
              <label className="block text-[10px] text-gray-600">{t("vscope.category")}</label>
              <select value={k.category || "general"} disabled={busy}
                      onChange={(e) => onSaveScope({ category: e.target.value })}
                      className="text-[10.5px] border border-gray-300 rounded px-1.5 py-1">
                {["general", "ai", "maps", "weather", "finance", "other"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-1 text-[10.5px] text-gray-700 ml-2">
              <input type="checkbox" checked={k.allow_reveal} disabled={busy}
                     onChange={(e) => onSaveScope({ allow_reveal: e.target.checked })} />
              {t("vscope.allow_reveal")}
            </label>
          </div>
          <p className="text-[9.5px] text-gray-500 leading-relaxed">{t("vscope.reveal_note")}</p>
        </div>
      )}
    </div>
  );
}
