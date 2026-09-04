"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";

type Recipient = { kind: string; name: string; purpose: string; note: string; added_at: string };
type BasisOption = { value: string; label_th: string; label_en: string; erasable: boolean; why: string };
type Ropa = {
  legal_basis: string;
  erasure_right: "auto" | "allowed" | "restricted";
  erasure_note: string;
  recipients: Recipient[];
  erasure: { erasable: boolean; reason_th: string; basis_label: string; source: string };
  basis_options: BasisOption[];
};

const KIND_ICON: Record<string, string>= { app: "", external: "", ai: "" };

/**
 * The ROPA half of an app's PDPA record: the lawful basis it relies on, who
 * receives its data, and what a deletion request against it would get.
 *
 * The three belong together. Under §33 the right to erasure follows from the
 * lawful basis under §24 — data held to satisfy a legal obligation cannot be
 * deleted on request, and deleting it would be the violation. So the panel
 * shows the answer to "can this be deleted" right under the basis that decides
 * it, instead of leaving it to be worked out case by case.
 */
export function RopaPanel({ appId }: { appId: number }) {
  const { t, locale } = useLang();
  const [data, setData] = useState<Ropa | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState("app");
  const [newPurpose, setNewPurpose] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const d = await api.getRopa(appId);
      setData(d);
      setNote(d.erasure_note || "");
    } catch (e: any) {
      setError(e.message);
    }
  }, [appId]);

  useEffect(() => { load(); }, [load]);

  const save = async (patch: Record<string, any>) => {
    setBusy(true);
    setError("");
    try {
      await api.updateRopa(appId, patch);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const addRecipient = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.addRopaRecipient(appId, newKind, newName.trim(), newPurpose.trim());
      setNewName("");
      setNewPurpose("");
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeRecipient = async (kind: string, name: string) => {
    setBusy(true);
    try {
      await api.removeRopaRecipient(appId, kind, name);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return (
      <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/60">
        <p className="text-[10px] text-gray-500">{error || t("ropa.loading")}</p>
      </div>
    );
  }

  const label = (o: BasisOption) => (locale === "th" ? o.label_th : o.label_en);
  const selected = data.basis_options.find((o) => o.value === data.legal_basis);

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-gray-50/60 space-y-3">
      <div>
        <p className="text-[11px] font-semibold text-gray-800 flex items-center gap-1.5">
          {t("ropa.title")}
        </p>
        <p className="text-[10px] text-gray-500 leading-snug mt-0.5">{t("ropa.subtitle")}</p>
      </div>

      {error && (
        <p className="text-[10px] text-red-600 bg-red-50 border border-red-200 rounded p-1.5">{error}</p>
      )}

      {/* Lawful basis */}
      <div>
        <label className="text-[10px] font-semibold text-gray-700 block mb-1">{t("ropa.basis")}</label>
        <select
          value={data.legal_basis}
          disabled={busy}
          onChange={(e) => save({ legal_basis: e.target.value })}
          className="w-full px-2 py-1.5 border border-gray-300 rounded text-[11px] bg-white outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
        >
          <option value="">{t("ropa.basis_unset")}</option>
          {data.basis_options.map((o) => (
            <option key={o.value} value={o.value}>{label(o)}</option>
          ))}
        </select>
        {selected && <p className="text-[9.5px] text-gray-500 mt-1 leading-snug">{selected.why}</p>}
      </div>

      {/* What a deletion request gets */}
      <div
        className={`rounded p-2 border ${
          data.erasure.erasable ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"
        }`}
      >
        <p className={`text-[10.5px] font-semibold ${data.erasure.erasable ? "text-green-800" : "text-amber-800"}`}>
          {data.erasure.erasable ? `✓ ${t("ropa.erasure_yes")}` : `✕ ${t("ropa.erasure_no")}`}
        </p>
        <p className={`text-[9.5px] mt-0.5 leading-snug ${data.erasure.erasable ? "text-green-700" : "text-amber-700"}`}>
          {data.erasure.reason_th}
        </p>
        <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
          {(["auto", "allowed", "restricted"] as const).map((v) => (
            <button
              key={v}
              type="button"
              disabled={busy}
              onClick={() => save({ erasure_right: v, erasure_note: note })}
              className={`text-[9.5px] px-1.5 py-0.5 rounded-md border transition disabled:opacity-40 ${
                data.erasure_right === v
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-500 border-gray-200 hover:border-gray-300"
              }`}
            >
              {t(`ropa.erasure_${v}`)}
            </button>
          ))}
        </div>
        {data.erasure_right !== "auto" && (
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => note !== data.erasure_note && save({ erasure_note: note, erasure_right: data.erasure_right })}
            placeholder={t("ropa.erasure_note_ph")}
            className="mt-1.5 w-full px-2 py-1 border border-gray-300 rounded text-[10px] outline-none focus:ring-2 focus:ring-brand-500"
          />
        )}
      </div>

      {/* Recipients */}
      <div>
        <label className="text-[10px] font-semibold text-gray-700 block mb-1">
          {t("ropa.recipients")} <span className="text-gray-400 font-normal">({data.recipients.length})</span>
        </label>
        {data.recipients.length === 0 ? (
          <p className="text-[10px] text-gray-400 italic">{t("ropa.recipients_none")}</p>
        ) : (
          <ul className="space-y-1">
            {data.recipients.map((r) => (
              <li key={`${r.kind}:${r.name}`} className="flex items-start gap-2 bg-white border border-gray-200 rounded px-2 py-1">
                <span className="text-[11px]">{KIND_ICON[r.kind] || "•"}</span>
                <span className="flex-1 min-w-0">
                  <span className="text-[10.5px] font-medium text-gray-800 break-all">{r.name}</span>
                  {r.purpose && <span className="block text-[9.5px] text-gray-500 leading-snug">{r.purpose}</span>}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => removeRecipient(r.kind, r.name)}
                  className="text-[10px] text-gray-400 hover:text-red-600 transition disabled:opacity-40"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex gap-1.5 mt-1.5">
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value)}
            className="px-1.5 py-1 border border-gray-300 rounded text-[10px] bg-white outline-none"
          >
            <option value="app">{t("ropa.kind_app")}</option>
            <option value="external">{t("ropa.kind_external")}</option>
            <option value="ai">{t("ropa.kind_ai")}</option>
          </select>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t("ropa.recipient_name_ph")}
            className="flex-1 min-w-0 px-2 py-1 border border-gray-300 rounded text-[10px] outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            type="button"
            onClick={addRecipient}
            disabled={busy || !newName.trim()}
            className="px-2 py-1 text-[10px] bg-brand-600 text-white rounded-md hover:bg-brand-700 transition disabled:opacity-40"
          >
            {t("ropa.add")}
          </button>
        </div>
        <input
          type="text"
          value={newPurpose}
          onChange={(e) => setNewPurpose(e.target.value)}
          placeholder={t("ropa.recipient_purpose_ph")}
          className="mt-1 w-full px-2 py-1 border border-gray-300 rounded text-[10px] outline-none focus:ring-2 focus:ring-brand-500"
        />
        <p className="text-[9.5px] text-gray-500 mt-1 leading-snug">{t("ropa.recipients_hint")}</p>
      </div>
    </div>
  );
}
