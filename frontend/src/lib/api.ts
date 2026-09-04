// ─── Vault scoping — ตัวตน / กลุ่ม / ความสามารถ ─────────────────── //
export interface VaultGrantRow {
  grant_id: number;
  app_id: number;
  slug: string;
  name: string;
  capability: string;
  expires_at: string | null;
  // ชื่อที่แอปตัวนี้จะได้รับจริง อาจต่างจากชื่อของกุญแจเมื่อสองระบบอ่านคนละชื่อ
  env_name: string;
  env_overridden: boolean;
  env_valid: boolean;
}

export interface VaultScopeKey {
  id: number;
  name: string;
  provider: string;
  /** general | ai | maps | weather | finance | other — ใช้จัดกลุ่มบนหน้าแรก */
  category: string;
  namespace: string;
  namespace_explicit: boolean;
  env_name: string;
  env_derived: string;
  env_overridden: boolean;
  // ชื่อที่โปรแกรมอ่านไม่ได้ = กุญแจที่ส่งไปแล้วไม่มีใครใช้
  env_valid: boolean;
  allow_reveal: boolean;
  granted_to: VaultGrantRow[];
  grant_count: number;
}

export interface VaultScopeOverview {
  keys: VaultScopeKey[];
  apps: { app_id: number; slug: string; name: string; status: string; key_count: number; keys: string[] }[];
  namespaces: { namespace: string; keys: number }[];
  totals: {
    keys: number; keys_ungranted: number; keys_no_reveal: number; keys_bad_env: number;
    grants_bad_env: number;
    apps: number; apps_without_keys: number;
  };
  migration: {
    total_keys: number;
    apps: { slug: string; name: string; had_before: number; has_now: number; loses: number }[];
  };
}

// ─── Business flow ──────────────────────────────────────────────── //
export interface FlowStepRow {
  id: number;
  flow_key: string;
  flow_label: string;
  step_no: number;
  label: string;
  app_id: number | null;
  app_name: string | null;
  app_slug: string | null;
  api_entry_id: number | null;
  // ขั้นที่ตรวจไม่ได้มีสองแบบ — คนทำเองตลอดไป กับยังไม่ได้เชื่อม (งานที่ค้าง)
  unbound_kind: "manual" | "planned";
  // unverified = ยังไม่เคยตรวจ หรือเป็นขั้นที่คนทำเอง — ไม่ใช่ "พัง"
  status: "unverified" | "ok" | "drifted" | "broken";
  drift_note: string;
  verified_at: string | null;
  latency_ms: number | null;
  http_code: number | null;
}

export interface Flow {
  flow_key: string;
  flow_label: string;
  steps: FlowStepRow[];
  ok: number;
  drifted: number;
  broken: number;
  unverified: number;
}

// ─── System map ─────────────────────────────────────────────────── //
export interface MapNode {
  id: number;
  slug: string;
  name: string;
  status: string;
  port: number | null;
  version: number;
  access_mode: string;
  pii_fields: number;
  pii_unconfirmed: number;
  pdpa_declared: boolean;
  retention: string;
  tunnel_open: boolean;
  has_schema: boolean;
  catalog_seen_at: string | null;
  // ผลยิงจริงครั้งล่าสุด — ไม่ใช่การอนุมานจากสถานะคอนเทนเนอร์
  reach_status: "OK" | "FAIL" | "UNKNOWN";
  reach_http: number | null;
  reach_ms: number | null;
  reach_at: string | null;
  reach_message: string;
}

export interface DependencyEdge {
  id: number;
  from_app_id: number;
  to_app_id: number | null;
  target: string;
  external: boolean;
  kind: "http_api" | "database" | "external";
  origin: "scan" | "declared" | "inferred" | "token";
  evidence: string;
  /** ชี้ไปที่แถวจริงที่ทำให้เส้นนี้เกิด — null เมื่อไม่มีอะไรให้ชี้ */
  evidence_ref: {
    kind: "token" | "app" | "person";
    token_id?: number; app_id?: number; label?: string;
    user?: string | null; at?: string | null;
  } | null;
  confirmed: boolean;
  last_seen_at: string | null;
}

/** ภาพรวมหน้าแรก — สี่มุมมอง กรองตามสิทธิ์ของผู้เรียกแล้ว */
export interface SystemOverview {
  generated_at: string;
  role: string;
  performance: {
    cpu_percent: number | null;
    memory_percent: number | null;
    disk_percent: number | null;
    measured_at: string | null;
    trend: { at: string | null; cpu: number; mem: number }[];
    apps_total: number;
    apps_stopped: number;
    unreachable: number;
    never_tested: number;
    slowest: { slug: string; ms: number }[];
    /** รายการจริงเบื้องหลังตัวเลข — ใช้ตรวจว่านับอะไรอยู่ */
    details?: Record<string, string[]>;
    /** เรียงตามหน่วยความจำ — CPU ณ วินาทีเดียวกระโดดเกินกว่าจะจัดอันดับได้ */
    top_consumers: { slug: string; memory_mb: number; cpu_percent: number }[];
  };
  privacy: {
    fields_total: number;
    fields_unconfirmed: number;
    apps_no_purpose: number;
    apps_no_purpose_examples: string[];
    apps_no_retention: number;
    external_targets: number;
    details?: Record<string, string[]>;
  };
  risk: {
    edges_total: number;
    edges_unconfirmed: number;
    apps_without_edges: number;
    steps_broken: number;
    steps_drifted: number;
    steps_planned: number;
    changes_unassessed: number;
    details?: Record<string, string[]>;
  };
  /** AI ที่มีอยู่จริง — โมเดล ปลายทาง แอปที่เข้าถึงได้ และ AI ที่เรียกเข้ามา */
  ai: {
    models: { label: string; provider: string; model: string; base_url: string; has_key: boolean }[];
    models_count: number;
    models_without_key: number;
    apps_with_ai: number;
    apps_total: number;
    ai_callers: { caller: string; target: string; scope: string }[];
    ai_callers_count: number;
    ai_callers_revoked: number;
    keys?: number;
    keys_ungranted?: number;
    details?: Record<string, string[]>;
  };
  /** สรุปว่าแต่ละเมนูในแถบข้างมีของอยู่เท่าไร — อ้างด้วย href ชุดเดียวกับแถบข้าง */
  menus: {
    href: string;
    count: number;
    unit: string;
    /** ยอดสะสมทั้งหมด เมื่อต่างจากยอดที่ใช้อยู่ */
    note?: string;
    items?: string[];
  }[];
  /** เฉพาะผู้ดูแลระบบ — จำนวนกุญแจก็บอกขนาดของสิ่งที่มีอยู่ */
  security?: {
    tokens_active: number;
    tokens_expiring: number;
    tokens_expiring_list: { label: string; caller: string; expires_at: string }[];
    keys_total: number;
    keys_ungranted: number;
    keys_revealable: number;
    audit_warnings_7d: number;
    tunnels_open: number;
    apps_public: number;
    details?: Record<string, string[]>;
  };
}

/** หกมุมมองเดียวกับหน้าแรก แต่ของแอปตัวเดียว */
export interface AppOverview {
  app_id: number;
  slug: string;
  name: string;
  status: string;
  version: number;
  port: number | null;
  access_mode: string;
  app_type: string;
  logo_data: string;
  performance: {
    memory_mb: number | null; cpu_percent: number | null;
    reach_status: string | null; reach_ms: number | null; reach_message: string;
  };
  privacy: {
    fields_total: number; fields_unconfirmed: number; fields: string[];
    has_purpose: boolean; retention: string; legal_basis: string;
  };
  risk: {
    edges_out: number; edges_in: number; edges_unconfirmed: number; edges: string[];
    flow_steps: number; steps: string[]; changes_unassessed: number;
  };
  security?: {
    keys: number; key_names: string[]; ai_keys: number;
    tokens: number; token_names: string[]; tunnel_open: boolean;
  };
}

/** ข้อมูลส่วนบุคคลเดินผ่านเส้นไหน — คำถามของ ROPA */
export interface PiiFlowEdge {
  edge_id: number;
  from: string;
  to: string;
  holder: string;
  external: boolean;
  origin: string;
  confirmed: boolean;
  via_gateway: boolean;
  pii_fields: number;
  pii_confirmed: number;
  purpose: string;
  policy: { block: number; mask: number; allow: number };
  policy_unconfirmed: number;
  /** ปลายทางภายในถือ PII และไม่มีจุดกรอง */
  unfiltered_pii: boolean;
  /** ออกนอกองค์กร — มองไม่เห็นเนื้อคำขอ จึงบอกไม่ได้ว่าส่งอะไร */
  external_unknown: boolean;
}

export interface PiiFlow {
  edges: PiiFlowEdge[];
  totals: {
    edges: number; with_pii: number; unfiltered_pii: number;
    via_gateway: number; external: number;
  };
}

export interface SystemMap {
  nodes: MapNode[];
  edges: DependencyEdge[];
  apps_without_edges: string[];
}

/** แผนที่เปลี่ยนไปอย่างไรในช่วงที่ผ่านมา — ISO 13485 ข้อ 7.3.9 ถามคำถามนี้ */
export interface SystemMapDelta {
  days: number;
  since: string;
  last_scan_at: string | null;
  /** ตอบเรื่อง "เส้นที่หายไป" ได้ก็ต่อเมื่อมีการสแกนจริงในช่วงนี้ */
  vanished_answerable: boolean;
  added: (DependencyEdge & { created_at: string | null })[];
  confirmed: DependencyEdge[];
  vanished: (DependencyEdge & { last_seen_at: string | null })[];
  deploys: { app_id: number; slug: string; name: string; version: number; note: string; at: string | null }[];
  tokens: {
    id: number; label: string; caller: string; target: string;
    expires_at: string | null;
    state: "issued" | "revoked" | "expired" | "expiring";
  }[];
  totals: { added: number; confirmed: number; vanished: number; deploys: number; tokens: number };
}

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

  // "protected" puts the iVS login in front of the app: the container stops
  // publishing its port to the network and iVS serves it instead. Recreates
  // the container, so it takes a few seconds.
  // ── Field-level PDPA policy ──────────────────────────────────── //
  // Rules derived from the PII scan, enforced on data leaving an app.
  getFieldPolicy: (appId: number) =>
    request<{
      total: number; pending_review: number; blocked: number; masked: number; allowed: number;
      fields: { id: number; field_name: string; category: string; action: "block" | "mask" | "allow";
                confirmed: boolean; origin: string; note: string }[];
    }>(`/pdpa/${appId}/field-policy`),

  deriveFieldPolicy: (appId: number) =>
    request<{ created: number; kept: number; pending_review: number }>(
      `/pdpa/${appId}/field-policy/derive`,
      { method: "POST" }
    ),

  confirmFieldPolicy: (appId: number, field_name: string, action: "block" | "mask" | "allow", note = "") =>
    request<{ field_name: string; action: string; confirmed: boolean }>(
      `/pdpa/${appId}/field-policy`,
      { method: "PUT", body: JSON.stringify({ field_name, action, note }) }
    ),

  previewFieldPolicy: (appId: number, sample: any) =>
    request<{ result: any; applied: { field: string; action: string }[] }>(
      `/pdpa/${appId}/field-policy/preview`,
      { method: "POST", body: JSON.stringify({ sample }) }
    ),

  // ── System map — what depends on what ────────────────────────── //
  getSystemMap: () => request<SystemMap>(`/dependencies`),

  getSystemMapDelta: (days = 7) =>
    request<SystemMapDelta>(`/dependencies/delta?days=${days}`),

  getPiiFlow: () => request<PiiFlow>(`/dependencies/pii`),

  /** ไฟล์เดียวเปิดได้เอง — ให้เบราว์เซอร์โหลดตรง ไม่ต้องผ่าน request() ที่คาด JSON */
  // ดาวน์โหลดไฟล์ที่ต้องมีสิทธิ์ — ลิงก์ธรรมดาใช้ไม่ได้
  //
  // <a href> เป็นการนำทางของเบราว์เซอร์ ไม่ผ่านตัวห่อ request() จึงไม่มีหัว
  // Authorization ติดไป และเซิร์ฟเวอร์ตอบ 401 ปุ่มส่งออกแผนที่ระบบเงียบมา
  // ตลอดด้วยเหตุนี้ ไม่มีอะไรฟ้อง เพราะการนำทางที่ล้มเหลวไม่ขึ้นที่หน้าจอเดิม
  downloadWithAuth: async (path: string, filename: string) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const res = await fetch(`${API_BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(detail.slice(0, 200) || `ส่งออกไม่สำเร็จ (HTTP ${res.status})`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // ── Vault scoping ─────────────────────────────────────────────── //
  getVaultScope: () => request<VaultScopeOverview>(`/vault/scope/overview`),

  grantVaultKey: (keyId: number, appId: number, note = "", envOverride = "") =>
    request<VaultScopeKey>(`/vault/${keyId}/grants`, {
      method: "POST",
      body: JSON.stringify({
        app_id: appId, capability: "inject", note, env_override: envOverride,
      }),
    }),

  // ชื่อตัวแปรต่อสิทธิ์ — ความลับใบเดียวถึงสองระบบด้วยชื่อที่แต่ละฝั่งอ่านจริง
  updateGrantEnvName: (grantId: number, envOverride: string) =>
    request<VaultScopeKey>(`/vault/grants/${grantId}/env-name`, {
      method: "PUT", body: JSON.stringify({ env_override: envOverride }),
    }),

  grantVaultNamespace: (keyId: number, namespace: string, appId: number) =>
    request<{ granted: number; keys: string[] }>(`/vault/${keyId}/grants/by-namespace`, {
      method: "POST", body: JSON.stringify({ namespace, app_id: appId }),
    }),

  revokeVaultGrant: (grantId: number) =>
    request<any>(`/vault/grants/${grantId}`, { method: "DELETE" }),

  updateVaultKeyScope: (keyId: number, patch: Record<string, any>) =>
    request<VaultScopeKey>(`/vault/${keyId}/scope`, { method: "PUT", body: JSON.stringify(patch) }),

  // ── Business flow — คนประกาศลำดับ เครื่องตรวจว่ายังจริง ──────────── //
  getFlows: () => request<{ flows: Flow[] }>(`/flows`),

  addFlowStep: (flowKey: string, data: Record<string, any>) =>
    request<FlowStepRow>(`/flows/${flowKey}/steps`, { method: "POST", body: JSON.stringify(data) }),

  updateFlowStep: (stepId: number, data: Record<string, any>) =>
    request<FlowStepRow>(`/flows/steps/${stepId}`, { method: "PUT", body: JSON.stringify(data) }),

  moveFlowStep: (stepId: number, direction: "up" | "down") =>
    request<{ moved: boolean }>(`/flows/steps/${stepId}/move`, {
      method: "PUT", body: JSON.stringify({ direction }),
    }),

  deleteFlowStep: (stepId: number) =>
    request<any>(`/flows/steps/${stepId}`, { method: "DELETE" }),

  verifyFlow: (flowKey: string) =>
    request<any>(`/flows/${flowKey}/verify`, { method: "POST" }),

  verifyFlowStep: (stepId: number) =>
    request<FlowStepRow>(`/flows/steps/${stepId}/verify`, { method: "POST" }),

  verifyReachability: () =>
    request<{ tested: number; ok: number; fail: number }>(`/dependencies/verify`, { method: "POST" }),

  scanDependencies: (appId: number) =>
    request<any>(`/dependencies/${appId}/scan`, { method: "POST" }),

  declareDependency: (appId: number, data: Record<string, any>) =>
    request<DependencyEdge>(`/dependencies/${appId}/declare`, {
      method: "POST", body: JSON.stringify(data),
    }),

  confirmDependency: (depId: number) =>
    request<DependencyEdge>(`/dependencies/edge/${depId}/confirm`, { method: "PUT" }),

  deleteDependency: (depId: number) =>
    request<any>(`/dependencies/edge/${depId}`, { method: "DELETE" }),

  // ── Design controls (ISO 13485 §7.3 / ISO 14971) ─────────────── //
  // ขอบเขตของเครื่องมือ — นับจากตารางจริงในหลังบ้าน ไม่ใช่ตัวเลขที่พิมพ์ไว้
  isoScope: () =>
    request<{
      covers: { iso13485: string[]; iso14971: string[]; iec62304_count: number; total: number };
      not_covered: { clause: string; th: string; en: string }[];
    }>("/trace/scope"),

  getTraceMatrix: (appId: number) => request<any>(`/trace/matrix/${appId}`),

  createRequirement: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/requirements/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  updateRequirement: (reqId: number, data: Record<string, any>) =>
    request<any>(`/trace/requirements/${reqId}`, { method: "PUT", body: JSON.stringify(data) }),

  createTest: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/tests/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  createRisk: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/risks/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  acceptRisk: (riskId: number) =>
    request<any>(`/trace/risks/${riskId}/accept`, { method: "PUT" }),

  // Returns the bundle itself, so it goes through fetch rather than request().
  getDeviceCriteria: () => request<any>("/trace/device/criteria"),

  getAiCriteria: () => request<any>("/trace/ai/criteria"),

  listSnapshots: (appId: number) => request<any>(`/trace/snapshots/${appId}`),

  diffSnapshots: (appId: number, a: number, b: number) =>
    request<any>(`/trace/snapshots/${appId}/diff?a=${a}&b=${b}`),

  getConformityReport: (appId: number) => request<any>(`/trace/conformity/${appId}`),

  getSecurityRecord: (appId: number) => request<any>(`/trace/security/${appId}`),

  saveSecurityRecord: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/security/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  getIecRecord: (appId: number) => request<any>(`/trace/iec/${appId}`),

  saveIecRecord: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/iec/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  getEpChecklist: (appId: number) => request<any>(`/trace/ep/${appId}`),

  saveEpChecklist: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/ep/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  getAiDossier: (appId: number) => request<any>(`/trace/ai/${appId}`),

  saveAiDossier: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/ai/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  getDeviceDetermination: (appId: number) => request<any>(`/trace/device/${appId}`),

  assessDevice: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/device/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  createChange: (appId: number, data: Record<string, any>) =>
    request<any>(`/trace/changes/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  updateChange: (changeId: number, data: Record<string, any>) =>
    request<any>(`/trace/changes/${changeId}`, { method: "PUT", body: JSON.stringify(data) }),

  approveChange: (changeId: number) =>
    request<any>(`/trace/changes/${changeId}/approve`, { method: "PUT" }),

  exportDhf: async (appId: number): Promise<Blob> => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`/api/trace/dhf/${appId}`, { headers, credentials: "include" });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || `Export failed (HTTP ${res.status})`);
    }
    return res.blob();
  },

  // ── Data mart — outside data, fetched once and shared ────────── //
  listDataMartSources: () =>
    request<{ sources: any[] }>("/datamart/sources"),

  createDataMartSource: (data: {
    name: string; url: string; method: string; vault_key_name: string;
    description: string; fetch_interval_minutes: number; retention_days: number;
  }) =>
    request<any>("/datamart/sources", { method: "POST", body: JSON.stringify(data) }),

  fetchDataMartSource: (id: number) =>
    request<any>(`/datamart/sources/${id}/fetch`, { method: "POST" }),

  getDataMartLatest: (id: number) =>
    request<{ fetched_at: string; expires_at: string | null; content_hash: string; data: any }>(
      `/datamart/sources/${id}/latest`
    ),

  deleteDataMartSource: (id: number) =>
    request<{ deleted: boolean }>(`/datamart/sources/${id}`, { method: "DELETE" }),

  // ── Exchange tokens — credentials for calling an app's API ───── //
  // The plaintext is in the create response and nowhere else, ever.
  listExchangeTokens: (appId: number) =>
    request<{ app_id: number; app_name: string; tokens: any[] }>(`/exchange/tokens/${appId}`),

  createExchangeToken: (
    appId: number,
    data: {
      caller_name: string; caller_kind: string; scope: "read" | "write";
      allowed_paths: string[]; ttl_hours: number | null;
      rate_limit_per_hour: number; label: string;
    }
  ) =>
    request<any>(`/exchange/tokens/${appId}`, { method: "POST", body: JSON.stringify(data) }),

  revokeExchangeToken: (tokenId: number) =>
    request<any>(`/exchange/tokens/${tokenId}`, { method: "DELETE" }),

  // Check what a token would be allowed to do, without making the call.
  verifyExchangeToken: (token: string, method: string, path: string) =>
    request<{ allowed: boolean; reason: string; caller_name?: string; scope?: string }>(
      `/exchange/verify`,
      { method: "POST", body: JSON.stringify({ token, method, path }) }
    ),

  // ── ROPA: recipients, lawful basis, erasure right ────────────── //
  getRopa: (appId: number) =>
    request<{
      app_id: number; app_name: string; legal_basis: string;
      erasure_right: "auto" | "allowed" | "restricted"; erasure_note: string;
      recipients: { kind: string; name: string; purpose: string; note: string; added_at: string }[];
      erasure: { erasable: boolean; reason_th: string; basis_label: string; source: string };
      basis_options: { value: string; label_th: string; label_en: string; erasable: boolean; why: string }[];
    }>(`/pdpa/${appId}/ropa`),

  updateRopa: (appId: number, patch: Record<string, any>) =>
    request<any>(`/pdpa/${appId}/ropa`, { method: "PUT", body: JSON.stringify(patch) }),

  addRopaRecipient: (appId: number, kind: string, name: string, purpose = "", note = "") =>
    request<{ added: boolean; recipients: any[] }>(`/pdpa/${appId}/ropa/recipients`, {
      method: "POST",
      body: JSON.stringify({ kind, name, purpose, note }),
    }),

  removeRopaRecipient: (appId: number, kind: string, name: string) =>
    request<{ recipients: any[] }>(
      `/pdpa/${appId}/ropa/recipients?kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name)}`,
      { method: "DELETE" }
    ),

  // Answer a deletion request for one activity, with the reason to send back.
  checkErasure: (appId: number) =>
    request<{ erasable: boolean; reason_th: string; basis_label: string; source: string }>(
      `/pdpa/${appId}/erasure-check`
    ),

  setAccessMode: (id: number, mode: "public" | "protected") => {
    const fd = new FormData();
    fd.append("mode", mode);
    return request<{ message: string; access_mode: string; restarted: boolean }>(
      `/apps/${id}/access-mode`,
      { method: "POST", body: fd }
    );
  },

  // deleteData also destroys the app's persistent data volume; omit it and the
  // volume survives, so redeploying under the same name restores the data.
  deleteApp: (id: number, deleteData = false) =>
    request<any>(`/apps/${id}?delete_data=${deleteData}`, { method: "DELETE" }),

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

  /** ภาพรวมหน้าแรก — คำขอเดียว คิวรีล้วน ไม่แตะ Docker */
  getSystemOverview: () => request<SystemOverview>("/system/overview"),

  getAppOverview: (appId: number) =>
    request<AppOverview>(`/system/overview/app/${appId}`),

  getAuditLogs: () => request<any[]>("/system/audit-logs"),

  getTunnels: () => request<any[]>("/tunnels"),

  // durationMinutes = null → ไม่มีกำหนดหมดอายุ (ต้องมีเหตุผลกำกับ)
  createTunnel: (appId: number, durationMinutes: number | null, permanentReason = "") =>
    request<any>("/tunnels", {
      method: "POST",
      body: JSON.stringify({
        app_id: appId,
        duration_minutes: durationMinutes,
        permanent_reason: permanentReason,
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
  // live=true ถาม Docker ทีละคอนเทนเนอร์ ราวสองวินาทีต่อแอป — ให้คนกดเอง
  getResources: (live = false) =>
    request<any>(`/system/resources${live ? "?live=true" : ""}`),

  getResourceHistory: (hours: number = 1) =>
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
  getModules: () =>
    request<{
      variant: string;
      label_th: string;
      label_en: string;
      edition: string;
      public: boolean;
      core_menus: string[];
      visible_menus: string[];
      menu_labels: Record<string, { th: string; en: string }>;
      modules: Record<string, { state: "active" | "demo" | "absent"; menu: string; th: string; what: string }>;
      demo_only: string[];
    }>("/system/modules"),

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
};

// ─── OpenCLI Bridge types ─────────────────────────────────────────── //
