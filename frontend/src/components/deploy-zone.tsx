"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { api } from "@/lib/api";
import { useLang } from "@/components/lang-provider";
import { DeployGuide } from "@/components/deploy-guide";

type ValidationResult = {
  valid: boolean;
  app_type: string;
  issues: string[];
  warnings: string[];
  files: string[];
};

const TYPE_PROMPT_MAP: Record<string, string> = {
  static: "static",
  nodejs: "nodejs",
  fastapi: "fastapi",
  streamlit: "streamlit",
  fullstack: "fullstack",
  python: "fastapi",
  unknown: "static",
};

const TYPE_ICONS: Record<string, string> = {
  static: "🌐",
  nodejs: "🟢",
  fastapi: "⚡",
  streamlit: "📊",
  fullstack: "🔮",
  python: "🐍",
  unknown: "❓",
};

const FILE_SIZE_WARN_MB = 50;

export function DeployZone({ onDeployed }: { onDeployed: () => void }) {
  const { t } = useLang();
  const [dragging, setDragging] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [validating, setValidating] = useState(false);
  const [appName, setAppName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [promptCopied, setPromptCopied] = useState(false);
  const [showSizeWarning, setShowSizeWarning] = useState(false);
  const [buildLogs, setBuildLogs] = useState<string[]>([]);
  const [showBuildLog, setShowBuildLog] = useState(false);
  const [buildStatus, setBuildStatus] = useState<string>("");
  const fileRef = useRef<HTMLInputElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll build logs
  useEffect(() => {
    if (logEndRef.current && showBuildLog) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [buildLogs, showBuildLog]);

  const validateFile = async (file: File) => {
    setValidating(true);
    setValidation(null);
    setStatus("");
    try {
      const result = await api.validateApp(file);
      setValidation(result);
      if (result.valid) {
        setStatus("");
      }
    } catch (e: any) {
      setStatus(`${t("deploy.fail")}: ${e.message}`);
    } finally {
      setValidating(false);
    }
  };

  const handleFileSelected = (file: File) => {
    const sizeMB = file.size / 1024 / 1024;

    // Check file size warning
    if (sizeMB > FILE_SIZE_WARN_MB) {
      setSelectedFile(file);
      setShowSizeWarning(true);
      return;
    }

    proceedWithFile(file);
  };

  const proceedWithFile = (file: File) => {
    setSelectedFile(file);
    setShowSizeWarning(false);
    setValidation(null);
    setPromptCopied(false);
    setBuildLogs([]);
    setBuildStatus("");
    setShowBuildLog(false);
    if (!appName) setAppName(file.name.replace(".zip", "").replace(/[^a-zA-Z0-9\s-]/g, ""));
    validateFile(file);
  };

  const handleSizeWarningAccept = () => {
    if (selectedFile) {
      setShowSizeWarning(false);
      setValidation(null);
      setPromptCopied(false);
      setBuildLogs([]);
      setBuildStatus("");
      if (!appName) setAppName(selectedFile.name.replace(".zip", "").replace(/[^a-zA-Z0-9\s-]/g, ""));
      validateFile(selectedFile);
    }
  };

  const handleSizeWarningCancel = () => {
    setSelectedFile(null);
    setShowSizeWarning(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith(".zip")) {
      handleFileSelected(file);
    } else {
      setStatus(t("deploy.zip_only"));
    }
  }, [appName, t]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelected(file);
  };

  const handleReselect = () => {
    setSelectedFile(null);
    setValidation(null);
    setAppName("");
    setDescription("");
    setStatus("");
    setPromptCopied(false);
    setShowSizeWarning(false);
    setBuildLogs([]);
    setBuildStatus("");
    setShowBuildLog(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleDeploy = async () => {
    if (!selectedFile || !appName.trim()) return;
    setDeploying(true);
    setStatus(t("deploy.uploading"));
    setBuildLogs([]);
    setBuildStatus("building");
    setShowBuildLog(true);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("name", appName.trim());
      formData.append("description", description);
      formData.append("env_vars", "{}");

      // Start deploy — this triggers build on backend
      const result = await api.deployApp(formData);

      // After deploy completes, try to stream build logs
      if (result && result.id) {
        try {
          await api.streamBuildLogs(result.id, (data: any) => {
            if (data.line) {
              setBuildLogs(prev => [...prev, data.line]);
            }
            if (data.done) {
              setBuildStatus(data.status || "success");
            }
          });
        } catch {
          // SSE failed, that's ok — deploy already succeeded
        }
      }

      setBuildStatus("success");
      setStatus(t("deploy.success"));
      setSelectedFile(null);
      setAppName("");
      setDescription("");
      setValidation(null);
      onDeployed();
    } catch (e: any) {
      setBuildStatus("error");
      setStatus(`${t("deploy.fail")}: ${e.message}`);
    } finally {
      setDeploying(false);
    }
  };

  const copyPrompt = () => {
    if (!validation) return;
    const promptKey = `guide.prompt.${TYPE_PROMPT_MAP[validation.app_type] || "static"}`;
    const prompt = t(promptKey);
    navigator.clipboard.writeText(prompt).then(() => {
      setPromptCopied(true);
      setTimeout(() => setPromptCopied(false), 2500);
    });
  };

  const isValid = validation?.valid === true;
  const isInvalid = validation?.valid === false;
  const fileSizeMB = selectedFile ? (selectedFile.size / 1024 / 1024).toFixed(1) : "0";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center mb-3">
        <h3 className="font-semibold text-gray-900 text-sm">{t("deploy.title")}</h3>
        <DeployGuide />
      </div>

      {/* File Size Warning Popup */}
      {showSizeWarning && selectedFile && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl w-[440px] max-w-[90vw] overflow-hidden">
            {/* Warning header */}
            <div className="bg-amber-50 px-5 pt-5 pb-3">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl">⚠️</span>
                </div>
                <div>
                  <h3 className="text-sm font-bold text-amber-900">{t("deploy.file_too_large_title")}</h3>
                  <p className="text-xs text-amber-700 mt-0.5">{selectedFile.name} — {fileSizeMB} MB</p>
                </div>
              </div>
            </div>
            {/* Body */}
            <div className="px-5 py-4">
              <p className="text-xs text-gray-700 leading-relaxed">
                {t("deploy.file_too_large_msg").replace("{size}", fileSizeMB)}
              </p>
              <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="text-[10px] font-semibold text-blue-800 mb-1">🧹 Auto-Sanitize</p>
                <p className="text-[10px] text-blue-700">{t("deploy.auto_sanitize_desc")}</p>
              </div>
            </div>
            {/* Actions */}
            <div className="px-5 pb-5 flex gap-2">
              <button
                onClick={handleSizeWarningAccept}
                className="flex-1 py-2 bg-amber-500 text-white text-xs font-semibold rounded-lg hover:bg-amber-600 transition"
              >
                {t("deploy.auto_sanitize")}
              </button>
              <button
                onClick={handleSizeWarningCancel}
                className="flex-1 py-2 bg-gray-100 text-gray-700 text-xs font-medium rounded-lg hover:bg-gray-200 transition"
              >
                {t("deploy.cancel_upload")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Drop Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !selectedFile && fileRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-5 text-center transition-all ${
          dragging ? "border-brand-400 bg-brand-50"
            : selectedFile
              ? isValid ? "border-green-300 bg-green-50" : isInvalid ? "border-red-300 bg-red-50" : "border-blue-300 bg-blue-50"
            : "border-gray-300 hover:border-brand-300 hover:bg-gray-50 cursor-pointer"
        }`}
      >
        <input ref={fileRef} type="file" accept=".zip" onChange={handleFileSelect} className="hidden" />
        {selectedFile ? (
          <div className="flex items-center justify-center gap-2">
            <svg className="w-4 h-4 text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div>
              <p className={`font-medium text-xs ${isValid ? "text-green-700" : isInvalid ? "text-red-700" : "text-blue-700"}`}>{selectedFile.name}</p>
              <p className="text-[10px] text-gray-500 mt-0.5">
                {fileSizeMB} MB
                {parseFloat(fileSizeMB) > FILE_SIZE_WARN_MB && (
                  <span className="text-amber-600 ml-1">⚠️ {t("deploy.auto_sanitize_note")}</span>
                )}
              </p>
            </div>
          </div>
        ) : (
          <div>
            <svg className="w-7 h-7 mx-auto text-gray-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-gray-500 text-xs">{t("deploy.drag")}</p>
            <p className="text-[10px] text-gray-400 mt-0.5">{t("deploy.browse")}</p>
          </div>
        )}
      </div>

      {/* Validating spinner */}
      {validating && (
        <div className="mt-3 flex items-center gap-2 text-blue-600">
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-xs font-medium">{t("deploy.validating")}</span>
        </div>
      )}

      {/* Validation Result */}
      {validation && !validating && (
        <div className="mt-3">
          {/* Detected type badge */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-gray-500">{t("deploy.detected_type")}</span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-700">
              {TYPE_ICONS[validation.app_type] || "📦"} {t(`deploy.type.${validation.app_type}`)}
            </span>
          </div>

          {/* ✅ Valid */}
          {isValid && (
            <div className="flex items-center gap-2 p-2 bg-green-50 border border-green-200 rounded-lg">
              <svg className="w-4 h-4 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs text-green-700 font-medium">{t("deploy.valid")}</span>
            </div>
          )}

          {/* ❌ Invalid — Show issues + prompt */}
          {isInvalid && (
            <div className="space-y-2">
              {/* Issues */}
              <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-[10px] font-semibold text-red-700 uppercase tracking-wider mb-1.5">{t("deploy.issues")}</p>
                <ul className="space-y-1">
                  {validation.issues.map((issue, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[11px] text-red-600">
                      <svg className="w-3 h-3 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                      </svg>
                      {t(`deploy.issue.${issue}`)}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Recommended Prompt */}
              <div className="p-2.5 bg-brand-50 border border-brand-200 rounded-lg">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[10px] font-semibold text-brand-700">{t("deploy.fix_prompt_title")}</p>
                  <button
                    onClick={copyPrompt}
                    className={`flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-md transition-all ${
                      promptCopied
                        ? "bg-green-100 text-green-700"
                        : "bg-brand-600 text-white hover:bg-brand-700"
                    }`}
                  >
                    {promptCopied ? (
                      <>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        {t("deploy.prompt_copied")}
                      </>
                    ) : (
                      <>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        {t("deploy.copy_prompt")}
                      </>
                    )}
                  </button>
                </div>
                <pre className="text-[10px] text-gray-600 bg-white border border-gray-200 rounded p-2 whitespace-pre-wrap max-h-32 overflow-y-auto leading-relaxed">
                  {t(`guide.prompt.${TYPE_PROMPT_MAP[validation.app_type] || "static"}`)}
                </pre>
              </div>

              {/* Reselect button */}
              <button
                onClick={handleReselect}
                className="w-full py-1.5 text-xs text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition"
              >
                {t("deploy.reselect")}
              </button>
            </div>
          )}

          {/* Warnings (shown for both valid and invalid) */}
          {validation.warnings.length > 0 && (
            <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-[10px] font-semibold text-amber-700 uppercase tracking-wider mb-1">{t("deploy.warnings")}</p>
              <ul className="space-y-0.5">
                {validation.warnings.map((warn, i) => {
                  // Handle dynamic warnings with ":" parameters
                  // e.g. "dockerfile_db_dependency:src/server.js:MySQL"
                  //      "dockerfile_cmd_missing_file:src/server.js"
                  //      "multiple_server_files:src/server.js,src/local-server.js"
                  const parts = warn.split(":");
                  const key = parts[0];
                  let message = t(`deploy.warn.${key}`);
                  const isCritical = warn.startsWith("dockerfile_db_dependency") || warn.startsWith("dockerfile_cmd_missing_file");

                  if (parts.length >= 2) {
                    message = message.replace("{file}", parts[1]);
                    if (parts.length >= 3) message = message.replace("{db}", parts[2]);
                    message = message.replace("{files}", parts.slice(1).join(", "));
                  }

                  // Fallback: if translation not found, show raw key
                  if (message === `deploy.warn.${key}`) message = warn;

                  return (
                    <li key={i} className={`flex items-start gap-1.5 text-[10px] ${isCritical ? "text-red-700 font-semibold" : "text-amber-700"}`}>
                      <span className="mt-px">{isCritical ? "🚨" : "⚠️"}</span>
                      {message}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Deploy form — only show when valid */}
      {selectedFile && isValid && (
        <div className="mt-3 space-y-2">
          <input type="text" value={appName} onChange={(e) => setAppName(e.target.value)}
            placeholder={t("deploy.name")}
            className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
          <input type="text" value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder={t("deploy.desc")}
            className="w-full px-2.5 py-1.5 border border-gray-300 rounded-md text-xs focus:ring-2 focus:ring-brand-500 focus:border-transparent outline-none" />
          <div className="flex gap-2">
            <button onClick={handleDeploy} disabled={deploying || !appName.trim()}
              className="flex-1 py-1.5 bg-brand-600 text-white font-medium rounded-md hover:bg-brand-700 transition disabled:opacity-50 text-xs">
              {deploying ? t("deploy.deploying") : t("deploy.submit")}
            </button>
            <button onClick={handleReselect} disabled={deploying}
              className="py-1.5 px-4 text-xs text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition disabled:opacity-50">
              {t("deploy.cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Build Log Viewer */}
      {showBuildLog && buildLogs.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-wider">
                {t("deploy.build_log_title")}
              </p>
              {buildStatus === "building" && (
                <svg className="w-3 h-3 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {buildStatus === "success" && <span className="text-green-500 text-xs">✓</span>}
              {buildStatus === "error" && <span className="text-red-500 text-xs">✗</span>}
              {buildStatus === "timeout" && <span className="text-amber-500 text-xs">⏱</span>}
            </div>
            <button onClick={() => setShowBuildLog(false)} className="text-[10px] text-gray-400 hover:text-gray-600">
              ✕ {t("deploy.close")}
            </button>
          </div>
          <div className="bg-gray-900 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-[10px] leading-relaxed">
            {buildLogs.map((line, i) => (
              <div key={i} className={`${
                line.includes("✓") ? "text-green-400" :
                line.includes("✗") ? "text-red-400" :
                line.includes("[IVS]") ? "text-blue-400" :
                line.includes("Step") ? "text-yellow-300" :
                "text-gray-300"
              }`}>
                {line}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
          {buildStatus === "timeout" && (
            <div className="mt-1.5 p-2 bg-amber-50 border border-amber-200 rounded text-[10px] text-amber-700">
              ⏱ {t("deploy.build_timeout")}
            </div>
          )}
        </div>
      )}

      {status && !showBuildLog && (
        <p className={`mt-2 text-[10px] ${status.includes("fail") || status.includes("ล้มเหลว") || status.includes("กรุณา") ? "text-red-600" : "text-green-600"}`}>
          {status}
        </p>
      )}
    </div>
  );
}
