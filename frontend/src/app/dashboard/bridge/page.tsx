"use client";
import { useEffect, useState, useCallback } from "react";
import {
  api,
  BridgeImport,
  BridgeDeletion,
  BridgeRoundtrip,
  BridgeChunkHit,
  BridgePreflight,
  BridgeLlmConfig,
  BridgeRegenResult,
  BridgeProject,
  BridgeCodeVersion,
  BridgeMcpToken,
  BridgeDashboard,
  BridgeCodeReport,
  BridgeLlmModel,
} from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { cn, formatLegalTimestamp } from "@/lib/utils";
import { Pagination, usePagination } from "@/components/pagination";
import { PasswordConfirmModal } from "@/components/password-confirm-modal";

function humanBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

export default function BridgePage() {
  const { t } = useLang();
  const [imports, setImports] = useState<BridgeImport[]>([]);
  const [deletions, setDeletions] = useState<BridgeDeletion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gated, setGated] = useState(false);

  // import form
  const [sourceKind, setSourceKind] = useState("sqlite");
  const [sourceRef, setSourceRef] = useState("");
  const sourcePlaceholders: Record<string, string> = {
    sqlite: "data/ivs.db",
    postgres: "postgresql+psycopg2://user:pass@host:5432/db",
    mysql: "mysql+pymysql://user:pass@host/db",
    mssql: "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server",
    oracle: "oracle+oracledb://user:pass@host:1521/?service_name=ORCL",
    sqldump: "file:///path/to/dump.sql  (mysqldump / pg_dump)",
    rest: "https://host/api  (OpenAPI)",
  };
  const [pii, setPii] = useState<"exclude" | "anonymize">("exclude");
  const [submitting, setSubmitting] = useState(false);

  // multi-model registry (AI agents from Vault)
  const [aiModels, setAiModels] = useState<BridgeLlmModel[]>([]);
  const [vaultKeys, setVaultKeys] = useState<{ id: number; name: string; provider: string; category: string }[]>([]);
  const [mmModel, setMmModel] = useState("");
  const [mmBaseUrl, setMmBaseUrl] = useState("");
  const [mmKeyId, setMmKeyId] = useState<number | "">("");
  const [mmTest, setMmTest] = useState<Record<number, string>>({});
  const [modModelId, setModModelId] = useState<number | "">(""); // per-module chosen model

  // dashboard + chat
  const [dash, setDash] = useState<BridgeDashboard | null>(null);
  const [chatMsg, setChatMsg] = useState("");
  const [chatLog, setChatLog] = useState<{ role: "you" | "ai"; text: string }[]>([]);
  const [chatBusy, setChatBusy] = useState(false);

  // projects
  const [projects, setProjects] = useState<BridgeProject[]>([]);
  const [projectId, setProjectId] = useState<number | "">("");
  const [newProjName, setNewProjName] = useState("");
  const [codePath, setCodePath] = useState("");
  const [codeRep, setCodeRep] = useState<BridgeCodeReport | null>(null);
  const [codeBusy, setCodeBusy] = useState(false);

  // modules (per import) — step-by-step build
  const [modFor, setModFor] = useState<BridgeImport | null>(null);
  const [mods, setMods] = useState<{ module: string; tables: string[]; commands: number }[]>([]);
  const [modBusy, setModBusy] = useState<string | null>(null);
  const [modResult, setModResult] = useState<Record<string, string>>({});
  const [allBusy, setAllBusy] = useState(false);
  const [allProgress, setAllProgress] = useState("");

  // merge + deploy whole system
  const [mergeFor, setMergeFor] = useState<BridgeImport | null>(null);
  const [mergeName, setMergeName] = useState("");
  const [mergeBusy, setMergeBusy] = useState(false);

  // code versions (per import) modal
  const [codeFor, setCodeFor] = useState<BridgeImport | null>(null);
  const [codeVersions, setCodeVersions] = useState<BridgeCodeVersion[]>([]);
  const [codeToDelete, setCodeToDelete] = useState<BridgeCodeVersion | null>(null);
  const [deployFor, setDeployFor] = useState<BridgeCodeVersion | null>(null);
  const [deployName, setDeployName] = useState("");

  // MCP tokens (ENT)
  const [tokenProject, setTokenProject] = useState<number | "">("");
  const [tokens, setTokens] = useState<BridgeMcpToken[]>([]);
  const [tokName, setTokName] = useState("");
  const [tokScope, setTokScope] = useState("read");
  const [newToken, setNewToken] = useState<string | null>(null);
  const [tokBusy, setTokBusy] = useState(false);

  // preflight advisor
  const [pf, setPf] = useState<BridgePreflight | null>(null);
  const [pfBusy, setPfBusy] = useState(false);

  // viewer + delete + round-trip
  const [viewing, setViewing] = useState<BridgeImport | null>(null);
  const [viewMd, setViewMd] = useState<string>("");
  const [toDelete, setToDelete] = useState<BridgeImport | null>(null);
  const [rt, setRt] = useState<BridgeRoundtrip | null>(null);
  const [rtBusy, setRtBusy] = useState<number | null>(null);

  // LLM provider (regen) + generation
  const [llm, setLlm] = useState<BridgeLlmConfig | null>(null);
  const [llmProvider, setLlmProvider] = useState("manual");
  const [llmModel, setLlmModel] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmKey, setLlmKey] = useState("");
  const [llmBusy, setLlmBusy] = useState(false);
  const [llmTest, setLlmTest] = useState<{ ok: boolean; detail: string } | null>(null);
  const [llmTestBusy, setLlmTestBusy] = useState(false);
  const [regen, setRegen] = useState<BridgeRegenResult | null>(null);
  const [regenBusy, setRegenBusy] = useState<number | null>(null);

  // ui toggles
  const [showDeletions, setShowDeletions] = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const [tab, setTab] = useState<"import" | "ai" | "work" | "connect" | "create">("import");

  // provider-specific placeholders + defaults
  const provPlaceholders: Record<string, { model: string; base: string }> = {
    manual: { model: "", base: "" },
    anthropic: { model: "claude-opus-4-8", base: "(default Anthropic API)" },
    openai: { model: "llama3.1", base: "http://localhost:11434/v1" },
  };
  const onProviderChange = (p: string) => {
    setLlmProvider(p);
    setLlmTest(null);
    // clear stale model/base_url when switching so old provider's values don't linger
    setLlmModel("");
    setLlmBaseUrl("");
  };
  const testLlm = async () => {
    setLlmTestBusy(true);
    setLlmTest(null);
    try {
      const r = await api.testBridgeLlm();
      setLlmTest({ ok: r.ok, detail: r.detail });
    } catch (e: any) {
      setLlmTest({ ok: false, detail: e?.message || "test failed" });
    } finally {
      setLlmTestBusy(false);
    }
  };

  // AI retrieval (ENT)
  const [aiId, setAiId] = useState<number | "">("");
  const [aiQ, setAiQ] = useState("");
  const [aiHits, setAiHits] = useState<BridgeChunkHit[] | null>(null);
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [imp, del, cfg, projs, dsh] = await Promise.all([
        api.listBridgeImports(false),
        api.listBridgeDeletions(),
        api.getBridgeLlmConfig(),
        api.listBridgeProjects(),
        api.getBridgeDashboard(),
      ]);
      setImports(imp);
      setDeletions(del);
      setProjects(projs);
      setDash(dsh);
      setLlm(cfg);
      try {
        const mm = await api.getBridgeLlmModels();
        setAiModels(mm.models);
        setVaultKeys(mm.vault_keys);
      } catch { /* ENT/vault optional */ }
      setLlmProvider(cfg.provider);
      setLlmModel(cfg.model);
      setLlmBaseUrl(cfg.base_url);
      setGated(false);
    } catch (e: any) {
      if (String(e?.message || "").includes("Pro or Enterprise")) setGated(true);
      else setError(e?.message || "load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refreshModels = async () => {
    const mm = await api.getBridgeLlmModels();
    setAiModels(mm.models);
    setVaultKeys(mm.vault_keys);
  };
  // provider is inferred from the chosen Vault key (anthropic/claude → anthropic,
  // everything else → openai-compatible). One less field to fill.
  const providerOfKey = (keyId: number | ""): string => {
    if (keyId === "") return "openai";
    const k = vaultKeys.find((v) => v.id === Number(keyId));
    return k && /anthropic|claude/i.test(k.provider) ? "anthropic" : "openai";
  };
  const addModel = async () => {
    if (!mmModel.trim()) return;
    try {
      await api.createBridgeLlmModel({
        label: mmModel.trim(),                    // label auto = model name
        provider: providerOfKey(mmKeyId),          // inferred from the key
        model: mmModel.trim(),
        base_url: mmBaseUrl.trim() || undefined,
        vault_key_id: mmKeyId === "" ? null : Number(mmKeyId),
      });
      setMmModel(""); setMmBaseUrl(""); setMmKeyId("");
      await refreshModels();
    } catch (e: any) {
      setError(e?.message || "add model failed");
    }
  };
  const testModel = async (id: number) => {
    setMmTest((m) => ({ ...m, [id]: "…" }));
    try {
      const r = await api.testBridgeLlmModel(id);
      setMmTest((m) => ({ ...m, [id]: r.ok ? `🟢 ${r.detail}` : `🔴 ${r.detail}` }));
    } catch (e: any) {
      setMmTest((m) => ({ ...m, [id]: `🔴 ${e?.message || "error"}` }));
    }
  };
  const delModel = async (id: number) => {
    try {
      await api.deleteBridgeLlmModel(id);
      await refreshModels();
    } catch (e: any) {
      setError(e?.message || "delete failed");
    }
  };

  // drag a file/folder onto a path field → use its absolute path when the browser
  // exposes it (desktop/Electron); else fall back to the file name + a hint.
  const onDropPath = (setter: (v: string) => void) => (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0] as any;
    if (f?.path) setter(f.path);
    else if (f?.name) setError(`เบราว์เซอร์อ่าน path เต็มไม่ได้ (ความปลอดภัย). วางเอง: ลากไฟล์ '${f.name}' → คัดลอก path จาก Finder (Cmd+Option+C)`);
  };
  const allowDrop = (e: React.DragEvent) => e.preventDefault();

  const sendChat = async () => {
    if (!chatMsg.trim() || chatBusy) return;
    const msg = chatMsg.trim();
    setChatLog((l) => [...l, { role: "you", text: msg }]);
    setChatMsg("");
    setChatBusy(true);
    try {
      const r = await api.bridgeChat(msg, projectId === "" ? null : Number(projectId));
      setChatLog((l) => [...l, { role: "ai", text: r.reply }]);
    } catch (e: any) {
      setChatLog((l) => [...l, { role: "ai", text: e?.message || "error" }]);
    } finally {
      setChatBusy(false);
    }
  };

  const analyzeCode = async () => {
    if (projectId === "" || !codePath.trim() || codeBusy) return;
    setCodeBusy(true);
    setError(null);
    try {
      setCodeRep(await api.analyzeProjectCode(Number(projectId), codePath.trim()));
    } catch (e: any) {
      setError(e?.message || "analyze failed");
    } finally {
      setCodeBusy(false);
    }
  };

  const createProject = async () => {
    if (!newProjName.trim()) return;
    try {
      const p = await api.createBridgeProject(newProjName.trim());
      setNewProjName("");
      const projs = await api.listBridgeProjects();
      setProjects(projs);
      setProjectId(p.id);
    } catch (e: any) {
      setError(e?.message || "create project failed");
    }
  };

  const openModules = async (imp: BridgeImport) => {
    setModFor(imp);
    setMods([]);
    setModResult({});
    setAllProgress("");
    try {
      const [ms, codes] = await Promise.all([
        api.listImportModules(imp.id),
        api.listImportCode(imp.id),
      ]);
      setMods(ms);
      // prefill done-state from PERSISTED code versions (survives refresh; so we
      // don't regenerate — and don't spend tokens on — modules already built)
      const done: Record<string, string> = {};
      for (const cv of codes) {
        if (cv.module && !done[cv.module]) {
          done[cv.module] = `✅ ${t("bridge.mod.have")} v${cv.version} (${cv.provider})`;
        }
      }
      setModResult(done);
    } catch (e: any) {
      setError(e?.message || "load modules failed");
    }
  };

  const genOne = async (imp: BridgeImport, mod: string) => {
    setModBusy(mod);
    try {
      const r = await api.generateModule(imp.id, mod, modModelId === "" ? null : Number(modModelId));
      const txt = r.files > 0 ? `✅ ${r.files} files (${r.provider})` : `⚠️ ${r.note}`;
      setModResult((m) => ({ ...m, [mod]: txt }));
      return r.files > 0;
    } catch (e: any) {
      setModResult((m) => ({ ...m, [mod]: `❌ ${e?.message || "failed"}` }));
      return false;
    } finally {
      setModBusy(null);
    }
  };

  const genModule = async (mod: string) => {
    if (!modFor || modBusy || allBusy) return;
    await genOne(modFor, mod);
  };

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const genAll = async (force: boolean) => {
    if (!modFor || allBusy) return;
    setAllBusy(true);
    const imp = modFor;
    // force → redo every module; else only those not yet succeeded (resume)
    const todo = mods.filter((mo) => force || !modResult[mo.module]?.startsWith("✅"));
    let done = 0;
    for (let i = 0; i < todo.length; i++) {
      const mo = todo[i];
      setAllProgress(`${i + 1}/${todo.length} — ${mo.module}`);
      const ok = await genOne(imp, mo.module);
      if (ok) done++;
      // pace requests to avoid provider rate limits; longer pause after a failure
      if (i < todo.length - 1) await sleep(ok ? 1500 : 4000);
    }
    const okTotal = mods.filter((mo) => modResult[mo.module]?.startsWith("✅")).length + 0;
    setAllProgress(`เสร็จ — รอบนี้สำเร็จ ${done}/${todo.length}`);
    setAllBusy(false);
  };

  const remainingCount = mods.filter((mo) => !modResult[mo.module]?.startsWith("✅")).length;

  const doMergeDeploy = async () => {
    if (!mergeFor || !mergeName.trim() || mergeBusy) return;
    setMergeBusy(true);
    setError(null);
    try {
      const r = await api.mergeDeployImport(mergeFor.id, mergeName.trim(), true);
      setMergeFor(null);
      setMergeName("");
      if (r.deploy) {
        alert(`รวม ${r.files} ไฟล์ → Deploy: ${r.deploy.slug} :${r.deploy.port} (${r.deploy.status})`);
      } else {
        alert(`รวมแล้ว (code v${r.version}, ${r.files} ไฟล์) — แต่ deploy ไม่สำเร็จ: ${r.deploy_error || "?"}. Export/Deploy เองได้จากปุ่ม โค้ด`);
      }
    } catch (e: any) {
      setError(e?.message || "merge failed");
    } finally {
      setMergeBusy(false);
    }
  };

  const openCode = async (imp: BridgeImport) => {
    setCodeFor(imp);
    setCodeVersions([]);
    try {
      setCodeVersions(await api.listImportCode(imp.id));
    } catch (e: any) {
      setError(e?.message || "load code failed");
    }
  };

  const doDeploy = async () => {
    if (!deployFor || !deployName.trim()) return;
    try {
      const r = await api.deployCode(deployFor.id, deployName.trim());
      setDeployFor(null);
      setDeployName("");
      if (codeFor) setCodeVersions(await api.listImportCode(codeFor.id));
      setError(null);
      alert(`Deployed → ${r.slug} :${r.port} (${r.status})`);
    } catch (e: any) {
      setError(e?.message || "deploy failed");
    }
  };

  const exportCode = async (cv: BridgeCodeVersion) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "/api"}${api.exportCodeUrl(cv.id)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );
    if (!res.ok) {
      setError("export failed");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `opencli-code-v${cv.version}-${cv.id}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const loadTokens = async (pid: number) => {
    setNewToken(null);
    try {
      setTokens(await api.listMcpTokens(pid));
    } catch (e: any) {
      setError(e?.message || "load tokens failed");
    }
  };

  const mintToken = async () => {
    if (tokenProject === "" || !tokName.trim() || tokBusy) return;
    setTokBusy(true);
    try {
      const r = await api.createMcpToken(Number(tokenProject), tokName.trim(), tokScope);
      setNewToken(r.token);
      setTokName("");
      await loadTokens(Number(tokenProject));
    } catch (e: any) {
      setError(e?.message || "mint failed");
    } finally {
      setTokBusy(false);
    }
  };

  const revokeToken = async (id: number) => {
    try {
      await api.revokeMcpToken(id);
      if (tokenProject !== "") await loadTokens(Number(tokenProject));
    } catch (e: any) {
      setError(e?.message || "revoke failed");
    }
  };

  const saveLlm = async () => {
    if (llmBusy) return;
    setLlmBusy(true);
    setError(null);
    setLlmTest(null);   // clear any stale test result on save
    try {
      const cfg = await api.setBridgeLlmConfig({
        provider: llmProvider,
        model: llmModel,
        base_url: llmBaseUrl,
        api_key: llmKey || undefined,
      });
      setLlm(cfg);
      setLlmKey("");
    } catch (e: any) {
      setError(e?.message || "save failed");
    } finally {
      setLlmBusy(false);
    }
  };

  const runRegen = async (imp: BridgeImport) => {
    setRegenBusy(imp.id);
    setRegen(null);
    setError(null);
    try {
      setRegen(await api.generateBridgeRegen(imp.id));
    } catch (e: any) {
      setError(e?.message || "generate failed");
    } finally {
      setRegenBusy(null);
    }
  };

  const runPreflight = async () => {
    if (!sourceRef.trim() || pfBusy) return;
    setPfBusy(true);
    setError(null);
    setPf(null);
    try {
      const r = await api.preflightBridgeImport({
        source_kind: sourceKind,
        source_ref: sourceRef.trim(),
      });
      setPf(r);
      setPii(r.recommended_pii_profile); // apply advisor recommendation
    } catch (e: any) {
      setError(e?.message || "preflight failed");
    } finally {
      setPfBusy(false);
    }
  };

  const doImport = async () => {
    if (!sourceRef.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createBridgeImport({
        source_kind: sourceKind,
        source_ref: sourceRef.trim(),
        pii_profile: pii,
        project_id: projectId === "" ? null : Number(projectId),
      });
      setSourceRef("");
      await load();
    } catch (e: any) {
      setError(e?.message || "import failed");
    } finally {
      setSubmitting(false);
    }
  };

  const openStructure = async (imp: BridgeImport) => {
    setViewing(imp);
    setViewMd("");
    try {
      const r = await api.getBridgeStructure(imp.id);
      setViewMd(r.structure_md);
    } catch (e: any) {
      setViewMd(`# error\n${e?.message || "not available"}`);
    }
  };

  const runRoundtrip = async (imp: BridgeImport) => {
    setRtBusy(imp.id);
    setRt(null);
    try {
      setRt(await api.getBridgeRoundtrip(imp.id));
    } catch (e: any) {
      setError(e?.message || "round-trip failed");
    } finally {
      setRtBusy(null);
    }
  };

  const aiRebuild = async () => {
    if (aiId === "" || aiBusy) return;
    setAiBusy(true);
    setAiNote(null);
    try {
      const r = await api.rebuildBridgeIndex(Number(aiId));
      setAiNote(`${t("bridge.ai.indexed")}: ${r.chunks} (${r.backend})`);
    } catch (e: any) {
      setAiNote(e?.message || "error");
    } finally {
      setAiBusy(false);
    }
  };

  const aiSearch = async () => {
    if (aiId === "" || !aiQ.trim() || aiBusy) return;
    setAiBusy(true);
    setAiNote(null);
    setAiHits(null);
    try {
      const r = await api.queryBridgeIndex(Number(aiId), aiQ.trim(), 5);
      setAiHits(r.results);
      if (r.results.length === 0) setAiNote(t("bridge.ai.no_hits"));
    } catch (e: any) {
      setAiNote(e?.message || "error");
    } finally {
      setAiBusy(false);
    }
  };

  const impPg = usePagination(imports, 10);
  const delPg = usePagination(deletions, 10);

  if (gated) {
    return (
      <div className="p-6">
        <h1 className="text-lg font-bold text-gray-900 mb-3">OpenCLI Bridge</h1>
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800 text-sm font-medium">
          {t("bridge.gated")}
        </div>
      </div>
    );
  }

  const importHistoryCard = (withActions: boolean) => (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900 text-sm">
          {withActions ? t("bridge.col.project") : t("bridge.history")}
        </h3>
        {!withActions && (
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="text-xs text-brand-600 hover:underline"
          >
            + {t("bridge.add_data")}
          </button>
        )}
      </div>
      {loading ? (
        <p className="p-8 text-center text-gray-400 text-xs">…</p>
      ) : imports.length === 0 ? (
        <p className="p-8 text-center text-gray-400 text-xs">{t("bridge.empty")}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">{t("bridge.col.project")}</th>
                  {withActions && <th className="px-4 py-2 text-left">{t("bridge.col.actions")}</th>}
                  <th className="px-4 py-2 text-left">{t("bridge.col.size")}</th>
                  <th className="px-4 py-2 text-left">SHA-256</th>
                  <th className="px-4 py-2 text-left">PII</th>
                  <th className="px-4 py-2 text-left">{t("bridge.col.cmds")}</th>
                  <th className="px-4 py-2 text-left">{t("bridge.col.when")}</th>
                </tr>
              </thead>
              <tbody className="text-gray-700">
                {impPg.paged.map((imp) => (
                  <tr key={imp.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium text-gray-900">{imp.id}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{imp.source_kind}:{imp.source_ref}</td>
                    {withActions && (
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <button onClick={() => openModules(imp)} className="text-indigo-700 font-medium hover:underline mr-3">{t("bridge.mod.btn")}</button>
                        <button onClick={() => { setMergeFor(imp); setMergeName(""); }} className="text-green-700 font-medium hover:underline mr-3">{t("bridge.merge.btn")}</button>
                        <button onClick={() => openCode(imp)} className="text-indigo-500 hover:underline mr-3">{t("bridge.code.btn")}</button>
                        <button onClick={() => runRoundtrip(imp)} disabled={rtBusy === imp.id} className="text-green-700 hover:underline mr-3 disabled:opacity-50">{rtBusy === imp.id ? "…" : t("bridge.roundtrip")}</button>
                        <button onClick={() => openStructure(imp)} className="text-brand-600 hover:underline mr-3">{t("bridge.view")}</button>
                        <button onClick={() => setToDelete(imp)} className="text-red-600 hover:underline">{t("bridge.delete")}</button>
                      </td>
                    )}
                    <td className="px-4 py-2.5">{humanBytes(imp.source_bytes)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500" title={imp.sha256_raw}>{imp.sha256_raw.slice(0, 12)}…</td>
                    <td className="px-4 py-2.5">{imp.pii_profile}</td>
                    <td className="px-4 py-2.5">{imp.command_count ?? "—"}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-gray-600">{formatLegalTimestamp(imp.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={impPg.total} page={impPg.page} pageSize={impPg.pageSize}
            onPageChange={impPg.setPage} onPageSizeChange={impPg.setPageSize} itemLabel={t("bridge.history")} />
        </>
      )}
    </div>
  );

  const deletionCard = () => (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <button onClick={() => setShowDeletions((v) => !v)}
        className="w-full px-4 py-3 border-b border-gray-100 flex items-center justify-between text-left hover:bg-gray-50">
        <h3 className="font-semibold text-gray-900 text-sm">
          {t("bridge.deletions")} <span className="text-gray-400 font-normal">({deletions.length})</span>
        </h3>
        <span className="text-gray-400 text-xs">{showDeletions ? "▲" : "▼"}</span>
      </button>
      {!showDeletions ? null : deletions.length === 0 ? (
        <p className="p-8 text-center text-gray-400 text-xs">{t("bridge.no_deletions")}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2 text-left">{t("bridge.col.import")}</th>
                  <th className="px-4 py-2 text-left">SHA-256</th>
                  <th className="px-4 py-2 text-left">{t("bridge.col.reason")}</th>
                  <th className="px-4 py-2 text-left">{t("bridge.col.when")}</th>
                </tr>
              </thead>
              <tbody className="text-gray-700">
                {delPg.paged.map((d) => (
                  <tr key={d.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium text-gray-900">#{d.import_id}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500" title={d.sha256_raw}>{d.sha256_raw.slice(0, 12)}…</td>
                    <td className="px-4 py-2.5">{d.reason || "—"}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-gray-600">{formatLegalTimestamp(d.deleted_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination total={delPg.total} page={delPg.page} pageSize={delPg.pageSize}
            onPageChange={delPg.setPage} onPageSizeChange={delPg.setPageSize} itemLabel={t("bridge.deletions")} />
        </>
      )}
    </div>
  );

  const tabs: { id: typeof tab; label: string }[] = [
    { id: "import", label: t("bridge.tab.import") },
    { id: "ai", label: t("bridge.tab.ai") },
    { id: "work", label: t("bridge.tab.work") },
    { id: "connect", label: t("bridge.tab.connect") },
    { id: "create", label: t("bridge.tab.create") },
  ];

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">OpenCLI Control Center</h1>
          <p className="text-gray-500 text-xs mt-0.5">{t("bridge.subtitle")}</p>
        </div>
        {dash && (
          <span className="text-[10px] uppercase tracking-wide bg-brand-50 text-brand-700 px-2 py-1 rounded-full font-semibold">
            {dash.edition}
          </span>
        )}
      </div>

      {/* Control-center hero cards */}
      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: t("bridge.dash.projects"), value: dash.projects },
            { label: t("bridge.dash.imports"), value: dash.imports },
            { label: t("bridge.dash.code"), value: dash.code_versions },
            { label: t("bridge.dash.deployed"), value: dash.deployed },
            { label: t("bridge.dash.tokens"), value: dash.active_tokens },
          ].map((c) => (
            <div key={c.label} className="bg-white rounded-lg border border-gray-200 p-3">
              <div className="text-2xl font-bold text-gray-900">{c.value}</div>
              <div className="text-[11px] text-gray-500 mt-0.5">{c.label}</div>
            </div>
          ))}
        </div>
      )}
      {dash && (
        <div className="text-xs text-gray-500">
          {t("bridge.dash.provider")}: <b>{dash.provider}</b>{" "}
          {dash.provider === "manual" ? "" : dash.provider_has_key ? "🔑" : "⚠️ no key"}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200">
        {tabs.map((tb) => (
          <button
            key={tb.id}
            onClick={() => setTab(tb.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium -mb-px border-b-2 transition",
              tab === tb.id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-500 hover:text-gray-800"
            )}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {/* Tab: การสร้างสรรค์ — natural-language chat */}
      {tab === "create" && (
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-2">
        <h3 className="font-semibold text-gray-900 text-sm">{t("bridge.chat.title")}</h3>
        <p className="text-xs text-gray-400">{t("bridge.chat.desc")}</p>
        {chatLog.length > 0 && (
          <div className="max-h-64 overflow-auto space-y-2 py-1">
            {chatLog.map((m, i) => (
              <div
                key={i}
                className={cn(
                  "text-sm rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap",
                  m.role === "you"
                    ? "bg-brand-50 text-brand-900 ml-auto"
                    : "bg-gray-50 text-gray-800 border border-gray-100"
                )}
              >
                {m.text}
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={chatMsg}
            onChange={(e) => setChatMsg(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendChat()}
            placeholder={t("bridge.chat.ph")}
            className="flex-1 rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
          />
          <button
            onClick={sendChat}
            disabled={chatBusy || !chatMsg.trim()}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {chatBusy ? "…" : t("bridge.chat.send")}
          </button>
        </div>
      </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Tab: นำเข้าใหม่ — import form + history (no actions) + deletions */}
      {tab === "import" && (
      <>
      {/* Import form */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-sm">{t("bridge.new_import")}</h3>
          <button
            onClick={() => setShowExplain(true)}
            className="text-xs text-brand-600 hover:underline"
          >
            {t("bridge.explain.btn")}
          </button>
        </div>
        {/* pick or create a project/app first */}
        <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="">{t("bridge.proj.none")}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.imports})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <input
              value={newProjName}
              onChange={(e) => setNewProjName(e.target.value)}
              placeholder={t("bridge.proj.new_ph")}
              className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
            />
            <button
              onClick={createProject}
              disabled={!newProjName.trim()}
              className="rounded-lg px-3 py-2 text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50 whitespace-nowrap"
            >
              {t("bridge.proj.create")}
            </button>
          </div>
        </div>
        {/* attach legacy code (the 'โค้ดเดิม' input) — needs a project */}
        {projectId !== "" && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
            <p className="text-xs font-medium text-gray-700">{t("bridge.code2.title")}</p>
            <div className="flex gap-2">
              <input
                value={codePath}
                onChange={(e) => setCodePath(e.target.value)}
                onDrop={onDropPath(setCodePath)}
                onDragOver={allowDrop}
                placeholder={t("bridge.code2.ph")}
                className="flex-1 rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
              />
              <button
                onClick={analyzeCode}
                disabled={codeBusy || !codePath.trim()}
                className="rounded-lg px-3 py-2 text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50 whitespace-nowrap"
              >
                {codeBusy ? "…" : t("bridge.code2.analyze")}
              </button>
            </div>
            {codeRep && (
              <div className="text-xs text-gray-600 space-y-1">
                <div>
                  {t("bridge.code2.files")} <b>{codeRep.files}</b> ·{" "}
                  {t("bridge.code2.modules")} <b>{Object.keys(codeRep.modules).length}</b> ·{" "}
                  {t("bridge.code2.tables")} <b>{codeRep.tables_referenced.length}</b> ·{" "}
                  roles: {codeRep.roles.join(", ")}
                </div>
                {codeRep.secret_count > 0 && (
                  <div className="text-red-700">
                    ⚠️ {t("bridge.code2.secrets")} <b>{codeRep.secret_count}</b> (
                    {codeRep.secrets.slice(0, 4).map((s) => s.file).join(", ")}
                    {codeRep.secrets.length > 4 ? "…" : ""}) — {t("bridge.code2.excluded")}
                  </div>
                )}
                <div className="text-green-700">✅ {t("bridge.code2.attached")}</div>
              </div>
            )}
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-[9rem_1fr_auto_auto]">
          <select
            value={sourceKind}
            onChange={(e) => setSourceKind(e.target.value)}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="sqlite">SQLite</option>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="mssql">SQL Server</option>
            <option value="oracle">Oracle</option>
            <option value="sqldump">SQL dump (.sql)</option>
            <option value="rest">REST/OpenAPI</option>
          </select>
          <input
            value={sourceRef}
            onChange={(e) => setSourceRef(e.target.value)}
            onDrop={onDropPath(setSourceRef)}
            onDragOver={allowDrop}
            placeholder={sourcePlaceholders[sourceKind] || t("bridge.source_ref_ph")}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
          />
          <select
            value={pii}
            onChange={(e) => setPii(e.target.value as any)}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="exclude">{t("bridge.pii.exclude")}</option>
            <option value="anonymize">{t("bridge.pii.anonymize")}</option>
          </select>
          <button
            onClick={runPreflight}
            disabled={pfBusy || !sourceRef.trim()}
            className="rounded-lg px-3 py-2 text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {pfBusy ? "…" : t("bridge.pf.check")}
          </button>
          <button
            onClick={doImport}
            disabled={submitting || !sourceRef.trim()}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition",
              submitting || !sourceRef.trim()
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-brand-600 text-white hover:bg-brand-700"
            )}
          >
            {submitting ? t("bridge.importing") : t("bridge.import_btn")}
          </button>
        </div>
        <p className="text-xs text-gray-400">{t("bridge.readonly_note")}</p>

        {/* Preflight advisor result */}
        {pf && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-600">
              <span className="font-semibold text-gray-800">{t("bridge.pf.title")}</span>
              <span>{t("bridge.col.source")}: <b>{pf.site}</b></span>
              <span>{t("bridge.rt.tables")} {pf.tables}</span>
              <span>rows {pf.total_rows.toLocaleString()}</span>
              <span>
                {t("bridge.pf.rec_pii")}: <b>{pf.recommended_pii_profile}</b>
              </span>
            </div>
            {pf.recommended_exclude_tables.length > 0 && (
              <p className="text-xs text-red-700">
                {t("bridge.pf.exclude")}: {pf.recommended_exclude_tables.join(", ")}
              </p>
            )}
            <ul className="space-y-1 max-h-56 overflow-auto">
              {pf.findings.map((f, i) => (
                <li key={i} className="text-xs flex gap-2">
                  <span
                    className={cn(
                      "shrink-0 font-semibold uppercase w-14",
                      f.severity === "critical"
                        ? "text-red-600"
                        : f.severity === "warn"
                        ? "text-amber-600"
                        : "text-gray-400"
                    )}
                  >
                    {f.severity}
                  </span>
                  <span className="text-gray-700">
                    <span className="font-mono">{f.target}</span> — {f.message}{" "}
                    <span className="text-gray-500">→ {f.recommendation}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {importHistoryCard(false)}
      {deletionCard()}
      </>
      )}

      {/* Tab: AI Agent — provider config + multi-model registry */}
      {tab === "ai" && (
      <>
      {/* LLM provider (regen) — vendor-neutral */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-sm">{t("bridge.llm.title")}</h3>
          {llm && (
            <span className="text-[10px] text-gray-500">
              {t("bridge.llm.current")}: <b>{llm.provider}</b>
              {llm.model ? ` / ${llm.model}` : ""} {llm.has_key ? "🔑" : ""}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-400">{t("bridge.llm.desc")}</p>
        <div
          className={cn(
            "grid gap-2",
            llmProvider === "manual" ? "sm:grid-cols-1" : "sm:grid-cols-[10rem_1fr_1fr]"
          )}
        >
          <select
            value={llmProvider}
            onChange={(e) => onProviderChange(e.target.value)}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            {(llm?.available_providers ?? [{ name: "manual", needs_key: false }]).map((p) => (
              <option key={p.name} value={p.name}>{p.name}</option>
            ))}
          </select>
          {llmProvider !== "manual" && (
            <>
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder={provPlaceholders[llmProvider]?.model || "model"}
                className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
              />
              <input
                value={llmBaseUrl}
                onChange={(e) => setLlmBaseUrl(e.target.value)}
                placeholder={provPlaceholders[llmProvider]?.base || "base_url"}
                className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
              />
            </>
          )}
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
          {llmProvider !== "manual" ? (
            <input
              value={llmKey}
              onChange={(e) => setLlmKey(e.target.value)}
              type="password"
              placeholder={llm?.has_key ? t("bridge.llm.key_set") : t("bridge.llm.key_ph")}
              className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
            />
          ) : (
            <div />
          )}
          <button
            onClick={testLlm}
            disabled={llmTestBusy}
            className="rounded-lg px-4 py-2 text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {llmTestBusy ? "…" : t("bridge.llm.test")}
          </button>
          <button
            onClick={saveLlm}
            disabled={llmBusy}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {t("bridge.llm.save")}
          </button>
        </div>
        {llmTest && (
          <p
            className={cn(
              "text-xs font-medium",
              llmTest.ok ? "text-green-700" : "text-red-600"
            )}
          >
            {llmTest.ok ? "🟢 " : "🔴 "}
            {llmTest.ok ? t("bridge.llm.ready") : t("bridge.llm.notready")} — {llmTest.detail}
          </p>
        )}
        <p className="text-xs text-gray-400">{t("bridge.llm.note")}</p>
      </div>

      {/* Multi-model registry — several AI agents from the Vault (Pro/ENT) */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-sm">{t("bridge.mm.title")}</h3>
          <span className="text-[9px] uppercase tracking-wide bg-purple-100 text-purple-700 px-1.5 py-px rounded-full font-semibold">
            Pro/Enterprise
          </span>
        </div>
        <p className="text-xs text-gray-400">{t("bridge.mm.desc")}</p>
        {aiModels.length > 0 && (
          <ul className="space-y-1.5">
            {aiModels.map((mo) => (
              <li key={mo.id} className="flex items-center gap-2 text-xs border border-gray-100 rounded-lg p-2">
                <span className="font-medium text-gray-900">{mo.label}</span>
                <span className="text-gray-500 font-mono">{mo.provider}/{mo.model}</span>
                {mo.vault_key_name && <span className="text-gray-400">🔑 {mo.vault_key_name}</span>}
                {mmTest[mo.id] && <span className="ml-1">{mmTest[mo.id]}</span>}
                <button onClick={() => testModel(mo.id)} className="ml-auto text-brand-600 hover:underline">
                  {t("bridge.mm.test")}
                </button>
                <button onClick={() => delModel(mo.id)} className="text-red-600 hover:underline">
                  {t("bridge.delete")}
                </button>
              </li>
            ))}
          </ul>
        )}
        {/* minimal form: pick key first (provider auto), then model; base_url optional */}
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr]">
          <label className="text-xs text-gray-500 flex flex-col gap-1">
            1. {t("bridge.mm.pick_key")}
            <select value={mmKeyId === "" ? "" : String(mmKeyId)}
              onChange={(e) => setMmKeyId(e.target.value === "" ? "" : Number(e.target.value))}
              className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none">
              <option value="">{t("bridge.mm.no_key")}</option>
              {vaultKeys.map((k) => (
                <option key={k.id} value={String(k.id)}>
                  {k.name} — {k.provider}{k.category && k.category !== "general" ? ` · ${k.category}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-500 flex flex-col gap-1">
            <span>2. model — <span className="text-gray-400">{providerOfKey(mmKeyId)}</span></span>
            <input value={mmModel} onChange={(e) => setMmModel(e.target.value)}
              placeholder={t("bridge.mm.model_ph")}
              className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none" />
          </label>
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
          {providerOfKey(mmKeyId) === "openai" && (
            <input value={mmBaseUrl} onChange={(e) => setMmBaseUrl(e.target.value)}
              placeholder={t("bridge.mm.base_ph")}
              className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none" />
          )}
          <button onClick={addModel} disabled={!mmModel.trim()}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50 sm:col-start-2">
            {t("bridge.mm.add")}
          </button>
        </div>
        <p className="text-xs text-gray-400">{t("bridge.mm.note")}</p>
      </div>
      </>
      )}

      {/* Tab: การทำงาน โครงการ/APP — banners + history (with actions) + deletions */}
      {tab === "work" && (
      <>
      {/* Regen result banner */}
      {regen && (
        <div className="rounded-lg border border-indigo-300 bg-indigo-50 p-3 text-sm text-indigo-900 flex items-start gap-3">
          <span className="font-semibold">🛠 {regen.mode}</span>
          <span>
            {t("bridge.regen.via")} <b>{regen.provider}</b>
            {regen.model ? ` / ${regen.model}` : ""} · {t("bridge.regen.files")} {regen.files}
            {regen.verify && (
              <> · {regen.verify.ok ? "✅ deploy-valid" : `❌ ${regen.verify.issues.join(", ")}`}</>
            )}
            <span className="block text-xs text-indigo-700 mt-0.5">{regen.note}</span>
          </span>
          <button onClick={() => setRegen(null)} className="ml-auto text-gray-400 hover:text-gray-700">✕</button>
        </div>
      )}

      {/* Round-trip result banner (success metric) */}
      {rt && (
        <div
          className={cn(
            "rounded-lg border p-3 text-sm flex items-start gap-3",
            rt.passed
              ? "border-green-300 bg-green-50 text-green-800"
              : "border-red-300 bg-red-50 text-red-800"
          )}
        >
          <span className="font-semibold">
            {rt.passed ? "✅ PASS" : "❌ FAIL"}
          </span>
          <span>
            <span className="font-mono">{rt.site}</span> — {t("bridge.rt.fidelity")}{" "}
            <b>{(rt.fidelity * 100).toFixed(1)}%</b>
            {" · "}
            {t("bridge.rt.tables")} {rt.tables_matched}/{rt.tables_total}
            {" · "}
            {t("bridge.rt.cols")} {rt.columns_correct}/{rt.columns_expected}
            {" · "}
            {t("bridge.rt.pii")} {rt.pii_dropped}
            {rt.defects.length > 0 && (
              <span className="block mt-1 font-mono text-xs">
                {rt.defects
                  .map((d) => `${d.table}: -[${d.missing}] +[${d.extra}]`)
                  .join("  ")}
              </span>
            )}
          </span>
          <button onClick={() => setRt(null)} className="ml-auto text-gray-400 hover:text-gray-700">✕</button>
        </div>
      )}

      {importHistoryCard(true)}
      {deletionCard()}
      </>
      )}

      {/* Tab: เชื่อม AI Agent ภายนอก — MCP tokens + AI search */}
      {tab === "connect" && (
      <>
      {/* Connect external AI Agent — MCP tokens (Enterprise) */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-sm">{t("bridge.tok.title")}</h3>
          <span className="text-[9px] uppercase tracking-wide bg-purple-100 text-purple-700 px-1.5 py-px rounded-full font-semibold">
            Enterprise
          </span>
        </div>
        <p className="text-xs text-gray-400">{t("bridge.tok.desc")}</p>
        <div className="grid gap-2 sm:grid-cols-[10rem_1fr_8rem_auto]">
          <select
            value={tokenProject}
            onChange={(e) => {
              const v = e.target.value === "" ? "" : Number(e.target.value);
              setTokenProject(v);
              if (v !== "") loadTokens(Number(v));
            }}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="">{t("bridge.tok.pick")}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <input
            value={tokName}
            onChange={(e) => setTokName(e.target.value)}
            placeholder={t("bridge.tok.name_ph")}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
          />
          <select
            value={tokScope}
            onChange={(e) => setTokScope(e.target.value)}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="read">read</option>
            <option value="read_write">read_write</option>
          </select>
          <button
            onClick={mintToken}
            disabled={tokBusy || tokenProject === "" || !tokName.trim()}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:bg-gray-100 disabled:text-gray-400"
          >
            {t("bridge.tok.mint")}
          </button>
        </div>
        {newToken && (
          <div className="rounded-lg border border-green-300 bg-green-50 p-2.5 text-xs">
            <p className="text-green-800 font-medium mb-1">{t("bridge.tok.once")}</p>
            <code className="font-mono break-all text-green-900">{newToken}</code>
          </div>
        )}
        {tokenProject !== "" && tokens.length > 0 && (
          <ul className="space-y-1">
            {tokens.map((tk) => (
              <li key={tk.id} className="flex items-center gap-2 text-xs">
                <span className="font-mono text-gray-700">{tk.prefix}…</span>
                <span className="text-gray-500">{tk.name} · {tk.scope}</span>
                {tk.revoked ? (
                  <span className="text-red-500">{t("bridge.tok.revoked")}</span>
                ) : (
                  <button
                    onClick={() => revokeToken(tk.id)}
                    className="ml-auto text-red-600 hover:underline"
                  >
                    {t("bridge.tok.revoke")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-gray-400">{t("bridge.tok.note")}</p>
      </div>

      {/* AI retrieval / quick Q&A (Enterprise sub-feature) */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-sm">{t("bridge.ai.title")}</h3>
          <span className="text-[9px] uppercase tracking-wide bg-purple-100 text-purple-700 px-1.5 py-px rounded-full font-semibold">
            Enterprise
          </span>
        </div>
        <p className="text-xs text-gray-400">{t("bridge.ai.desc")}</p>
        <div className="grid gap-2 sm:grid-cols-[8rem_1fr_auto_auto]">
          <select
            value={aiId}
            onChange={(e) => setAiId(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="">{t("bridge.ai.pick")}</option>
            {imports.map((i) => (
              <option key={i.id} value={i.id}>#{i.id} {i.source_ref.split("/").pop()}</option>
            ))}
          </select>
          <input
            value={aiQ}
            onChange={(e) => setAiQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && aiSearch()}
            placeholder={t("bridge.ai.q_ph")}
            className="rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none"
          />
          <button
            onClick={aiSearch}
            disabled={aiBusy || aiId === "" || !aiQ.trim()}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 disabled:bg-gray-100 disabled:text-gray-400"
          >
            {t("bridge.ai.search")}
          </button>
          <button
            onClick={aiRebuild}
            disabled={aiBusy || aiId === ""}
            className="rounded-lg px-3 py-2 text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {t("bridge.ai.rebuild")}
          </button>
        </div>
        {aiNote && <p className="text-xs text-gray-500">{aiNote}</p>}
        {aiHits && aiHits.length > 0 && (
          <ul className="space-y-1.5">
            {aiHits.map((h) => (
              <li key={h.id} className="rounded-lg bg-gray-50 border border-gray-100 p-2.5 text-xs">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-mono text-brand-600">{h.kind}:{h.ref}</span>
                  <span className="text-gray-400">score {h.score}</span>
                </div>
                <div className="text-gray-600">{h.text}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
      </>
      )}

      {/* Merge + Deploy whole system */}
      {mergeFor && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setMergeFor(null)}
        >
          <div className="bg-white border border-gray-200 rounded-xl max-w-md w-full p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h3 className="text-gray-900 font-semibold text-sm mb-1">{t("bridge.merge.title")}</h3>
            <p className="text-xs text-gray-500 mb-3">{t("bridge.merge.desc")}</p>
            <input
              value={mergeName}
              onChange={(e) => setMergeName(e.target.value)}
              placeholder={t("bridge.code.appname_ph")}
              className="w-full rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 mb-3"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setMergeFor(null)} className="px-3 py-2 text-sm text-gray-600">
                {t("bridge.cancel")}
              </button>
              <button
                onClick={doMergeDeploy}
                disabled={mergeBusy || !mergeName.trim()}
                className="px-4 py-2 text-sm font-medium bg-green-700 text-white rounded-lg hover:bg-green-800 disabled:opacity-50"
              >
                {mergeBusy ? "…" : t("bridge.merge.go")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modules — step-by-step build */}
      {modFor && (
        <div
          className="fixed inset-0 z-40 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setModFor(null)}
        >
          <div
            className="bg-white border border-gray-200 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-auto p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-gray-900 font-semibold text-sm">
                {t("bridge.mod.title")} #{modFor.id}
              </h3>
              <div className="flex items-center gap-2">
                {Object.keys(modResult).length > 0 && remainingCount > 0 && (
                  <button
                    onClick={() => genAll(false)}
                    disabled={allBusy || mods.length === 0}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium border border-indigo-300 text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                  >
                    {t("bridge.mod.resume")} ({remainingCount})
                  </button>
                )}
                <button
                  onClick={() => genAll(true)}
                  disabled={allBusy || mods.length === 0}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {allBusy ? t("bridge.mod.all_busy") : t("bridge.mod.all")}
                </button>
                <button onClick={() => setModFor(null)} className="text-gray-400 hover:text-gray-700">✕</button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mb-1">{t("bridge.mod.desc")}</p>
            {aiModels.length > 0 && (
              <div className="flex items-center gap-2 mb-2 text-xs">
                <span className="text-gray-500">{t("bridge.mod.use_model")}:</span>
                <select
                  value={modModelId}
                  onChange={(e) => setModModelId(e.target.value === "" ? "" : Number(e.target.value))}
                  className="rounded-lg bg-white border border-gray-300 px-2 py-1 text-xs text-gray-900"
                >
                  <option value="">{t("bridge.mod.default_model")}</option>
                  {aiModels.map((mo) => (
                    <option key={mo.id} value={mo.id}>{mo.label} ({mo.model})</option>
                  ))}
                </select>
              </div>
            )}
            {allProgress && (
              <p className="text-xs text-indigo-700 mb-2 font-medium">⏳ {allProgress}</p>
            )}
            {mods.length === 0 ? (
              <p className="text-gray-500 text-xs">…</p>
            ) : (
              <ul className="space-y-2">
                {mods.map((mo) => (
                  <li key={mo.module} className="flex items-center gap-3 border border-gray-100 rounded-lg p-2.5">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-gray-900">{mo.module}</div>
                      <div className="text-[11px] text-gray-500 truncate font-mono">
                        {mo.tables.join(", ")}
                      </div>
                      {modResult[mo.module] && (
                        <div className="text-[11px] mt-0.5">{modResult[mo.module]}</div>
                      )}
                    </div>
                    <button
                      onClick={() => genModule(mo.module)}
                      disabled={modBusy === mo.module || allBusy}
                      className={cn(
                        "rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 whitespace-nowrap",
                        modResult[mo.module]?.startsWith("✅")
                          ? "border border-gray-300 text-gray-600 hover:bg-gray-50"
                          : "bg-brand-600 text-white hover:bg-brand-700"
                      )}
                    >
                      {modBusy === mo.module
                        ? "…"
                        : modResult[mo.module]?.startsWith("✅")
                        ? t("bridge.mod.regen")
                        : t("bridge.mod.gen")}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-gray-400 mt-3">{t("bridge.mod.note")}</p>
          </div>
        </div>
      )}

      {/* Code versions modal */}
      {codeFor && (
        <div
          className="fixed inset-0 z-40 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setCodeFor(null)}
        >
          <div
            className="bg-white border border-gray-200 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-auto p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-gray-900 font-semibold text-sm">
                {t("bridge.code.title")} #{codeFor.id}
              </h3>
              <button onClick={() => setCodeFor(null)} className="text-gray-400 hover:text-gray-700">✕</button>
            </div>
            {codeVersions.length === 0 ? (
              <p className="text-gray-500 text-xs">{t("bridge.code.empty")}</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-[9px] uppercase">
                  <tr>
                    <th className="px-2 py-1.5 text-left">v</th>
                    <th className="px-2 py-1.5 text-left">provider</th>
                    <th className="px-2 py-1.5 text-left">files</th>
                    <th className="px-2 py-1.5 text-left">deploy-valid</th>
                    <th className="px-2 py-1.5 text-left">status</th>
                    <th className="px-2 py-1.5"></th>
                  </tr>
                </thead>
                <tbody className="text-gray-700">
                  {codeVersions.map((cv) => (
                    <tr key={cv.id} className="border-t border-gray-100">
                      <td className="px-2 py-1.5 font-medium">
                        v{cv.version}{cv.module ? <span className="text-indigo-600"> · {cv.module}</span> : ""}
                      </td>
                      <td className="px-2 py-1.5">{cv.provider}{cv.model ? `/${cv.model}` : ""}</td>
                      <td className="px-2 py-1.5">{cv.files_count}</td>
                      <td className="px-2 py-1.5">{cv.verify_ok ? "✅" : "—"}</td>
                      <td className="px-2 py-1.5">{cv.status}</td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-right">
                        <button
                          onClick={() => { setDeployFor(cv); setDeployName(""); }}
                          className="text-green-700 hover:underline mr-2"
                        >
                          {t("bridge.code.deploy")}
                        </button>
                        <button onClick={() => exportCode(cv)} className="text-brand-600 hover:underline mr-2">
                          {t("bridge.code.export")}
                        </button>
                        <button onClick={() => setCodeToDelete(cv)} className="text-red-600 hover:underline">
                          {t("bridge.delete")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Deploy dialog */}
      {deployFor && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setDeployFor(null)}
        >
          <div className="bg-white border border-gray-200 rounded-xl max-w-sm w-full p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h3 className="text-gray-900 font-semibold text-sm mb-3">
              {t("bridge.code.deploy")} v{deployFor.version}
            </h3>
            <input
              value={deployName}
              onChange={(e) => setDeployName(e.target.value)}
              placeholder={t("bridge.code.appname_ph")}
              className="w-full rounded-lg bg-white border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 mb-3"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeployFor(null)} className="px-3 py-2 text-sm text-gray-600">
                {t("bridge.cancel") || "Cancel"}
              </button>
              <button
                onClick={doDeploy}
                disabled={!deployName.trim()}
                className="px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
              >
                {t("bridge.code.deploy")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Code delete confirm (password re-auth) */}
      {codeToDelete && (
        <PasswordConfirmModal
          title={t("bridge.code.del_title")}
          description={t("bridge.code.del_desc")}
          consequences={[`v${codeToDelete.version} · ${codeToDelete.provider} · ${codeToDelete.files_count} files`]}
          confirmLabel={t("bridge.delete")}
          onCancel={() => setCodeToDelete(null)}
          onConfirm={async (password) => {
            await api.deleteCode(codeToDelete.id, password, "deleted via dashboard");
            setCodeToDelete(null);
            if (codeFor) setCodeVersions(await api.listImportCode(codeFor.id));
          }}
        />
      )}

      {/* Explain modal — what "new import" does */}
      {showExplain && (
        <div
          className="fixed inset-0 z-40 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setShowExplain(false)}
        >
          <div
            className="bg-white border border-gray-200 rounded-xl max-w-lg w-full p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-gray-900 font-semibold text-sm">{t("bridge.explain.title")}</h3>
              <button onClick={() => setShowExplain(false)} className="text-gray-400 hover:text-gray-700">✕</button>
            </div>
            <ol className="space-y-2 text-sm text-gray-700 list-decimal pl-5">
              <li>{t("bridge.explain.s1")}</li>
              <li>{t("bridge.explain.s2")}</li>
              <li>{t("bridge.explain.s3")}</li>
              <li>{t("bridge.explain.s4")}</li>
              <li>{t("bridge.explain.s5")}</li>
            </ol>
            <p className="text-xs text-gray-400 mt-3">{t("bridge.explain.foot")}</p>
          </div>
        </div>
      )}

      {/* Structure viewer */}
      {viewing && (
        <div
          className="fixed inset-0 z-40 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setViewing(null)}
        >
          <div
            className="bg-white border border-gray-200 rounded-xl max-w-3xl w-full max-h-[80vh] overflow-auto p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-gray-900 font-semibold text-sm">
                {t("bridge.structure_of")} #{viewing.id}
              </h3>
              <button
                onClick={() => setViewing(null)}
                className="text-gray-400 hover:text-gray-700"
              >
                ✕
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-xs text-gray-700 font-mono">
              {viewMd || "…"}
            </pre>
          </div>
        </div>
      )}

      {/* Delete confirm (password re-auth) */}
      {toDelete && (
        <PasswordConfirmModal
          title={t("bridge.delete_title")}
          description={t("bridge.delete_desc")}
          consequences={[
            `${t("bridge.col.source")}: ${toDelete.source_kind}:${toDelete.source_ref}`,
            `SHA-256: ${toDelete.sha256_raw.slice(0, 24)}…`,
          ]}
          confirmLabel={t("bridge.delete")}
          onCancel={() => setToDelete(null)}
          onConfirm={async (password) => {
            await api.deleteBridgeImport(toDelete.id, password, "deleted via dashboard");
            setToDelete(null);
            await load();
          }}
        />
      )}
    </div>
  );
}
