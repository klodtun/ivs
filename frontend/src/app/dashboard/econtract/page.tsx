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

type Seal = {
  seal_id: string; org_name: string; org_tax_id: string; image_data: string;
  authority_note: string; is_active: boolean; created_at: string | null;
};

type TabKey = "issue" | "verify" | "list" | "seal" | "original" | "api";

// แท็บ: 4 อันเดิมใช้ i18n, 2 อันใหม่ใช้ label ตรง (ยังไม่มี key ใน i18n)
const TABS: { key: TabKey; label?: string }[] = [
  { key: "issue" }, { key: "verify" },
  { key: "list", label: "กระบวนการ/ลงนาม" },
  { key: "seal", label: "e-Seal" },
  { key: "original", label: "e-Original + e-Retention" },
  { key: "api" },
];

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
  ["POST", "/api/econtract/{id}/sign", "ลงนาม (signer_name, method, identity_ref, signing_mode)"],
  ["GET", "/api/econtract/{id}/compliance", "รายงาน 7 ขั้นตอน — ทำอะไรไปแล้ว ยังค้างอะไร"],
  ["POST", "/api/econtract/{id}/steps/{step}", "บันทึกขั้นตอนนอกระบบ (e_seal, e_stamp_duty, print_out, e_retention)"],
  ["GET", "/api/econtract/seals", "ตราประทับนิติบุคคลที่ลงทะเบียนไว้"],
  ["POST", "/api/econtract/seals", "ลงทะเบียนตราประทับ (org_name, org_tax_id, image_data)"],
  ["POST", "/api/econtract/{id}/seal", "ประทับตราลงใบรับรอง (seal_id) → บันทึกขั้นตอน e-Seal"],
  ["GET", "/api/econtract/originals", "ภาพรวมความเป็นต้นฉบับ (ม.10) + การเก็บรักษา (ม.12)"],
  ["GET", "/api/econtract/{id}/chain", "โซ่หลักฐาน — ลำดับเหตุการณ์ + ผลตรวจความต่อเนื่อง (ม.11)"],
  ["POST", "/api/econtract/{id}/deliver", "บันทึกการส่งร่างให้คู่สัญญา (recipients)"],
  ["POST", "/api/econtract/{id}/acceptance", "บันทึกคำสนอง ม.13 (party, source=first_party|imported)"],
  ["POST", "/api/econtract/{id}/lock", "ตรึงต้นฉบับ ม.10 — หลังจากนี้ลงนาม/ประทับตราเพิ่มไม่ได้"],
  ["GET", "/api/econtract/{id}/attachments", "หลักฐานตัวจริงที่แนบไว้"],
  ["POST", "/api/econtract/{id}/attachments", "แนบหลักฐาน (file, kind) — เก็บ hash เสมอ เก็บไฟล์เมื่อเปิดโหมด"],
  ["POST", "/api/econtract/{id}/retention-storage", "เปิด/ปิดการเก็บตัวไฟล์จริง (store)"],
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
  const [tab, setTab] = useState<TabKey>("issue");
  const [list, setList] = useState<Cert[]>([]);
  const [copied, setCopied] = useState(false);

  // e-Seal
  const [seals, setSeals] = useState<Seal[]>([]);
  const [sealForm, setSealForm] = useState({ org_name: "", org_tax_id: "", authority_note: "" });
  const [sealImg, setSealImg] = useState("");
  const [savingSeal, setSavingSeal] = useState(false);
  const [applyCert, setApplyCert] = useState("");
  const [applySeal, setApplySeal] = useState("");
  const [applying, setApplying] = useState(false);

  // โซ่หลักฐาน + lifecycle
  const [chain, setChain] = useState<any | null>(null);
  const [lifeAct, setLifeAct] = useState<"" | "deliver" | "acceptance">("");
  const [lifeVal, setLifeVal] = useState({ recipients: "", party: "", source: "first_party", evidence: "" });
  const [lifeBusy, setLifeBusy] = useState(false);
  const [signMode, setSignMode] = useState("in_person");
  const [acceptFile, setAcceptFile] = useState<File | null>(null);
  const [confirmLock, setConfirmLock] = useState(false);

  // หลักฐานตัวจริง
  const [attachments, setAttachments] = useState<any[]>([]);
  const [storeFiles, setStoreFiles] = useState(false);
  const [attKind, setAttKind] = useState("original_document");
  const [attTitle, setAttTitle] = useState("");
  const [attBusy, setAttBusy] = useState(false);
  const [signRole, setSignRole] = useState("");

  // ข้อ 6 — ค่าเริ่มต้นแสดงเฉพาะวันนี้ เพื่อไม่ให้ช้าเมื่อสัญญาสะสมเยอะ
  const [scope, setScope] = useState("today");
  const [search, setSearch] = useState("");

  // e-Original + e-Retention
  const [originals, setOriginals] = useState<any | null>(null);
  const [origFilter, setOrigFilter] = useState<"all" | "locked" | "incomplete">("all");

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
      await refreshDetail(cid);
      setSignName(""); setSignId(""); setSignMethod("typed"); setStepForm(null);
      setLifeAct(""); setSignMode("in_person"); setAcceptFile(null); setConfirmLock(false);
    } catch (e) { console.error(e); }
  };
  const refreshDetail = async (cid: string) => {
    const d = await api.getEContract(cid);
    setDetail(d);
    setChain(await api.getEContractChain(cid).catch(() => null));
    setAttachments(await api.listEContractAttachments(cid).catch(() => []));
    const ret = (d?.compliance?.steps || []).find((x: any) => x.step === "e_retention");
    setStoreFiles(!!ret?.detail?.store_files_enabled);
  };

  // อีเมลที่ส่งร่างไป — ใช้เป็นตัวเลือกตอนลงนาม เพื่อให้ตัวตนผูกกับการส่งจริง
  const deliveredEmails: string[] = (chain?.links || [])
    .filter((l: any) => l.step === "deliver")
    .flatMap((l: any) => l.payload?.recipients || []);
  const identityMismatch = deliveredEmails.length > 0 && signId.trim() !== ""
    && !deliveredEmails.map((e) => e.toLowerCase()).includes(signId.trim().toLowerCase());

  const uploadAttachment = async (f: File | null) => {
    if (!f || !detail || attBusy) return;
    setAttBusy(true);
    try {
      await api.uploadEContractAttachment(detail.cert_id, f, attKind, "", attTitle);
      setAttTitle("");
      await refreshDetail(detail.cert_id);
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setAttBusy(false); }
  };

  const toggleStoreFiles = async (on: boolean) => {
    if (!detail) return;
    try {
      await api.setEContractRetentionStorage(detail.cert_id, on);
      await refreshDetail(detail.cert_id);
    } catch (e: any) { alert(e?.message || "error"); }
  };

  const runLifecycle = async (fn: () => Promise<any>) => {
    if (!detail || lifeBusy) return;
    setLifeBusy(true);
    try {
      await fn();
      await refreshDetail(detail.cert_id);
      setLifeAct("");
      setLifeVal({ recipients: "", party: "", source: "first_party", evidence: "" });
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setLifeBusy(false); }
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
      await api.signEContract(detail.cert_id, signName.trim(), signMethod, identity, signMode, signRole);
      await refreshDetail(detail.cert_id);
      setSignName(""); setSignId(""); setSignRole(""); clearCanvas();
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setSigning(false); }
  };

  const load = useCallback(async () => {
    try { setList(await api.listEContracts(scope, search)); } catch (e) { console.error(e); }
  }, [scope, search]);
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

  const loadSeals = useCallback(async () => {
    try { setSeals(await api.listEContractSeals()); } catch (e) { console.error(e); }
  }, []);
  const loadOriginals = useCallback(async () => {
    try { setOriginals(await api.getEContractOriginals(scope, search)); } catch (e) { console.error(e); }
  }, [scope, search]);
  useEffect(() => { if (tab === "seal") loadSeals(); }, [tab, loadSeals]);
  useEffect(() => { if (tab === "original") loadOriginals(); }, [tab, loadOriginals]);
  useEffect(() => { if (tab === "list") load(); }, [tab, load]);

  const doCreateSeal = async () => {
    if (!sealForm.org_name.trim() || savingSeal) return;
    setSavingSeal(true);
    try {
      await api.createEContractSeal({ ...sealForm, image_data: sealImg });
      setSealForm({ org_name: "", org_tax_id: "", authority_note: "" });
      setSealImg("");
      await loadSeals();
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setSavingSeal(false); }
  };

  const doApplySeal = async () => {
    if (!applyCert.trim() || !applySeal || applying) return;
    setApplying(true);
    try {
      await api.applyEContractSeal(applyCert.trim(), applySeal);
      alert(`ประทับตราลงบน ${applyCert.trim()} เรียบร้อย`);
      setApplyCert("");
      await load();
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setApplying(false); }
  };

  const onSealFile = (f: File | null) => {
    if (!f) return;
    if (f.size > 280_000) { alert("ไฟล์ใหญ่เกิน 280 KB"); return; }
    const r = new FileReader();
    r.onload = () => setSealImg(String(r.result || ""));
    r.readAsDataURL(f);
  };

  const doRecordStep = async (status: "done" | "waived") => {
    if (!detail || !stepForm || savingStep) return;
    setSavingStep(true);
    try {
      await api.recordEContractStep(detail.cert_id, stepForm.step, {
        actor: stepForm.actor, ref: stepForm.ref, note: stepForm.note, status,
      });
      await refreshDetail(detail.cert_id);
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

      <div className="flex gap-1 border-b border-gray-200 flex-wrap">
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setTab(key)}
            className={cn("px-3 py-1.5 text-xs font-medium -mb-px border-b-2 transition",
              tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800")}>
            {label ?? t(`ect.tab_${key}`)}
          </button>
        ))}
      </div>

      {(tab === "list" || tab === "original") && (
        <div className="flex flex-wrap items-center gap-1.5">
          {([["today", "วันนี้"], ["7d", "7 วัน"], ["30d", "30 วัน"], ["all", "ทั้งหมด"]] as const).map(([k, label]) => (
            <button key={k} onClick={() => setScope(k)}
              className={cn("px-2.5 py-1 text-[11px] rounded-md border transition",
                scope === k ? "bg-brand-50 border-brand-200 text-brand-700 font-medium"
                            : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50")}>
              {label}
            </button>
          ))}
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="ค้นหา Cert ID หรือชื่อไฟล์"
            className="px-2.5 py-1 border border-gray-300 rounded-md text-[11px] outline-none focus:ring-2 focus:ring-brand-500 min-w-[200px]" />
          {scope !== "all" && (
            <span className="text-[10px] text-gray-400">
              แสดงเฉพาะช่วงที่เลือกเพื่อความเร็ว — การประเมิน 7 ขั้นตอนทำต่อใบรับรอง
            </span>
          )}
        </div>
      )}

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
                <button onClick={() => setIssued(null)} title="ปิด"
                  className="text-green-600 hover:text-green-800 text-base leading-none px-1">&times;</button>
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
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[10px] uppercase tracking-wide text-gray-400">{t("ect.col_cert")}</span>
                    <button onClick={() => openDetail(vResult.cert!.cert_id)}
                      className="text-xs font-mono text-brand-700 hover:text-brand-800 underline underline-offset-2 text-left break-all">
                      {vResult.cert.cert_id} →
                    </button>
                    <span className="text-[10px] text-gray-400">คลิกเพื่อดูกระบวนการลงนามและโซ่หลักฐาน</span>
                  </div>
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
                <tr><td colSpan={6} className="px-3 py-8 text-center text-gray-400">
                  {scope === "all" ? t("ect.empty") : "ไม่มีรายการในช่วงที่เลือก — ลองเปลี่ยนเป็น \"ทั้งหมด\""}
                </td></tr>
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

      {/* ── e-Seal ─────────────────────────────────────────────────── */}
      {tab === "seal" && (
        <div className="space-y-4 max-w-3xl">
          <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
            <p className="text-[11px] text-gray-600 leading-relaxed">
              <b>ตราประทับนิติบุคคลอิเล็กทรอนิกส์ (ม.9 วรรคท้าย)</b> — ใช้หลักความน่าเชื่อถือ
              ของลายมือชื่ออิเล็กทรอนิกส์โดยอนุโลม. ตราประทับแสดงความสัมพันธ์ระหว่าง
              <b> นิติบุคคล</b> กับข้อมูล ส่วนลายมือชื่อแสดงความสัมพันธ์ระหว่าง<b>บุคคล</b>กับข้อมูล
              — <b className="text-red-700">ลายเซ็นของกรรมการตีความเป็นตราประทับบริษัทไม่ได้</b>
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* ลงทะเบียนตรา */}
            <div className="bg-white rounded-lg border border-gray-200 p-3 space-y-2">
              <h3 className="text-xs font-semibold text-gray-800">ลงทะเบียนตราประทับ</h3>
              <input value={sealForm.org_name} placeholder="ชื่อนิติบุคคล (ตามที่จดทะเบียน)"
                onChange={(e) => setSealForm({ ...sealForm, org_name: e.target.value })}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
              <input value={sealForm.org_tax_id} placeholder="เลขประจำตัวผู้เสียภาษี (ถ้ามี)"
                onChange={(e) => setSealForm({ ...sealForm, org_tax_id: e.target.value })}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs font-mono outline-none focus:ring-2 focus:ring-brand-500" />
              <input value={sealForm.authority_note} placeholder="อ้างอิงระเบียบ/มติที่ให้อำนาจใช้ตรา"
                onChange={(e) => setSealForm({ ...sealForm, authority_note: e.target.value })}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
              <div>
                <label className="text-[10px] uppercase tracking-wide text-gray-400">ภาพตราประทับ (≤ 280 KB)</label>
                <input type="file" accept="image/*" onChange={(e) => onSealFile(e.target.files?.[0] ?? null)}
                  className="w-full mt-0.5 text-[11px] text-gray-500 file:mr-2 file:px-2.5 file:py-1 file:text-[10px] file:font-medium file:rounded file:border-0 file:bg-brand-600 file:text-white hover:file:bg-brand-700 file:cursor-pointer" />
                {sealImg && (
                  <div className="mt-1.5 flex items-center gap-2">
                    <img src={sealImg} alt="seal" className="h-14 border border-gray-200 rounded bg-white p-1" />
                    <button onClick={() => setSealImg("")} className="text-[10px] text-gray-400 hover:text-red-600">ลบภาพ</button>
                  </div>
                )}
              </div>
              <button onClick={doCreateSeal} disabled={!sealForm.org_name.trim() || savingSeal}
                className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
                {savingSeal ? "กำลังบันทึก…" : "ลงทะเบียนตรา"}
              </button>
            </div>

            {/* ประทับลงใบรับรอง */}
            <div className="bg-white rounded-lg border border-gray-200 p-3 space-y-2">
              <h3 className="text-xs font-semibold text-gray-800">ประทับตราลงใบรับรอง</h3>
              <select value={applyCert} onChange={(e) => setApplyCert(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                <option value="">— เลือกใบรับรอง —</option>
                {list.map((c) => (
                  <option key={c.cert_id} value={c.cert_id}>{c.cert_id} · {c.filename}</option>
                ))}
              </select>
              <select value={applySeal} onChange={(e) => setApplySeal(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                <option value="">— เลือกตราประทับ —</option>
                {seals.filter((s) => s.is_active).map((s) => (
                  <option key={s.seal_id} value={s.seal_id}>{s.org_name} ({s.seal_id})</option>
                ))}
              </select>
              <button onClick={doApplySeal} disabled={!applyCert || !applySeal || applying}
                className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
                {applying ? "กำลังประทับ…" : "ประทับตรา"}
              </button>
              <p className="text-[10px] text-gray-400">
                ระบบจะบันทึกเป็นขั้นตอนที่ 3 (e-Seal) ของใบรับรองนั้น พร้อมชื่อนิติบุคคลและรหัสตรา
              </p>
            </div>
          </div>

          {/* รายการตรา */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-3 py-2 text-[11px] font-semibold text-gray-600 bg-gray-50 border-b border-gray-200">
              ตราประทับที่ลงทะเบียนไว้ ({seals.length})
            </div>
            {seals.length === 0 ? (
              <div className="px-3 py-8 text-center text-gray-400 text-xs">ยังไม่มีตราประทับ</div>
            ) : seals.map((s) => (
              <div key={s.seal_id} className="flex items-center gap-3 px-3 py-2 border-b border-gray-100 last:border-0">
                {s.image_data
                  ? <img src={s.image_data} alt="" className="h-10 w-10 object-contain border border-gray-200 rounded bg-white p-0.5 flex-shrink-0" />
                  : <div className="h-10 w-10 rounded border border-dashed border-gray-300 flex items-center justify-center text-[9px] text-gray-300 flex-shrink-0">ไม่มีภาพ</div>}
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-xs font-medium text-gray-800">{s.org_name}</span>
                    <span className="text-[10px] font-mono text-gray-400">{s.seal_id}</span>
                    {!s.is_active && <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-500 rounded">เลิกใช้</span>}
                  </div>
                  {s.org_tax_id && <div className="text-[10px] text-gray-500 font-mono">เลขผู้เสียภาษี {s.org_tax_id}</div>}
                  {s.authority_note && <div className="text-[10px] text-gray-400">{s.authority_note}</div>}
                </div>
                {s.is_active && (
                  <button onClick={async () => {
                    if (!confirm(`เลิกใช้ตรา "${s.org_name}"? สัญญาที่ประทับไปแล้วยังอ้างอิงได้ตามเดิม`)) return;
                    try { await api.deactivateEContractSeal(s.seal_id); await loadSeals(); }
                    catch (e: any) { alert(e?.message || "error"); }
                  }} className="text-[10px] text-gray-400 hover:text-red-600 flex-shrink-0">เลิกใช้</button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── e-Original + e-Retention ───────────────────────────────── */}
      {tab === "original" && (
        <div className="space-y-4">
          {!originals ? (
            <p className="text-xs text-gray-400 py-8 text-center">กำลังโหลด…</p>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {[
                  [scope === "all" ? "ใบรับรองทั้งหมด" : "ในช่วงที่เลือก",
                   `${originals.total}${originals.total_all && originals.total !== originals.total_all ? ` / ${originals.total_all}` : ""}`,
                   "text-gray-800"],
                  ["เป็นต้นฉบับแล้ว (ม.10)", originals.locked_originals, "text-green-700"],
                  ["เก็บรักษายังไม่ครบ (ม.12)", originals.retention_incomplete, "text-amber-700"],
                  ["โหมดจัดเก็บ", originals.storage_mode === "hash_only" ? "hash-only" : originals.storage_mode, "text-gray-800"],
                ].map(([label, val, cls]) => (
                  <div key={String(label)} className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                    <div className="text-[10px] uppercase tracking-wide text-gray-400">{label}</div>
                    <div className={cn("text-lg font-bold", cls)}>{val}</div>
                  </div>
                ))}
              </div>

              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="text-[11px] text-amber-800 leading-relaxed">⚠ {originals.storage_note_th}</p>
              </div>

              <div className="flex gap-1">
                {([["all", "ทั้งหมด"], ["locked", "เป็นต้นฉบับแล้ว"], ["incomplete", "เก็บรักษายังไม่ครบ"]] as const).map(([k, label]) => (
                  <button key={k} onClick={() => setOrigFilter(k)}
                    className={cn("px-2.5 py-1 text-[11px] rounded-md border transition",
                      origFilter === k ? "bg-brand-50 border-brand-200 text-brand-700 font-medium"
                                       : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50")}>
                    {label}
                  </button>
                ))}
              </div>

              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 text-gray-500 text-[10px] uppercase">
                    <tr>
                      <th className="px-3 py-2 text-left">ใบรับรอง</th>
                      <th className="px-3 py-2 text-left">ต้นฉบับ (ม.10)</th>
                      <th className="px-3 py-2 text-left">เก็บรักษา (ม.12)</th>
                      <th className="px-3 py-2 text-left">เก็บถึง</th>
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {(originals.items as any[])
                      .filter((it) => origFilter === "all"
                        || (origFilter === "locked" && it.original.status === "done")
                        || (origFilter === "incomplete" && ["partial", "pending"].includes(it.retention.status)))
                      .map((it) => {
                        const os = STEP_STYLE[it.original.status] || STEP_STYLE.pending;
                        const rs = STEP_STYLE[it.retention.status] || STEP_STYLE.pending;
                        return (
                          <tr key={it.cert_id} className="border-t border-gray-100 hover:bg-gray-50 align-top">
                            <td className="px-3 py-2">
                              <div className="font-mono font-semibold text-brand-700">{it.cert_id}</div>
                              <div className="text-gray-600">{it.filename}</div>
                              <div className="text-[10px] text-gray-400">
                                {it.profile_name_th}{it.doc_format ? ` · ${it.doc_format}` : ""}
                                {it.signature_count ? ` · ลงนาม ${it.signature_count} ราย` : ""}
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              <span className={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px]", os.cls)}>
                                {os.icon} {os.label}
                              </span>
                              <div className="text-[10px] text-gray-500 mt-0.5">{it.original.summary_th}</div>
                            </td>
                            <td className="px-3 py-2">
                              <span className={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px]", rs.cls)}>
                                {rs.icon} {rs.label}
                              </span>
                              <div className="text-[10px] text-gray-500 mt-0.5">{it.retention.summary_th}</div>
                              {it.retention.missing?.length > 0 && (
                                <div className="text-[10px] text-amber-700 mt-0.5">ขาด: {it.retention.missing.join(", ")}</div>
                              )}
                            </td>
                            <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                              {it.retention.keep_until ? it.retention.keep_until.slice(0, 10) : "—"}
                              {it.retention.period_years ? <div className="text-[10px] text-gray-400">{it.retention.period_years} ปี</div> : null}
                            </td>
                            <td className="px-3 py-2 text-right whitespace-nowrap">
                              <button onClick={() => openDetail(it.cert_id)} className="text-[10px] text-brand-600 hover:text-brand-700 mr-2">
                                {t("ect.view")}
                              </button>
                              <a href={api.evidenceBundleUrl(it.cert_id)} className="text-[10px] text-gray-400 hover:text-gray-600">.zip</a>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </>
          )}
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

      {/* ยืนยันก่อนตรึงต้นฉบับ — ย้อนกลับไม่ได้ */}
      {confirmLock && detail && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60] p-6"
          onClick={() => setConfirmLock(false)}>
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-gray-900 mb-1">ยืนยันการตรึงต้นฉบับ (ม.10)</h3>
            <p className="text-[11px] text-gray-500 font-mono mb-3">{detail.cert_id}</p>

            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 mb-3">
              <p className="text-[11px] font-semibold text-red-800 mb-1">หลังตรึงแล้วจะทำสิ่งเหล่านี้ไม่ได้อีก</p>
              <ul className="text-[11px] text-red-700 space-y-0.5 list-disc list-inside">
                <li>ลงลายมือชื่อเพิ่ม</li>
                <li>ประทับตรานิติบุคคล (e-Seal)</li>
                <li>บันทึกการส่งร่าง หรือคำสนอง</li>
              </ul>
              <p className="text-[10px] text-red-600 mt-1.5">
                ม.10 กำหนดว่าต้นฉบับต้องไม่มีการเปลี่ยนแปลงนับแต่สร้างเสร็จสมบูรณ์ —
                <b> การตรึงย้อนกลับไม่ได้</b> ถ้าต้องแก้ไขภายหลังต้องทำเป็นฉบับแก้ไขที่อ้างถึงฉบับนี้
              </p>
            </div>

            <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 mb-3">
              <p className="text-[11px] text-gray-600 mb-1">สถานะปัจจุบัน</p>
              <p className="text-[11px] text-gray-800">
                ลงนามแล้ว <b>{(detail.signatures || []).length}</b> ราย
                {(detail.compliance?.steps || []).find((x: any) => x.step === "e_seal")?.status === "done"
                  ? " · ประทับตราแล้ว" : " · ยังไม่ได้ประทับตรา"}
              </p>
              <p className="text-[10px] text-gray-500 mt-1">
                ยังทำได้หลังตรึง: ชำระอากรแสตมป์ · แนบหลักฐาน · บันทึกการเก็บรักษา · สิ่งพิมพ์ออก
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => { setConfirmLock(false); runLifecycle(() => api.lockEContractOriginal(detail.cert_id)); }}
                disabled={lifeBusy}
                className="px-4 py-1.5 bg-red-600 text-white text-xs font-medium rounded-md hover:bg-red-700 disabled:opacity-50">
                🔒 ยืนยันตรึงต้นฉบับ
              </button>
              <button onClick={() => setConfirmLock(false)}
                className="px-4 py-1.5 border border-gray-300 text-gray-600 text-xs rounded-md hover:bg-gray-50">
                ยกเลิก
              </button>
            </div>
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

            {/* ── โซ่หลักฐาน (ม.11) ──────────────────────────────────── */}
            {chain && (() => {
              const v = chain.verification || {};
              const locked = !!v.locked;
              return (
                <div className="mb-4">
                  <div className="flex items-baseline justify-between mb-1">
                    <h3 className="text-xs font-semibold text-gray-800">โซ่หลักฐาน (ลำดับเหตุการณ์)</h3>
                    <span className="text-[10px] font-mono text-gray-400">{chain.version}</span>
                  </div>
                  <div className={cn("rounded-md border px-2.5 py-1.5 mb-2 text-[11px]",
                    v.valid ? "bg-green-50 border-green-200 text-green-800"
                            : "bg-red-50 border-red-200 text-red-700")}>
                    {v.valid ? "✓" : "✕"} {v.reason_th}
                    {v.head_hash && (
                      <div className="text-[10px] font-mono opacity-70 mt-0.5">
                        หัวโซ่ {String(v.head_hash).slice(0, 32)}…
                      </div>
                    )}
                  </div>

                  <div className="border border-gray-200 rounded-md overflow-hidden">
                    {(chain.links || []).map((l: any) => (
                      <div key={l.seq} className={cn("flex items-start gap-2 px-2.5 py-1.5 border-b border-gray-100 last:border-0",
                        l.step === "original" && "bg-brand-50/40")}>
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-white border border-gray-300 text-gray-600 flex items-center justify-center text-[10px] font-bold mt-0.5">
                          {l.seq}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline gap-1.5 flex-wrap">
                            <span className="text-[11px] font-medium text-gray-800">
                              {l.step_th}
                              {l.step === "attachment" && (
                                <span className="text-gray-500 font-normal">
                                  {" — "}{l.payload?.title || l.payload?.filename}
                                  {l.payload?.kind_th ? ` (${l.payload.kind_th})` : ""}
                                </span>
                              )}
                              {l.step === "sign" && l.payload?.signer_name && (
                                <span className="text-gray-500 font-normal">
                                  {" — "}{l.payload.signer_name}
                                  {l.payload?.signer_role ? ` · ${l.payload.signer_role}` : ""}
                                </span>
                              )}
                              {l.step === "seal" && l.payload?.org_name && (
                                <span className="text-gray-500 font-normal">{" — "}{l.payload.org_name}</span>
                              )}
                              {l.step === "deliver" && l.payload?.recipient_count && (
                                <span className="text-gray-500 font-normal">
                                  {" — "}{l.payload.recipient_count} ราย
                                </span>
                              )}
                              {l.step === "offer_acceptance" && l.payload?.party && (
                                <span className="text-gray-500 font-normal">{" — "}{l.payload.party}</span>
                              )}
                            </span>
                            {l.sections?.length > 0 && (
                              <span className="text-[9px] text-gray-400">ม.{l.sections.join(", ม.")}</span>
                            )}
                            {l.step === "original" && (
                              <span className="text-[9px] px-1 py-0.5 bg-brand-100 text-brand-700 rounded">จุดตรึง</span>
                            )}
                            {l.post_lock && (
                              <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-500 rounded">ผนวกหลังตรึง</span>
                            )}
                            <span className="ml-auto text-[9px] text-gray-400">{fmt(l.recorded_at)}</span>
                          </div>
                          <div className="text-[10px] font-mono text-gray-400 truncate">
                            {String(l.chain_hash).slice(0, 24)}…
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* การกระทำตามวงจร */}
                  {!locked ? (
                    <div className="mt-2 space-y-1.5">
                      <div className="flex flex-wrap gap-1.5">
                        <button onClick={() => setLifeAct(lifeAct === "deliver" ? "" : "deliver")}
                          className="text-[10px] px-2 py-1 border border-gray-300 text-gray-600 rounded hover:bg-gray-50">
                          + ส่งร่างให้คู่สัญญา
                        </button>
                        <button onClick={() => setLifeAct(lifeAct === "acceptance" ? "" : "acceptance")}
                          className="text-[10px] px-2 py-1 border border-gray-300 text-gray-600 rounded hover:bg-gray-50">
                          + คำสนอง (ม.13)
                        </button>
                        <button onClick={() => runLifecycle(() => api.lockEContractOriginal(detail.cert_id))}
                          disabled={lifeBusy}
                          className="text-[10px] px-2 py-1 bg-brand-600 text-white rounded hover:bg-brand-700 disabled:opacity-50">
                          🔒 ตรึงต้นฉบับ (ม.10)
                        </button>
                      </div>

                      {lifeAct === "deliver" && (
                        <div className="bg-gray-50 border border-gray-200 rounded-md p-2 space-y-1.5">
                          <textarea value={lifeVal.recipients} rows={2}
                            placeholder="อีเมลผู้รับ คั่นด้วย , หรือขึ้นบรรทัดใหม่"
                            onChange={(e) => setLifeVal({ ...lifeVal, recipients: e.target.value })}
                            className="w-full px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500" />
                          <p className="text-[10px] text-gray-500">
                            บันทึกว่า <b>ส่งไปยังที่อยู่ที่อ้างว่าเป็นของเขา</b> — ยังไม่ใช่การยืนยันตัวตน
                            การพิสูจน์เกิดตอนคู่สัญญากรอก OTP ในขั้นลงนาม
                          </p>
                          <button onClick={() => runLifecycle(() => api.deliverEContract(detail.cert_id, lifeVal.recipients))}
                            disabled={!lifeVal.recipients.trim() || lifeBusy}
                            className="px-3 py-1 bg-brand-600 text-white text-[11px] rounded hover:bg-brand-700 disabled:opacity-50">
                            บันทึกการส่ง
                          </button>
                        </div>
                      )}

                      {lifeAct === "acceptance" && (
                        <div className="bg-gray-50 border border-gray-200 rounded-md p-2 space-y-1.5">
                          <input value={lifeVal.party} placeholder="คู่สัญญาผู้ตอบรับ"
                            onChange={(e) => setLifeVal({ ...lifeVal, party: e.target.value })}
                            className="w-full px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500" />
                          <select value={lifeVal.source}
                            onChange={(e) => setLifeVal({ ...lifeVal, source: e.target.value })}
                            className="w-full px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500">
                            <option value="first_party">ระบบบันทึกเอง — คู่สัญญากดยอมรับในระบบ (น้ำหนักสูง)</option>
                            <option value="imported">นำเข้าจากภายนอก เช่น อีเมลตอบกลับ/แชท (น้ำหนักขึ้นกับที่มา)</option>
                          </select>
                          <input value={lifeVal.evidence} placeholder="อ้างอิงหลักฐาน (ข้อความ/เลขที่/ที่มา)"
                            onChange={(e) => setLifeVal({ ...lifeVal, evidence: e.target.value })}
                            className="w-full px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500" />
                          <div>
                            <label className="text-[10px] uppercase tracking-wide text-gray-400">แนบไฟล์หลักฐานคำสนอง (ถ้ามี)</label>
                            <input type="file" onChange={(e) => setAcceptFile(e.target.files?.[0] ?? null)}
                              className="w-full mt-0.5 text-[11px] text-gray-500 file:mr-2 file:px-2.5 file:py-1 file:text-[10px] file:font-medium file:rounded file:border-0 file:bg-brand-600 file:text-white hover:file:bg-brand-700 file:cursor-pointer" />
                            {acceptFile && (
                              <p className="text-[10px] text-gray-500 mt-0.5">
                                {acceptFile.name} · ระบบจะบันทึกลายนิ้วมือเสมอ
                                {storeFiles ? " และเก็บตัวไฟล์ไว้ (โหมดเก็บไฟล์เปิด)" : " แต่ไม่เก็บตัวไฟล์ (โหมดเก็บไฟล์ปิด)"}
                              </p>
                            )}
                          </div>
                          <button onClick={() => runLifecycle(async () => { await api.acceptEContract(detail.cert_id, lifeVal.party, lifeVal.source, lifeVal.evidence, acceptFile); setAcceptFile(null); })}
                            disabled={!lifeVal.party.trim() || lifeBusy}
                            className="px-3 py-1 bg-brand-600 text-white text-[11px] rounded hover:bg-brand-700 disabled:opacity-50">
                            บันทึกคำสนอง
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="mt-2 text-[10px] text-gray-500 bg-gray-50 border border-gray-200 rounded px-2 py-1.5">
                      🔒 ตรึงต้นฉบับแล้ว — ลงนามหรือประทับตราเพิ่มไม่ได้อีก (ม.10)
                      ขั้นตอนที่ผนวกได้ต่อจากนี้: อากรแสตมป์ · การเก็บรักษา · สิ่งพิมพ์ออก
                    </p>
                  )}
                </div>
              );
            })()}

            {/* ── หลักฐานตัวจริง + โหมดเก็บไฟล์ ─────────────────────── */}
            <div className="mb-4">
              <h3 className="text-xs font-semibold text-gray-800 mb-1">หลักฐานตัวจริง</h3>
              <label className={cn("flex items-start gap-2 rounded-md border px-2.5 py-2 cursor-pointer transition",
                storeFiles ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200")}>
                <input type="checkbox" checked={storeFiles} className="mt-0.5"
                  disabled={chain?.verification?.locked && storeFiles}
                  onChange={(e) => toggleStoreFiles(e.target.checked)} />
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-gray-800">เก็บตัวไฟล์จริงไว้ในเครื่องนี้</p>
                  <p className="text-[10px] text-gray-600 leading-relaxed mt-0.5">
                    {storeFiles
                      ? "เปิดอยู่ — ไฟล์ที่แนบจะถูกเก็บไว้ ดาวน์โหลด/พิมพ์ย้อนหลังได้ ตรงเงื่อนไข ม.10(2) ที่ต้องแสดงข้อความในภายหลังได้"
                      : "ปิดอยู่ — เก็บเฉพาะลายนิ้วมือ พิสูจน์ได้ว่าไฟล์ไม่ถูกแก้ แต่เอาเอกสารมาแสดงย้อนหลังไม่ได้"}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-0.5">
                    ไฟล์เก็บในเครื่องนี้เท่านั้น ไม่ส่งออกไปที่ใด · ปิดสวิตช์ไม่ลบไฟล์ที่เก็บไปแล้ว
                  </p>
                  {chain?.verification?.locked && storeFiles && (
                    <p className="text-[10px] text-gray-500 mt-0.5">
                      🔒 ตรึงต้นฉบับแล้ว — ปิดไม่ได้ เพราะจะลดระดับการเก็บรักษาของสัญญาที่สมบูรณ์แล้ว (มาตรา 12)
                    </p>
                  )}
                </div>
              </label>

              {chain?.verification?.locked && (
                <p className="text-[10px] text-gray-500 mt-1.5">
                  หลังตรึงต้นฉบับ แนบได้เฉพาะ <b>เอกสารตัวจริงที่ตรงกับใบรับรอง</b> ·
                  สิ่งพิมพ์ออก · หลักฐานอื่น — ระบบจะตรวจว่า SHA-256 ตรงกับที่ออกใบรับรองไว้
                </p>
              )}
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <select value={attKind} onChange={(e) => setAttKind(e.target.value)}
                  className="px-2 py-1 border border-gray-300 rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="original_document">เอกสาร/สัญญาตัวจริง</option>
                  <option value="acceptance_evidence" disabled={!!chain?.verification?.locked}>
                    หลักฐานคำสนอง{chain?.verification?.locked ? " — ตรึงแล้วแนบไม่ได้" : ""}
                  </option>
                  <option value="print_out">สิ่งพิมพ์ออก</option>
                  <option value="other">หลักฐานอื่น</option>
                </select>
                {attKind === "other" && !attTitle.trim() && (
                  <span className="text-[10px] text-amber-700 w-full">
                    หลักฐานอื่นต้องระบุชื่อเอกสารก่อน จึงจะเลือกไฟล์ได้ — เพื่อให้รู้ว่าเอกสารนั้นคืออะไร
                  </span>
                )}
                <input value={attTitle} onChange={(e) => setAttTitle(e.target.value)}
                  placeholder={attKind === "other" ? "ชื่อเอกสาร (จำเป็น)" : "ชื่อเอกสาร (ถ้ามี)"}
                  className={cn("px-2 py-1 border rounded text-[11px] outline-none focus:ring-2 focus:ring-brand-500 flex-1 min-w-[160px]",
                    attKind === "other" && !attTitle.trim() ? "border-amber-300 bg-amber-50" : "border-gray-300")} />
                <input type="file" disabled={attBusy || (attKind === "other" && !attTitle.trim())}
                  onChange={(e) => { uploadAttachment(e.target.files?.[0] ?? null); e.currentTarget.value = ""; }}
                  className="text-[11px] text-gray-500 file:mr-2 file:px-2.5 file:py-1 file:text-[10px] file:font-medium file:rounded file:border-0 file:bg-brand-600 file:text-white hover:file:bg-brand-700 file:cursor-pointer" />
              </div>

              {attachments.length > 0 && (
                <div className="mt-1.5 border border-gray-200 rounded-md overflow-hidden">
                  {attachments.map((a) => (
                    <div key={a.id} className="flex items-center gap-2 px-2.5 py-1.5 border-b border-gray-100 last:border-0">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-1.5 flex-wrap">
                          <span className="text-[11px] font-medium text-gray-800">{a.title || a.filename}</span>
                          {a.title && <span className="text-[10px] text-gray-400">{a.filename}</span>}
                          <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-600 rounded">{a.kind_th}</span>
                          {a.stored
                            ? <span className="text-[9px] px-1 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded">เก็บไฟล์แล้ว</span>
                            : <span className="text-[9px] px-1 py-0.5 bg-gray-50 text-gray-500 border border-gray-200 rounded">เฉพาะลายนิ้วมือ</span>}
                        </div>
                        <div className="text-[10px] font-mono text-gray-400 truncate">
                          SHA-256 {String(a.sha256).slice(0, 32)}…
                        </div>
                      </div>
                      {a.stored && (
                        <a href={api.attachmentDownloadUrl(detail.cert_id, a.id)}
                          className="text-[10px] text-brand-600 hover:text-brand-700 flex-shrink-0">⬇ ดาวน์โหลด</a>
                      )}
                    </div>
                  ))}
                </div>
              )}
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
                                  {s.status === "done" ? (
                                    <div className="mt-1 rounded border border-green-200 bg-green-50 px-2 py-1">
                                      <p className="text-[11px] font-medium text-green-800">
                                        ✓ ชำระอากรแสตมป์แล้ว
                                      </p>
                                      {s.detail.receipt_ref && (
                                        <p className="text-[10px] text-green-700 mt-0.5">
                                          รหัสรับรอง <span className="font-mono">{s.detail.receipt_ref}</span>
                                          {s.detail.paid_at ? ` · ${fmt(s.detail.paid_at)}` : ""}
                                        </p>
                                      )}
                                    </div>
                                  ) : s.status === "waived" ? (
                                    <p className="text-[10px] text-gray-500 mt-1">
                                      – ระบุว่าไม่เข้าข่ายต้องเสียอากร
                                    </p>
                                  ) : null}
                                </div>
                              )}

                              {canRecord && !editing && (
                                s.step === "e_seal" ? (
                                  <div className="mt-1">
                                    <button
                                      onClick={() => {
                                        setApplyCert(detail.cert_id);
                                        setTab("seal");
                                        setDetail(null);
                                      }}
                                      className="text-[10px] px-2 py-0.5 bg-brand-600 text-white rounded hover:bg-brand-700">
                                      ไปที่ e-Seal เพื่อประทับตราใบรับรองนี้ →
                                    </button>
                                    <button
                                      onClick={() => setStepForm({ step: s.step, actor: "", ref: "", note: "" })}
                                      className="ml-1.5 text-[10px] px-2 py-0.5 border border-gray-300 text-gray-500 rounded hover:bg-gray-50">
                                      บันทึกด้วยมือ
                                    </button>
                                  </div>
                                ) : (
                                  <button
                                    onClick={() => setStepForm({ step: s.step, actor: "", ref: "", note: "" })}
                                    className="mt-1 text-[10px] px-2 py-0.5 border border-brand-200 text-brand-700 rounded hover:bg-brand-50">
                                    บันทึกขั้นตอนนี้
                                  </button>
                                )
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
                      {sg.signer_role && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{sg.signer_role}</span>
                      )}
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

            {/* sign form — ซ่อนเมื่อตรึงต้นฉบับแล้ว เพราะ backend จะปฏิเสธอยู่ดี */}
            {chain?.verification?.locked ? (
              <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
                <p className="text-[11px] text-gray-600">
                  🔒 ตรึงต้นฉบับแล้ว — ลงลายมือชื่อเพิ่มไม่ได้ (มาตรา 10)
                </p>
              </div>
            ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input value={signName} onChange={(e) => setSignName(e.target.value)} placeholder={t("ect.signer_name")}
                  className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
                <select value={signMethod} onChange={(e) => setSignMethod(e.target.value)}
                  className="px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="typed">{t("ect.method_typed")}</option>
                  <option value="drawn">{t("ect.method_drawn")}</option>
                  <option value="otp" disabled>ยืนยันด้วย OTP/อีเมล — ยังไม่เปิดให้บริการ</option>
                </select>
              </div>
              {/* ฐานะที่ลงนาม — พิสูจน์ว่าใครผูกพันฝ่ายใด และใครเป็นเพียงพยาน */}
              <div>
                <input value={signRole} onChange={(e) => setSignRole(e.target.value)}
                  list="signer-roles" placeholder="ฐานะในสัญญา เช่น ผู้ว่าจ้าง / ผู้รับจ้าง / พยาน"
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
                <datalist id="signer-roles">
                  {["ผู้ว่าจ้าง", "ตัวแทนผู้ว่าจ้าง", "ผู้รับจ้าง", "ตัวแทนผู้รับจ้าง",
                    "ผู้ให้เช่า", "ผู้เช่า", "ผู้ให้กู้", "ผู้กู้", "ผู้ค้ำประกัน",
                    "ผู้มอบอำนาจ", "ผู้รับมอบอำนาจ", "พยาน"].map((r) => <option key={r} value={r} />)}
                </datalist>
              </div>
              {/* ลงนามต่อหน้า vs ระยะไกล มีน้ำหนักพยานต่างกัน จึงต้องบันทึกแยก */}
              <div>
                <select value={signMode} onChange={(e) => setSignMode(e.target.value)}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="in_person">ลงนามต่อหน้า — บนเครื่องของหน่วยงาน</option>
                  <option value="remote" disabled>ลงนามระยะไกล — ยังไม่เปิดให้บริการ</option>
                </select>
                {signMode === "in_person" && (
                  <p className="text-[10px] text-amber-700 mt-1">
                    ⚠ IP ที่บันทึกจะเป็นของหน่วยงาน ไม่ได้พิสูจน์ตัวคู่สัญญา —
                    ระบบจะบันทึกผู้ใช้ที่ควบคุมเครื่องขณะลงนามไว้ด้วย
                  </p>
                )}
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
                <div>
                  {/* อีเมลลงนามควรเป็นอีเมลเดียวกับที่ส่งร่างไป มิฉะนั้นโซ่ตัวตนขาด */}
                  {deliveredEmails.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1 mb-1">
                      <span className="text-[10px] text-gray-400">อีเมลที่ส่งร่างไป:</span>
                      {deliveredEmails.map((em) => (
                        <button key={em} onClick={() => setSignId(em)}
                          className={cn("text-[10px] px-1.5 py-0.5 rounded border transition",
                            signId.trim().toLowerCase() === em.toLowerCase()
                              ? "bg-brand-50 border-brand-200 text-brand-700 font-medium"
                              : "bg-white border-gray-200 text-gray-500 hover:bg-gray-50")}>
                          {em}
                        </button>
                      ))}
                    </div>
                  )}
                  <input value={signId} onChange={(e) => setSignId(e.target.value)}
                    list="delivered-emails" placeholder={t("ect.identity")}
                    className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
                  <datalist id="delivered-emails">
                    {deliveredEmails.map((em) => <option key={em} value={em} />)}
                  </datalist>
                  {identityMismatch && (
                    <p className="text-[10px] text-amber-700 mt-1">
                      ⚠ อีเมลนี้ไม่ตรงกับที่ส่งร่างไป — โซ่การระบุตัวตนจะขาด
                      ระบบไม่ห้าม แต่จะบันทึกไว้ในหลักฐานว่าไม่ตรง
                    </p>
                  )}
                  {deliveredEmails.length === 0 && (
                    <p className="text-[10px] text-gray-400 mt-1">
                      ยังไม่ได้บันทึกการส่งร่าง — บันทึก &quot;ส่งร่างให้คู่สัญญา&quot; ก่อน
                      จะได้ยืนยันได้ว่าลงนามด้วยอีเมลเดียวกับที่ส่งร่างไป
                    </p>
                  )}
                </div>
              )}
              <button onClick={doSign} disabled={!signName.trim() || signing}
                className="px-4 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-md hover:bg-brand-700 disabled:opacity-50">
                {signing ? t("ect.signing") : t("ect.sign_btn")}
              </button>
            </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
