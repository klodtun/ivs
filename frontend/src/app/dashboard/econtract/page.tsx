"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { EContractGuide } from "@/components/econtract-guide";
import { cn } from "@/lib/utils";

type Cert = {
  cert_id: string; filename: string; size_bytes: number; sha256: string;
  ntp_time: string | null; ntp_server_name: string; signature: string;
  signer: string; note: string; created_at: string | null; signature_count?: number;
  profile_key?: string; profile_version?: number; doc_format?: string;
};

type ProfileRow = {
  key: string; name_th: string; group: string; scenario_ref: number | null;
  risk_tier: string; blocked: boolean; blocked_reason_th: string;
  version: number; required_steps: string[];
};

type StepRow = {
  step: string; order: number; name_th: string; short_th: string; desc_th: string;
  sections: string[]; level: string; required: boolean; status: string;
  summary_th: string; next_action_th: string; note_th: string; detail: any;
};

// ขั้นตอนที่บันทึกด้วยมือได้ — ที่เหลือระบบตรวจจากข้อมูลจริงเอง
const MANUAL_STEPS = new Set(["e_seal", "e_stamp_duty", "print_out", "e_retention"]);

const STEP_STYLE: Record<string, { icon: string; cls: string; label: string }> = {
  done:         { icon: "✓", cls: "bg-green-50 border-green-200 text-green-800",   label: "ทำแล้ว" },
  partial:      { icon: "◐", cls: "bg-amber-50 border-amber-200 text-amber-800",   label: "ยังไม่ครบ" },
  pending:      { icon: "○", cls: "bg-red-50 border-red-200 text-red-700",         label: "ยังไม่ได้ทำ" },
  overdue:      { icon: "!", cls: "bg-red-100 border-red-300 text-red-800",        label: "เลยกำหนด" },
  not_required: { icon: "–", cls: "bg-gray-50 border-gray-200 text-gray-500",      label: "ไม่ต้องทำ" },
  optional:     { icon: "–", cls: "bg-gray-50 border-gray-200 text-gray-500",      label: "ไม่บังคับ" },
  waived:       { icon: "–", cls: "bg-gray-50 border-gray-200 text-gray-500",      label: "ระบุว่าไม่ต้องทำ" },
  blocked:      { icon: "✕", cls: "bg-red-100 border-red-300 text-red-800",        label: "ทำไม่ได้" },
};

const ENDPOINTS = [
  ["GET", "/api/econtract/profiles", "ประเภทสัญญาทั้งหมด + ขั้นตอนที่บังคับของแต่ละประเภท"],
  ["GET", "/api/econtract/profiles/{key}", "โปรไฟล์ 7 เรื่องที่ resolve แล้ว (?sector=gov)"],
  ["POST", "/api/econtract/certify", "อัปโหลดไฟล์ → ออกใบรับรอง (hash + เวลา NTP + ลายเซ็นระบบ + profile_key)"],
  ["POST", "/api/econtract/{id}/sign", "ลงนามอิเล็กทรอนิกส์ (signer_name, method, identity_ref)"],
  ["GET", "/api/econtract/{id}/compliance", "รายงาน 7 ขั้นตอน — ทำอะไรไปแล้ว ยังค้างอะไร"],
  ["POST", "/api/econtract/{id}/steps/{step}", "บันทึกขั้นตอนนอกระบบ (e_seal, e_stamp_duty, print_out, e_retention)"],
  ["GET", "/api/econtract/{id}/stamp-duty", "ข้อมูลสำหรับยื่นอากรแสตมป์ (อ.ส.9) — JSON"],
  ["GET", "/api/econtract/{id}/stamp-duty/download", "ดาวน์โหลดใบข้อมูลยื่น อ.ส.9 (?format=txt|json)"],
  ["POST", "/api/econtract/verify", "ตรวจสอบ (ไฟล์เดิม หรือ cert_id) → valid/invalid"],
  ["GET", "/api/econtract/{id}", "รายละเอียดใบรับรอง + ลายเซ็น + รายงาน 7 ขั้นตอน"],
  ["GET", "/api/econtract/{id}/evidence", "ชุดหลักฐาน .zip (cert + signatures + audit + 7 ขั้นตอน + manifest)"],
];

const ECONTRACT_PROMPT = `Build a web app that runs on iVS (Internal Vibe Server) and implements
legally-compliant electronic contracts (e-Contract) under Thailand's
Electronic Transactions Act. Do NOT roll your own crypto/timestamp —
call the iVS e-Contract API, which provides integrity, a Thai legal-NTP
trusted timestamp, e-signatures and evidence bundles.

Requirements:
1. Let the user upload/prepare a contract document.
2. Certify it: POST {IVS_URL}/api/econtract/certify  (multipart: file, signer, note)
   -> store the returned cert_id + sha256 with the contract.
3. Collect signatures: POST {IVS_URL}/api/econtract/{cert_id}/sign
   (form: signer_name, method = typed|drawn|otp, identity_ref)
   -> show each signer, method and timestamp.
4. Verify anytime: POST {IVS_URL}/api/econtract/verify  (file OR cert_id)
   -> show VALID / INVALID (tampered).
5. Offer the evidence bundle: link to GET {IVS_URL}/api/econtract/{cert_id}/evidence (.zip).

Rules:
- Auth: send the iVS bearer token in the Authorization header on every call.
- Read IVS_URL and the token from environment variables / iVS Vault — never hardcode.
- Keep all contract data on the iVS host (PDPA §28 — no cross-border transfer).
- Show the trusted timestamp and SHA-256 to the user as legal evidence.
- Package for iVS: single container, listen on process.env.PORT, no separate DB
  service (use SQLite/JSON if you need local storage).`;

export default function EContractPage() {
  const { t } = useLang();
  const [tab, setTab] = useState<"issue" | "verify" | "list" | "api">("issue");
  const [list, setList] = useState<Cert[]>([]);
  const [copied, setCopied] = useState(false);

  // contract profiles (ชั้น 7 เรื่อง)
  const [profiles, setProfiles] = useState<ProfileRow[]>([]);
  const [groups, setGroups] = useState<Record<string, string>>({});
  const [profileKey, setProfileKey] = useState("generic");
  const [sector, setSector] = useState("");
  const [stepForm, setStepForm] = useState<{ step: string; actor: string; ref: string; note: string } | null>(null);
  const [savingStep, setSavingStep] = useState(false);

  // issue
  const [file, setFile] = useState<File | null>(null);
  const [signer, setSigner] = useState("");
  const [note, setNote] = useState("");
  const [issuing, setIssuing] = useState(false);
  const [issued, setIssued] = useState<Cert | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // verify
  const [vfile, setVfile] = useState<File | null>(null);
  const [certId, setCertId] = useState("");
  const [vResult, setVResult] = useState<{ valid: boolean; reason: string; cert: Cert | null } | null>(null);
  const [vdrag, setVdrag] = useState(false);

  // detail + sign
  const [detail, setDetail] = useState<any | null>(null);
  const [signName, setSignName] = useState("");
  const [signMethod, setSignMethod] = useState("typed");
  const [signId, setSignId] = useState("");
  const [signing, setSigning] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);
  const hasInkRef = useRef(false);

  const canvasPos = (e: React.PointerEvent) => {
    const c = canvasRef.current!; const r = c.getBoundingClientRect();
    return { x: (e.clientX - r.left) * (c.width / r.width), y: (e.clientY - r.top) * (c.height / r.height) };
  };
  const startDraw = (e: React.PointerEvent) => {
    const c = canvasRef.current; if (!c) return;
    drawingRef.current = true; hasInkRef.current = true;
    const ctx = c.getContext("2d")!; ctx.lineWidth = 2; ctx.lineCap = "round"; ctx.strokeStyle = "#1c1a29";
    const p = canvasPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y);
    c.setPointerCapture(e.pointerId);
  };
  const moveDraw = (e: React.PointerEvent) => {
    if (!drawingRef.current) return;
    const ctx = canvasRef.current!.getContext("2d")!; const p = canvasPos(e);
    ctx.lineTo(p.x, p.y); ctx.stroke();
  };
  const endDraw = () => { drawingRef.current = false; };
  const clearCanvas = () => {
    const c = canvasRef.current; if (!c) return;
    c.getContext("2d")!.clearRect(0, 0, c.width, c.height); hasInkRef.current = false;
  };

  const openDetail = async (cid: string) => {
    try {
      setDetail(await api.getEContract(cid));
      setSignName(""); setSignId(""); setSignMethod("typed"); setStepForm(null);
    } catch (e) { console.error(e); }
  };
  const doSign = async () => {
    if (!detail || !signName.trim() || signing) return;
    let identity = signId;
    if (signMethod === "drawn") {
      if (!hasInkRef.current) { alert(t("ect.draw_empty")); return; }
      identity = canvasRef.current!.toDataURL("image/png");
    }
    setSigning(true);
    try {
      await api.signEContract(detail.cert_id, signName.trim(), signMethod, identity);
      setDetail(await api.getEContract(detail.cert_id));
      setSignName(""); setSignId(""); clearCanvas();
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setSigning(false); }
  };

  const load = useCallback(async () => {
    try { setList(await api.listEContracts()); } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api.listEContractProfiles()
      .then((r) => { setProfiles(r.profiles || []); setGroups(r.groups || {}); })
      .catch((e) => console.error(e));
  }, []);

  const selectedProfile = profiles.find((p) => p.key === profileKey);

  const doIssue = async () => {
    if (!file || issuing || selectedProfile?.blocked) return;
    setIssuing(true); setIssued(null);
    try {
      const c = await api.certifyEContract(file, signer, note, profileKey, sector);
      setIssued(c); setFile(null); setSigner(""); setNote("");
      await load();
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setIssuing(false); }
  };

  const doRecordStep = async (status: "done" | "waived") => {
    if (!detail || !stepForm || savingStep) return;
    setSavingStep(true);
    try {
      await api.recordEContractStep(detail.cert_id, stepForm.step, {
        actor: stepForm.actor, ref: stepForm.ref, note: stepForm.note, status,
      });
      setDetail(await api.getEContract(detail.cert_id));
      setStepForm(null);
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setSavingStep(false); }
  };

  const doVerify = async () => {
    setVResult(null);
    try { setVResult(await api.verifyEContract(vfile, certId.trim())); }
    catch (e: any) { alert(e?.message || "error"); }
  };

  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "—");
  const short = (h: string) => `${h.slice(0, 20)}…${h.slice(-8)}`;

  const Field = ({ label, value, mono }: { label: string; value: string; mono?: boolean }) => (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-gray-400">{label}</span>
      <span className={cn("text-xs text-gray-800 break-all", mono && "font-mono")}>{value}</span>
    </div>
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold text-gray-900">{t("ect.title")}</h1>
        <p className="text-xs text-gray-500">{t("ect.subtitle")}</p>
      </div>

      <div className="flex gap-1 border-b border-gray-200">
        {(["issue", "verify", "list", "api"] as const).map((k) => (
          <button key={k} onClick={() => setTab(k)}
            className={cn("px-3 py-1.5 text-xs font-medium -mb-px border-b-2 transition",
              tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800")}>
            {t(`ect.tab_${k}`)}
          </button>
        ))}
      </div>

      {tab === "issue" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3 max-w-2xl">
          {/* ประเภทสัญญา → กำหนดว่าต้องทำอะไรบ้างใน 7 เรื่อง */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div className="md:col-span-2">
              <div className="flex items-center">
                <label className="text-[10px] uppercase tracking-wide text-gray-400">ประเภทสัญญา</label>
                <EContractGuide />
              </div>
              <select value={profileKey} onChange={(e) => setProfileKey(e.target.value)}
                className="w-full mt-0.5 px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                {Object.entries(groups).map(([g, label]) => {
                  const rows = profiles.filter((p) => p.group === g);
                  if (!rows.length) return null;
                  return (
                    <optgroup key={g} label={label}>
                      {rows.map((p) => (
                        <option key={p.key} value={p.key}>
                          {p.blocked ? "🚫 " : ""}{p.name_th}
                          {p.scenario_ref ? ` (สถานการณ์ ${p.scenario_ref})` : ""}
                        </option>
                      ))}
                    </optgroup>
                  );
                })}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wide text-gray-400">ภาคส่วน</label>
              <select value={sector} onChange={(e) => setSector(e.target.value)}
                className="w-full mt-0.5 px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                <option value="">เอกชน</option>
                <option value="gov">ภาครัฐ</option>
              </select>
            </div>
          </div>

          {selectedProfile?.blocked ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2">
              <p className="text-xs font-semibold text-red-800">🚫 ทำเป็นสัญญาอิเล็กทรอนิกส์ไม่ได้</p>
              <p className="text-[11px] text-red-700 mt-0.5">{selectedProfile.blocked_reason_th}</p>
            </div>
          ) : selectedProfile ? (
            <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-1">
                ต้องทำ {selectedProfile.required_steps.length} จาก 7 ขั้นตอน
              </p>
              <div className="flex flex-wrap gap-1">
                {["e_document", "e_signature", "e_seal", "e_original", "e_retention", "e_stamp_duty", "print_out"].map((s, i) => {
                  const on = selectedProfile.required_steps.includes(s);
                  return (
                    <span key={s} title={s}
                      className={cn("text-[10px] px-1.5 py-0.5 rounded border",
                        on ? "bg-brand-50 border-brand-200 text-brand-700 font-medium"
                           : "bg-white border-gray-200 text-gray-400 line-through")}>
                      {i + 1}. {s.replace("e_", "").replace("_", " ")}
                    </span>
                  );
                })}
              </div>
              {sector === "gov" && (
                <p className="text-[10px] text-gray-500 mt-1.5">
                  ภาครัฐ: ยกระดับลายมือชื่อเป็นแบบเชื่อถือได้ + ใบรับรองจาก CA และต้องเก็บเลขที่สารบรรณ
                </p>
              )}
            </div>
          ) : null}

          <label
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); setFile(e.dataTransfer.files?.[0] ?? null); setIssued(null); }}
            className={cn("block border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition",
              dragging ? "border-brand-500 bg-brand-50" : "border-gray-300 bg-gray-50")}>
            <input ref={fileRef} type="file" className="hidden"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setIssued(null); e.currentTarget.value = ""; }} />
            <p className="text-xs font-medium text-gray-700">{file ? file.name : t("ect.drop")}</p>
            <p className="text-[10px] text-gray-400 mt-1">{t("ect.drop_hint")}</p>
          </label>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input value={signer} onChange={(e) => setSigner(e.target.value)} placeholder={t("ect.signer")}
              className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("ect.note")}
              className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
          </div>

          <button onClick={doIssue} disabled={!file || issuing || !!selectedProfile?.blocked}
            className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
            {issuing ? t("ect.issuing") : t("ect.issue_btn")}
          </button>

          {issued && (
            <div className="mt-2 bg-green-50 border border-green-200 rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-green-600">✓</span>
                <span className="font-mono text-xs font-bold text-green-800">{issued.cert_id}</span>
                <a href={api.downloadEContractUrl(issued.cert_id)}
                  className="ml-auto text-[10px] px-2 py-0.5 bg-green-600 text-white rounded hover:bg-green-700">
                  {t("ect.download")}
                </a>
              </div>
              <Field label={t("ect.field_hash")} value={issued.sha256} mono />
              <Field label={t("ect.field_time")} value={`${fmt(issued.ntp_time)} · ${issued.ntp_server_name || "NTP"}`} />
              <Field label={t("ect.field_sig")} value={issued.signature} mono />
            </div>
          )}
        </div>
      )}

      {tab === "verify" && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3 max-w-2xl">
          <label
            onDragOver={(e) => { e.preventDefault(); setVdrag(true); }}
            onDragLeave={() => setVdrag(false)}
            onDrop={(e) => { e.preventDefault(); setVdrag(false); setVfile(e.dataTransfer.files?.[0] ?? null); setVResult(null); }}
            className={cn("block border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition",
              vdrag ? "border-brand-500 bg-brand-50" : "border-gray-300 bg-gray-50")}>
            <input type="file" className="hidden"
              onChange={(e) => { setVfile(e.target.files?.[0] ?? null); setVResult(null); e.currentTarget.value = ""; }} />
            <p className="text-xs font-medium text-gray-700">{vfile ? vfile.name : t("ect.drop")}</p>
            <p className="text-[10px] text-gray-400 mt-1">{t("ect.drop_hint")}</p>
          </label>
          <input value={certId} onChange={(e) => setCertId(e.target.value)} placeholder={t("ect.verify_by_id") + " (ECT-…)"}
            className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs font-mono outline-none focus:ring-2 focus:ring-brand-500" />
          <button onClick={doVerify} disabled={!vfile && !certId.trim()}
            className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
            {t("ect.verify_btn")}
          </button>

          {vResult && (
            <div className={cn("rounded-lg border p-3 space-y-2",
              vResult.valid ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200")}>
              <div className={cn("text-xs font-bold flex items-center gap-2", vResult.valid ? "text-green-800" : "text-red-700")}>
                <span>{vResult.valid ? "✓" : "✗"}</span>
                {vResult.valid ? t("ect.valid") : t("ect.invalid")} — {vResult.reason}
              </div>
              {vResult.cert && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                  <Field label={t("ect.col_cert")} value={vResult.cert.cert_id} mono />
                  <Field label={t("ect.col_file")} value={vResult.cert.filename} />
                  <Field label={t("ect.field_time")} value={`${fmt(vResult.cert.ntp_time)} · ${vResult.cert.ntp_server_name || "NTP"}`} />
                  <Field label={t("ect.field_hash")} value={short(vResult.cert.sha256)} mono />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "list" && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-500 text-[10px] uppercase">
              <tr>
                <th className="px-3 py-2 text-left">{t("ect.col_cert")}</th>
                <th className="px-3 py-2 text-left">{t("ect.col_file")}</th>
                <th className="px-3 py-2 text-left">ประเภทสัญญา</th>
                <th className="px-3 py-2 text-left">{t("ect.col_time")}</th>
                <th className="px-3 py-2 text-left">{t("ect.col_hash")}</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {list.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">{t("ect.empty")}</td></tr>
              )}
              {list.map((c) => (
                <tr key={c.cert_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono font-semibold text-brand-700">{c.cert_id}</td>
                  <td className="px-3 py-2 text-gray-700">
                    {c.filename}
                    {c.doc_format && <span className="ml-1 text-[10px] text-gray-400">{c.doc_format}</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-600">
                    {profiles.find((p) => p.key === c.profile_key)?.name_th || c.profile_key || "—"}
                  </td>
                  <td className="px-3 py-2 text-gray-600">{fmt(c.ntp_time)}</td>
                  <td className="px-3 py-2 font-mono text-gray-500">{short(c.sha256)}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button onClick={() => openDetail(c.cert_id)} className="text-[10px] text-brand-600 hover:text-brand-700 mr-2">
                      {t("ect.view")}{c.signature_count ? ` (${c.signature_count})` : ""}
                    </button>
                    <a href={api.downloadEContractUrl(c.cert_id)} className="text-[10px] text-gray-400 hover:text-gray-600">.json</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "api" && (
        <div className="space-y-4 max-w-3xl">
          <p className="text-xs text-gray-500">{t("ect.api_desc")}</p>

          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-3 py-2 text-[11px] font-semibold text-gray-600 bg-gray-50 border-b border-gray-200">{t("ect.api_endpoints")}</div>
            {ENDPOINTS.map(([m, path, desc]) => (
              <div key={path} className="flex items-start gap-3 px-3 py-2 border-b border-gray-100 last:border-0">
                <span className={cn("text-[10px] font-bold font-mono px-1.5 py-0.5 rounded flex-shrink-0",
                  m === "GET" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700")}>{m}</span>
                <span className="text-[11px] font-mono text-gray-800 flex-shrink-0">{path}</span>
                <span className="text-[11px] text-gray-500">{desc}</span>
              </div>
            ))}
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-semibold text-gray-600 uppercase tracking-wide">{t("ect.api_prompt")}</span>
              <div className="flex gap-1">
                <button
                  onClick={() => { const b = new Blob([ECONTRACT_PROMPT], { type: "text/markdown" }); const u = URL.createObjectURL(b); const a = document.createElement("a"); a.href = u; a.download = "ivs-econtract-prompt.md"; a.click(); URL.revokeObjectURL(u); }}
                  className="text-[10px] px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-brand-100 hover:text-brand-700">
                  ⬇ {t("ect.download_md")}
                </button>
                <button
                  onClick={() => { navigator.clipboard?.writeText(ECONTRACT_PROMPT); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                  className={cn("text-[10px] px-2 py-1 rounded", copied ? "bg-green-100 text-green-700" : "bg-brand-600 text-white hover:bg-brand-700")}>
                  {copied ? `✓ ${t("ect.copied")}` : `⧉ ${t("ect.copy")}`}
                </button>
              </div>
            </div>
            <pre className="bg-gray-900 text-gray-100 text-[10.5px] rounded-lg p-3 whitespace-pre-wrap font-mono max-h-[420px] overflow-y-auto">{ECONTRACT_PROMPT}</pre>
          </div>
        </div>
      )}

      {detail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-sm font-bold text-brand-700">{detail.cert_id}</span>
              <div className="flex items-center gap-2">
                <a href={api.evidenceBundleUrl(detail.cert_id)}
                  className="text-[10px] px-2 py-1 bg-brand-600 text-white rounded hover:bg-brand-700">
                  ⬇ {t("ect.evidence")}
                </a>
                <button onClick={() => setDetail(null)} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-4">
              <Field label={t("ect.col_file")} value={`${detail.filename}${detail.doc_format ? ` · ${detail.doc_format}` : ""}`} />
              <Field label={t("ect.field_time")} value={`${fmt(detail.ntp_time)} · ${detail.ntp_server_name || "NTP"}`} />
              <Field label={t("ect.field_hash")} value={detail.sha256} mono />
              <Field label={t("ect.field_sig")} value={short(detail.signature)} mono />
            </div>

            {/* ── 7 เรื่องของวงจร e-Contract ─────────────────────────── */}
            {detail.compliance && (() => {
              const c = detail.compliance;
              const pct = c.summary.required_total
                ? Math.round((c.summary.required_done / c.summary.required_total) * 100) : 0;
              return (
                <div className="mb-4">
                  <div className="flex items-baseline justify-between mb-1">
                    <h3 className="text-xs font-semibold text-gray-800">
                      7 ขั้นตอนของวงจร e-Contract
                    </h3>
                    <span className="text-[10px] text-gray-400 font-mono">
                      {c.profile.key} v{c.profile.version} · {c.profile.hash?.slice(0, 8)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[11px] font-medium text-gray-700">{c.profile.name_th}</span>
                    {Object.entries(c.profile.resolved_from || {})
                      .filter(([k]) => k !== "baseline")
                      .map(([k, v]) => (
                        <span key={k} className="text-[10px] px-1.5 py-0.5 bg-brand-50 text-brand-700 rounded">{String(v)}</span>
                      ))}
                    <span className="ml-auto text-[10px] text-gray-500">
                      ครบ {c.summary.required_done}/{c.summary.required_total} ขั้นตอนที่บังคับ
                    </span>
                  </div>
                  <div className="h-1 bg-gray-100 rounded-full overflow-hidden mb-2">
                    <div className={cn("h-full rounded-full transition-all",
                      pct === 100 ? "bg-green-500" : "bg-brand-500")} style={{ width: `${pct}%` }} />
                  </div>

                  {(c.profile.warnings || []).map((w: any, i: number) => (
                    <div key={i} className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5">
                      <p className="text-[11px] text-amber-800">⚠ {w.text_th}</p>
                    </div>
                  ))}

                  <div className="border border-gray-200 rounded-md overflow-hidden">
                    {(c.steps as StepRow[]).map((s) => {
                      const st = STEP_STYLE[s.status] || STEP_STYLE.pending;
                      const canRecord = MANUAL_STEPS.has(s.step)
                        && !["done", "waived", "blocked"].includes(s.status);
                      const editing = stepForm && stepForm.step === s.step ? stepForm : null;
                      return (
                        <div key={s.step} className="border-b border-gray-100 last:border-0">
                          <div className="flex items-start gap-2 px-2.5 py-2">
                            <span className={cn(
                              "flex-shrink-0 w-5 h-5 rounded-full border flex items-center justify-center text-[11px] font-bold mt-0.5",
                              st.cls)}>{st.icon}</span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-baseline gap-1.5 flex-wrap">
                                <span className="text-[11px] font-medium text-gray-800">
                                  {s.order}. {s.name_th}
                                </span>
                                <span className="text-[10px] text-gray-400 font-mono">{s.short_th}</span>
                                {s.required && (
                                  <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-600 rounded">บังคับ</span>
                                )}
                                {s.level === "LOCKED" && (
                                  <span className="text-[9px] px-1 py-0.5 bg-red-50 text-red-600 rounded" title="กำหนดโดยกฎหมาย แก้ไม่ได้">🔒 กฎหมาย</span>
                                )}
                                <span className="ml-auto text-[9px] text-gray-400">
                                  ม.{s.sections.join(", ม.")}
                                </span>
                              </div>
                              {s.summary_th && (
                                <p className="text-[11px] text-gray-600 mt-0.5">{s.summary_th}</p>
                              )}
                              {s.next_action_th && (
                                <p className="text-[11px] text-brand-700 mt-0.5">→ {s.next_action_th}</p>
                              )}
                              {s.note_th && (
                                <p className="text-[10px] text-gray-400 mt-0.5">{s.note_th}</p>
                              )}

                              {/* อากรแสตมป์: ลิงก์ไป e-Filing + ดาวน์โหลดข้อมูลสำหรับยื่น */}
                              {s.step === "e_stamp_duty" && s.detail?.efiling_url && (
                                <div className="mt-1.5 rounded-md border border-gray-200 bg-white px-2 py-1.5">
                                  <p className="text-[10px] text-gray-500">
                                    {s.detail.channel_label_th}
                                    {s.detail.channel_note_th ? ` — ${s.detail.channel_note_th}` : ""}
                                  </p>
                                  <div className="flex flex-wrap items-center gap-1.5 mt-1">
                                    <a href={s.detail.efiling_url} target="_blank" rel="noopener noreferrer"
                                      className="text-[10px] px-2 py-0.5 bg-brand-600 text-white rounded hover:bg-brand-700">
                                      ↗ ยื่นที่ e-Filing (อ.ส.9)
                                    </a>
                                    {s.detail.worksheet_available && (
                                      <>
                                        <a href={api.stampDutyDownloadUrl(detail.cert_id, "txt")}
                                          className="text-[10px] px-2 py-0.5 border border-brand-200 text-brand-700 rounded hover:bg-brand-50">
                                          ⬇ ข้อมูลสำหรับยื่น (.txt)
                                        </a>
                                        <a href={api.stampDutyDownloadUrl(detail.cert_id, "json")}
                                          className="text-[10px] px-2 py-0.5 border border-gray-200 text-gray-500 rounded hover:bg-gray-50">
                                          .json
                                        </a>
                                      </>
                                    )}
                                    {s.detail.manual_url && (
                                      <a href={s.detail.manual_url} target="_blank" rel="noopener noreferrer"
                                        className="text-[10px] text-gray-400 hover:text-gray-600 underline">
                                        คู่มือกรมสรรพากร
                                      </a>
                                    )}
                                  </div>
                                  {s.detail.receipt_ref && (
                                    <p className="text-[10px] text-green-700 mt-1">
                                      รหัสรับรองการเสียอากร: <span className="font-mono">{s.detail.receipt_ref}</span>
                                    </p>
                                  )}
                                </div>
                              )}

                              {canRecord && !editing && (
                                <button
                                  onClick={() => setStepForm({ step: s.step, actor: "", ref: "", note: "" })}
                                  className="mt-1 text-[10px] px-2 py-0.5 border border-brand-200 text-brand-700 rounded hover:bg-brand-50">
                                  บันทึกขั้นตอนนี้
                                </button>
                              )}
                            </div>
                          </div>

                          {editing && (
                            <div className="bg-gray-50 border-t border-gray-100 px-2.5 py-2 space-y-1.5">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                                <input value={editing.actor} placeholder="ผู้ดำเนินการ / หน่วยงาน"
                                  onChange={(e) => setStepForm({ ...editing, actor: e.target.value })}
                                  className="px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500" />
                                <input value={editing.ref}
                                  placeholder={s.step === "e_stamp_duty" ? "รหัสรับรองการเสียอากร (อ.ส.9)" : "เลขที่อ้างอิง"}
                                  onChange={(e) => setStepForm({ ...editing, ref: e.target.value })}
                                  className="px-2 py-1 border border-gray-300 rounded text-[11px] font-mono outline-none focus:ring-2 focus:ring-brand-500" />
                              </div>
                              <input value={editing.note} placeholder="หมายเหตุ"
                                onChange={(e) => setStepForm({ ...editing, note: e.target.value })}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500" />
                              <div className="flex gap-1.5">
                                <button onClick={() => doRecordStep("done")} disabled={savingStep}
                                  className="px-3 py-1 bg-brand-600 text-white text-[11px] rounded hover:bg-brand-700 disabled:opacity-50">
                                  {savingStep ? "กำลังบันทึก…" : "บันทึกว่าทำแล้ว"}
                                </button>
                                {!s.required && (
                                  <button onClick={() => doRecordStep("waived")} disabled={savingStep}
                                    className="px-3 py-1 border border-gray-300 text-gray-600 text-[11px] rounded hover:bg-gray-100 disabled:opacity-50">
                                    ระบุว่าไม่ต้องทำ
                                  </button>
                                )}
                                <button onClick={() => setStepForm(null)}
                                  className="px-3 py-1 text-gray-400 text-[11px] hover:text-gray-600">ยกเลิก</button>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-gray-400 mt-1.5">
                    รายงานนี้บอกว่าทำครบตามโปรไฟล์ที่เลือกหรือยัง — ไม่ใช่คำวินิจฉัยว่าสัญญาสมบูรณ์ตามกฎหมาย
                  </p>
                </div>
              );
            })()}

            {/* signatures */}
            <h3 className="text-xs font-semibold text-gray-800 mb-2">{t("ect.sign_title")}</h3>
            <div className="border border-gray-200 rounded-md overflow-hidden mb-3">
              {(detail.signatures || []).length === 0 ? (
                <div className="px-3 py-4 text-center text-gray-400 text-xs">{t("ect.sig_none")}</div>
              ) : (
                (detail.signatures || []).map((sg: any) => (
                  <div key={sg.id} className="px-3 py-2 border-b border-gray-100 last:border-0 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-green-600">✓</span>
                      <span className="font-medium text-gray-800">{sg.signer_name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-brand-50 text-brand-700 rounded">{t(`ect.method_${sg.method}`)}</span>
                      <span className="ml-auto text-[10px] text-gray-400">{t("ect.sig_at")} {fmt(sg.signed_at)}</span>
                    </div>
                    {sg.method === "drawn" && typeof sg.identity_ref === "string" && sg.identity_ref.startsWith("data:image") && (
                      <img src={sg.identity_ref} alt="signature" className="mt-1.5 h-12 border border-gray-200 rounded bg-white" />
                    )}
                  </div>
                ))
              )}
            </div>

            {/* sign form */}
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input value={signName} onChange={(e) => setSignName(e.target.value)} placeholder={t("ect.signer_name")}
                  className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
                <select value={signMethod} onChange={(e) => setSignMethod(e.target.value)}
                  className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="typed">{t("ect.method_typed")}</option>
                  <option value="drawn">{t("ect.method_drawn")}</option>
                  <option value="otp">{t("ect.method_otp")}</option>
                </select>
              </div>
              {signMethod === "drawn" ? (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-gray-500">{t("ect.draw_here")}</span>
                    <button onClick={clearCanvas} className="text-[10px] text-gray-500 hover:text-red-600">{t("ect.clear")}</button>
                  </div>
                  <canvas ref={canvasRef} width={560} height={140}
                    onPointerDown={startDraw} onPointerMove={moveDraw} onPointerUp={endDraw} onPointerLeave={endDraw}
                    className="w-full h-[140px] bg-white border-2 border-dashed border-gray-300 rounded-md touch-none cursor-crosshair" />
                </div>
              ) : (
                <input value={signId} onChange={(e) => setSignId(e.target.value)} placeholder={t("ect.identity")}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
              )}
              <button onClick={doSign} disabled={!signName.trim() || signing}
                className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
                {signing ? t("ect.signing") : t("ect.sign_btn")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
