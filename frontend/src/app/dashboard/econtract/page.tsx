"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn } from "@/lib/utils";

type Cert = {
  cert_id: string; filename: string; size_bytes: number; sha256: string;
  ntp_time: string | null; ntp_server_name: string; signature: string;
  signer: string; note: string; created_at: string | null;
};

const ENDPOINTS = [
  ["POST", "/api/econtract/certify", "อัปโหลดไฟล์ → ออกใบรับรอง (hash + เวลา NTP + ลายเซ็นระบบ)"],
  ["POST", "/api/econtract/{id}/sign", "ลงนามอิเล็กทรอนิกส์ (signer_name, method, identity_ref)"],
  ["POST", "/api/econtract/verify", "ตรวจสอบ (ไฟล์เดิม หรือ cert_id) → valid/invalid"],
  ["GET", "/api/econtract/{id}", "รายละเอียดใบรับรอง + ลายเซ็นทั้งหมด"],
  ["GET", "/api/econtract/{id}/evidence", "ชุดหลักฐาน .zip (cert + signatures + audit + manifest)"],
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

  // detail + sign
  const [detail, setDetail] = useState<any | null>(null);
  const [signName, setSignName] = useState("");
  const [signMethod, setSignMethod] = useState("typed");
  const [signId, setSignId] = useState("");
  const [signing, setSigning] = useState(false);

  const openDetail = async (cid: string) => {
    try { setDetail(await api.getEContract(cid)); setSignName(""); setSignId(""); setSignMethod("typed"); }
    catch (e) { console.error(e); }
  };
  const doSign = async () => {
    if (!detail || !signName.trim() || signing) return;
    setSigning(true);
    try {
      await api.signEContract(detail.cert_id, signName.trim(), signMethod, signId);
      setDetail(await api.getEContract(detail.cert_id));
      setSignName(""); setSignId("");
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setSigning(false); }
  };

  const load = useCallback(async () => {
    try { setList(await api.listEContracts()); } catch (e) { console.error(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const doIssue = async () => {
    if (!file || issuing) return;
    setIssuing(true); setIssued(null);
    try {
      const c = await api.certifyEContract(file, signer, note);
      setIssued(c); setFile(null); setSigner(""); setNote("");
      await load();
    } catch (e: any) { alert(e?.message || "error"); }
    finally { setIssuing(false); }
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

          <button onClick={doIssue} disabled={!file || issuing}
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
          <label className="block border-2 border-dashed border-gray-300 bg-gray-50 rounded-lg p-6 text-center cursor-pointer">
            <input type="file" className="hidden"
              onChange={(e) => { setVfile(e.target.files?.[0] ?? null); e.currentTarget.value = ""; }} />
            <p className="text-xs font-medium text-gray-700">{vfile ? vfile.name : t("ect.drop")}</p>
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
                <th className="px-3 py-2 text-left">{t("ect.col_time")}</th>
                <th className="px-3 py-2 text-left">{t("ect.col_hash")}</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {list.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-8 text-center text-gray-400">{t("ect.empty")}</td></tr>
              )}
              {list.map((c) => (
                <tr key={c.cert_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono font-semibold text-brand-700">{c.cert_id}</td>
                  <td className="px-3 py-2 text-gray-700">{c.filename}</td>
                  <td className="px-3 py-2 text-gray-600">{fmt(c.ntp_time)}</td>
                  <td className="px-3 py-2 font-mono text-gray-500">{short(c.sha256)}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button onClick={() => openDetail(c.cert_id)} className="text-[10px] text-brand-600 hover:text-brand-700 mr-2">{t("ect.view")}</button>
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
              <Field label={t("ect.col_file")} value={detail.filename} />
              <Field label={t("ect.field_time")} value={`${fmt(detail.ntp_time)} · ${detail.ntp_server_name || "NTP"}`} />
              <Field label={t("ect.field_hash")} value={detail.sha256} mono />
              <Field label={t("ect.field_sig")} value={short(detail.signature)} mono />
            </div>

            {/* signatures */}
            <h3 className="text-xs font-semibold text-gray-800 mb-2">{t("ect.sign_title")}</h3>
            <div className="border border-gray-200 rounded-md overflow-hidden mb-3">
              {(detail.signatures || []).length === 0 ? (
                <div className="px-3 py-4 text-center text-gray-400 text-xs">{t("ect.sig_none")}</div>
              ) : (
                (detail.signatures || []).map((sg: any) => (
                  <div key={sg.id} className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 last:border-0 text-xs">
                    <span className="text-green-600">✓</span>
                    <span className="font-medium text-gray-800">{sg.signer_name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-brand-50 text-brand-700 rounded">{t(`ect.method_${sg.method}`)}</span>
                    <span className="ml-auto text-[10px] text-gray-400">{t("ect.sig_at")} {fmt(sg.signed_at)}</span>
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
              <input value={signId} onChange={(e) => setSignId(e.target.value)} placeholder={t("ect.identity")}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs outline-none focus:ring-2 focus:ring-brand-500" />
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
