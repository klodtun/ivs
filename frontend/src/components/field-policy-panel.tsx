"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

type Action = "block" | "mask" | "allow";

type FieldRule = {
  id: number;
  field_name: string;
  category: string;
  action: Action;
  confirmed: boolean;
  origin: string;
  note: string;
};

type Summary = {
  total: number;
  pending_review: number;
  blocked: number;
  masked: number;
  allowed: number;
  fields: FieldRule[];
};

const SAMPLE = JSON.stringify(
  { seat: "A-12", guest_name: "สมชาย ใจดี", email: "somchai@example.com", amount: 500 },
  null,
  1
);

/**
 * Field rules for one app: what the PII scan found, what each field's rule is,
 * and what a response actually looks like once the rules run.
 *
 * The preview is the point of the panel. A list of field names tells a reviewer
 * very little; seeing the response come back with the national ID gone and the
 * email replaced tells them exactly what opening this app's API would disclose.
 */
export function FieldPolicyPanel({ appId, appName }: { appId: number; appName: string }) {
  const { t } = useLang();
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyField, setBusyField] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [sample, setSample] = useState(SAMPLE);
  const [preview, setPreview] = useState<{ result: any; applied: any[] } | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.getFieldPolicy(appId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [appId]);

  useEffect(() => { load(); }, [load]);

  const derive = async () => {
    setLoading(true);
    setError("");
    try {
      await api.deriveFieldPolicy(appId);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const setAction = async (field: string, action: Action) => {
    setBusyField(field);
    setError("");
    try {
      await api.confirmFieldPolicy(appId, field, action);
      await load();
      if (showPreview) await runPreview();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusyField(null);
    }
  };

  const runPreview = async () => {
    setError("");
    try {
      const parsed = JSON.parse(sample);
      setPreview(await api.previewFieldPolicy(appId, parsed));
      setShowPreview(true);
    } catch (e: any) {
      setError(e instanceof SyntaxError ? t("fp.bad_json") : e.message);
    }
  };

  const actionStyle: Record<Action, string> = {
    block: "bg-red-100 text-red-700 border-red-200",
    mask: "bg-amber-100 text-amber-700 border-amber-200",
    allow: "bg-gray-100 text-gray-600 border-gray-200",
  };

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/60">
      <div className="flex items-center justify-between gap-2 mb-1">
        <p className="text-[11px] font-semibold text-gray-800 flex items-center gap-1.5">
          {t("fp.title")}
        </p>
        <button
          type="button"
          onClick={derive}
          disabled={loading}
          className="text-[10px] px-2 py-0.5 rounded-md bg-brand-600 text-white hover:bg-brand-700 transition disabled:opacity-50"
        >
          {loading ? t("fp.working") : t("fp.derive")}
        </button>
      </div>
      <p className="text-[10px] text-gray-500 mb-2 leading-snug">{t("fp.subtitle")}</p>

      {error && (
        <p className="text-[10px] text-red-600 bg-red-50 border border-red-200 rounded p-1.5 mb-2">{error}</p>
      )}

      {data && data.total > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2 text-[10px]">
          <span className="px-1.5 py-0.5 rounded bg-white border border-gray-200 text-gray-600">
            {t("fp.count_total")}: <b>{data.total}</b>
          </span>
          {data.pending_review > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-700 font-medium">
              {t("fp.count_pending")}: <b>{data.pending_review}</b>
            </span>
          )}
          <span className="px-1.5 py-0.5 rounded bg-red-50 border border-red-200 text-red-700">
            {t("fp.action_block")}: <b>{data.blocked}</b>
          </span>
          <span className="px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700">
            {t("fp.action_mask")}: <b>{data.masked}</b>
          </span>
          <span className="px-1.5 py-0.5 rounded bg-white border border-gray-200 text-gray-600">
            {t("fp.action_allow")}: <b>{data.allowed}</b>
          </span>
        </div>
      )}

      {data && data.total === 0 && !loading && (
        <p className="text-[10px] text-gray-500 italic py-2">{t("fp.empty")}</p>
      )}

      {data && data.total > 0 && (
        <div className="max-h-56 overflow-y-auto rounded border border-gray-200 bg-white">
          <table className="w-full text-[10.5px]">
            <thead className="sticky top-0 bg-gray-50">
              <tr className="text-gray-500">
                <th className="text-left font-semibold px-2 py-1.5">{t("fp.col_field")}</th>
                <th className="text-left font-semibold px-2 py-1.5">{t("fp.col_action")}</th>
              </tr>
            </thead>
            <tbody>
              {data.fields.map((f) => (
                <tr key={f.id} className="border-t border-gray-100">
                  <td className="px-2 py-1.5 align-top">
                    <div className="font-mono text-gray-800 break-all">{f.field_name}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {f.category && <span className="text-[9px] text-gray-400">{f.category}</span>}
                      {!f.confirmed && (
                        <span className="text-[9px] px-1 rounded bg-blue-50 text-blue-600 font-medium">
                          {t("fp.pending")}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-1.5">
                    <div className="flex gap-1">
                      {(["block", "mask", "allow"] as Action[]).map((a) => (
                        <button
                          key={a}
                          type="button"
                          disabled={busyField === f.field_name}
                          onClick={() => setAction(f.field_name, a)}
                          className={`px-1.5 py-0.5 rounded-md border text-[9.5px] font-medium transition disabled:opacity-40 ${
                            f.action === a
                              ? actionStyle[a]
                              : "bg-white text-gray-400 border-gray-200 hover:border-gray-300"
                          }`}
                        >
                          {t(`fp.action_${a}`)}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Preview — what a response looks like after the rules run */}
      {data && data.total > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between gap-2 mb-1">
            <p className="text-[10px] font-semibold text-gray-700">{t("fp.preview_title")}</p>
            <button
              type="button"
              onClick={runPreview}
              className="text-[10px] px-2 py-0.5 rounded-md bg-gray-200 text-gray-700 hover:bg-gray-300 transition"
            >
              {t("fp.preview_run")}
            </button>
          </div>
          <textarea
            value={sample}
            onChange={(e) => setSample(e.target.value)}
            rows={4}
            spellCheck={false}
            className="w-full px-2 py-1.5 border border-gray-300 rounded font-mono text-[10px] outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
          />
          {showPreview && preview && (
            <div className="mt-1.5">
              <p className="text-[10px] text-gray-600 mb-1">{t("fp.preview_result")}</p>
              <pre className="bg-gray-900 text-green-300 rounded p-2 text-[10px] font-mono overflow-x-auto max-h-40 overflow-y-auto">
{JSON.stringify(preview.result, null, 1)}
              </pre>
              {preview.applied.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {preview.applied.map((a: any, i: number) => (
                    <li key={i} className="text-[9.5px] text-gray-500">
                      <span className={a.action === "block" ? "text-red-600" : "text-amber-600"}>
                        {a.action === "block" ? "✕" : "◐"}
                      </span>{" "}
                      <span className="font-mono">{a.field}</span> — {t(`fp.action_${a.action}`)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
