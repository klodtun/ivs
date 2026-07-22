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


class EContractCert(Base):
    """
    หลักฐานรับรองเวลา + ความครบถ้วน ของเอกสาร/สัญญาอิเล็กทรอนิกส์
    ตาม พ.ร.บ. ว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ (integrity §12, เวลาที่เชื่อถือได้).
    - sha256: ลายนิ้วมือเนื้อหา (ความครบถ้วน)
    - ntp_time + ntp_server: เวลาที่เชื่อถือได้จาก NTP ราชการไทย
    - signature: HMAC-SHA256(sha256|ntp_time) ด้วย SECRET_KEY ของเครื่อง
      -> ตรวจสอบได้ว่าใบรับรองออกโดย iVS เครื่องนี้และไม่ถูกแก้
    """
    __tablename__ = "econtract_certs"

    id = Column(Integer, primary_key=True, index=True)
    cert_id = Column(String(40), unique=True, index=True, nullable=False)  # ECT-...
    filename = Column(String(400), nullable=False)
    size_bytes = Column(Integer, default=0)
    sha256 = Column(String(64), index=True, nullable=False)
    ntp_time = Column(DateTime, nullable=False)
    ntp_server = Column(String(120), default="")
    ntp_server_name = Column(String(200), default="")
    signature = Column(String(64), nullable=False)
    signer = Column(String(120), default="")       # ผู้ขอออกใบรับรอง (ชื่อผู้ใช้)
    note = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class EContractSignature(Base):
    """
    ลายมือชื่ออิเล็กทรอนิกส์ต่อใบรับรอง e-Contract (§9 / §26).
    ระบุตัวผู้ลงนาม + วิธี + เวลา NTP + IP และผูกด้วย HMAC เพื่อตรวจการแก้ไข
    (ลายเซ็นที่เชื่อถือได้ — reliable e-signature).
    """
    __tablename__ = "econtract_signatures"

    id = Column(Integer, primary_key=True, index=True)
    cert_id = Column(String(40), ForeignKey("econtract_certs.cert_id"), index=True, nullable=False)
    signer_name = Column(String(200), nullable=False)
    method = Column(String(20), default="typed")   # typed | drawn | otp
    identity_ref = Column(Text, default="")        # อีเมล/เบอร์ที่ยืนยัน หรือ data URI ลายเซ็นวาด
    signed_at = Column(DateTime, nullable=False)
    ip_address = Column(String(45), default="")
    signature = Column(String(64), nullable=False) # HMAC(cert_sha256|signer|signed_at|method)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)


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
    # นโยบายการทำข้อมูลนิรนาม/แฝง ตอนส่งออก/เปิด API:
    #   none = ไม่ระบุ, anonymous = นิรนาม, pseudonymous = ข้อมูลแฝง
    anonymization_mode = Column(String(20), default="none")
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


class ApiCatalogEntry(Base):
    """
    Managed API catalog — auto-discovered from deployed apps' OpenAPI specs.

    Each row is one API endpoint (or one app's API root). Sensitive fields
    (api_key, schema, base_url) are stored encrypted with VAULT_KEY.

    Lifecycle:
      1. Background scanner reads /openapi.json from each running app's port.
      2. New endpoints are inserted as catalog entries (encrypted).
      3. Admin can test the endpoint via UI button — result stored in
         last_test_status / last_test_message.
      4. Admin can replace the URL/key/schema. The old version goes to
         ApiCatalogVersion history; admin can restore any prior version.
    """
    __tablename__ = "api_catalog_entries"

    id              = Column(Integer, primary_key=True, index=True)
    app_id          = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=True, index=True)
    name            = Column(String(200), nullable=False)
    method          = Column(String(10), default="GET")
    path            = Column(String(500), default="/")
    encrypted_base_url    = Column(Text, nullable=False)     # Fernet
    encrypted_api_key     = Column(Text, nullable=True)      # Fernet
    encrypted_schema      = Column(Text, nullable=True)      # Fernet — OpenAPI snippet
    description     = Column(Text, default="")
    category        = Column(String(50), default="app")      # "app" | "external"
    current_version = Column(Integer, default=1)
    # Last test results
    last_test_at        = Column(DateTime, nullable=True)
    last_test_status    = Column(String(20), default="UNKNOWN")  # OK | FAIL | UNKNOWN
    last_test_message   = Column(Text, default="")
    last_test_http_code = Column(Integer, nullable=True)
    last_test_latency_ms = Column(Integer, nullable=True)
    is_active       = Column(Boolean, default=True)
    discovery_source = Column(String(20), default="auto")    # auto | manual
    created_at      = Column(DateTime, default=utcnow)
    updated_at      = Column(DateTime, default=utcnow, onupdate=utcnow)

    versions = relationship(
        "ApiCatalogVersion",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="ApiCatalogVersion.version_number.desc()",
    )


class ApiCatalogVersion(Base):
    """
    Encrypted history of prior API definitions. Created every time an
    ApiCatalogEntry is replaced so the prior config can be restored.
    """
    __tablename__ = "api_catalog_versions"

    id              = Column(Integer, primary_key=True, index=True)
    catalog_id      = Column(Integer, ForeignKey("api_catalog_entries.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    version_number  = Column(Integer, nullable=False)
    encrypted_base_url    = Column(Text, nullable=False)
    encrypted_api_key     = Column(Text, nullable=True)
    encrypted_schema      = Column(Text, nullable=True)
    method          = Column(String(10), default="GET")
    path            = Column(String(500), default="/")
    replaced_by_id  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason          = Column(Text, default="")
    created_at      = Column(DateTime, default=utcnow, index=True)

    entry = relationship("ApiCatalogEntry", back_populates="versions")


class MachineRegistry(Base):
    """
    Known IVS machines in the fleet — foundation for Enterprise multi-machine management.

    Each row represents one IVS instance, identified by its machine fingerprint
    (HMAC of MAC + CPU + mobo serial). Machines can be added manually (admin
    pastes fingerprint + serial) or via LAN auto-discovery (mDNS scan).

    In IVS Free this table stores only the local machine itself.
    In IVS Enterprise the admin can add remote machines, assign them to groups,
    and monitor their health from a single dashboard.
    """
    __tablename__ = "machine_registry"

    id            = Column(Integer, primary_key=True, index=True)
    fingerprint   = Column(String(16), unique=True, nullable=False, index=True)
    serial        = Column(String(32), nullable=True)
    hostname      = Column(String(255), nullable=True)
    ip_address    = Column(String(45), nullable=True)
    port          = Column(Integer, default=3000)
    edition       = Column(String(10), default="FREE")   # FREE | LITE | STD | PRO | ENT
    group_name    = Column(String(100), nullable=True)   # Enterprise grouping
    notes         = Column(Text, nullable=True)
    is_self       = Column(Boolean, default=False)       # True = this machine
    # discovery_source: "manual" | "mdns" | "self"
    discovery_source = Column(String(20), default="manual")
    last_seen     = Column(DateTime, nullable=True)
    added_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime, default=utcnow, index=True)


# ---------------------------------------------------------------------------
# OpenCLI Bridge (Pro/Enterprise) — see docs/opencli-bridge-architecture.md
#
# Raw imported legacy data is NEVER stored. Only metadata + the SHA-256 of the
# raw bytes lives here. Transformed artifacts (cli-manifest.json + markdown)
# live as FILES under deployed_apps/_bridge/<id>/, not in the DB.
# ---------------------------------------------------------------------------

class OpenCliImportStatus(str, enum.Enum):
    PENDING     = "pending"       # metadata row created, not yet transformed
    TRANSFORMED = "transformed"   # manifest + markdown written to artifact_dir
    PUBLISHED   = "published"     # exposed via MCP (P2)
    DELETED     = "deleted"       # soft-deleted; see OpenCliImportDeletion


class OpenCliPiiProfile(str, enum.Enum):
    EXCLUDE   = "exclude"     # drop PII-bearing columns/values entirely
    ANONYMIZE = "anonymize"   # replace via pii_anonymizer (HMAC-stable tokens)


class OpenCliImport(Base):
    __tablename__ = "opencli_imports"

    id            = Column(Integer, primary_key=True, index=True)
    project_id    = Column(Integer, ForeignKey("opencli_projects.id", ondelete="CASCADE"),
                           nullable=True, index=True)          # which project/app
    importer_id   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"),
                           nullable=True, index=True)          # WHO imported
    source_kind   = Column(String(20), nullable=False)         # sqlite | rest | file
    source_ref    = Column(String(1024), nullable=False)       # path/url only — no data
    source_bytes  = Column(Integer, nullable=False, default=0) # probed size
    sha256_raw    = Column(String(64), nullable=False, index=True)  # HASH of raw import
    pii_profile   = Column(Enum(OpenCliPiiProfile), nullable=False,
                           default=OpenCliPiiProfile.EXCLUDE)
    status        = Column(Enum(OpenCliImportStatus), nullable=False,
                           default=OpenCliImportStatus.PENDING, index=True)
    artifact_dir  = Column(String(1024), nullable=True)        # files, not blob
    manifest_sha  = Column(String(64), nullable=True)          # sha256 of cli-manifest.json
    command_count = Column(Integer, nullable=True)             # #commands emitted
    created_at    = Column(DateTime, default=utcnow, index=True)
    # NOTE: raw imported data is intentionally NOT a column here.

    importer   = relationship("User", foreign_keys=[importer_id])
    deletions  = relationship("OpenCliImportDeletion", back_populates="parent",
                              cascade="all, delete-orphan")


class OpenCliImportDeletion(Base):
    __tablename__ = "opencli_import_deletions"

    id          = Column(Integer, primary_key=True, index=True)
    import_id   = Column(Integer, ForeignKey("opencli_imports.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    deleted_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"),
                         nullable=True)                        # WHO deleted
    reason      = Column(Text, nullable=True)
    sha256_raw  = Column(String(64), nullable=False)           # preserved for the record
    deleted_at  = Column(DateTime, default=utcnow, index=True)

    parent  = relationship("OpenCliImport", back_populates="deletions")


class OpenCliProject(Base):
    """A project/app groups many imports (versions) + generated code + MCP tokens.
    Multiple people can add imports to the same project over time."""
    __tablename__ = "opencli_projects"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)
    slug        = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_id    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, default=utcnow, index=True)
    updated_at  = Column(DateTime, default=utcnow, onupdate=utcnow)

    owner    = relationship("User", foreign_keys=[owner_id])
    imports  = relationship("OpenCliImport", backref="project")


class OpenCliCodeStatus(str, enum.Enum):
    GENERATED = "generated"   # code written, not deployed
    DEPLOYED  = "deployed"    # pushed to an IVS app
    DELETED   = "deleted"     # soft-deleted (kept as history until purge)


class OpenCliCodeVersion(Base):
    """One generated code set for a project. Every regeneration is a new version;
    old versions are kept as history until explicitly deleted (iVS standard)."""
    __tablename__ = "opencli_code_versions"

    id            = Column(Integer, primary_key=True, index=True)
    project_id    = Column(Integer, ForeignKey("opencli_projects.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    import_id     = Column(Integer, ForeignKey("opencli_imports.id", ondelete="SET NULL"),
                           nullable=True)                        # source import version
    version       = Column(Integer, nullable=False, default=1)   # per-project increment
    module        = Column(String(60), nullable=True)            # which module (None = whole app)
    provider      = Column(String(30), nullable=False)           # manual|anthropic|openai
    model         = Column(String(100), nullable=True)
    files_count   = Column(Integer, nullable=False, default=0)
    code_dir      = Column(String(1024), nullable=True)          # files on disk
    sha256        = Column(String(64), nullable=True)            # hash of the code set
    app_type      = Column(String(20), nullable=True)            # from verify_candidate
    verify_ok     = Column(Boolean, default=False)
    deployed_app_id = Column(Integer, ForeignKey("apps.id", ondelete="SET NULL"), nullable=True)
    status        = Column(Enum(OpenCliCodeStatus), nullable=False,
                           default=OpenCliCodeStatus.GENERATED, index=True)
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime, default=utcnow, index=True)


class OpenCliLlmModel(Base):
    """A configured AI model/agent for code generation. Key comes from the IVS
    Vault (คลัง API Key), not stored here — Pro/Enterprise. Multiple can be
    registered so different models build different modules (multi-agent)."""
    __tablename__ = "opencli_llm_models"

    id           = Column(Integer, primary_key=True, index=True)
    label        = Column(String(100), nullable=False)     # agent display name
    provider     = Column(String(30), nullable=False)      # anthropic | openai
    model        = Column(String(100), nullable=False)
    base_url     = Column(String(500), nullable=True)
    vault_key_id = Column(Integer, ForeignKey("vault_keys.id", ondelete="SET NULL"), nullable=True)
    created_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime, default=utcnow)


class OpenCliMcpToken(Base):
    """A scoped access token an external AI agent uses to connect to the MCP
    server for one project. Only the hash is stored; the value is shown once."""
    __tablename__ = "opencli_mcp_tokens"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("opencli_projects.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    name        = Column(String(200), nullable=False)             # human label
    token_hash  = Column(String(64), unique=True, nullable=False, index=True)  # sha256(token)
    prefix      = Column(String(16), nullable=False)              # first chars, for display
    scope       = Column(String(20), nullable=False, default="read")  # read | read_write
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, default=utcnow, index=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at  = Column(DateTime, nullable=True)


class OpenCliGenAttempt(Base):
    """History of every module generation attempt (success OR error). Lets the UI
    show past failures (500/428/parse/save) per module so the operator can pick a
    better AI. Kept forever as an audit of what each model produced."""
    __tablename__ = "opencli_gen_attempts"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, index=True, nullable=True)   # project-combined gen
    import_id   = Column(Integer, index=True, nullable=True)   # per-import gen
    module      = Column(String(60), nullable=True)
    provider    = Column(String(30), nullable=True)
    model       = Column(String(100), nullable=True)
    model_id    = Column(Integer, nullable=True)               # chosen OpenCliLlmModel
    ok          = Column(Boolean, default=False, index=True)
    files       = Column(Integer, default=0)
    error_code  = Column(String(20), nullable=True)            # "500" | "428" | "parse" | "save"
    note        = Column(Text, nullable=True)                  # short explanation
    created_by  = Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=utcnow, index=True)
