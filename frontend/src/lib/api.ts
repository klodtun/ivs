// ─── API Catalog types ──────────────────────────────────────────── //
export interface CatalogEntry {
  id: number;
  app_id: number | null;
  name: string;
  method: string;
  path: string;
  base_url: string;
  full_url: string;
  api_key: string | null;
  has_api_key: boolean;
  schema_snippet: string | null;
  schema_size: number;
  description: string;
  category: string;
  current_version: number;
  last_test_at: string | null;
  last_test_status: string;
  last_test_message: string;
  last_test_http_code: number | null;
  last_test_latency_ms: number | null;
  is_active: boolean;
  discovery_source: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface CatalogVersion {
  id: number;
  catalog_id: number;
  version_number: number;
  base_url: string;
  has_api_key: boolean;
  method: string;
  path: string;
  replaced_by_id: number | null;
  reason: string;
  created_at: string | null;
}

// ─── Enterprise types ────────────────────────────────────────────────────── //
export interface MachineRegistryEntry {
  id: number;
  fingerprint: string;
  serial: string | null;
  hostname: string | null;
  ip_address: string | null;
  port: number;
  edition: string;
  group_name: string | null;
  notes: string | null;
  is_self: boolean;
  discovery_source: string;
  last_seen: string | null;
  created_at: string;
}

export interface DiscoveredMachine {
  hostname: string | null;
  ip_address: string;
  port: number;
  product: string | null;
  version: string | null;
  fingerprint: string | null;
  already_registered: boolean;
}
// ─────────────────────────────────────────────────────────────────────────── //

const API_BASE = "/api";
const BACKEND_DIRECT =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000/api`
    : "/api";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    // Body may be JSON (FastAPI {detail}) or an HTML error page (e.g. the
    // dev server mid-recompile). Fall back to the HTTP status so failures
    // are diagnosable instead of an opaque "Request failed".
    const err = await res.json().catch(() => null);
    const detail = err?.detail;
    const msg =
      (typeof detail === "string" && detail) ||
      `Request failed (HTTP ${res.status})`;
    throw new Error(msg);
  }

  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request("/auth/logout", { method: "POST" }),

  getMe: () => request<any>("/auth/me"),

  hasDefaultAdmin: () =>
    request<{ exists: boolean }>("/auth/default-admin-exists"),

  adminCount: () =>
    request<{ count: number }>("/auth/admin-count"),

  factoryResetLastAdmin: () =>
    request<{ reset: string; username: string; previous?: string }>(
      "/auth/factory-reset-last-admin",
      { method: "POST" }
    ),

  dockerStatus: () =>
    request<{ running: boolean }>("/system/docker/status"),

  shutdownIvs: () =>
    request<{ shutting_down: boolean; delay_seconds: number }>(
      "/system/shutdown", { method: "POST" }
    ),

  dockerStart: () =>
    request<{
      already_running: boolean;
      ready: boolean;
      launch?: { system: string; method: string | null; launched: boolean; error: string | null };
      message?: string;
    }>("/system/docker/start", { method: "POST" }),

  getUsers: () => request<any[]>("/auth/users"),

  createUser: (data: {
    username: string;
    email: string;
    password: string;
    role: string;
  }) =>
    request<any>("/auth/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateUser: (id: number, data: any) =>
    request<any>(`/auth/users/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Dedicated disable endpoint — requires the admin's own password.
  // Re-enabling goes through the regular updateUser({is_active: true}) call.
  disableUser: (id: number, password: string) =>
    request<any>(`/auth/users/${id}/disable`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }),

  deleteUser: (id: number, password: string) =>
    request<{ message: string; reassigned_apps: number; new_owner: string }>(
      `/auth/users/${id}`,
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      }
    ),

  getUserAccess: (id: number) =>
    request<{ user_id: number; app_ids: number[]; access_all: boolean }>(`/auth/users/${id}/access`),

  setUserAccess: (id: number, data: { user_id: number; app_ids: number[]; access_all: boolean }) =>
    request<any>(`/auth/users/${id}/access`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  getApps: () => request<any[]>("/apps"),

  getApp: (id: number) => request<any>(`/apps/${id}`),

  validateApp: async (file: File) => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${BACKEND_DIRECT}/apps/validate`, {
      method: "POST",
      headers,
      body: fd,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Validation failed" }));
      throw new Error(err.detail || "Validation failed");
    }
    return res.json() as Promise<{
      valid: boolean;
      app_type: string;
      issues: string[];
      warnings: string[];
      files: string[];
    }>;
  },

  deployApp: async (formData: FormData) => {
    // Upload large files directly to backend (bypass Next.js proxy for reliability)
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${BACKEND_DIRECT}/apps`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      const detail = err?.detail;
      // Structured rejects (e.g. edition gate) return an object detail with
      // localized messages — surface the one matching the active locale.
      if (detail && typeof detail === "object") {
        const loc =
          typeof window !== "undefined"
            ? localStorage.getItem("ivs_locale") || "th"
            : "th";
        const msg =
          loc === "th"
            ? detail.message_th || detail.message_en
            : detail.message_en || detail.message_th;
        const e = new Error(msg || "Request failed") as Error & { code?: string };
        e.code = detail.code;
        throw e;
      }
      throw new Error(detail || "Request failed");
    }
    return res.json();
  },

  setAppLogo: (id: number, logoData: string) => {
    const fd = new FormData();
    fd.append("logo_data", logoData);
    return request<{ message: string; has_logo: boolean }>(`/apps/${id}/logo`, {
      method: "PUT",
      body: fd,
    });
  },

  startApp: (id: number) =>
    request<any>(`/apps/${id}/start`, { method: "POST" }),

  stopApp: (id: number) =>
    request<any>(`/apps/${id}/stop`, { method: "POST" }),

  restartApp: (id: number) =>
    request<any>(`/apps/${id}/restart`, { method: "POST" }),

  deleteApp: (id: number) =>
    request<any>(`/apps/${id}`, { method: "DELETE" }),

  exportApp: (id: number) =>
    request<{
      filename: string;
      size_bytes: number;
      size_human: string;
      data_paths_copied: number;
      data_paths_skipped: number;
      errors: string[];
      download_url: string;
    }>(`/apps/${id}/export`, { method: "POST" }),

  getAppLogs: (id: number) => request<{ logs: string }>(`/apps/${id}/logs`),

  streamBuildLogs: async (id: number, onLog: (data: any) => void): Promise<void> => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/apps/${id}/build-logs`, { headers });
    if (!res.ok || !res.body) return;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            onLog(data);
            if (data.done) return;
          } catch {}
        }
      }
    }
  },

  getAppVersions: (id: number) => request<any[]>(`/apps/${id}/versions`),

  getSystemHealth: () => request<any>("/system/health"),

  getAuditLogs: () => request<any[]>("/system/audit-logs"),

  getTunnels: () => request<any[]>("/tunnels"),

  createTunnel: (appId: number, durationMinutes: number) =>
    request<any>("/tunnels", {
      method: "POST",
      body: JSON.stringify({
        app_id: appId,
        duration_minutes: durationMinutes,
      }),
    }),

  revokeTunnel: (id: number) =>
    request<any>(`/tunnels/${id}`, { method: "DELETE" }),

  getTunnelConfig: () =>
    request<{
      provider: string;
      ngrok_token_masked: string;
      cloudflare_token_masked: string;
      ngrok_configured: boolean;
      cloudflare_configured: boolean;
    }>("/tunnels/config"),

  updateTunnelConfig: (body: {
    provider?: string;
    ngrok_token?: string;
    cloudflare_token?: string;
  }) =>
    request<{ message: string }>("/tunnels/config", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getVaultKeys: () => request<any[]>("/vault"),

  getVaultKey: (id: number) => request<any>(`/vault/${id}`),

  createVaultKey: (data: {
    name: string;
    provider: string;
    category: string;
    value: string;
    description: string;
  }) =>
    request<any>("/vault", { method: "POST", body: JSON.stringify(data) }),

  deleteVaultKey: (id: number, password: string) =>
    request<any>(`/vault/${id}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }),

  revealVaultKey: (id: number) =>
    request<{ id: number; name: string; value: string }>(
      `/vault/${id}/reveal`,
      { method: "POST" }
    ),

  healthCheck: () => request<{ status: string }>("/health"),

  getNtpStatus: () => request<{
    synced: boolean;
    ntp_server: string | null;
    ntp_server_name: string | null;
    ntp_authority: string | null;
    ntp_stratum: number | null;
    offset_ms: number;
    last_sync: string | null;
    sync_count: number;
  }>("/ntp-status"),

  // Audit Log Export — accepts optional date range and chunk size
  exportAuditLogs: (opts?: {
    start_date?: string | null;
    end_date?: string | null;
    max_records_per_file?: number;
  }) =>
    request<any>("/system/audit-logs/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts || {}),
    }),

  getAuditLogExports: () => request<any[]>("/system/audit-logs/exports"),

  // Retention policy (per พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560 §26)
  getRetentionSettings: () =>
    request<{
      [logType: string]: {
        days: number;
        default: number;
        min: number;
        max_recommended: number;
        max_allowed: number;
      };
    }>("/system/retention"),

  updateRetentionSettings: (values: Record<string, number>) =>
    request<any>("/system/retention", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    }),

  getGiteaCredentials: () =>
    request<{ username: string; password: string; is_default: boolean }>(
      "/system/gitea-credentials"
    ),

  updateGiteaCredentials: (username: string, password: string) =>
    request<{ username: string; password: string; is_default: boolean }>(
      "/system/gitea-credentials",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      }
    ),

  // GDPR / APPI / PDPA — Right to be Forgotten
  previewGdprErasure: (target_type: string, target_value: string) =>
    request<{ target_type: string; rows_affected: Record<string, number> }>(
      "/system/gdpr/erasure/preview",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_type, target_value }),
      }
    ),

  executeGdprErasure: (
    target_type: string,
    target_value: string,
    reason: string,
    legal_basis: string,
    password: string
  ) =>
    request<{
      id: number;
      target_hash: string;
      rows_affected: Record<string, number>;
      sha256_proof: string;
      certificate: string;
      created_at: string | null;
    }>("/system/gdpr/erasure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_type, target_value, reason, legal_basis, password }),
    }),

  listGdprErasures: () =>
    request<Array<{
      id: number;
      target_type: string;
      target_hash: string;
      reason: string;
      legal_basis: string;
      requested_by: number;
      requested_ip: string | null;
      rows_affected: Record<string, number>;
      sha256_proof: string;
      created_at: string | null;
    }>>("/system/gdpr/erasure/history"),

  triggerRetentionPurge: (password: string) =>
    request<Record<string, number>>("/system/retention/purge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    }),

  downloadAuditLogExport: (id: number) =>
    `${API_BASE}/system/audit-logs/exports/${id}/download`,

  // Resources
  getResources: () => request<any>("/system/resources"),

  getResourceHistory: (hours: number = 24) =>
    request<any[]>(`/system/resources/history?hours=${hours}`),

  exportResourceReport: () =>
    request<{ filename: string; sha256_hash: string; download_url: string }>(
      "/system/resources/export",
      { method: "POST" }
    ),

  downloadResourceReport: (filename: string) =>
    `${API_BASE}/system/resources/export/${filename}`,

  // mDNS
  getMdnsStatus: () => request<{
    running: boolean;
    hostname: string;
    mdns_address: string;
    default_hostname: string;
    ip: string;
    port: number;
    saved_hostname: string;
    enabled: boolean;
  }>("/system/mdns"),

  updateMdnsHostname: (hostname: string) =>
    request<any>("/system/mdns", {
      method: "PUT",
      body: JSON.stringify({ hostname }),
    }),

  toggleMdns: (enabled: boolean) =>
    request<{ enabled: boolean; ip: string; port: number; running: boolean }>(
      "/system/mdns/toggle",
      { method: "PUT", body: JSON.stringify({ enabled }) }
    ),

  getLanIp: () =>
    request<{
      ip: string;
      port: number;
      url: string;
      mdns_running: boolean;
      mdns_address: string | null;
    }>("/system/lan-ip"),

  resetMdnsHostname: () =>
    request<any>("/system/mdns/reset", { method: "POST" }),

  // Network Info
  getNetworkInfo: () => request<{
    server_ip: string;
    hostname: string;
    gateway: string | null;
    dns_servers: string[];
    interfaces: {
      name: string;
      ipv4: string | null;
      netmask: string | null;
      mac: string | null;
      is_up: boolean;
      speed: number;
    }[];
    internet: boolean;
    mdns_available: boolean;
    mdns_hostname: string | null;
    mdns_service: string | null;
    platform: string;
  }>("/system/network"),

  getLicense: () =>
    request<{
      serial: string;
      edition: string;
      region: string;
      fingerprint: string;
      fingerprint_current: string;
      fingerprint_status: string;
      created_at: string | null;
      bound_file: string;
      serial_valid: boolean;
    }>("/system/license"),

  // DNS Config
  getDNSConfig: () => request<{ domain_suffix: string; server_ip: string }>("/system/dns-config"),

  updateDNSConfig: (domain_suffix: string) =>
    request<{ domain_suffix: string; server_ip: string }>("/system/dns-config", {
      method: "PUT",
      body: JSON.stringify({ domain_suffix }),
    }),

  // PDPA / ROPA
  getPdpaRecords: () => request<any[]>("/pdpa"),

  getPasswordPolicy: () => request<{
    min_length: number;
    require_upper: boolean;
    require_lower: boolean;
    require_number: boolean;
    require_symbol: boolean;
  }>("/pdpa/password-policy"),

  updatePasswordPolicy: (policy: {
    min_length?: number;
    require_upper?: boolean;
    require_lower?: boolean;
    require_number?: boolean;
    require_symbol?: boolean;
  }) => request<any>("/pdpa/password-policy", {
    method: "PUT",
    body: JSON.stringify(policy),
  }),

  getPdpaRecord: (appId: number) => request<any>(`/pdpa/${appId}`),

  updatePdpaRecord: (appId: number, data: {
    purpose?: string;
    pii_fields?: string[];
    retention_period?: string;
    security_notes?: string;
    anonymization_mode?: string;
  }) =>
    request<any>(`/pdpa/${appId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  getAnonymizationPrompt: (appId: number) =>
    request<{
      app_id: number;
      app_name: string;
      detected_fields: string[];
      current_mode: string;
      prompts: { anonymous: string; pseudonymous: string };
    }>(`/pdpa/${appId}/anonymization-prompt`),

  scanAppPii: (appId: number) =>
    request<any>(`/pdpa/${appId}/scan`, { method: "POST" }),

  scanAllAppsPii: () =>
    request<any>("/pdpa/scan-all", { method: "POST" }),

  exportRopa: () =>
    request<{ filename: string; sha256_hash: string; download_url: string; record_count: number }>(
      "/pdpa/export",
      { method: "POST" }
    ),

  downloadRopaReport: (filename: string) =>
    `${API_BASE}/pdpa/export/${filename}`,

  // Privacy Notice
  getPrivacyNotice: (appId: number) =>
    request<{
      app_id: number;
      app_name: string;
      app_slug: string;
      privacy_notice_enabled: boolean;
      privacy_notice_title: string;
      privacy_notice_detail: string;
      privacy_policy_url: string;
      privacy_notice_url: string;
    }>(`/pdpa/${appId}/privacy-notice`),

  getPrivacyNoticeBySlug: (slug: string) =>
    request<{
      app_id: number;
      app_name: string;
      app_slug: string;
      privacy_notice_enabled: boolean;
      privacy_notice_title: string;
      privacy_notice_detail: string;
      privacy_policy_url: string;
      privacy_notice_url: string;
    }>(`/pdpa/privacy-notice/by-slug/${slug}`),

  // PDPA Consent — accept/decline tracking per user, per app
  recordPdpaConsent: (appId: number, decision: "accepted" | "declined") =>
    request<{
      id: number;
      decision: string;
      app_id: number;
      notice_version: string | null;
      created_at: string | null;
    }>(`/pdpa/${appId}/consent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }),

  getMyPdpaConsent: (appId: number) =>
    request<{
      id?: number;
      decision: "accepted" | "declined" | null;
      created_at: string | null;
      notice_version?: string | null;
    }>(`/pdpa/${appId}/consent`),

  listMyPdpaConsents: () =>
    request<Array<{
      app_id: number;
      app_name: string;
      app_slug: string;
      decision: "accepted" | "declined";
      created_at: string | null;
      notice_version: string | null;
    }>>(`/pdpa/consents/mine`),

  updatePrivacyNotice: (appId: number, data: {
    privacy_notice_enabled?: boolean;
    privacy_notice_title?: string;
    privacy_notice_detail?: string;
    privacy_policy_url?: string;
    privacy_notice_url?: string;
  }) =>
    request<any>(`/pdpa/${appId}/privacy-notice`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Enterprise — Machine Registry
  getEnterpriseself: () =>
    request<MachineRegistryEntry>("/enterprise/machines/self"),

  listEnterpriseMachines: () =>
    request<MachineRegistryEntry[]>("/enterprise/machines"),

  addEnterpriseMachine: (data: {
    fingerprint: string;
    serial?: string;
    hostname?: string;
    ip_address?: string;
    port?: number;
    group_name?: string;
    notes?: string;
  }) =>
    request<MachineRegistryEntry>("/enterprise/machines", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  patchEnterpriseMachine: (fingerprint: string, data: {
    group_name?: string;
    notes?: string;
    hostname?: string;
  }) =>
    request<MachineRegistryEntry>(`/enterprise/machines/${fingerprint}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  removeEnterpriseMachine: (fingerprint: string) =>
    request<void>(`/enterprise/machines/${fingerprint}`, { method: "DELETE" }),

  discoverEnterpriseMachines: () =>
    request<DiscoveredMachine[]>("/enterprise/machines/discover"),

  // ── API Catalog ────────────────────────────────────────────────────────── //
  listCatalog: () =>
    request<CatalogEntry[]>("/catalog"),

  getCatalogEntry: (id: number) =>
    request<CatalogEntry>(`/catalog/${id}`),

  createCatalogEntry: (data: {
    name: string;
    base_url: string;
    method?: string;
    path?: string;
    api_key?: string;
    api_schema?: string;
    description?: string;
    category?: string;
    app_id?: number;
  }) =>
    request<CatalogEntry>("/catalog", { method: "POST", body: JSON.stringify(data) }),

  scanCatalog: () =>
    request<{
      scanned: number;
      new: number;
      updated: number;
      failed: number;
      details: { slug: string; status: string }[];
    }>("/catalog/scan", { method: "POST" }),

  testCatalogEntry: (id: number) =>
    request<{
      status: string;
      http_code: number | null;
      latency_ms: number;
      message: string;
      body_snippet: string;
    }>(`/catalog/${id}/test`, { method: "POST" }),

  replaceCatalogEntry: (id: number, data: {
    base_url?: string;
    api_key?: string;
    api_schema?: string;
    method?: string;
    path?: string;
    reason?: string;
  }) =>
    request<CatalogEntry>(`/catalog/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  getCatalogHistory: (id: number) =>
    request<CatalogVersion[]>(`/catalog/${id}/history`),

  restoreCatalogVersion: (entryId: number, versionId: number) =>
    request<CatalogEntry>(`/catalog/${entryId}/restore/${versionId}`, { method: "POST" }),

  revealCatalogKey: (id: number) =>
    request<CatalogEntry>(`/catalog/${id}/reveal-key`, { method: "POST" }),

  deleteCatalogEntry: (id: number) =>
    request<void>(`/catalog/${id}`, { method: "DELETE" }),

  // ─── OpenCLI Bridge (Pro/Enterprise) ──────────────────────────── //
  listBridgeImports: (includeDeleted = false) =>
    request<BridgeImport[]>(`/opencli/imports?include_deleted=${includeDeleted}`),

  createBridgeImport: (data: {
    source_kind: string;
    source_ref: string;
    pii_profile: "exclude" | "anonymize";
    project_id?: number | null;
  }) =>
    request<BridgeImport>(`/opencli/imports`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getBridgeDashboard: () => request<BridgeDashboard>(`/opencli/dashboard`),
  bridgeChat: (message: string, project_id?: number | null) =>
    request<{ provider: string; mode: string; reply: string }>(`/opencli/chat`, {
      method: "POST",
      body: JSON.stringify({ message, project_id: project_id ?? null }),
    }),

  analyzeProjectCode: (projectId: number, path: string) =>
    request<BridgeCodeReport>(`/opencli/projects/${projectId}/analyze-code`, {
      method: "POST",
      body: JSON.stringify({ path }),
    }),

  listBridgeProjects: () => request<BridgeProject[]>(`/opencli/projects`),
  createBridgeProject: (name: string, description?: string) =>
    request<{ id: number; name: string; slug: string }>(`/opencli/projects`, {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),

  listImportModules: (importId: number) =>
    request<{ module: string; tables: string[]; commands: number }[]>(
      `/opencli/imports/${importId}/modules`
    ),
  generateModule: (importId: number, module: string, model_id?: number | null) =>
    request<BridgeRegenResult>(`/opencli/imports/${importId}/regen/module`, {
      method: "POST",
      body: JSON.stringify({ module, model_id: model_id ?? null }),
    }),

  getBridgeLlmModels: () =>
    request<{
      models: BridgeLlmModel[];
      vault_keys: { id: number; name: string; provider: string; category: string }[];
    }>(`/opencli/llm/models`),
  createBridgeLlmModel: (data: {
    label: string;
    provider: string;
    model: string;
    base_url?: string;
    vault_key_id?: number | null;
  }) =>
    request<{ id: number; label: string }>(`/opencli/llm/models`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  testBridgeLlmModel: (id: number) =>
    request<{ ok: boolean; detail: string }>(`/opencli/llm/models/${id}/test`, {
      method: "POST",
    }),
  deleteBridgeLlmModel: (id: number) =>
    request<{ ok: boolean }>(`/opencli/llm/models/${id}`, { method: "DELETE" }),

  mergeDeployImport: (importId: number, name: string, deploy: boolean) =>
    request<{
      merged_code_id: number;
      version: number;
      files: number;
      deploy: { app_id: number; slug: string; port: number; status: string } | null;
      deploy_error?: string;
    }>(`/opencli/imports/${importId}/merge-deploy`, {
      method: "POST",
      body: JSON.stringify({ name, deploy }),
    }),

  listImportCode: (importId: number) =>
    request<BridgeCodeVersion[]>(`/opencli/imports/${importId}/code`),
  deployCode: (codeId: number, name: string) =>
    request<{ app_id: number; slug: string; port: number; status: string }>(
      `/opencli/code/${codeId}/deploy`,
      { method: "POST", body: JSON.stringify({ name }) }
    ),
  deleteCode: (codeId: number, password: string, reason?: string) =>
    request<{ ok: boolean }>(`/opencli/code/${codeId}`, {
      method: "DELETE",
      body: JSON.stringify({ password, reason }),
    }),
  exportCodeUrl: (codeId: number) => `/opencli/code/${codeId}/export`,

  listMcpTokens: (projectId: number) =>
    request<BridgeMcpToken[]>(`/opencli/projects/${projectId}/tokens`),
  createMcpToken: (projectId: number, name: string, scope: string) =>
    request<{ id: number; name: string; scope: string; token: string; note: string }>(
      `/opencli/projects/${projectId}/tokens`,
      { method: "POST", body: JSON.stringify({ name, scope }) }
    ),
  revokeMcpToken: (tokenId: number) =>
    request<{ ok: boolean }>(`/opencli/tokens/${tokenId}`, { method: "DELETE" }),

  preflightBridgeImport: (data: { source_kind: string; source_ref: string }) =>
    request<BridgePreflight>(`/opencli/imports/preflight`, {
      method: "POST",
      body: JSON.stringify({ ...data, pii_profile: "exclude" }),
    }),

  getBridgeManifest: (id: number) =>
    request<any[]>(`/opencli/imports/${id}/manifest`),

  getBridgeStructure: (id: number) =>
    request<{ import_id: number; structure_md: string }>(
      `/opencli/imports/${id}/structure`
    ),

  getBridgeRoundtrip: (id: number) =>
    request<BridgeRoundtrip>(`/opencli/imports/${id}/roundtrip`),

  getBridgeLlmConfig: () =>
    request<BridgeLlmConfig>(`/opencli/llm/config`),

  setBridgeLlmConfig: (data: {
    provider: string;
    model?: string;
    base_url?: string;
    api_key?: string;
  }) =>
    request<BridgeLlmConfig>(`/opencli/llm/config`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  testBridgeLlm: () =>
    request<{ provider: string; ok: boolean; detail: string }>(
      `/opencli/llm/test`,
      { method: "POST" }
    ),

  generateBridgeRegen: (id: number) =>
    request<BridgeRegenResult>(`/opencli/imports/${id}/regen/generate`, {
      method: "POST",
    }),

  rebuildBridgeIndex: (id: number) =>
    request<{ import_id: number; backend: string; chunks: number }>(
      `/opencli/imports/${id}/index/rebuild`,
      { method: "POST" }
    ),

  queryBridgeIndex: (id: number, text: string, k = 5) =>
    request<{ import_id: number; query: string; results: BridgeChunkHit[] }>(
      `/opencli/imports/${id}/index/query`,
      { method: "POST", body: JSON.stringify({ text, k }) }
    ),

  deleteBridgeImport: (id: number, password: string, reason?: string) =>
    request<BridgeDeletion>(`/opencli/imports/${id}`, {
      method: "DELETE",
      body: JSON.stringify({ password, reason }),
    }),

  listBridgeDeletions: () =>
    request<BridgeDeletion[]>(`/opencli/deletions`),
};

// ─── OpenCLI Bridge types ─────────────────────────────────────────── //
export interface BridgeImport {
  id: number;
  importer_id: number | null;
  source_kind: string;
  source_ref: string;
  source_bytes: number;
  sha256_raw: string;
  pii_profile: "exclude" | "anonymize";
  status: string;
  artifact_dir: string | null;
  manifest_sha: string | null;
  command_count: number | null;
  created_at: string;
}

export interface BridgeDeletion {
  id: number;
  import_id: number;
  deleted_by: number | null;
  reason: string | null;
  sha256_raw: string;
  deleted_at: string;
}

export interface BridgeLlmModel {
  id: number;
  label: string;
  provider: string;
  model: string;
  base_url: string;
  vault_key_id: number | null;
  vault_key_name: string | null;
}

export interface BridgeCodeReport {
  root: string;
  files: number;
  modules: Record<string, string[]>;
  tables_referenced: string[];
  roles: string[];
  secrets: { file: string; kind: string }[];
  secret_count: number;
}

export interface BridgeDashboard {
  projects: number;
  imports: number;
  code_versions: number;
  deployed: number;
  active_tokens: number;
  provider: string;
  provider_has_key: boolean;
  edition: string;
}

export interface BridgeProject {
  id: number;
  name: string;
  slug: string;
  description: string;
  owner_id: number | null;
  imports: number;
  code_versions: number;
  created_at: string;
}

export interface BridgeCodeVersion {
  id: number;
  project_id: number;
  import_id: number;
  version: number;
  module?: string | null;
  provider: string;
  model: string | null;
  files_count: number;
  app_type: string | null;
  verify_ok: boolean;
  status: string;
  deployed_app_id: number | null;
  sha256: string | null;
  created_at: string;
}

export interface BridgeMcpToken {
  id: number;
  name: string;
  prefix: string;
  scope: string;
  created_at: string;
  last_used_at: string | null;
  revoked: boolean;
}

export interface BridgeLlmConfig {
  provider: string;
  model: string;
  base_url: string;
  has_key: boolean;
  available_providers: { name: string; needs_key: boolean }[];
}

export interface BridgeRegenResult {
  import_id: number;
  module?: string | null;
  provider: string;
  mode: string;
  model: string | null;
  files: number;
  candidate_dir: string | null;
  verify: { app_type: string | null; issues: string[]; ok: boolean } | null;
  note: string;
  brief: any | null;
}

export interface BridgeFinding {
  severity: "critical" | "warn" | "info";
  code: string;
  target: string;
  message: string;
  recommendation: string;
}

export interface BridgePreflight {
  site: string;
  source_kind: string;
  tables: number;
  total_rows: number;
  recommended_pii_profile: "exclude" | "anonymize";
  recommended_exclude_tables: string[];
  findings: BridgeFinding[];
}

export interface BridgeChunkHit {
  id: string;
  kind: string;
  ref: string;
  score: number;
  text: string;
  metadata: Record<string, any>;
}

export interface BridgeRoundtrip {
  import_id: number;
  site: string;
  pii_profile: string;
  tables_total: number;
  tables_matched: number;
  columns_expected: number;
  columns_correct: number;
  pii_dropped: number;
  fidelity: number;
  passed: boolean;
  defects: { table: string; missing: string[]; extra: string[] }[];
}
