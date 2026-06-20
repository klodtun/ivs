import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class AppStatus(str, enum.Enum):
    BUILDING = "building"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class AppType(str, enum.Enum):
    NODEJS = "nodejs"
    PYTHON = "python"
    STATIC = "static"
    FULLSTACK = "fullstack"
    UNKNOWN = "unknown"


class TunnelStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PdpaStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    PARTIAL = "partial"
    COMPLETE = "complete"


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    apps = relationship("App", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")
    app_access = relationship("UserAppAccess", back_populates="user", cascade="all, delete-orphan")


class App(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, default="")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    app_type = Column(Enum(AppType), default=AppType.UNKNOWN)
    status = Column(Enum(AppStatus), default=AppStatus.STOPPED)
    port = Column(Integer, nullable=True)
    domain = Column(String(200), nullable=True)
    container_id = Column(String(100), nullable=True)
    current_version = Column(Integer, default=1)
    source_path = Column(String(500), nullable=True)
    env_vars = Column(Text, default="{}")
    # Small logo as a data URI (data:image/png;base64,...). Stored inline so
    # no static mount / file management is needed. Downscaled client-side to
    # keep it tiny and the cards uniform. Null -> render initials avatar.
    logo_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="apps")
    versions = relationship("AppVersion", back_populates="app", order_by="AppVersion.version.desc()")
    tunnels = relationship("Tunnel", back_populates="app")
    user_access = relationship("UserAppAccess", back_populates="app", cascade="all, delete-orphan")


class AppVersion(Base):
    __tablename__ = "app_versions"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    version = Column(Integer, nullable=False)
    commit_message = Column(String(500), default="")
    source_snapshot = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    app = relationship("App", back_populates="versions")


class Tunnel(Base):
    __tablename__ = "tunnels"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    public_url = Column(String(500), nullable=True)
    status = Column(Enum(TunnelStatus), default=TunnelStatus.ACTIVE)
    expires_at = Column(DateTime, nullable=False)
    container_id = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    app = relationship("App", back_populates="tunnels")


class VaultKey(Base):
    __tablename__ = "vault_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    category = Column(String(50), default="general")
    encrypted_value = Column(Text, nullable=False)
    description = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class UserAppAccess(Base):
    __tablename__ = "user_app_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=True)
    access_all = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="app_access")
    app = relationship("App", back_populates="user_access")


class AuditLog(Base):
    """
    Audit Log ตามมาตรฐาน พ.ร.บ. คอมพิวเตอร์ (Computer Crime Act)
    - Timestamp: ระดับมิลลิวินาที + UTC timezone
    - Log Level: INFO / WARNING / ERROR / DEBUG
    - Identifier: request_id (UUID) + session_id (JWT hash)
    - Context: user_id, username, action, resource, details, IP, user_agent
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, default="")
    log_level = Column(String(10), default="INFO")
    request_id = Column(String(36), nullable=True)
    session_id = Column(String(16), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ntp_server = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="audit_logs")


class AppLogEntry(Base):
    """Persistent storage of per-app container log lines.

    Required by พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560
    (90-day minimum retention of computer-traffic data, §26).

    These are intentionally separate from AuditLog so they don't pollute
    the system-event view — but they ARE included when an admin exports
    the audit bundle, one file per app, respecting the same date range
    and chunk-size selection.
    """
    __tablename__ = "app_log_entries"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    # Timestamp from the container itself (docker --timestamps), UTC
    timestamp = Column(DateTime, nullable=False, index=True)
    # The raw log line content, truncated to 8KB if huge
    log_line = Column(Text, nullable=False, default="")
    # stdout / stderr — Docker doesn't distinguish in this API call, default stdout
    stream = Column(String(10), default="stdout")
    # When the collector inserted the row (for diagnostics / replication lag)
    created_at = Column(DateTime, default=utcnow)


class AuditLogExport(Base):
    __tablename__ = "audit_log_exports"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    record_count = Column(Integer, default=0)
    exported_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    # NEW: date range used for the export (NULL = unbounded on that side).
    # Used by the UI to label history rows like "01 Jan – 27 May".
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    # NEW: how many .md chunks live inside the bundle .zip
    # (1 for legacy single-file .md exports).
    file_count = Column(Integer, default=1)


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AppPdpa(Base):
    """
    PDPA ROPA (Record of Processing Activities) per app.
    ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562
    """
    __tablename__ = "app_pdpa"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), unique=True, nullable=False)
    purpose = Column(Text, default="")                   # วัตถุประสงค์
    pii_fields = Column(Text, default="[]")              # JSON: PII fields ที่ผู้ใช้ยืนยัน
    pii_auto_detected = Column(Text, default="[]")       # JSON: ผล scan อัตโนมัติ
    retention_period = Column(String(100), default="")   # ระยะเวลาเก็บ เช่น "1 ปี"
    has_masking = Column(Boolean, default=False)          # พบ masking script หรือไม่
    masking_details = Column(Text, default="")            # รายละเอียด masking ที่พบ
    security_notes = Column(Text, default="")             # หมายเหตุมาตรการเพิ่มเติม
    status = Column(Enum(PdpaStatus), default=PdpaStatus.NOT_STARTED)
    # Privacy Notice — ประกาศแจ้งเตือนก่อนใช้งาน
    privacy_notice_enabled = Column(Boolean, default=False)   # Toggle เปิด/ปิดใช้ Privacy Notice ของ IVS
    privacy_notice_title = Column(String(300), default="")    # หัวเรื่องประกอบแจ้งเตือน
    privacy_notice_detail = Column(Text, default="")          # รายละเอียดโดยย่อ
    privacy_policy_url = Column(String(500), default="")      # URL นโยบายคุ้มครองข้อมูลส่วนบุคคล
    privacy_notice_url = Column(String(500), default="")      # URL ประกาศแจ้งเตือนโดยละเอียด
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    app = relationship("App")


class GdprErasureRequest(Base):
    """Audit trail for GDPR Art. 17 / APPI Art. 30 / PDPA §35 erasure
    requests. The target identifier is stored ONLY as an HMAC hash so the
    erasure record itself never re-introduces the PII we just erased.
    """
    __tablename__ = "gdpr_erasure_requests"

    id            = Column(Integer, primary_key=True, index=True)
    target_type   = Column(String(20), nullable=False)   # "email" | "ip" | "username" | "user_id"
    target_hash   = Column(String(64), nullable=False, index=True)
    reason        = Column(Text, default="")
    legal_basis   = Column(String(64), default="")       # e.g. "GDPR Art. 17(1)(a)"
    requested_by  = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_ip  = Column(String(45), nullable=True)
    rows_affected = Column(Text, default="{}")           # JSON {audit_logs: N, app_logs: N, ...}
    sha256_proof  = Column(String(64), nullable=False)
    created_at    = Column(DateTime, default=utcnow, index=True)


class PdpaConsent(Base):
    """
    Per-user, per-app record of consent decisions for the PDPA Privacy
    Notice popup.

    PDPA §19 requires informed consent and the ability for the data
    subject to withdraw consent as easily as they granted it. We keep
    each decision as a discrete row so the history is preserved — the
    "current" decision for a user/app is the most recent row.

    A user can change their mind any time by clicking the privacy-notice
    link on the AppCard; that creates a new row with the new decision
    and the prior row is naturally superseded.
    """
    __tablename__ = "pdpa_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    decision = Column(String(20), nullable=False)  # "accepted" | "declined"
    # Evidence captured at the moment of consent — required for §19 audit
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    # Optional reference to which version of the notice they saw
    notice_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class ResourceMetric(Base):
    """Historical resource usage snapshots — collected every 60 seconds."""
    __tablename__ = "resource_metrics"

    id = Column(Integer, primary_key=True, index=True)
    cpu_percent = Column(Integer, default=0)          # 0-100
    memory_used_mb = Column(Integer, default=0)
    memory_total_mb = Column(Integer, default=0)
    disk_used_gb = Column(Integer, default=0)
    disk_total_gb = Column(Integer, default=0)
    gpu_memory_used_mb = Column(Integer, nullable=True)
    gpu_memory_total_mb = Column(Integer, nullable=True)
    apps_running = Column(Integer, default=0)
    apps_total = Column(Integer, default=0)
    per_app_json = Column(Text, default="[]")         # JSON: [{slug, cpu, mem_mb}]
    created_at = Column(DateTime, default=utcnow, index=True)
