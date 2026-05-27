from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str
    role: str


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    allowed_app_ids: list[int] = []
    access_all_apps: bool = False

    class Config:
        from_attributes = True


class UserAppAccessSet(BaseModel):
    user_id: int
    app_ids: list[int] = []
    access_all: bool = False


class UserAppAccessResponse(BaseModel):
    user_id: int
    app_ids: list[int] = []
    access_all: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class AppCreate(BaseModel):
    name: str
    description: str = ""
    env_vars: dict = {}


class AppUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    env_vars: Optional[dict] = None


class AppResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    owner_id: int
    app_type: str
    status: str
    port: Optional[int]
    domain: Optional[str]
    current_version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppDetailResponse(AppResponse):
    owner: UserResponse
    versions: list = []

    class Config:
        from_attributes = True


class AppVersionResponse(BaseModel):
    id: int
    version: int
    commit_message: str
    created_at: datetime

    class Config:
        from_attributes = True


class TunnelCreate(BaseModel):
    app_id: int
    duration_minutes: int = 60


class TunnelResponse(BaseModel):
    id: int
    app_id: int
    public_url: Optional[str]
    status: str
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class VaultKeyCreate(BaseModel):
    name: str
    provider: str
    category: str = "general"
    value: str
    description: str = ""


class VaultKeyResponse(BaseModel):
    id: int
    name: str
    provider: str
    category: str
    description: str
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class VaultKeyDetailResponse(VaultKeyResponse):
    masked_value: str


class SystemHealth(BaseModel):
    cpu_percent: float
    memory_total: int
    memory_used: int
    memory_percent: float
    disk_total: int
    disk_used: int
    disk_percent: float
    docker_running: bool
    dns_running: bool
    apps_running: int
    apps_total: int


class AuditLogResponse(BaseModel):
    """Audit Log Response — พ.ร.บ. คอมพิวเตอร์ compliant"""
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: str
    log_level: Optional[str] = "INFO"
    request_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    ntp_server: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogExportResponse(BaseModel):
    id: int
    filename: str
    sha256_hash: str
    record_count: int
    exported_by: int
    created_at: datetime
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    file_count: int = 1

    class Config:
        from_attributes = True


class AuditLogExportRequest(BaseModel):
    """Optional filters for /api/system/audit-logs/export.

    All fields are optional. Defaults: export all records, single file,
    chunk at 5000 records (keeps each .md file readable in editors).
    """
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_records_per_file: int = 5000


class DNSConfigUpdate(BaseModel):
    domain_suffix: str


class DNSConfigResponse(BaseModel):
    domain_suffix: str
    server_ip: str


# ── PDPA / ROPA ──

class PdpaUpdate(BaseModel):
    purpose: Optional[str] = None
    pii_fields: Optional[list[str]] = None
    retention_period: Optional[str] = None
    security_notes: Optional[str] = None


class PdpaResponse(BaseModel):
    id: int
    app_id: int
    app_name: str = ""
    app_slug: str = ""
    purpose: str = ""
    pii_fields: list[str] = []
    pii_auto_detected: list[str] = []
    retention_period: str = ""
    has_masking: bool = False
    masking_details: str = ""
    security_notes: str = ""
    status: str = "not_started"
    privacy_notice_enabled: bool = False
    privacy_notice_title: str = ""
    privacy_notice_detail: str = ""
    privacy_policy_url: str = ""
    privacy_notice_url: str = ""
    updated_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PdpaScanResult(BaseModel):
    app_id: int
    app_name: str
    pii_fields_detected: list[str] = []
    masking_detected: bool = False
    masking_patterns: list[str] = []
    files_scanned: int = 0
    scan_details: list[dict] = []


class RopaExportResponse(BaseModel):
    filename: str
    sha256_hash: str
    download_url: str
    record_count: int


# ── Privacy Notice ──

class PrivacyNoticeUpdate(BaseModel):
    privacy_notice_enabled: Optional[bool] = None
    privacy_notice_title: Optional[str] = None
    privacy_notice_detail: Optional[str] = None
    privacy_policy_url: Optional[str] = None
    privacy_notice_url: Optional[str] = None


class PrivacyNoticeResponse(BaseModel):
    app_id: int
    app_name: str = ""
    app_slug: str = ""
    privacy_notice_enabled: bool = False
    privacy_notice_title: str = ""
    privacy_notice_detail: str = ""
    privacy_policy_url: str = ""
    privacy_notice_url: str = ""
