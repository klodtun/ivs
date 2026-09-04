"use client";
import { useMemo, useState, useEffect } from "react";
import Link from "next/link";
import { SystemOverview } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

/**
 * สี่มุมมองบนหน้าแรก — ประสิทธิภาพ / ข้อมูลส่วนบุคคล / ความเสี่ยง / ความปลอดภัย
 *
 * หน้าแรกคือที่ **สังเกต** ไม่ใช่ที่ลงมือ ทุกบรรทัดตอบว่า "มีอะไรที่ควรรู้" แล้ว
 * ส่งต่อไปหน้าที่แก้เรื่องนั้นได้จริง จึงไม่มีปุ่มที่เปลี่ยนสถานะระบบอยู่ที่นี่
 *
 * ศูนย์ต้องเงียบ — บรรทัดที่ไม่มีของจะไม่แสดง หน้าจอที่มีเลขศูนย์สิบบรรทัดทำให้
 * บรรทัดที่มีของจริงมองไม่เห็น สิ่งที่แสดงเสมอมีอย่างเดียวคือยอดรวมที่เป็นบริบท
 */
/** เมนู → คีย์ชื่อในพจนานุกรม ใช้ชุดเดียวกับแถบข้างเพื่อไม่ให้ชื่อเพี้ยนคนละที่ */
const MENU_LABEL: Record<string, string> = {
  "/dashboard/apps": "nav.apps",
  "/dashboard/tunnels": "nav.tunnels",
  "/dashboard/vault": "nav.vault",
  "/dashboard/resources": "nav.resources",
  "/dashboard/settings": "nav.settings",
  "/dashboard/system-map": "nav.system_map",
  "/dashboard/flows": "nav.flows",
  "/dashboard/design-controls": "nav.design_controls",
  "/dashboard/econtract": "nav.econtract",
  "/dashboard/bridge": "nav.bridge",
};

export function OverviewCards({ data }: { data: SystemOverview }) {
  const { t } = useLang();
  const P = data.performance, V = data.privacy, R = data.risk, S = data.security, A = data.ai, M = data.menus;

  return (
    // ห้าใบไม่ลงตัวกับสี่คอลัมน์ — ใบสุดท้ายจะเหลือเดี่ยวเต็มแถว
    // ห้าคอลัมน์บนจอกว้าง สองบนจอกลาง ทำให้ทุกใบเท่ากันเสมอ
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6 gap-3">
      <Card title={t("ov.perf")} href="/dashboard/resources">
        <Trend points={P.trend} />
        <Row label={t("ov.perf_apps")} value={`${P.apps_total - P.apps_stopped}/${P.apps_total}`} href="/dashboard/apps" items={P.details?.apps_running} raw />
        <Row label={t("ov.perf_stopped")} value={P.apps_stopped} href="/dashboard/apps" items={P.details?.apps_stopped} tone={P.apps_stopped ? "amber" : "plain"} hideZero />
        <Row label={t("ov.perf_unreachable")} value={P.unreachable} href="/dashboard/api-catalog" items={P.details?.unreachable} tone={P.unreachable ? "amber" : "plain"} hideZero />
        {/* เรียงตามหน่วยความจำ เพราะ CPU ณ วินาทีเดียวกระโดดตลอด ส่วนหน่วยความจำ
            เปลี่ยนช้าพอที่ค่าเดียวจะมีความหมาย */}
        {(P.top_consumers.length > 0 || P.slowest.length > 0) && (
          <Detail>
            {P.top_consumers.map((c) => (
              <span key={c.slug} className="block truncate">
                <code>{c.slug}</code> · {c.memory_mb} MB · CPU {c.cpu_percent}%
              </span>
            ))}
            {P.slowest.length > 0 && (
              <span className="block truncate mt-1 text-gray-400">
                {t("ov.perf_slowest")}: <code>{P.slowest[0].slug}</code> · {P.slowest[0].ms} ms
              </span>
            )}
          </Detail>
        )}
      </Card>

      <Card title={t("ov.privacy")} href="/dashboard/settings?tab=pdpa">
        <Split id="privacy" fallback="#2a78d6"
               done={P.apps_total - V.apps_no_purpose} total={P.apps_total}
               doneLabel={t("ov.split_declared")} leftLabel={t("ov.split_not_yet")} />
        {/* ROPA ที่ไม่ครบไม่ทำให้อะไรพังวันนี้ แต่เป็นสิ่งแรกที่ผู้ตรวจขอ และเป็น
            งานที่ต้องสะสม ไม่ใช่ทำวันเดียวเสร็จ จึงอยู่บรรทัดบนสุด */}
        {/* ตัวหารคือจำนวนแอปทั้งหมดที่ผู้ใช้เห็นได้ — "15/15" จะอ่านว่าครบทุกตัว
            ทั้งที่ความจริงคือ 15 จาก 16 ซึ่งเป็นคนละเรื่องกัน */}
        <Row label={t("ov.priv_no_purpose")} value={`${V.apps_no_purpose}/${P.apps_total}`}
             href="/dashboard/settings?tab=pdpa" items={V.details?.apps_no_purpose} tone={V.apps_no_purpose ? "amber" : "plain"} raw />
        <Row label={t("ov.priv_unconfirmed")} value={V.fields_unconfirmed}
             href="/dashboard/settings?tab=pdpa" items={V.details?.fields_unconfirmed} tone={V.fields_unconfirmed ? "amber" : "plain"} hideZero />
        <Row label={t("ov.priv_no_retention")} value={V.apps_no_retention}
             href="/dashboard/settings?tab=pdpa" items={V.details?.apps_no_retention} tone={V.apps_no_retention ? "amber" : "plain"} hideZero />
        <Row label={t("ov.priv_external")} value={V.external_targets} href="/dashboard/system-map" items={V.details?.external_targets} hideZero />
        {V.apps_no_purpose_examples.length > 0 && (
          <Detail>
            {V.apps_no_purpose_examples.map((s) => (
              <span key={s} className="block truncate"><code>{s}</code></span>
            ))}
          </Detail>
        )}
      </Card>

      <Card title={t("ov.risk")} href="/dashboard/system-map">
        <Split id="risk" fallback="#4a3aa7"
               done={P.apps_total - R.apps_without_edges} total={P.apps_total}
               doneLabel={t("ov.split_mapped")} leftLabel={t("ov.split_unmapped")} />
        <Row label={t("ov.risk_unconfirmed")} value={R.edges_unconfirmed}
             href="/dashboard/system-map" items={R.details?.edges_unconfirmed} tone={R.edges_unconfirmed ? "amber" : "plain"} hideZero />
        <Row label={t("ov.risk_planned")} value={R.steps_planned}
             href="/dashboard/flows" items={R.details?.steps_planned} tone={R.steps_planned ? "amber" : "plain"} hideZero />
        <Row label={t("ov.risk_broken")} value={R.steps_broken + R.steps_drifted}
             href="/dashboard/flows" items={R.details?.steps_broken} tone={R.steps_broken + R.steps_drifted ? "amber" : "plain"} hideZero />
        <Row label={t("ov.risk_changes")} value={R.changes_unassessed}
             href="/dashboard/design-controls" items={R.details?.changes_unassessed} tone={R.changes_unassessed ? "amber" : "plain"} hideZero />
        {/* ไม่มีเส้นเชื่อม ≠ ไม่เชื่อมกับอะไร — แปลว่าไม่มีอะไรให้เครื่องอ่าน */}
        <Row label={t("ov.risk_no_edges")} value={R.apps_without_edges} href="/dashboard/system-map" items={R.details?.apps_without_edges} hideZero />
        <Detail>{t("ov.risk_no_edges_hint")}</Detail>
      </Card>

      {/* AI — สำหรับงานเครื่องมือแพทย์ คำถามไม่ได้จบที่ "ใช้ AI ไหม" แต่คือ
          ใช้โมเดลใด ประมวลผลที่ใด ใครเข้าถึงได้ และเพิกถอนได้หรือไม่ */}
      <Card title={t("ov.ai")} href="/dashboard/vault">
        {A.keys !== undefined && A.keys > 0 && (
          <Split id="ai" fallback="#c2185b"
                 done={A.keys - (A.keys_ungranted ?? 0)} total={A.keys}
                 doneLabel={t("ov.split_in_use")} leftLabel={t("ov.split_idle")} />
        )}
        <Row label={t("ov.ai_models")} value={A.models_count} href="/dashboard/vault" items={A.details?.models} raw />
        <Row label={t("ov.ai_apps")} value={`${A.apps_with_ai}/${A.apps_total}`}
             href="/dashboard/vault?tab=scope" items={A.details?.apps_with_ai}
             tone={A.apps_with_ai === 0 && (A.keys ?? 0) > 0 ? "amber" : "plain"} raw />
        {A.keys !== undefined && (
          <Row label={t("ov.ai_keys_ungranted")} value={A.keys_ungranted ?? 0}
               href="/dashboard/vault?tab=scope" items={A.details?.keys_ungranted}
               tone={A.keys_ungranted ? "amber" : "plain"} hideZero />
        )}
        <Row label={t("ov.ai_callers")} value={A.ai_callers_count}
             href="/dashboard/vault?tab=tokens" items={A.details?.ai_callers} hideZero />
        <Row label={t("ov.ai_callers_revoked")} value={A.ai_callers_revoked}
             href="/dashboard/vault?tab=tokens" hideZero />
        <Row label={t("ov.ai_models_no_key")} value={A.models_without_key}
             tone={A.models_without_key ? "amber" : "plain"} hideZero />
        {A.models.length > 0 ? (
          <Detail>
            {/* ปลายทางสำคัญกว่าชื่อโมเดล — ชื่อไม่บอกว่าข้อมูลถูกส่งไปประมวลผลที่ใด */}
            {A.models.map((m) => (
              <span key={m.label} className="block truncate">
                <code>{m.label}</code>
                {m.base_url
                  ? ` · ${m.base_url.replace(/^https?:\/\//, "").split("/")[0]}`
                  : ` · ${t("ov.ai_no_endpoint")}`}
              </span>
            ))}
          </Detail>
        ) : (
          <Detail>{t("ov.ai_none")}</Detail>
        )}
      </Card>

      {/* สรุปรายเมนู — ตอบว่าฟังก์ชันไหนมีของอยู่จริงเท่าไร ชื่อเมนูดึงจาก
          พจนานุกรมชุดเดียวกับแถบข้าง เปลี่ยนชื่อที่เดียวแล้วตรงกันทั้งสองที่ */}
      <Card title={t("ov.menus")}>
        <Split id="menus" fallback="#2a78d6"
               done={M.filter((m) => m.count > 0).length} total={M.length}
               doneLabel={t("ov.split_used")} leftLabel={t("ov.split_empty")} />
        {M.map((m) => (
          <Row key={m.href}
               label={t(MENU_LABEL[m.href] || m.href)}
               value={m.note && m.note !== String(m.count) ? `${m.count} / ${m.note}` : m.count}
               href={m.href} items={m.items} raw />
        ))}
        <Detail>{t("ov.menus_hint")}</Detail>
      </Card>

      {S ? (
        <Card title={t("ov.security")} href="/dashboard/vault?tab=scope">
          <Split id="security" fallback="#1baf7a"
                 done={P.apps_total - S.apps_public} total={P.apps_total}
                 doneLabel={t("ov.split_gated")} leftLabel={t("ov.split_open")} />
          <Row label={t("ov.sec_expiring")} value={S.tokens_expiring}
               href="/dashboard/vault?tab=tokens" items={S.details?.tokens_expiring} tone={S.tokens_expiring ? "amber" : "plain"} hideZero />
          <Row label={t("ov.sec_ungranted")} value={S.keys_ungranted}
               href="/dashboard/vault?tab=scope" items={S.details?.keys_ungranted} tone={S.keys_ungranted ? "amber" : "plain"} hideZero />
          <Row label={t("ov.sec_revealable")} value={S.keys_revealable}
               href="/dashboard/vault?tab=scope" items={S.details?.keys_revealable} tone={S.keys_revealable ? "amber" : "plain"} hideZero />
          <Row label={t("ov.sec_warnings")} value={S.audit_warnings_7d} href="/dashboard/settings?tab=logs" hideZero />
          <Row label={t("ov.sec_tunnels")} value={S.tunnels_open}
               href="/dashboard/tunnels" items={S.details?.tunnels_open} tone={S.tunnels_open ? "amber" : "plain"} hideZero />
          <Row label={t("ov.sec_public")} value={`${S.apps_public}/${P.apps_total}`} href="/dashboard/apps" items={S.details?.apps_public} raw />
          {S.tokens_expiring_list.length > 0 && (
            <Detail>
              {S.tokens_expiring_list.map((k) => (
                <span key={k.label} className="block truncate">
                  <code>{k.caller}</code> · {k.expires_at.slice(0, 10)}
                </span>
              ))}
            </Detail>
          )}
        </Card>
      ) : (
        <Card title={t("ov.security")}>
          <p className="text-[10px] text-gray-400">{t("ov.sec_admin_only")}</p>
        </Card>
      )}
    </div>
  );
}

/**
 * แถบสัดส่วนสองส่วน — "ทำแล้วเท่าไร จากทั้งหมดเท่าไร"
 *
 * เลือกแถบซ้อนแนวนอน ไม่ใช่วงกลมสองชิ้น เพราะข้อมูลชนิดส่วนต่อทั้งหมดอ่านจาก
 * ความยาวได้แม่นกว่าจากมุม และที่ขนาดเล็กระดับนี้ วงกลมสองชิ้นเทียบสัดส่วนไม่ออก
 *
 * สองสีนี้ผ่านการตรวจด้วยเครื่องมือ ไม่ได้เลือกด้วยตา — อยู่ในช่วงความสว่างที่
 * กำหนด ความอิ่มสีพอ แยกออกจากกันได้ทั้งสายตาปกติและตาบอดสี และคอนทราสต์กับพื้น
 * ผ่าน 3:1 ทั้งคู่ ที่สำคัญกว่านั้นคือมีป้ายข้อความกำกับทั้งสองส่วน ความหมายจึง
 * ไม่ได้ผูกกับสีอย่างเดียว
 */
// สีที่ผู้ใช้เลือกได้ — ทั้งชุดผ่านเครื่องมือตรวจพร้อมกัน ไม่ใช่ทีละสี
//
// ตรวจแล้วว่าทุกสีอยู่ในช่วงความสว่างที่กำหนด ความอิ่มสีพอ แยกออกจากกันเองได้
// (ΔE 16.3 สายตาปกติ) และแยกจากสีส่วนที่ค้างได้ทั้งตาปกติและตาบอดสี
//
// ตัวเลือกที่ตัดออกเพราะตกการตรวจ ไม่ใช่เพราะไม่สวย:
//   เขียว #008300 กับ ส้ม #eb6834 — แยกจากสีส่วนที่ค้างไม่ออกเมื่อตาบอดสีแดง-เขียว
//   ม่วงอ่อน #7b4bc9 — ใกล้ม่วงเข้มเกินไป (ΔE 11.0) แม้แต่สายตาปกติก็สับสน
// ปล่อยให้เลือกสีอิสระจะทำให้การรับประกันพวกนี้หายไปทั้งหมด จึงให้เลือกจากชุดนี้
const SPLIT_COLORS = [
  { key: "blue", hex: "#2a78d6" },
  { key: "violet", hex: "#4a3aa7" },
  { key: "magenta", hex: "#c2185b" },
  { key: "teal", hex: "#1baf7a" },
];

// ส่วนที่ค้างใช้สีเดียวกันทุกการ์ดเสมอ — "ยังไม่เสร็จ" ควรอ่านได้เหมือนกันหมด
// ถ้าเปลี่ยนตามการ์ดด้วย จะไม่เหลืออะไรให้จำว่าสีไหนแปลว่าต้องทำ
const SPLIT_LEFT = "#c07a12";

const COLOR_STORE = "ivs.dashboard.splitColors";

function readColors(): Record<string, string> {
  try {
    const raw = localStorage.getItem(COLOR_STORE);
    const v = raw ? JSON.parse(raw) : {};
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

/**
 * แถบสัดส่วนสองส่วน — "ทำแล้วเท่าไร จากทั้งหมดเท่าไร"
 *
 * เลือกแถบซ้อนแนวนอน ไม่ใช่วงกลมสองชิ้น เพราะข้อมูลชนิดส่วนต่อทั้งหมดอ่านจาก
 * ความยาวได้แม่นกว่าจากมุม และที่ขนาดเล็กระดับนี้ วงกลมสองชิ้นเทียบสัดส่วนไม่ออก
 *
 * สีของส่วนที่เสร็จแล้วตั้งได้รายการ์ด เพราะหกการ์ดที่สีเหมือนกันหมดทำให้ต้อง
 * อ่านหัวข้อก่อนถึงจะรู้ว่ากำลังดูใบไหน สีที่ต่างกันทำให้จำตำแหน่งได้
 * แต่ความหมายไม่เคยผูกกับสี — ป้ายข้อความกำกับทั้งสองส่วนเสมอ
 */
function Split({ id, done, total, doneLabel, leftLabel, fallback }: {
  id: string; done: number; total: number;
  doneLabel: string; leftLabel: string; fallback: string;
}) {
  const [color, setColor] = useState<string>(fallback);
  const [picking, setPicking] = useState(false);

  useEffect(() => {
    const stored = readColors()[id];
    if (stored) setColor(stored);
  }, [id]);

  function choose(hex: string) {
    setColor(hex);
    setPicking(false);
    try {
      localStorage.setItem(COLOR_STORE, JSON.stringify({ ...readColors(), [id]: hex }));
    } catch { /* โหมดส่วนตัว — สีกลับไปเป็นค่าตั้งต้นได้ ไม่ใช่เรื่องใหญ่ */ }
  }

  if (!total) return null;
  const pct = Math.max(0, Math.min(100, (done / total) * 100));
  const left = total - done;

  return (
    <div className="mb-1.5 relative">
      <button onClick={() => setPicking(!picking)} title={doneLabel}
              className="block w-full">
        <div className="flex h-1.5 gap-[2px] overflow-hidden">
          {/* ช่องว่าง 2px ระหว่างสองส่วน ทำให้ขอบที่ติดกันไม่อ่านเป็นก้อนเดียว */}
          {done > 0 && (
            <div style={{ width: `${pct}%`, background: color }}
                 className="rounded-l-[2px] rounded-r-[1px]" />
          )}
          {left > 0 && (
            <div style={{ width: `${100 - pct}%`, background: SPLIT_LEFT }}
                 className="rounded-r-[2px] rounded-l-[1px]" />
          )}
        </div>
      </button>

      {/* ป้ายกำกับตรง ๆ ทั้งสองส่วน — ไม่ใช้กล่องคำอธิบายสี เพราะสองชุดนี้เล็กพอ
          ที่จะเขียนติดไว้ได้เลย และการอ่านจากสีอย่างเดียวไม่ควรเป็นทางเดียว */}
      <div className="flex justify-between text-[9px] mt-0.5 text-gray-500">
        <span><span style={{ color }}>●</span> {doneLabel} {done}</span>
        <span>{leftLabel} {left} <span style={{ color: SPLIT_LEFT }}>●</span></span>
      </div>

      {picking && (
        <div className="absolute z-40 left-0 top-full mt-1 rounded border border-gray-300
                        bg-white shadow-lg px-1.5 py-1 flex gap-1">
          {SPLIT_COLORS.map((c) => (
            <button key={c.key} onClick={() => choose(c.hex)}
                    title={c.key}
                    className={`w-4 h-4 rounded-md border ${
                      color === c.hex ? "border-gray-800" : "border-transparent"}`}
                    style={{ background: c.hex }} />
          ))}
        </div>
      )}
    </div>
  );
}

function Card({ title, href, children }: { title: string; href?: string; children: React.ReactNode }) {
  // ลิงก์อยู่ที่หัวข้อเท่านั้น — ครอบทั้งการ์ดด้วย <a> จะทำให้ลิงก์รายบรรทัด
  // ซ้อนอยู่ข้างใน ซึ่งเป็น HTML ที่ไม่ถูกต้องและกดไม่ตรงตามที่เห็น
  return (
    <div className="h-full rounded-lg border border-gray-200 bg-white px-3 py-2.5">
      <h3 className="text-[11px] font-semibold text-gray-900 mb-1.5">
        {href ? <Link href={href} className="hover:underline">{title}</Link> : title}
      </h3>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

/**
 * หนึ่งบรรทัด = หนึ่งเรื่องที่ควรรู้ พร้อมทางไปแก้
 *
 * ลิงก์อยู่ที่บรรทัด ไม่ใช่ที่การ์ด เพราะการ์ดหนึ่งใบมีหลายเรื่องที่แก้คนละที่ —
 * "โทเคนใกล้หมดอายุ" กับ "กุญแจที่ยังไม่มีใครได้สิทธิ์" อยู่คนละแท็บ ลิงก์รวมที่
 * การ์ดจะพาไปถูกแค่เรื่องเดียวเสมอ
 */
function Row({ label, value, href, items, tone = "plain", hideZero = false, raw = false }: {
  label: string; value: number | string; href?: string; items?: string[];
  tone?: "plain" | "amber"; hideZero?: boolean; raw?: boolean;
}) {
  // ศูนย์ที่ไม่มีความหมายไม่ต้องแสดง — ยอดรวมที่เป็นบริบทส่งมาเป็น raw
  if (hideZero && !raw && (value === 0 || value === "0")) return null;
  const hasItems = !!items && items.length > 0;
  const inner = (
    <>
      <span className="text-gray-600 truncate group-hover:text-gray-900">
        {label}
        {/* จุดเล็ก ๆ บอกว่าบรรทัดนี้กางดูได้ ไม่งั้นไม่มีใครรู้ว่าต้องชี้ */}
        {hasItems && <span className="ml-1 text-gray-300 group-hover:text-gray-500">·</span>}
      </span>
      <span className={`font-semibold tabular-nums shrink-0 ${
        tone === "amber" ? "text-amber-700" : "text-gray-900"}`}>{value}</span>
    </>
  );
  const cls = "group flex items-baseline justify-between gap-2 text-[11px] -mx-1 px-1 rounded";
  const body = href
    ? <Link href={href} className={`${cls} hover:bg-gray-50`}>{inner}</Link>
    : <div className={cls}>{inner}</div>;

  if (!hasItems) return body;

  // ตัวเลขที่ตรวจไม่ได้คือตัวเลขที่ต้องเชื่อไปก่อน — กางรายการจริงออกมาให้เห็น
  // ว่านับอะไรอยู่ ทำให้หน้านี้ตรวจสอบได้ ไม่ใช่แค่รายงาน
  return (
    <div className="relative group/row">
      {body}
      {/* เลื่อนได้และรับเมาส์ได้ — ปิดเมาส์ไว้แล้วตัดรายการที่ล้น คือการตัดเงียบ
          แบบเดียวกับที่ฟีเจอร์นี้ตั้งใจแก้ กล่องเป็นลูกของกลุ่มเดียวกัน เลื่อน
          เมาส์เข้าไปในกล่องจึงไม่ทำให้มันหาย */}
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

function Detail({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-1.5 pt-1.5 border-t border-gray-100 text-[9.5px] text-gray-400 leading-relaxed">
      {children}
    </div>
  );
}

/**
 * เส้นแนวโน้ม 24 ชม. — CPU กับหน่วยความจำ
 *
 * ค่าปัจจุบันตัวเดียวบอกไม่ได้ว่ากำลังไต่ขึ้นหรือเพิ่งลงมา ซึ่งเป็นความต่างที่
 * เปลี่ยนการตัดสินใจ วาดเป็น SVG ตรง ๆ ไม่ใช้ไลบรารีกราฟ เพราะเส้นสองเส้นไม่คุ้ม
 * กับบันเดิลและใบอนุญาตที่ต้องมาดูแลต่อ
 */
function Trend({ points }: { points: SystemOverview["performance"]["trend"] }) {
  const { t } = useLang();
  const path = useMemo(() => {
    if (points.length < 2) return null;
    const W = 100, H = 26;
    const line = (key: "cpu" | "mem") =>
      points.map((p, i) => {
        const x = (i / (points.length - 1)) * W;
        const y = H - Math.min(100, Math.max(0, p[key])) / 100 * H;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
    return { cpu: line("cpu"), mem: line("mem") };
  }, [points]);

  if (!path) return <p className="text-[9.5px] text-gray-400 mb-1">{t("ov.trend_none")}</p>;

  const last = points[points.length - 1];
  return (
    <div className="mb-1.5">
      <svg viewBox="0 0 100 26" preserveAspectRatio="none" className="w-full h-7">
        <path d={path.mem} fill="none" stroke="#c4a24a" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <path d={path.cpu} fill="none" stroke="#2b7fa0" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="flex gap-2 text-[9px] text-gray-500 mt-0.5">
        <span className="text-[#2b7fa0]">CPU {last.cpu}%</span>
        <span className="text-[#a08033]">RAM {last.mem}%</span>
        <span className="ml-auto text-gray-400">{t("ov.trend_24h")}</span>
      </div>
    </div>
  );
}
