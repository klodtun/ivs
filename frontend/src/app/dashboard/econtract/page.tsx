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

export default function EContractPage() {
  const { t } = useLang();
  const [tab, setTab] = useState<"issue" | "verify" | "list">("issue");
  const [list, setList] = useState<Cert[]>([]);

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
        {(["issue", "verify", "list"] as const).map((k) => (
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
                  <td className="px-3 py-2 text-right">
                    <a href={api.downloadEContractUrl(c.cert_id)} className="text-[10px] text-brand-600 hover:text-brand-700">.json</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
