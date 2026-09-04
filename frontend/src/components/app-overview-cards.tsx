"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api, AppOverview } from "@/lib/api";
import { App } from "@/types";
import { useLang } from "@/components/lang-provider";

/**
 * การ์ดเฉพาะแอป — หกมุมมองเดียวกับหน้าแรก แต่ของแอปตัวเดียว
 *
 * การ์ดรวมตอบว่าทั้งระบบเป็นอย่างไร คำถามถัดไปที่คนถามเสมอคือ "แล้วตัวนี้ล่ะ"
 * ซึ่งเดิมต้องเปิดหกหน้าแล้วประกอบเอง
 *
 * สิ่งที่เลือกไว้เก็บในเบราว์เซอร์ ไม่ใช่ในฐานข้อมูล — เป็นความชอบส่วนตัวของคน
 * ที่นั่งอยู่หน้าจอนั้น ไม่ใช่การตั้งค่าของระบบที่คนอื่นต้องเห็นตาม
 */
// อักษรย่อและสีพื้น ใช้กฎเดียวกับการ์ดในหน้าแอปพลิเคชัน แอปเดียวกันจึงหน้าตา
// เหมือนกันทั้งสองหน้า ถ้าคนละกฎ คนจะนึกว่าเป็นคนละแอป
const AVATAR_COLORS: Record<string, string> = {
  nodejs: "bg-green-500", python: "bg-yellow-500", fullstack: "bg-purple-500",
  static: "bg-blue-500", unknown: "bg-gray-400",
};

function initialsOf(name: string): string {
  const cleaned = (name || "").trim();
  if (!cleaned) return "?";
  const words = cleaned.split(/[\s_-]+/).filter(Boolean);
  if (words.length >= 2) {
    return (Array.from(words[0])[0] || "") + (Array.from(words[1])[0] || "");
  }
  return Array.from(cleaned).slice(0, 2).join("");
}

const STORE_KEY = "ivs.dashboard.appCards";

function readStored(): number[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const v = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v.filter((x) => typeof x === "number") : [];
  } catch {
    return [];
  }
}

export function AppOverviewCards({ canAdd }: { canAdd: boolean }) {
  const { t } = useLang();
  const [ids, setIds] = useState<number[]>([]);
  const [cards, setCards] = useState<Record<number, AppOverview | null>>({});
  const [picking, setPicking] = useState(false);
  const [apps, setApps] = useState<App[]>([]);

  useEffect(() => { setIds(readStored()); }, []);

  const persist = useCallback((next: number[]) => {
    setIds(next);
    try { localStorage.setItem(STORE_KEY, JSON.stringify(next)); } catch { /* โหมดส่วนตัว */ }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (const id of ids) {
        if (cards[id] !== undefined) continue;
        try {
          const d = await api.getAppOverview(id);
          if (!cancelled) setCards((c) => ({ ...c, [id]: d }));
        } catch {
          // แอปถูกลบไปแล้ว หรือหมดสิทธิ์เห็น — เก็บเป็น null แล้วบอกตรง ๆ
          // ดีกว่าเอาการ์ดหายไปเงียบ ๆ ให้คนสงสัยว่าตัวเองกดอะไรผิด
          if (!cancelled) setCards((c) => ({ ...c, [id]: null }));
        }
      }
    })();
    return () => { cancelled = true; };
  }, [ids, cards]);

  async function openPicker() {
    setPicking(true);
    try { setApps(await api.getApps()); } catch { setApps([]); }
  }

  if (!canAdd && ids.length === 0) return null;

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-3">
        {ids.map((id) => (
          <AppCard key={id} id={id} data={cards[id]} t={t}
                   onRemove={() => persist(ids.filter((x) => x !== id))} />
        ))}
        {canAdd && (
          <button onClick={openPicker}
                  className="h-full min-h-[120px] rounded-md border border-dashed border-gray-300
                             bg-white/50 text-gray-400 hover:border-brand-400 hover:text-brand-600
                             transition-colors flex flex-col items-center justify-center gap-1">
            <span className="text-lg leading-none">+</span>
            <span className="text-[10px]">{t("appcard.add")}</span>
          </button>
        )}
      </div>

      {picking && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4"
             onClick={() => setPicking(false)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md max-h-[70vh] overflow-y-auto"
               onClick={(e) => e.stopPropagation()}>
            <div className="px-3 py-2 border-b border-gray-100">
              <h3 className="text-xs font-semibold text-gray-900">{t("appcard.pick_title")}</h3>
              <p className="text-[10px] text-gray-500">{t("appcard.pick_desc")}</p>
            </div>
            <ul className="p-2 space-y-0.5">
              {apps.filter((a) => a.status === "running" && !ids.includes(a.id)).map((a) => (
                <li key={a.id}>
                  <button
                    onClick={() => { persist([...ids, a.id]); setPicking(false); }}
                    className="w-full text-left px-2 py-1.5 rounded-md hover:bg-gray-50 text-[11px]"
                  >
                    <span className="text-gray-900">{a.name}</span>
                    <span className="ml-1.5 font-mono text-[10px] text-gray-500">{a.slug}</span>
                  </button>
                </li>
              ))}
              {apps.filter((a) => a.status === "running" && !ids.includes(a.id)).length === 0 && (
                <li className="px-2 py-3 text-[10px] text-gray-400 text-center">
                  {t("appcard.pick_none")}
                </li>
              )}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

function AppCard({ id, data, t, onRemove }: {
  id: number; data: AppOverview | null | undefined;
  t: (s: string) => string; onRemove: () => void;
}) {
  if (data === undefined) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white px-3 py-2.5">
        <p className="text-[10px] text-gray-400">{t("common.loading")}</p>
      </div>
    );
  }
  if (data === null) {
    // ตอบตรง ๆ ว่าเข้าถึงไม่ได้แล้ว พร้อมทางเอาการ์ดออก
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5">
        <p className="text-[10px] text-amber-800">{t("appcard.gone")}</p>
        <button onClick={onRemove} className="mt-1 text-[10px] text-amber-700 underline">
          {t("appcard.remove")}
        </button>
      </div>
    );
  }

  const P = data.performance, V = data.privacy, R = data.risk, S = data.security;
  const reachOk = P.reach_status === "OK";

  return (
    // พื้นเทาอ่อนกับเส้นซ้าย แยกการ์ดแอปออกจากการ์ดภาพรวมที่เป็นพื้นขาว —
    // สองชุดนี้ตอบคนละคำถาม ("ทั้งระบบ" กับ "ตัวนี้") จึงไม่ควรอ่านเป็นชุดเดียวกัน
    <div className="rounded-lg border border-slate-200 border-l-[3px] border-l-slate-400
                    bg-slate-50 px-3 py-2.5">
      <div className="flex items-start justify-between gap-1 mb-1.5">
        <div className="flex items-start gap-1.5 min-w-0">
          {data.logo_data ? (
            <img src={data.logo_data} alt=""
                 className="w-6 h-6 rounded object-cover shrink-0 bg-white border border-slate-200" />
          ) : (
            <span className={`w-6 h-6 rounded shrink-0 flex items-center justify-center
                              text-[9px] font-semibold text-white
                              ${AVATAR_COLORS[data.app_type] || AVATAR_COLORS.unknown}`}>
              {initialsOf(data.name)}
            </span>
          )}
          <div className="min-w-0">
            <Link href="/dashboard/apps"
                  className="block text-[11px] font-semibold text-gray-900 truncate hover:underline">
              {data.name}
            </Link>
            <p className="font-mono text-[9px] text-gray-500 truncate">
              {data.slug} :{data.port} · v{data.version}
            </p>
          </div>
        </div>
        <button onClick={onRemove} title={t("appcard.remove")}
                className="text-gray-300 hover:text-red-600 text-[11px] leading-none shrink-0">✕</button>
      </div>

      <Line label={t("ov.perf")}
            value={reachOk ? `${P.reach_ms} ms` : (P.reach_status || "—")}
            tone={reachOk ? "plain" : "amber"} />
      {P.memory_mb !== null && (
        <Line label={t("appcard.memory")} value={`${P.memory_mb} MB`} />
      )}
      <Line label={t("appcard.access")}
            value={t(data.access_mode === "protected" ? "appcard.protected" : "appcard.public")}
            tone={data.access_mode === "protected" ? "plain" : "amber"} />

      <Sep />
      <Line label={t("ov.priv_unconfirmed")} value={V.fields_unconfirmed}
            tone={V.fields_unconfirmed ? "amber" : "plain"} items={V.fields} />
      <Line label={t("appcard.purpose")}
            value={t(V.has_purpose ? "appcard.yes" : "appcard.no")}
            tone={V.has_purpose ? "plain" : "amber"} />
      {V.retention && <Line label={t("ov.priv_no_retention_ok")} value={V.retention} />}

      <Sep />
      <Line label={t("appcard.edges")} value={`${R.edges_out} / ${R.edges_in}`} items={R.edges} />
      <Line label={t("ov.risk_unconfirmed")} value={R.edges_unconfirmed}
            tone={R.edges_unconfirmed ? "amber" : "plain"} />
      <Line label={t("appcard.steps")} value={R.flow_steps} items={R.steps} />
      <Line label={t("ov.risk_changes")} value={R.changes_unassessed}
            tone={R.changes_unassessed ? "amber" : "plain"} />

      {S && (
        <>
          <Sep />
          <Line label={t("appcard.keys")} value={S.keys} items={S.key_names} />
          {S.ai_keys > 0 && <Line label={t("ov.ai")} value={S.ai_keys} />}
          <Line label={t("appcard.tokens")} value={S.tokens} items={S.token_names} />
          {S.tunnel_open && (
            <Line label={t("ov.sec_tunnels")} value={t("appcard.yes")} tone="amber" />
          )}
        </>
      )}
    </div>
  );
}

function Sep() {
  return <div className="my-1 border-t border-slate-200" />;
}

function Line({ label, value, tone = "plain", items }: {
  label: string; value: number | string; tone?: "plain" | "amber"; items?: string[];
}) {
  const hasItems = !!items && items.length > 0;
  const row = (
    <div className="group flex items-baseline justify-between gap-2 text-[10.5px]">
      <span className="text-gray-600 truncate">
        {label}{hasItems && <span className="ml-1 text-gray-300">·</span>}
      </span>
      <span className={`font-semibold tabular-nums shrink-0 ${
        tone === "amber" ? "text-amber-700" : "text-gray-900"}`}>{value}</span>
    </div>
  );
  if (!hasItems) return row;
  return (
    <div className="relative group/row">
      {row}
      <div className="invisible group-hover/row:visible absolute z-30 left-0 right-0 top-full mt-0.5
                      opacity-0 group-hover/row:opacity-100 transition-opacity">
        <div className="rounded border border-gray-300 bg-white shadow-lg px-2 py-1.5
                        max-h-56 overflow-y-auto">
          <p className="text-[9px] text-gray-400 mb-0.5">{label} · {items!.length}</p>
          <ul className="space-y-0.5">
            {items!.map((it, i) => (
              <li key={i} className="text-[9.5px] font-mono text-gray-700 truncate">{it}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
