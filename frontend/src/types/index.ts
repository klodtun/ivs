export interface User {
  id: number;
  username: string;
  email: string;
  role: "admin" | "developer" | "viewer";
  is_active: boolean;
  created_at: string;
  allowed_app_ids?: number[];
  access_all_apps?: boolean;
}

export interface App {
  id: number;
  name: string;
  slug: string;
  description: string;
  owner_id: number;
  app_type: "nodejs" | "python" | "static" | "fullstack" | "unknown";
  status: "building" | "running" | "stopped" | "error";
  port: number | null;
  domain: string | null;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface AppVersion {
  id: number;
  version: number;
  commit_message: string;
  created_at: string;
}

export interface Tunnel {
  id: number;
  app_id: number;
  public_url: string | null;
  status: "active" | "expired" | "revoked";
  expires_at: string;
  created_at: string;
}

export interface VaultKey {
  id: number;
  name: string;
  provider: string;
  category: string;
  description: string;
  created_by: number;
  created_at: string;
  masked_value?: string;
}

export interface SystemHealth {
  cpu_percent: number;
  memory_total: number;
  memory_used: number;
  memory_percent: number;
  disk_total: number;
  disk_used: number;
  disk_percent: number;
  docker_running: boolean;
  dns_running: boolean;
  apps_running: number;
  apps_total: number;
}

export interface AuditLog {
  id: number;
  user_id: number | null;
  username: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: string;
  log_level: string | null;
  request_id: string | null;
  session_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  ntp_server: string | null;
  created_at: string;
}

export interface AuditLogExport {
  id: number;
  filename: string;
  sha256_hash: string;
  record_count: number;
  exported_by: number;
  created_at: string;
  start_date: string | null;
  end_date: string | null;
  file_count: number;
}

export interface ResourceSystem {
  cpu_percent: number;
  cpu_cores: number;
  memory_used_mb: number;
  memory_total_mb: number;
  memory_percent: number;
  disk_used_gb: number;
  disk_total_gb: number;
  disk_percent: number;
  gpu_type: "nvidia" | "apple_silicon" | "none";
  gpu_used_mb: number | null;
  gpu_total_mb: number | null;
}

export interface ResourceCapacity {
  apps_running: number;
  apps_total: number;
  estimated_apps_can_add: number;
  estimated_ram_per_app_mb: number;
  ram_free_mb: number;
}

export interface ResourceAppStats {
  slug: string;
  name: string;
  app_type: string;
  cpu_percent: number;
  memory_mb: number;
  memory_limit_mb: number;
  port: number | null;
}

export interface ResourceAlert {
  level: "warning" | "critical";
  type: string;
  message: string;
}

export interface ResourceData {
  system: ResourceSystem;
  capacity: ResourceCapacity;
  per_app: ResourceAppStats[];
  alerts: ResourceAlert[];
}

export interface ResourceHistory {
  time: string;
  cpu: number;
  mem_used: number;
  mem_total: number;
  disk_used: number;
  disk_total: number;
  gpu_used: number | null;
  gpu_total: number | null;
  apps_running: number;
  per_app: ResourceAppStats[];
}
