"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

/**
 * คู่มือ e-Contract — อธิบายสถานการณ์ทั้งหมดที่ปรากฏใน dropdown "ประเภทสัญญา"
 * และ 7 ขั้นตอนของวงจร e-Contract พร้อมลิงก์ดาวน์โหลดคู่มือฉบับเต็มของ ETDA
 *
 * เนื้อหาดึงจาก /api/econtract/profiles โดยตรง — เพิ่มประเภทสัญญาใน baseline.yaml
 * แล้วคู่มือจะอัปเดตตามเอง ไม่ต้องแก้ component
 */

type ProfileRow = {
  key: string; name_th: string; summary_th: string; group: string;
  scenario_ref: number | null; risk_tier: string; blocked: boolean;
  blocked_reason_th: string; version: number; required_steps: string[];
  legal?: { sections?: string[]; tax_th?: string; other_th?: string };
  warnings?: { severity: string; text_th: string }[];
};

type StepMeta = {
  key: string; order: number; name_th: string; short_th: string;
  desc_th: string; sections: string[];
};

type Handbook = {
  title_th: string; author_th: string; publisher_th: string; programme_th: string;
  pages: number; available: boolean; local_available: boolean;
  size_bytes: number; local_path: string; drive_url: string;
};

const RISK_STYLE: Record<string, { label: string; cls: string }> = {
  low:    { label: "ความเสี่ยงต่ำ",    cls: "bg-green-50 text-green-700 border-green-200" },
  medium: { label: "ความเสี่ยงปานกลาง", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  high:   { label: "ความเสี่ยงสูง",    cls: "bg-red-50 text-red-700 border-red-200" },
};

const STEP_SHORT = ["e_document", "e_signature", "e_seal", "e_original",
                    "e_retention", "e_stamp_duty", "print_out"];

export function EContractGuide() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"scenarios" | "steps" | "source">("scenarios");
  const [profiles, setProfiles] = useState<ProfileRow[]>([]);
  const [groups, setGroups] = useState<Record<string, string>>({});
  const [steps, setSteps] = useState<StepMeta[]>([]);
  const [handbook, setHandbook] = useState<Handbook | null>(null);
  const [expanded, setExpanded] = useState<string>("");

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    if (open) document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [open]);

  useEffect(() => {
    if (!open || profiles.length) return;
    api.listEContractProfiles()
      .then((r) => { setProfiles(r.profiles || []); setGroups(r.groups || {}); setSteps(r.steps || []); })
      .catch((e) => console.error(e));
    api.getEContractHandbook().then(setHandbook).catch(() => setHandbook(null));
  }, [open, profiles.length]);

  const fmtMB = (b: number) => `${(b / 1024 / 1024).toFixed(0)} MB`;

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 ml-2 px-1.5 py-0.5 text-[10px] font-medium text-brand-600 bg-brand-50 border border-brand-200 rounded-full hover:bg-brand-100 transition-colors"
        title="อธิบายประเภทสัญญาทั้งหมด 7 ขั้นตอนของวงจร e-Contract และคู่มือฉบับเต็มของ ETDA"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
        คู่มือ e-Contract
      </button>

      {open && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setOpen(false)} />
          <div className="fixed inset-4 sm:inset-auto sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 z-50 w-auto sm:w-[620px] max-h-[calc(100vh-2rem)] sm:max-h-[80vh] bg-white rounded-xl border border-gray-200 shadow-2xl overflow-hidden flex flex-col">
            {/* Header */}
            <div className="bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-3 flex items-center justify-between flex-shrink-0">
              <div>
                <h3 className="text-white font-semibold text-sm">คู่มือ e-Contract</h3>
                <p className="text-brand-100 text-[10px] mt-0.5">
                  สถานการณ์การใช้งาน · วงจร 7 ขั้นตอน · อ้างอิงคู่มือ ETDA
                </p>
              </div>
              <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white p-0.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-100 flex-shrink-0">
              {([["scenarios", "ประเภทสัญญา"], ["steps", "วงจร 7 ขั้นตอน"], ["source", "เอกสารอ้างอิง"]] as const).map(
                ([k, label]) => (
                  <button key={k} onClick={() => setTab(k)}
                    className={`flex-1 py-2 text-[11px] font-medium transition-colors ${
                      tab === k ? "text-brand-600 border-b-2 border-brand-500 bg-brand-50/50"
                                : "text-gray-500 hover:text-gray-700"}`}>
                    {label}
                  </button>
                )
              )}
            </div>

            <div className="overflow-y-auto flex-1 min-h-0">
              {/* ── ประเภทสัญญา ───────────────────────────────────── */}
              {tab === "scenarios" && (
                <div className="p-3 space-y-3">
                  <p className="text-[11px] text-gray-500 leading-relaxed">
                    ประเภทสัญญาที่เลือกได้ใน dropdown มาจากกรณีศึกษาในคู่มือ ETDA
                    แต่ละประเภทกำหนดว่าต้องทำกี่ขั้นตอนจาก 7 เรื่อง —
                    <b className="text-gray-700"> ไม่จำเป็นต้องทำครบทุกข้อเสมอไป</b> คลิกเพื่อดูรายละเอียด
                  </p>

                  {profiles.length === 0 && (
                    <p className="text-[11px] text-gray-400 text-center py-6">กำลังโหลด…</p>
                  )}

                  {Object.entries(groups).map(([g, label]) => {
                    const rows = profiles.filter((p) => p.group === g);
                    if (!rows.length) return null;
                    return (
                      <div key={g}>
                        <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
                          {label}
                        </div>
                        <div className="border border-gray-200 rounded-md overflow-hidden">
                          {rows.map((p) => {
                            const isOpen = expanded === p.key;
                            const risk = RISK_STYLE[p.risk_tier];
                            return (
                              <div key={p.key} className="border-b border-gray-100 last:border-0">
                                <button
                                  onClick={() => setExpanded(isOpen ? "" : p.key)}
                                  className="w-full text-left px-2.5 py-2 hover:bg-gray-50 transition-colors">
                                  <div className="flex items-baseline gap-1.5 flex-wrap">
                                    {p.blocked && <span className="text-[11px]">🚫</span>}
                                    <span className={`text-[11px] font-medium ${p.blocked ? "text-red-700" : "text-gray-800"}`}>
                                      {p.name_th}
                                    </span>
                                    {p.scenario_ref && (
                                      <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-500 rounded">
                                        สถานการณ์ {p.scenario_ref}
                                      </span>
                                    )}
                                    {risk && !p.blocked && (
                                      <span className={`text-[9px] px-1 py-0.5 rounded border ${risk.cls}`}>
                                        {risk.label}
                                      </span>
                                    )}
                                    {!p.blocked && (
                                      <span className="ml-auto text-[9px] text-gray-400">
                                        ต้องทำ {p.required_steps.length}/7
                                      </span>
                                    )}
                                  </div>
                                  {p.summary_th && (
                                    <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">{p.summary_th}</p>
                                  )}
                                </button>

                                {isOpen && (
                                  <div className="bg-gray-50 border-t border-gray-100 px-2.5 py-2 space-y-1.5">
                                    {p.blocked ? (
                                      <p className="text-[11px] text-red-700">{p.blocked_reason_th}</p>
                                    ) : (
                                      <>
                                        <div>
                                          <span className="text-[10px] uppercase tracking-wide text-gray-400">
                                            ขั้นตอนที่ต้องทำ
                                          </span>
                                          <div className="flex flex-wrap gap-1 mt-1">
                                            {STEP_SHORT.map((s, i) => {
                                              const on = p.required_steps.includes(s);
                                              const meta = steps.find((m) => m.key === s);
                                              return (
                                                <span key={s} title={meta?.desc_th}
                                                  className={`text-[9px] px-1.5 py-0.5 rounded border ${
                                                    on ? "bg-brand-50 border-brand-200 text-brand-700 font-medium"
                                                       : "bg-white border-gray-200 text-gray-400 line-through"}`}>
                                                  {i + 1}. {meta?.short_th || s}
                                                </span>
                                              );
                                            })}
                                          </div>
                                        </div>
                                        {p.legal?.sections?.length ? (
                                          <p className="text-[10px] text-gray-500">
                                            มาตราที่เกี่ยวข้อง: ม.{p.legal.sections.join(", ม.")}
                                            {p.legal.tax_th ? ` · ภาษี: ${p.legal.tax_th}` : ""}
                                          </p>
                                        ) : null}
                                        {p.legal?.other_th && (
                                          <p className="text-[10px] text-gray-500">กฎหมายอื่น: {p.legal.other_th}</p>
                                        )}
                                        {(p.warnings || []).map((w, i) => (
                                          <p key={i} className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-1">
                                            ⚠ {w.text_th}
                                          </p>
                                        ))}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ── วงจร 7 ขั้นตอน ────────────────────────────────── */}
              {tab === "steps" && (
                <div className="p-3 space-y-2">
                  <p className="text-[11px] text-gray-500 leading-relaxed">
                    วงจรการจัดทำสัญญาอิเล็กทรอนิกส์ตามประกาศ สพธอ. (21 มิ.ย. 2567) มี 7 เรื่อง
                    คู่สัญญาเลือกทำ <b className="text-gray-700">บางกระบวนการหรือทั้งหมด</b>
                    ได้ตามความเหมาะสมและประเภทสัญญา
                  </p>
                  <div className="border border-gray-200 rounded-md overflow-hidden">
                    {steps.map((s) => (
                      <div key={s.key} className="flex items-start gap-2 px-2.5 py-2 border-b border-gray-100 last:border-0">
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-50 border border-brand-200 text-brand-700 flex items-center justify-center text-[10px] font-bold mt-0.5">
                          {s.order}
                        </span>
                        <div className="min-w-0">
                          <div className="flex items-baseline gap-1.5">
                            <span className="text-[11px] font-medium text-gray-800">{s.name_th}</span>
                            <span className="text-[10px] font-mono text-gray-400">{s.short_th}</span>
                            <span className="text-[9px] text-gray-400">ม.{s.sections.join(", ม.")}</span>
                          </div>
                          <p className="text-[11px] text-gray-500 mt-0.5">{s.desc_th}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-md border border-gray-200 bg-gray-50 px-2.5 py-2">
                    <p className="text-[10px] text-gray-500 leading-relaxed">
                      <b className="text-gray-700">ทำอิเล็กทรอนิกส์ไม่ได้:</b> ธุรกรรมเกี่ยวกับ
                      ครอบครัวและมรดก (สมรส หย่า รับบุตรบุญธรรม พินัยกรรม) —
                      พ.ร.บ.ว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ ม.3 ไม่ใช้บังคับ
                    </p>
                  </div>
                </div>
              )}

              {/* ── เอกสารอ้างอิง ─────────────────────────────────── */}
              {tab === "source" && (
                <div className="p-3 space-y-3">
                  <div className="rounded-md border border-gray-200 overflow-hidden">
                    <div className="bg-gray-50 px-3 py-2 border-b border-gray-200">
                      <p className="text-[11px] font-semibold text-gray-800">
                        {handbook?.title_th || "(ร่าง) คู่มือการจัดทำสัญญาอิเล็กทรอนิกส์ e-Contract"}
                      </p>
                      <p className="text-[10px] text-gray-500 mt-0.5">
                        {handbook?.author_th} · {handbook?.publisher_th}
                      </p>
                    </div>
                    <div className="px-3 py-2 space-y-1.5">
                      <p className="text-[10px] text-gray-500">
                        เอกสารประกอบโครงการ {handbook?.programme_th || "Train the Transformers: e-Contract"}
                        {handbook?.pages ? ` · ${handbook.pages} หน้า` : ""}
                      </p>
                      <p className="text-[10px] text-gray-500 leading-relaxed">
                        ครอบคลุมนิยามและคำศัพท์ กฎหมายที่เกี่ยวข้อง กระบวนการจัดทำ 7 เรื่อง
                        ความต่างระหว่างภาครัฐกับเอกชน เครื่องมือและเกณฑ์คัดเลือกผู้พัฒนา
                        กรณีศึกษา 19 สถานการณ์ กรณีศึกษาต่างประเทศ และคำถามที่พบบ่อย
                      </p>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1">
                        {handbook?.drive_url && (
                          <a href={handbook.drive_url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-600 text-white text-[10px] font-medium rounded hover:bg-brand-700">
                            ↗ เปิดคู่มือ (Google Drive)
                          </a>
                        )}
                        {handbook?.local_available && (
                          <a href={api.econtractHandbookUrl()}
                            className="inline-flex items-center gap-1 px-2.5 py-1 border border-brand-200 text-brand-700 text-[10px] font-medium rounded hover:bg-brand-50">
                            ⬇ ดาวน์โหลดจากเครื่องนี้{handbook.size_bytes ? ` (${fmtMB(handbook.size_bytes)})` : ""}
                          </a>
                        )}
                      </div>
                      {!handbook?.local_available && (
                        <p className="text-[9px] text-gray-400 mt-1">
                          เครื่องนี้ไม่มีสำเนาในตัว — หน่วยงานที่ไม่ต่ออินเทอร์เน็ตวางไฟล์ไว้ที่{" "}
                          <span className="font-mono break-all">{handbook?.local_path}</span>{" "}
                          เพื่อให้ดาวน์โหลดตรงจาก iVS ได้
                        </p>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mb-1">
                      แหล่งอ้างอิงออนไลน์
                    </div>
                    <div className="border border-gray-200 rounded-md overflow-hidden">
                      {[
                        ["ระบบ อ.ส.9 (e-Filing) กรมสรรพากร", "ยื่นขอเสียอากรแสตมป์เป็นตัวเงิน",
                         "https://efiling.rd.go.th/ef-cms-web/"],
                        ["ETDA Web Validation", "ตรวจสอบลายมือชื่อที่ลงนามด้วยใบรับรอง",
                         "https://validation.teda.th/th/validate"],
                        ["สพธอ. (ETDA)", "ประกาศ มาตรฐาน และข้อเสนอแนะที่เกี่ยวข้อง",
                         "https://www.etda.or.th/"],
                      ].map(([name, desc, url]) => (
                        <a key={url} href={url} target="_blank" rel="noopener noreferrer"
                          className="block px-2.5 py-2 border-b border-gray-100 last:border-0 hover:bg-gray-50">
                          <div className="text-[11px] font-medium text-brand-700">↗ {name}</div>
                          <div className="text-[10px] text-gray-500">{desc}</div>
                        </a>
                      ))}
                    </div>
                  </div>

                  <p className="text-[9px] text-gray-400 leading-relaxed">
                    คู่มือฉบับนี้เผยแพร่ได้โดยได้รับความยินยอมจาก สพธอ. (ETDA) แล้ว ·
                    เนื้อหาในหน้าจอนี้เป็นการสรุปเพื่อประกอบการใช้งานระบบ
                    ไม่ใช่คำวินิจฉัยทางกฎหมายหรือทางภาษี
                  </p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
