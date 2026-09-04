import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, ForeignKey, Boolean, Text, Index,
    UniqueConstraint,
)
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
    # "public"    — the container publishes its port on 0.0.0.0; anyone who can
    #               reach IP:PORT reaches the app, with no iVS login involved.
    # "protected" — the container is bound to loopback only and iVS listens on
    #               the public port itself, forwarding a connection only after
    #               checking the iVS session (see services/app_gate_service.py).
    #               Access is audit-logged, so PDPA/§26 records cover the app too.
    access_mode = Column(String(20), default="public", nullable=False)
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
    # NULL = ไม่มีกำหนดหมดอายุ. การเชื่อมต่อประจำระหว่างสองระบบเป็นเรื่องปกติ
    # และการบังคับให้หมดอายุทุก N ชั่วโมงมีแต่จะทำให้คนตั้งเวลาสูงลิ่วแทน
    # ซึ่งแย่กว่าการยอมรับตรง ๆ ว่าตั้งใจให้ค้างไว้แล้วบันทึกเหตุผลกำกับ
    expires_at = Column(DateTime, nullable=True)
    # เหตุผลที่ต้องเปิดค้าง — บังคับกรอกเมื่อไม่กำหนดวันหมดอายุ
    permanent_reason = Column(Text, default="")
    # ผูกกับโทเคนใบใดใบหนึ่ง: เพิกถอนโทเคน = ปิดอุโมงค์ตามไปด้วย
    # ไม่ใช่เปิดทั้งแอปให้ใครก็ได้ที่รู้ URL
    token_id = Column(Integer, ForeignKey("exchange_tokens.id", ondelete="SET NULL"), nullable=True)
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
    # ขอบเขตแบบเส้นทาง — ใช้ให้สิทธิ์ทีละกลุ่ม เช่น openai/* โดยไม่ต้องไล่ทีละใบ
    # ค่าว่างแปลว่ายังไม่จัดกลุ่ม ไม่ได้แปลว่าอยู่ทุกกลุ่ม
    namespace = Column(String(120), default="", index=True)
    # ความสามารถระดับใบสำหรับฝั่งคน — กุญแจที่ตั้งเป็น False ใส่เข้าคอนเทนเนอร์ได้
    # แต่ไม่มีใครคัดลอกค่าออกไปได้ แม้เป็นผู้ดูแลระบบ
    allow_reveal = Column(Boolean, default=True)
    # ชื่อตัวแปรที่จะไปโผล่ในคอนเทนเนอร์ ตั้งเองได้
    #
    # ชื่อเริ่มต้นสร้างจาก {PROVIDER}_{NAME} ซึ่งอ่านง่ายสำหรับคน แต่แทบไม่เคย
    # ตรงกับชื่อที่โปรแกรมอ่านจริง (OPENAI_API_KEY, GEMINI_API_KEY) และบางครั้ง
    # ออกมาเป็นชื่อที่ใช้เป็นตัวแปรไม่ได้เลยเมื่อชื่อผู้ให้บริการมี :// หรือช่องว่าง
    # ผลคือกุญแจถูกส่งเข้าคอนเทนเนอร์ภายใต้ชื่อที่ไม่มีใครอ่าน — ได้ความเสี่ยง
    # โดยไม่ได้ประโยชน์ ช่องนี้จึงแยกชื่อที่แสดงออกจากชื่อที่ใช้จริง
    env_override = Column(String(120), default="")
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

    # ดึง audit trail ของทรัพยากรหนึ่ง ๆ เป็น query ร้อน (รายงาน 7 ขั้นตอนของ e-Contract
    # และการสร้างชุดหลักฐาน) — ถ้าไม่มี index จะเป็น full scan ที่โตตามจำนวน log
    # วัดจริง: 1M แถว 84 ms → 0.008 ms เมื่อมี index
    __table_args__ = (
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )


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
    # นโยบายการทำข้อมูลนิรนาม/แฝง ตอนส่งออก/เปิด API:
    #   none = ไม่ระบุ, anonymous = นิรนาม, pseudonymous = ข้อมูลแฝง
    anonymization_mode = Column(String(20), default="none")
    # ── ROPA: ฐานการประมวลผล ปลายทาง และสิทธิของเจ้าของข้อมูล ──
    # ฐานการประมวลผลตาม พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล ม.24 — เป็นตัวกำหนดว่า
    # คำขอลบตาม ม.33 ทำได้หรือไม่ ไม่ใช่ดุลพินิจของผู้ดูแลระบบ
    #   consent | contract | legal_obligation | vital_interest |
    #   public_task | legitimate_interest
    legal_basis = Column(String(30), default="")
    # ปลายทางที่ข้อมูลไหลไป — JSON: [{kind, name, purpose, note, added_at}]
    # kind: app (แอปอื่นใน iVS) | external (หน่วยงานภายนอก) | ai (โมเดล)
    # เพิ่มอัตโนมัติเมื่อเปิดการแลกเปลี่ยนข้อมูล เพราะการเปิด API คือการเพิ่ม
    # ผู้รับข้อมูลในกิจกรรมนี้ ซึ่งต้องปรากฏทั้งใน ROPA และประกาศแจ้งเตือน
    data_recipients = Column(Text, default="[]")
    # auto = ตัดสินจาก legal_basis | allowed = ลบได้เสมอ | restricted = ลบไม่ได้
    erasure_right = Column(String(20), default="auto")
    erasure_note = Column(Text, default="")               # เหตุผลเมื่อ restricted
    security_notes = Column(Text, default="")             # หมายเหตุมาตรการเพิ่มเติม
    status = Column(Enum(PdpaStatus), default=PdpaStatus.NOT_STARTED)

    # แอปถูกลบออกจาก iVS เมื่อไร — บันทึก ROPA ยังอยู่ต่อไป
    #
    # ROPA คือบันทึกว่า "เคยมีการประมวลผลข้อมูลส่วนบุคคลอะไรบ้าง" การถอดแอปออก
    # ไม่ได้ย้อนความจริงข้อนั้น PDPA ไม่ได้สั่งให้ลบบันทึกนี้ตามแอป และผู้ตรวจ
    # ถามถึงกิจกรรมที่เคยเกิด ไม่ใช่เฉพาะที่ยังเกิดอยู่ แถวจึงถูกประทับหมายเหตุ
    # ไม่ใช่ถูกลบ
    #
    # ชื่อแอปต้องถ่ายสำเนาไว้ตรงนี้ เพราะแถวใน apps หายไปพร้อมการลบ ถ้าไม่เก็บ
    # ไว้ บันทึกจะเหลือแค่เลข app_id ที่ไม่มีใครแปลได้ว่าคือแอปอะไร
    app_removed_at = Column(DateTime, nullable=True)
    app_name_at_removal = Column(String(200), default="")
    app_slug_at_removal = Column(String(200), default="")
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
    # Fingerprint of the schema as it was last reviewed. When a redeploy
    # changes an app's API, the tools generated from it would keep calling the
    # old shape and quietly return wrong answers — the failure mode v1.3.2 was
    # about. A mismatch parks the tool until someone confirms the new schema.
    schema_hash       = Column(String(64), default="")
    schema_confirmed  = Column(Boolean, default=True)
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
class FieldAction(str, enum.Enum):
    """What happens to a field when data leaves an app."""
    BLOCK = "block"    # drop the field entirely — it never leaves
    MASK = "mask"      # replace with an HMAC-stable token (see pii_anonymizer)
    ALLOW = "allow"    # pass through unchanged


class AppFieldPolicy(Base):
    """Per-field rule for data leaving an app — PDPA policy, enforced in code.

    The PII scan already finds which fields hold personal data, but the result
    only sat in app_pdpa.pii_auto_detected where nothing acted on it. One row
    here turns one of those findings into a rule the exchange layer applies on
    every response, so opening an API stops meaning opening personal data.

    Rows start unconfirmed with a safe default (block or mask, never allow) and
    do nothing until a human confirms them — a scan is evidence, not consent.
    """
    __tablename__ = "app_field_policies"

    id           = Column(Integer, primary_key=True, index=True)
    app_id       = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name   = Column(String(200), nullable=False, index=True)
    category     = Column(String(100), default="")        # PII category the scan assigned
    action       = Column(Enum(FieldAction), nullable=False, default=FieldAction.MASK)
    # False until someone reviews it. Unconfirmed rows are still enforced —
    # the safe default applies while review is pending, so a fresh scan can
    # never widen access on its own.
    confirmed    = Column(Boolean, default=False, index=True)
    confirmed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    origin       = Column(String(20), default="scan")     # scan | manual
    note         = Column(Text, default="")
    created_at   = Column(DateTime, default=utcnow)
    updated_at   = Column(DateTime, default=utcnow, onupdate=utcnow)


class TokenScope(str, enum.Enum):
    """Read and write are separate credentials, never one with two powers."""
    READ = "read"
    WRITE = "write"


class ExchangeToken(Base):
    """A credential to call one app's API through the iVS exchange layer.

    Only the hash is stored. The plaintext is shown once at issue and never
    again — a leaked database of these must not be a leaked set of working
    credentials, which is the same reason device tokens are peppered.

    Scope is `read` or `write`, and they are separate tokens on purpose.
    `GET /bookings` and `POST /bookings/cancel` are not the same risk, and a
    single credential covering both hands out write access every time someone
    only needed to read. It also gives AI a shape it can be trusted with: a
    read token can be handed to a model, a write token cannot.

    Revocation is why these are opaque rather than JWTs. A signed token that
    cannot be withdrawn is a key that stays valid after it leaks; here a check
    against this row happens on every call, so revoking is immediate.
    """
    __tablename__ = "exchange_tokens"

    id             = Column(Integer, primary_key=True, index=True)
    # HMAC of the plaintext, keyed by SECRET_KEY. Never the token itself.
    token_hash     = Column(String(64), nullable=False, unique=True, index=True)
    # First characters, shown in the UI so a row can be told apart at a glance.
    token_prefix   = Column(String(12), nullable=False)
    label          = Column(String(200), default="")

    caller_kind    = Column(String(20), default="app")     # app | ai | external
    caller_name    = Column(String(200), nullable=False)   # who holds this token
    target_app_id  = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                            nullable=False, index=True)

    scope          = Column(Enum(TokenScope), nullable=False, default=TokenScope.READ)
    # Allowed calls as "METHOD /path" entries; "*" means any path within scope.
    allowed_paths  = Column(Text, default='["*"]')

    # NULL = no expiry. Allowed, because a fixed exchange between two systems
    # may legitimately run for the life of an installation — but write tokens
    # are refused one, since an open-ended write credential is the thing most
    # likely to be forgotten and later abused.
    expires_at     = Column(DateTime, nullable=True)
    revoked_at     = Column(DateTime, nullable=True)

    # Rolling hourly cap. AI callers retry and loop; without a ceiling one bad
    # prompt can exhaust an app or a paid model budget in minutes.
    rate_limit_per_hour = Column(Integer, default=1000)
    window_start   = Column(DateTime, nullable=True)
    window_count   = Column(Integer, default=0)

    use_count      = Column(Integer, default=0)
    last_used_at   = Column(DateTime, nullable=True)
    created_by     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at     = Column(DateTime, default=utcnow)


class IdempotencyRecord(Base):
    """Remembers the result of a write so a repeat of it changes nothing.

    AI callers retry — a timeout, a dropped connection, a model that decides to
    try again. Without this, one retry is one extra booking cancelled or one
    guest checked in twice, and at a 2,880-seat event that is not a rounding
    error.

    The key comes from the caller and is scoped to the token, so two callers
    using the same key never collide. The request body is fingerprinted as
    well: the same key with different content is a mistake worth reporting
    rather than silently answering with the old result.
    """
    __tablename__ = "idempotency_records"

    id            = Column(Integer, primary_key=True, index=True)
    token_id      = Column(Integer, ForeignKey("exchange_tokens.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    idem_key      = Column(String(200), nullable=False, index=True)
    method        = Column(String(10), nullable=False)
    path          = Column(String(500), nullable=False)
    request_hash  = Column(String(64), nullable=False)     # SHA-256 of the body
    status_code   = Column(Integer, nullable=False)
    response_body = Column(Text, default="")
    created_at    = Column(DateTime, default=utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("token_id", "idem_key", name="uq_idem_token_key"),
    )


class DataMartSource(Base):
    """ข้อมูลจากภายนอกที่ iVS ดึงเข้ามาเก็บเป็นกองกลาง

    ก่อนหน้านี้แอปที่ต้องใช้ข้อมูลนอกต้องต่อเอง แปลว่ากุญแจกระจายอยู่ตามแอป
    และไม่มีใครเห็นภาพรวมว่าข้อมูลอะไรไหลเข้ามาบ้าง ที่นี่กุญแจอยู่ใน Vault
    ที่เดียว และทุกชุดข้อมูลมีที่มากับอายุกำกับตั้งแต่วินาทีที่เข้ามา

    ข้อมูลจากภายนอกคือความเสี่ยงสูงสุดในระบบ เพราะไม่มีใครควบคุมสิ่งที่ส่งมา
    จึงสแกน PII ทุกครั้งที่ดึง ไม่ใช่เชื่อว่าปลายทางส่งแต่ของที่สะอาด
    """
    __tablename__ = "datamart_sources"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(200), nullable=False)
    description   = Column(Text, default="")
    url           = Column(String(1000), nullable=False)
    method        = Column(String(10), default="GET")
    # ชื่อกุญแจใน Vault ไม่ใช่ตัวกุญแจ — ความลับอยู่ที่เดียว
    vault_key_name = Column(String(100), default="")
    auth_header   = Column(String(100), default="Authorization")
    fetch_interval_minutes = Column(Integer, default=60)
    retention_days = Column(Integer, default=30)
    is_active     = Column(Boolean, default=True, index=True)
    last_fetch_at = Column(DateTime, nullable=True)
    last_status   = Column(String(20), default="never")    # ok | failed | never
    last_message  = Column(Text, default="")
    last_pii_found = Column(Text, default="[]")            # JSON: หมวด PII ที่พบ
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime, default=utcnow)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)


class DataMartRecord(Base):
    """หนึ่งครั้งที่ดึงข้อมูลเข้ามา พร้อมที่มาและวันหมดอายุ

    เก็บเป็นรายครั้งไม่ใช่ทับของเดิม เพราะคำถามว่า "ตอนนั้นข้อมูลเป็นอย่างไร"
    ต้องตอบได้ และการทับทำให้ตอบไม่ได้อีกเลย
    """
    __tablename__ = "datamart_records"

    id          = Column(Integer, primary_key=True, index=True)
    source_id   = Column(Integer, ForeignKey("datamart_sources.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    payload     = Column(Text, default="")                 # JSON ที่ดึงมา
    content_hash = Column(String(64), default="", index=True)
    fetched_at  = Column(DateTime, default=utcnow, index=True)
    expires_at  = Column(DateTime, nullable=True, index=True)


# ── Design controls (ISO 13485 §7.3 / ISO 14971) ─────────────────────
#
# สามตารางนี้คือสิ่งที่ทำให้ "ตารางตามรอย" เกิดขึ้นได้: ความต้องการ ผลการทดสอบ
# และความเสี่ยง โดยผูกกลับไปหาเวอร์ชันของแอปที่มีอยู่แล้ว
#
# จุดสำคัญของการตามรอยไม่ใช่การเชื่อมสิ่งที่เชื่อมได้ แต่คือการทำให้เห็น
# **สิ่งที่ยังไม่เชื่อม** — ความต้องการที่ไม่มีใครทดสอบ และความเสี่ยงที่ไม่มี
# มาตรการรองรับ คือสิ่งแรกที่ผู้ตรวจประเมินมองหา

class RequirementKind(str, enum.Enum):
    USER_NEED = "user_need"        # ความต้องการผู้ใช้ (ขั้น NEED)
    DESIGN_INPUT = "design_input"  # ข้อกำหนดผลิตภัณฑ์ที่แปลงมาแล้ว
    REGULATORY = "regulatory"      # ข้อกำหนดจากกฎหมาย/มาตรฐาน


class RequirementStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    REJECTED = "rejected"          # ไม่ทำ พร้อมเหตุผล — มีค่าต่อผู้ตรวจไม่แพ้สิ่งที่ทำ


class Requirement(Base):
    """หนึ่งความต้องการ หนึ่งระเบียน พร้อมที่มาและผู้ให้ข้อมูล

    ISO 13485 ข้อ 7.3 กำหนดให้ปัจจัยนำเข้าการออกแบบต้องทบทวนและอนุมัติได้
    การจดว่า "หมอบอกมา" ไม่พอ — ต้องรู้ว่าใคร เมื่อไร และใครเป็นคนอนุมัติ
    """
    __tablename__ = "requirements"

    id           = Column(Integer, primary_key=True, index=True)
    app_id       = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    code         = Column(String(30), nullable=False, index=True)   # REQ-001
    kind         = Column(Enum(RequirementKind), default=RequirementKind.USER_NEED)
    title        = Column(String(300), nullable=False)
    description  = Column(Text, default="")
    source       = Column(String(300), default="")     # ใครบอก / มาจากเอกสารใด
    rationale    = Column(Text, default="")            # เหตุผลที่ทำหรือไม่ทำ
    priority     = Column(String(20), default="medium")
    status       = Column(Enum(RequirementStatus), default=RequirementStatus.DRAFT)
    reviewed_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at  = Column(DateTime, nullable=True)
    created_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime, default=utcnow)
    updated_at   = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "code", name="uq_requirement_app_code"),
    )


class RiskItem(Base):
    """รายการความเสี่ยงตามแนวทาง ISO 14971

    เก็บทั้งความเสี่ยงก่อนควบคุมและที่เหลืออยู่หลังควบคุม เพราะมาตรฐานสนใจ
    ความเสี่ยงคงเหลือมากกว่าความเสี่ยงตั้งต้น — การบอกว่า "มีมาตรการแล้ว"
    โดยไม่ประเมินว่าเหลือเท่าไร คือสิ่งที่ผู้ตรวจตีกลับ
    """
    __tablename__ = "risk_items"

    id            = Column(Integer, primary_key=True, index=True)
    app_id        = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    code          = Column(String(30), nullable=False, index=True)  # RISK-001
    hazard        = Column(String(300), nullable=False)             # อันตราย
    situation     = Column(Text, default="")                        # สถานการณ์ที่ทำให้เกิด
    harm          = Column(Text, default="")                        # ผลที่ตามมา
    severity      = Column(Integer, default=1)                      # 1-5
    probability   = Column(Integer, default=1)                      # 1-5
    control       = Column(Text, default="")                        # มาตรการควบคุม
    residual_severity    = Column(Integer, nullable=True)
    residual_probability = Column(Integer, nullable=True)
    accepted      = Column(Boolean, default=False)
    accepted_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_at   = Column(DateTime, nullable=True)
    # ความเสี่ยงที่มาตรการคือความต้องการข้อหนึ่ง — ผูกไว้เพื่อให้ตามรอยได้
    requirement_id = Column(Integer, ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True)
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "code", name="uq_risk_app_code"),
    )


class TestRecord(Base):
    """ผลการทดสอบหนึ่งครั้ง ผูกกับความต้องการและเวอร์ชันที่ทดสอบ

    ระบุเวอร์ชันเสมอ เพราะผลทดสอบที่ไม่รู้ว่าทดสอบกับอะไรไม่ใช่หลักฐาน
    และเก็บ audit_ref ไว้ชี้กลับไปยัง audit log เพื่อให้ยืนยันเวลาได้
    """
    __tablename__ = "test_records"

    id             = Column(Integer, primary_key=True, index=True)
    app_id         = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    code           = Column(String(30), nullable=False, index=True)  # TEST-001
    requirement_id = Column(Integer, ForeignKey("requirements.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    app_version    = Column(Integer, nullable=True)     # เวอร์ชันของแอปที่ทดสอบ
    method         = Column(Text, default="")           # วิธีทดสอบ
    expected       = Column(Text, default="")           # ผลที่คาดหวัง (เกณฑ์ผ่าน)
    actual         = Column(Text, default="")           # ผลที่ได้จริง
    result         = Column(String(20), default="pending")   # pass | fail | pending
    evidence_ref   = Column(String(500), default="")    # ไฟล์แนบ/ภาพหน้าจอ/log
    audit_ref      = Column(String(100), default="")    # request_id ใน audit log
    tested_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tested_at      = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "code", name="uq_test_app_code"),
    )


class ChangeStatus(str, enum.Enum):
    DRAFT = "draft"            # ระบบสร้างให้ตอน deploy ยังไม่มีใครประเมิน
    ASSESSED = "assessed"      # ประเมินผลกระทบแล้ว รออนุมัติ
    APPROVED = "approved"      # อนุมัติแล้ว
    REVERTED = "reverted"      # ย้อนกลับ


class ChangeRecord(Base):
    """การเปลี่ยนแปลงการออกแบบหนึ่งครั้ง ผูกกับเวอร์ชันที่เกิดจากมัน

    ISO 13485 ข้อ 7.3 กำหนดให้การเปลี่ยนแปลงการออกแบบต้องถูกทบทวน ประเมิน
    ผลกระทบ และอนุมัติก่อนนำไปใช้ โดยเฉพาะผลกระทบต่อผลิตภัณฑ์ที่ส่งมอบไปแล้ว

    ระเบียนนี้ถูกสร้าง **อัตโนมัติเมื่อ redeploy** เพราะการปล่อยเวอร์ชันใหม่คือ
    การเปลี่ยนแปลงไม่ว่าจะเรียกมันว่าอะไร ทีมที่ต้องจำเองว่าต้องมาบันทึกคือทีม
    ที่จะลืม และช่องว่างที่เกิดจากการลืมคือสิ่งที่ผู้ตรวจพบตอนไล่ดูย้อนหลัง

    สถานะเริ่มต้นเป็น draft พร้อมข้อความว่ายังไม่ประเมิน — ปรากฏในรายการช่องว่าง
    ทันที ไม่ใช่ผ่านไปเงียบ ๆ
    """
    __tablename__ = "change_records"

    id            = Column(Integer, primary_key=True, index=True)
    app_id        = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    code          = Column(String(30), nullable=False, index=True)   # CHG-001
    app_version   = Column(Integer, nullable=True, index=True)       # เวอร์ชันที่เกิดจากการเปลี่ยนนี้
    description   = Column(Text, default="")            # เปลี่ยนอะไร
    reason        = Column(Text, default="")            # ทำไมต้องเปลี่ยน
    # ประเมินผลกระทบ — หัวใจของข้อกำหนด ไม่ใช่แค่บันทึกว่าเปลี่ยนอะไร
    impact        = Column(Text, default="")
    # ผลกระทบต่อผลิตภัณฑ์ที่ส่งมอบ/ติดตั้งไปแล้ว (ข้อกำหนดถามตรง ๆ)
    affects_released = Column(Boolean, default=False)
    # ต้องทดสอบซ้ำหรือไม่ — ถ้าใช่แต่ยังไม่มีผลทดสอบของเวอร์ชันนี้ จะขึ้นเป็นช่องว่าง
    reverify_needed = Column(Boolean, default=True)
    requirement_ids = Column(Text, default="[]")        # JSON: ข้อกำหนดที่กระทบ
    risk_ids        = Column(Text, default="[]")        # JSON: ความเสี่ยงที่กระทบ
    status        = Column(Enum(ChangeStatus), default=ChangeStatus.DRAFT, index=True)
    origin        = Column(String(20), default="auto")  # auto (จาก deploy) | manual
    approved_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at   = Column(DateTime, nullable=True)
    created_by    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at    = Column(DateTime, default=utcnow)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "code", name="uq_change_app_code"),
    )


class DeviceVerdict(str, enum.Enum):
    UNASSESSED    = "unassessed"      # ยังไม่มีใครประเมิน
    NOT_DEVICE    = "not_device"      # ไม่เข้าข่ายนิยาม
    IS_DEVICE     = "is_device"       # เข้าข่าย ต้องเข้าสู่กระบวนการ
    ACCESSORY     = "accessory"       # อุปกรณ์เสริมตามนิยาม (2)
    NEEDS_RULING  = "needs_ruling"    # ก้ำกึ่ง ต้องยื่นให้ อย. วินิจฉัย


class DeviceDetermination(Base):
    """บันทึกการวินิจฉัยว่าโปรแกรมหนึ่งเข้าข่ายเครื่องมือแพทย์หรือไม่

    ตามนิยามมาตรา 4 แห่ง พ.ร.บ. เครื่องมือแพทย์ พ.ศ. 2551 และแก้ไขเพิ่มเติม
    ซอฟต์แวร์เป็นเครื่องมือแพทย์ได้ ถ้า **ผู้ผลิตหรือเจ้าของผลิตภัณฑ์มุ่งหมาย
    เฉพาะ** ให้ใช้กับมนุษย์หรือสัตว์ตามข้อ (ก) ถึง (ซ) — ตัวชี้ขาดจึงเป็น
    *วัตถุประสงค์การใช้งาน* ไม่ใช่ความสามารถทางเทคนิคของโปรแกรม

    เหตุผลที่ขั้นตอนนี้ต้องมาก่อนทุกอย่าง: ถ้าเข้าข่ายแล้วไม่ขึ้นทะเบียน คือ
    การกระทำที่ผิดกฎหมายตั้งแต่วันแรกที่นำออกใช้ ส่วนถ้าไม่เข้าข่ายแล้วไปทำ
    ระบบคุณภาพเต็มรูปแบบ ก็เสียเวลาและงบไปกับสิ่งที่ไม่มีใครเรียกร้อง
    การวินิจฉัยที่บันทึกไว้พร้อมเหตุผลจึงมีค่าทั้งสองทาง

    **ข้อจำกัดที่ต้องระบุทุกครั้ง**: นี่คือการประเมินตนเอง ไม่ใช่คำวินิจฉัย
    ของ อย. ผู้ที่มีอำนาจวินิจฉัยคือกองควบคุมเครื่องมือแพทย์เท่านั้น
    """
    __tablename__ = "device_determinations"

    id       = Column(Integer, primary_key=True, index=True)
    app_id   = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    code     = Column(String(30), nullable=False, index=True)   # MDD-001

    # ── วัตถุประสงค์ที่ประกาศไว้ — หัวใจของการวินิจฉัย ──
    intended_use = Column(Text, default="")        # เจ้าของผลิตภัณฑ์มุ่งหมายให้ใช้ทำอะไร
    target       = Column(String(20), default="none")   # none | human | animal | both

    # ข้อ (ก)–(ซ) ที่เข้าข่าย เก็บเป็น JSON list ของรหัสตัวอักษร
    purposes     = Column(Text, default="[]")

    # ผลสัมฤทธิ์เกิดจากเภสัชวิทยา/ภูมิคุ้มกัน/เผาผลาญเป็นหลักหรือไม่
    # ถ้าใช่ จะตกนิยามเครื่องมือแพทย์ และอาจเข้าข่ายยาแทน
    pharmacological = Column(Boolean, default=False)

    # เป็นอุปกรณ์เสริมที่มุ่งหมายให้ใช้ร่วมกับเครื่องมือแพทย์ ตามนิยาม (2)
    is_accessory    = Column(Boolean, default=False)

    # ประกาศว่า "ไม่ใช้ทางการแพทย์" ไว้หรือไม่ — เก็บไว้เพื่อเตือน ไม่ใช่เพื่อยกเว้น
    disclaims_medical = Column(Boolean, default=False)
    # วัดค่าที่ อย. ถือว่าเป็นเครื่องมือแพทย์เสมอ แม้ประกาศว่าไม่ใช้ทางการแพทย์
    measures_regulated = Column(Text, default="[]")

    # ประเภทของซอฟต์แวร์ตามอนุกรมวิธานของ อย. — SaMD กับ SiMD จัดระดับคนละวิธี
    software_kind  = Column(String(20), default="")     # wellness|nonmedical|samd|simd
    # สองแกนที่ใช้จัดระดับ SaMD ตามหลักเกณฑ์ 9–12
    samd_role      = Column(String(20), default="")     # inform|drive|monitor|control
    samd_condition = Column(String(20), default="")     # non_critical|critical
    rule_ref       = Column(String(40), default="")     # เช่น "ข้อ 10(1)"

    verdict     = Column(Enum(DeviceVerdict), default=DeviceVerdict.UNASSESSED, index=True)
    rationale   = Column(Text, default="")          # เหตุผลที่ระบบสรุป + ที่คนเพิ่มเติม
    risk_class  = Column(Integer, nullable=True)    # 1–4 เมื่อเข้าข่าย
    class_note  = Column(Text, default="")

    # ยื่นขอคำวินิจฉัยอย่างเป็นทางการจาก อย. แล้วหรือยัง
    ruling_requested = Column(Boolean, default=False)
    ruling_ref       = Column(String(120), default="")

    assessed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assessed_at = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=utcnow)
    updated_at  = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "code", name="uq_mdd_app_code"),
    )


class AiDossier(Base):
    """แฟ้มข้อมูลสำหรับซอฟต์แวร์ที่ใช้ AI/ML ตามแนวทางการขึ้นทะเบียน SaMD

    เอกสารของกองควบคุมเครื่องมือแพทย์เรียกร้องสิ่งที่ทีม AI ส่วนใหญ่ไม่ได้เก็บไว้
    ตั้งแต่ต้น แล้วย้อนกลับไปทำไม่ได้ — ที่มาของชุดข้อมูลตามภูมิศาสตร์และช่วงเวลา
    องค์ประกอบทางประชากร เกณฑ์คัดข้อมูลออก และสัดส่วนการแบ่งชุดฝึก/ปรับ/ทดสอบ
    ถ้าไม่บันทึกตอนเทรน ก็พิสูจน์ย้อนหลังไม่ได้ว่าโมเดลไม่มีอคติแฝง

    ข้อที่เข้มที่สุดคือ **ผลต้องแยกตามกลุ่มย่อย** อายุ เพศ ชาติพันธุ์ และสภาวะโรค
    ค่าเฉลี่ยรวมที่ดูดีอาจกลบไว้ว่าโมเดลทำงานแย่กับคนบางกลุ่ม และค่าทุกตัวต้องมี
    ช่วงความเชื่อมั่นกำกับ ตัวเลขเดี่ยว ๆ ที่ไม่มีช่วงความเชื่อมั่นไม่ถือเป็นหลักฐาน

    อีกข้อที่บังคับและเกี่ยวกับ iVS โดยตรง คือต้องเปิดเผยว่าข้อมูลถูกประมวลผล
    ในเครื่ององค์กรเอง หรือส่งออกไปนอกประเทศ
    """
    __tablename__ = "ai_dossiers"

    id     = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── วัตถุประสงค์การใช้แบบมีโครงสร้าง: อะไร ใคร ที่ไหน ──
    purpose_kinds = Column(Text, default="[]")     # diagnosis|screening|triage|...
    severity      = Column(String(20), default="")  # non_serious|serious|critical
    user_type     = Column(String(20), default="")  # lay|clinical|both
    environment   = Column(String(20), default="")  # non_clinical|general|specialty
    populations   = Column(Text, default="")        # อายุ เพศ ชาติพันธุ์ กลุ่มเปราะบาง
    contraindications = Column(Text, default="")
    compiled_statement = Column(Text, default="")   # ประโยควัตถุประสงค์ที่ประกอบแล้ว

    # ── การทำงานของซอฟต์แวร์ ──
    input_sources = Column(Text, default="")
    processing    = Column(Text, default="")        # deterministic|ml|simulation
    outputs       = Column(Text, default="")
    destination   = Column(Text, default="")

    # ── ความเข้ากันได้และความมั่นคงปลอดภัย ──
    interop       = Column(Text, default="[]")      # hl7|fhir|dicom|his|pacs|lis
    # ข้อบังคับ: ต้องเปิดเผยว่าประมวลผลในเครื่องหรือส่งออกนอกประเทศ
    data_locality = Column(String(20), default="")  # on_premise|domestic_cloud|offshore|mixed
    locality_note = Column(Text, default="")

    # ── ชุดข้อมูล (AI/ML) ──
    uses_ai        = Column(Boolean, default=False)
    data_sourcing  = Column(Text, default="")       # แหล่งที่มาเชิงภูมิศาสตร์ + ช่วงเวลาเก็บ
    data_demographics = Column(Text, default="")
    data_exclusion = Column(Text, default="")
    split_train    = Column(Integer, nullable=True)
    split_val      = Column(Integer, nullable=True)
    split_test     = Column(Integer, nullable=True)

    # ── สมรรถนะ ──
    # เก็บเป็น JSON: [{"metric":"sensitivity","value":95.0,"ci_low":93.1,"ci_high":96.4}]
    metrics   = Column(Text, default="[]")
    # ผลแยกตามกลุ่มย่อย: [{"group":"อายุ 60 ปีขึ้นไป","metric":"sensitivity","value":88.0,...}]
    subgroups = Column(Text, default="[]")

    # ── หลังออกสู่ตลาด ──
    update_plan   = Column(Text, default="")
    incident_plan = Column(Text, default="")

    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class EpChecklist(Base):
    """Essential Principles checklist — เอกสารบังคับทั้งช่องทาง Full และ Abridged

    รูปแบบตามที่ อย. ยอมรับ แต่ละแถวต้องตอบสามคำถาม: หลักการข้อนี้ใช้กับ
    ผลิตภัณฑ์หรือไม่ (Applicable) · แสดงความสอดคล้องด้วยวิธีใด (Method of
    Conformity) · และหลักฐานอยู่ในเอกสารฉบับไหน (Identity of Specific Documents)

    ช่องที่สามคือช่องที่ทำให้เอกสารนี้ต่างจากแบบฟอร์มติ๊กถูก การเขียนว่า
    "สอดคล้องตาม ISO 14971" โดยไม่ระบุว่าแฟ้มจัดการความเสี่ยงเลขที่เท่าไร
    คือคำกล่าวอ้างที่ตรวจไม่ได้ ผู้ประเมินจึงถามหาเลขเอกสารเสมอ

    เก็บแถวเป็น JSON เพราะชุดหลักการเป็นชุดตายตัวตามแม่แบบที่เลือก การแยกเป็น
    ตารางย่อยจะเพิ่มความซับซ้อนโดยไม่ได้อะไรกลับมา

    เอกสารระบุว่า checklist ต้องครบถ้วนสมบูรณ์ **และมีการลงนาม พร้อมวันที่
    อนุมัติ** ช่องลงนามสามช่องจึงเป็นส่วนหนึ่งของความครบถ้วน ไม่ใช่ส่วนเสริม
    """
    __tablename__ = "ep_checklists"

    id       = Column(Integer, primary_key=True, index=True)
    app_id   = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                      nullable=False, index=True, unique=True)
    # แม่แบบที่ใช้ — อย. ยอมรับสามฉบับ ต้องระบุว่าอ้างฉบับไหน
    template = Column(String(20), default="amdd")   # amdd | hsa | eu

    # [{"code":"EP1","applicable":true,"method":"ISO 14971:2019",
    #   "docs":"RISK-FILE-001","note":""}, ...]
    rows = Column(Text, default="[]")

    prepared_by   = Column(String(120), default="")
    prepared_role = Column(String(120), default="")
    reviewed_by   = Column(String(120), default="")
    reviewed_role = Column(String(120), default="")
    approved_by   = Column(String(120), default="")
    approved_role = Column(String(120), default="")
    approved_at   = Column(DateTime, nullable=True)

    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class SoftwareSafetyRecord(Base):
    """บันทึกตาม IEC 62304 — ระดับความปลอดภัยของซอฟต์แวร์ และผลตรวจรายข้อ

    IEC 62304 ต่างจากมาตรฐานอื่นตรงที่ **ปริมาณงานขึ้นกับระดับความปลอดภัย**
    ที่ประกาศไว้ ระดับ A ทำน้อย ระดับ C ทำมากที่สุด การเลือกระดับจึงเป็นการ
    ตัดสินใจที่มีผลตามมาโดยตรง และเป็นข้อแรกที่ผู้ประเมินจะย้อนถามว่าเลือก
    ด้วยเหตุผลอะไร

    เกณฑ์คือความรุนแรงของอันตรายที่เป็นไปได้ **ก่อน**มาตรการควบคุมภายนอก —
    A ไม่มีการบาดเจ็บหรือความเสียหายต่อสุขภาพ · B บาดเจ็บไม่ร้ายแรง ·
    C เสียชีวิตหรือบาดเจ็บสาหัส การประกาศระดับ A เพื่อลดงานเอกสารโดยไม่มี
    เหตุผลรองรับ คือสิ่งที่ตรวจพบได้ง่ายที่สุดเมื่อเทียบกับทะเบียนความเสี่ยง
    """
    __tablename__ = "software_safety_records"

    id     = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                    nullable=False, index=True, unique=True)

    safety_class    = Column(String(1), default="")   # A | B | C
    class_rationale = Column(Text, default="")
    # ซอฟต์แวร์ที่มีอยู่ก่อนแล้วนำมาใช้ซ้ำ มีเส้นทางเฉพาะในข้อ 4.4
    legacy_software = Column(Boolean, default=False)
    # ส่วนประกอบจากภายนอก (SOUP) ต้องระบุแยกตามข้อ 5.3.3–5.3.4 และ 8.1.2
    soup_items      = Column(Text, default="[]")

    # [{"clause":"5.4.1","evidence":"...","result":"pass|fail|na","doc":"..."}]
    rows = Column(Text, default="[]")

    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class SecurityRecord(Base):
    """กิจกรรมความมั่นคงปลอดภัยตลอดวงจรชีวิตผลิตภัณฑ์

    เอกสารแนวทางการขึ้นทะเบียน SaMD ระบุสี่อย่างที่ผู้ประเมินคาดหวังจะเห็น —
    การออกแบบตามหลัก safe by design · ตารางตามรอยภัยคุกคามกับมาตรการควบคุม ·
    รายงานผลการทดสอบ · และแผนรับมือหลังผลิตภัณฑ์ออกสู่ตลาด

    ส่วนที่ **ไม่ได้** เก็บในตารางนี้คือสถานะการคุ้มครองข้อมูลส่วนบุคคลของแอป
    เพราะ iVS รู้อยู่แล้วจากบันทึกกิจกรรมการประมวลผล นโยบายรายฟิลด์ โหมดการ
    เข้าถึง และการเปิดช่องทางสาธารณะ การให้กรอกซ้ำจะได้เอกสารที่ขัดกับระบบจริง
    ทันทีที่ใครเปลี่ยนค่าใดค่าหนึ่ง — จึงคำนวณสดทุกครั้งแทน
    """
    __tablename__ = "security_records"

    id     = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                    nullable=False, index=True, unique=True)

    # มาตรฐานที่อ้างว่าออกแบบตาม
    standards = Column(Text, default="[]")

    # ตารางตามรอยภัยคุกคาม — ที่เอกสารเรียกว่า traceability matrix ด้านความมั่นคง
    # [{"threat":"","vuln":"","control":"","verification":"","status":""}]
    threats = Column(Text, default="[]")

    # รายงานผลการทดสอบ
    # [{"kind":"vuln_scan|pentest|risk_analysis","date":"","ref":"","result":"","note":""}]
    reports = Column(Text, default="[]")

    # แผนหลังออกสู่ตลาด — เอกสารระบุไว้สี่แผน
    update_plan   = Column(Text, default="")
    patch_plan    = Column(Text, default="")
    incident_plan = Column(Text, default="")
    fsca_plan     = Column(Text, default="")
    secure_deploy = Column(Text, default="")

    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class DhfSnapshot(Base):
    """ภาพนิ่งของแฟ้มการออกแบบ ณ เวลาที่ส่งออก

    ISO 14971 ข้อ 10 กำหนดให้เก็บข้อมูลระหว่างการผลิตและหลังการผลิต แล้วนำกลับมา
    ประเมินความเสี่ยงใหม่ ข้อนี้เป็นข้อที่แทบไม่มีใครทำได้จริง ไม่ใช่เพราะไม่เข้าใจ
    แต่เพราะไม่มีข้อมูลว่าผลิตภัณฑ์เปลี่ยนไปอย่างไรหลังปล่อยใช้งาน

    การส่งออกแต่ละครั้งจึงถูกบันทึกเป็นภาพนิ่ง — ค่าแฮชของแฟ้ม เวลาที่อ้างอิง
    แหล่งเวลามาตรฐาน และตัวเลขสรุปทั้งหมด ณ ขณะนั้น เมื่อมีภาพนิ่งสองครั้ง
    ระบบจะเทียบได้ว่าอะไรเปลี่ยนไป: ความเสี่ยงใดเพิ่มเข้ามา ความเสี่ยงใดถูกปิด
    ข้อกำหนดใดเพิ่ม เวอร์ชันใดถูกปล่อย และข้อของมาตรฐานข้อใดขยับสถานะ

    นี่คือสิ่งที่ทำให้เอกสารประกอบการประเมินไม่ใช่ภาพนิ่งของวันยื่น แต่เป็น
    หลักฐานความสอดคล้องที่ต่อเนื่องตามเวลา
    """
    __tablename__ = "dhf_snapshots"

    id       = Column(Integer, primary_key=True, index=True)
    app_id   = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    code     = Column(String(30), nullable=False, index=True)   # SNAP-001

    app_version  = Column(Integer, nullable=True)
    zip_sha256   = Column(String(64), default="")
    file_count   = Column(Integer, default=0)
    size_bytes   = Column(Integer, default=0)

    # เวลาอ้างอิงจากแหล่งเวลามาตรฐาน — สิ่งที่ทำให้ลำดับเวลาของภาพนิ่งโต้แย้งได้ยาก
    ntp_server    = Column(String(120), default="")
    ntp_offset_ms = Column(String(40), default="")

    # ตัวเลขสรุปและรายละเอียดที่ใช้เทียบ เก็บเป็น JSON เพื่อให้เทียบข้ามรุ่นได้
    # แม้ภายหลังจะเพิ่มตัวชี้วัดใหม่
    metrics = Column(Text, default="{}")

    note       = Column(Text, default="")
    taken_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    taken_at   = Column(DateTime, default=utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("app_id", "code", name="uq_snapshot_app_code"),
    )


class DependencyKind(str, enum.Enum):
    HTTP_API = "http_api"    # เรียก API ของอีกแอปหนึ่งบนเครื่องนี้
    DATABASE = "database"    # ใช้ฐานข้อมูลที่อยู่นอกคอนเทนเนอร์ตัวเอง
    EXTERNAL = "external"    # ออกนอกองค์กร — LINE, OpenAI, SMTP, NTP


class DependencyOrigin(str, enum.Enum):
    SCAN     = "scan"        # ระบบตรวจพบจากสถานะจริงของเครื่อง
    DECLARED = "declared"    # คนประกาศเอง
    INFERRED = "inferred"    # เดาจากการอ่านโค้ด ต้องมีคนยืนยันก่อนถือว่าจริง
    # โทเคนแลกเปลี่ยนข้อมูลที่ยังไม่หมดอายุและไม่ถูกเพิกถอน
    #
    # แข็งแรงกว่า scan ด้วยซ้ำ: ตัวแปรใน env เป็นแค่ค่าที่ใครก็ตั้งไว้ ส่วนโทเคน
    # คือช่องทางที่มีคนอนุมัติ มีขอบเขตพาธกำกับ เพิกถอนได้ และทุกครั้งที่ถูกใช้
    # มีบันทึกไว้ ถ้าแผนที่ไม่อ่านตารางนี้ เส้นที่ iVS เป็นคนเปิดให้เองจะไม่ปรากฏ
    TOKEN    = "token"


class AppDependency(Base):
    """แอปหนึ่งพึ่งพาอะไร

    ทุกตารางอื่นใน iVS ผูกกับ app_id เดียว จึงตอบได้แค่ว่าแอปหนึ่ง ๆ เป็นอย่างไร
    ไม่มีตารางใดตอบได้ว่าแอปไหนเกี่ยวกับแอปไหน คำถามอย่าง "ถ้าตัวนี้หยุด อะไรพัง"
    หรือ "การแก้ครั้งนี้กระทบใคร" จึงไม่มีที่ให้ไปหาคำตอบ และเคยทำให้เข้าใจผิดว่า
    แอปสองตัวที่ชื่อคล้ายกันเป็นตัวเดียวกันมาแล้ว

    ระเบียนนี้เก็บเส้นเชื่อม ไม่ใช่จุด สิ่งที่ต้องระวังคือความน่าเชื่อถือของแต่ละ
    เส้นไม่เท่ากัน เส้นที่มาจากการอ่านสถานะจริงของเครื่องกับเส้นที่ AI เดาจากโค้ด
    ต้องแยกกันให้ออก มิฉะนั้นแผนที่จะดูน่าเชื่อกว่าที่ควรเป็น ซึ่งอันตรายกว่า
    การไม่มีแผนที่
    """
    __tablename__ = "app_dependencies"

    id           = Column(Integer, primary_key=True, index=True)
    from_app_id  = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False, index=True)
    # ปลายทางเป็นแอปบนเครื่องนี้ หรืออยู่ข้างนอก อย่างใดอย่างหนึ่ง
    to_app_id    = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"), nullable=True, index=True)
    external_ref = Column(String(300), default="")     # api.openai.com, time.navy.mi.th
    kind         = Column(Enum(DependencyKind), nullable=False)
    origin       = Column(Enum(DependencyOrigin), default=DependencyOrigin.SCAN, index=True)
    # เจอที่ไหน — ชื่อตัวแปรหรือแหล่งที่มา ไม่เก็บค่า เพราะค่ามักเป็นความลับ
    evidence     = Column(Text, default="")
    confirmed    = Column(Boolean, default=False, index=True)
    confirmed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    # ตรวจพบครั้งล่าสุดเมื่อไร — เส้นที่หายไปจากการสแกนไม่ถูกลบ แต่จะเก่าลง
    last_seen_at = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=utcnow)
    updated_at   = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "from_app_id", "to_app_id", "external_ref", "kind",
            name="uq_dep_edge",
        ),
    )


class FlowStepStatus(str, enum.Enum):
    UNVERIFIED = "unverified"   # ยังไม่เคยตรวจ
    OK         = "ok"           # ปลายทางยังตอบ และ schema ยังเหมือนเดิม
    DRIFTED    = "drifted"      # schema ของปลายทางเปลี่ยนไปจากตอนผูก
    BROKEN     = "broken"       # ปลายทางไม่ตอบ หรือรายการที่ผูกไว้หายไป


class FlowStep(Base):
    """ขั้นตอนหนึ่งในเส้นทางการทำงานที่คนเป็นผู้ประกาศ

    iVS เห็นแค่คอนเทนเนอร์กับพอร์ต ไม่มีอะไรใน runtime บอกได้ว่า
    ลงทะเบียน → ออกตั๋ว → ชำระเงิน → ออก QR → เช็คอิน คือลำดับของธุรกิจ
    ถ้าให้ AI เดาลำดับนี้ จะได้แผนภาพที่ดูน่าเชื่อแต่ผิด ซึ่งอันตรายกว่าไม่มี

    การแบ่งงานจึงเป็น: **คนประกาศลำดับ เครื่องตรวจว่ายังจริง** คนผูกแต่ละขั้นกับ
    endpoint ที่มีอยู่จริงในคลัง API แล้วระบบเช็คทุกวันว่าปลายทางยังตอบ และ
    schema ยังไม่เปลี่ยนไปจากวันที่ผูก

    ที่ต้องมีเครื่องคอยตรวจ เพราะเอกสารที่คนเขียนด้วยมือจะผิดภายในสัปดาห์ถัดไป
    (ดู OPERATIONS.md) แผนภาพ flow ที่ไม่มีใครตรวจก็เป็นแบบเดียวกัน
    """
    __tablename__ = "flow_steps"

    id           = Column(Integer, primary_key=True, index=True)
    flow_key     = Column(String(80), nullable=False, index=True)   # yeepeng-checkin-2026
    flow_label   = Column(String(200), default="")
    step_no      = Column(Integer, nullable=False)
    label        = Column(String(200), nullable=False)              # "ออกตั๋ว"
    app_id       = Column(Integer, ForeignKey("apps.id", ondelete="SET NULL"), nullable=True, index=True)
    api_entry_id = Column(Integer, ForeignKey("api_catalog_entries.id", ondelete="SET NULL"), nullable=True)
    # ค่า schema_hash ของปลายทาง ณ วันที่ผูก — ใช้เทียบว่าหน้าตา API เปลี่ยนไปไหม
    bound_schema_hash = Column(String(64), default="")
    # ขั้นที่ไม่มีปลายทางให้ตรวจ มีสองแบบ และเป็นคนละเรื่องกัน
    #   manual  — คนทำเอง เช่นตรวจบัตรหน้างาน รับเงินสด ไม่มีวันมี endpoint
    #   planned — ตั้งใจให้เครื่องทำ แต่ยังไม่ได้เชื่อม
    # เรียกรวมกันว่า "คนทำเอง" ทำให้งานที่ยังไม่ได้ทำหายไปจากสายตา — ไม่มีใคร
    # ทวงสิ่งที่ระบบบอกว่าไม่ใช่หน้าที่ของมัน
    unbound_kind = Column(String(20), default="manual")
    status       = Column(Enum(FlowStepStatus), default=FlowStepStatus.UNVERIFIED, index=True)
    drift_note   = Column(Text, default="")
    verified_at  = Column(DateTime, nullable=True)
    created_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime, default=utcnow)
    updated_at   = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("flow_key", "step_no", name="uq_flow_step_no"),
    )


class VaultCapability(str, enum.Enum):
    """สิ่งที่ทำได้กับกุญแจหนึ่งใบ — ไม่ใช่ระดับความไว้ใจ แต่เป็นการกระทำที่ระบุได้"""
    INJECT = "inject"   # ค่าถูกใส่เข้า env ของคอนเทนเนอร์ตอน deploy
    REVEAL = "reveal"   # ผู้ดูแลเปิดดูค่าจริงเพื่อคัดลอกได้
    ROTATE = "rotate"   # เปลี่ยนค่าของกุญแจใบนี้ได้


class VaultGrant(Base):
    """สิทธิ์หนึ่งบรรทัด: กุญแจใบไหน ให้แอปตัวไหน ทำอะไรได้

    เดิม iVS ส่งกุญแจ **ทุกใบเข้าทุกแอป** — `db.query(VaultKey).all()` แล้วยัด
    ลง env ของทุกคอนเทนเนอร์ เกมสถิตจึงถือกุญแจ OpenAI ชุดเดียวกับแอปที่เรียก AI
    จริง ถ้าแอปใดถูกเจาะหรือมีใครอ่าน env ได้ กุญแจหลุดทั้งชุดพร้อมกัน

    ตารางนี้กลับด้านเป็น **ปฏิเสธไว้ก่อน** ไม่มีแถวที่ตรงกัน = ไม่ได้รับกุญแจ
    ไม่มีไวลด์การ์ดตอนทำงานจริง การให้สิทธิ์ตามรูปแบบ namespace จะถูกกางออกเป็น
    แถวจริงตั้งแต่ตอนกด เพื่อให้คำถามว่า "ตอนนี้ใครถือกุญแจใบนี้บ้าง" ตอบได้ด้วย
    การอ่านตาราง ไม่ใช่ด้วยการตีความรูปแบบ

    เพิกถอนแล้วไม่ลบแถว — `revoked_at` เก็บไว้เป็นประวัติว่าเคยให้ไว้เมื่อไร
    ถอนเมื่อไร ซึ่งเป็นสิ่งที่ผู้ตรวจถามหลังเกิดเหตุ
    """
    __tablename__ = "vault_grants"

    id           = Column(Integer, primary_key=True, index=True)
    vault_key_id = Column(Integer, ForeignKey("vault_keys.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    app_id       = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    capability   = Column(Enum(VaultCapability), nullable=False,
                          default=VaultCapability.INJECT, index=True)
    note         = Column(Text, default="")
    # ชื่อตัวแปรเฉพาะสิทธิ์บรรทัดนี้ — ว่างไว้ = ใช้ชื่อของกุญแจ
    #
    # ความลับที่สองระบบใช้ร่วมกันมักมีชื่อคนละอย่างที่ปลายทางแต่ละฝั่ง Seat Event
    # อ่าน ROSTER_PASSWORD ส่วน Check-in Event อ่าน GUEST_EVENT_PASSWORD ทั้งที่
    # เป็นค่าเดียวกัน ถ้าชื่ออยู่ที่กุญแจอย่างเดียว ทางออกเดียวคือสร้างกุญแจ
    # สองใบใส่ค่าเดียวกัน ซึ่งจะหมุนไม่พร้อมกันแล้วเพี้ยนวันหนึ่ง
    #
    # ชื่อจึงเป็นเรื่องของ "ใบนี้ให้ใคร" ไม่ใช่ "ใบนี้คืออะไร" — ที่เดียวกับที่
    # ขอบเขตตามตัวตนอยู่แล้ว
    env_override = Column(String(120), default="")
    expires_at   = Column(DateTime, nullable=True)
    granted_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    granted_at   = Column(DateTime, default=utcnow)
    revoked_at   = Column(DateTime, nullable=True, index=True)
    revoked_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("vault_key_id", "app_id", "capability", name="uq_vault_grant"),
    )


# --------------------------------------------------------------------------- #
# รอยเท้าของเครื่องติดตั้ง — ฐานของการย้ายรุ่น Free → Pro → Enterprise
#
# ลูกค้าส่วนใหญ่เริ่มจาก Free แล้วค่อยขยับ ระหว่างนั้น AI ของลูกค้าจะแก้โค้ด
# iVS เอง ซึ่งเป็นสิ่งที่ iVS ชวนให้ทำตั้งแต่แรก ตอนย้ายรุ่นจึงมีสามอย่าง
# เคลื่อนพร้อมกัน ไม่ใช่อย่างเดียว: ข้อมูล โค้ด และคอนเทนเนอร์ที่รันอยู่จริง
#
# สองตารางนี้คือชั้นแรกของสี่ชั้น ดู docs/iVS_Edition_Migration_Design.md
# --------------------------------------------------------------------------- #


class Installation(Base):
    """หนึ่งแถวต่อหนึ่งเครื่องติดตั้ง ไม่มีวันมีสอง (id ถูกบังคับเป็น 1)

    ค่าที่นี่ผูกกับ "เครื่องนี้" ไม่ใช่ "รุ่นนี้" การอัปเกรดรุ่นห้ามแตะ เพราะ
    คอนเทนเนอร์ที่รันอยู่จริงบนเครื่องอ้างอิงค่าพวกนี้อยู่

    ตัวอย่างที่ทำให้ต้องมีตารางนี้: ลูกค้ารัน Free มาแปดเดือน มีสิบสองแอปชื่อ
    ivs-<slug> แล้วอัปเกรดเป็น Pro ที่ตั้งคำนำหน้าเป็น ivspro- หน้าจอจะว่าง
    เปล่าทั้งที่คอนเทนเนอร์ยังทำงานอยู่ ลูกค้าเห็นว่าแอปหาย จึงดีพลอยใหม่
    ได้คอนเทนเนอร์ซ้อน พอร์ตชน แล้วของเดิมถูกทับ ไม่มีขั้นไหนแจ้งเตือนเลย

    คำนำหน้าจึงเป็นสมบัติของเครื่อง ตั้งครั้งเดียวตอนติดตั้งครั้งแรกแล้วห้าม
    เปลี่ยนตลอดอายุเครื่องนั้น และมีด่านตอนบูตคอยยืนยันว่ายังตรงกันอยู่
    """
    __tablename__ = "installation"

    id                 = Column(Integer, primary_key=True)   # บังคับ = 1 เสมอ
    install_id         = Column(String(36), unique=True, nullable=False)
    installed_at       = Column(DateTime, default=utcnow)
    installed_version  = Column(String(20), default="")

    # ── ค่าที่ห้ามเปลี่ยนหลังติดตั้ง ──
    container_prefix   = Column(String(32), nullable=False, default="ivs-")
    port_range_start   = Column(Integer, nullable=False, default=10000)
    port_range_end     = Column(Integer, nullable=False, default=10999)
    docker_network     = Column(String(64), nullable=False, default="ivs-apps")

    # ── สถานะรุ่นปัจจุบัน ──
    # สองแกน ไม่ใช่แกนเดียว edition ตอบว่ากี่เครื่องและใครรับผิดชอบ variant
    # ตอบว่ากล่องนี้แจกมาเพื่อทำเรื่องอะไร iVS-eContract เป็นรุ่นฟรีที่มีโมดูล
    # สัญญาครบ ส่วน iVS Pro รุ่น base ไม่มีโมดูลนั้นแต่ดูแลได้หลายเครื่อง
    edition            = Column(String(8), default="FREE", index=True)
    variant            = Column(String(24), default="base", index=True)
    variant_changed_at = Column(DateTime, nullable=True)
    edition_changed_at = Column(DateTime, nullable=True)


class SchemaMigration(Base):
    """หนึ่งแถวต่อหนึ่ง migration ที่ลงแล้ว เรียงตามลำดับ ไม่ลบ

    ก่อนมีตารางนี้ การย้ายสคีมาเป็นรายการ ALTER TABLE ที่ยิงรวดเดียวทุกครั้ง
    ที่บูตโดยไม่จดอะไรไว้ ผลคือฐานข้อมูลตอบไม่ได้ว่าตัวเองผ่านอะไรมาแล้ว ซึ่ง
    ยอมรับได้ตอนมีเครื่องเดียว แต่ยอมรับไม่ได้ตอนต้องอัปเกรดเครื่องของลูกค้าที่
    เราไม่เคยเห็นและถอยกลับไม่ได้ถ้าพลาด

    checksum เก็บ sha256 ของสิ่งที่รันจริง ไว้จับกรณีที่มีคนแก้ migration เก่า
    หลังปล่อยออกไปแล้ว — เครื่องที่ลงก่อนกับเครื่องที่ลงหลังจะได้สคีมาต่างกัน
    ทั้งที่บัญชีบอกว่าผ่าน migration เดียวกัน เป็นบั๊กที่หาต้นตอยากที่สุดแบบหนึ่ง

    หลักเดียวกับ ROPA: บัญชีที่ลบได้คือบัญชีที่เชื่อไม่ได้
    """
    __tablename__ = "schema_migrations"

    id           = Column(Integer, primary_key=True, index=True)
    migration_id = Column(String(64), unique=True, nullable=False, index=True)
    # รุ่นที่ลง migration นี้ — migration ของ Pro จะไม่ปรากฏบนเครื่อง Free
    edition      = Column(String(8), default="FREE")
    app_version  = Column(String(20), default="")
    applied_at   = Column(DateTime, default=utcnow, index=True)
    duration_ms  = Column(Integer, default=0)
    checksum     = Column(String(64), default="")
    ok           = Column(Boolean, default=True)
    error        = Column(Text, default="")


class FileBaseline(Base):
    """ลายนิ้วมือของไฟล์หนึ่งไฟล์ ณ เวลาที่บันทึก

    ชั้นที่สามของรอยเท้า และเป็นชั้นที่ตัดสินว่าการอัปเกรดจะราบรื่นหรือทับงาน
    ลูกค้า สคีมาย้ายได้เพราะเราคุมมันทั้งหมด แต่โค้ดที่ AI ของลูกค้าแก้ไว้ในไฟล์
    แกนนั้นเราไม่รู้ว่ามีอยู่ จนกว่าจะเขียนทับมันไปแล้ว

    zone แบ่งสามเขตตามที่ประกาศไว้ในแผน:
        core    แกนที่เราดูแล การอัปเกรดเขียนทับ ถ้าลูกค้าแก้ต้องเตือนก่อน
        extend  เขตของลูกค้า (custom/) การอัปเกรดไม่แตะตลอดไป
        gray    ตั้งค่าและธีม รวมสามทาง แจ้งเมื่อชน

    source บอกว่าลายนี้เชื่อได้แค่ไหน:
        release     มาจากไฟล์รายการที่แนบมากับรุ่น — บอกได้จริงว่าลูกค้าแก้อะไร
        first_boot  จดจากสภาพที่พบตอนบูตแรก — ถ้าลูกค้าแก้ไปก่อนหน้านั้นแล้ว
                    การแก้นั้นจะกลายเป็นค่าตั้งต้นโดยที่เราไม่มีทางรู้

    ความต่างสองอย่างนี้ต้องปรากฏในรายงาน ไม่ใช่ซ่อนไว้ เพราะรายงานที่บอกว่า
    "ไม่มีไฟล์ถูกแก้" ทั้งที่วัดจากฐานที่แก้แล้ว เป็นรายงานที่หลอกคนอ่าน
    """
    __tablename__ = "file_baselines"

    id          = Column(Integer, primary_key=True, index=True)
    path        = Column(String(400), nullable=False, index=True)
    zone        = Column(String(12), default="core", index=True)
    sha256      = Column(String(64), default="")
    size        = Column(Integer, default=0)
    version     = Column(String(20), default="")
    source      = Column(String(12), default="first_boot")
    recorded_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("path", name="uq_file_baseline_path"),
    )


class UpgradeSnapshot(Base):
    """สภาพของเครื่องก่อนการอัปเกรดหนึ่งครั้ง เก็บไว้เพื่อให้ถอยได้

    การอัปเกรดที่ถอยไม่ได้คือการอัปเกรดที่ไม่มีใครกล้ากด โดยเฉพาะบนเครื่องที่มี
    ข้อมูลคนไข้หรืองานจริงอยู่ แถวนี้จึงบันทึกทุกอย่างที่ต้องใช้ตอบคำถาม
    "เมื่อกี้มันเป็นยังไง" ตั้งแต่ก่อนแตะอะไร

    report เก็บรายงานก่อนอัปเกรดทั้งฉบับไว้เป็นหลักฐาน ไม่ใช่แค่ผลสรุป เพราะ
    ข้อโต้แย้งหลังเกิดเหตุมักอยู่ที่ว่า "ตอนนั้นระบบเตือนหรือเปล่า"
    """
    __tablename__ = "upgrade_snapshots"

    id             = Column(Integer, primary_key=True, index=True)
    from_edition   = Column(String(8), default="")
    to_edition     = Column(String(8), default="")
    from_version   = Column(String(20), default="")
    to_version     = Column(String(20), default="")
    started_at     = Column(DateTime, default=utcnow, index=True)
    finished_at    = Column(DateTime, nullable=True)
    outcome        = Column(String(16), default="preflight")  # preflight|running|ok|failed|rolled_back
    db_backup_path = Column(String(400), default="")
    containers     = Column(Text, default="[]")   # JSON ของคอนเทนเนอร์ ณ ตอนนั้น
    report         = Column(Text, default="")     # รายงานก่อนอัปเกรดทั้งฉบับ (JSON)
    created_by     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EndpointExposure(str, enum.Enum):
    """สถานะการเปิดเส้นทางหนึ่งให้ช่องทางภาษาธรรมชาติเรียกได้"""
    PENDING = "pending"    # พบแล้ว ยังไม่มีใครอนุมัติ — เรียกไม่ได้
    ALLOWED = "allowed"    # คนอนุมัติแล้ว
    DENIED  = "denied"     # คนปฏิเสธแล้ว — ไม่ต้องถามซ้ำทุกครั้งที่สแกน


class AppEndpointExposure(Base):
    """เส้นทางหนึ่งของแอปหนึ่ง กับคำตอบว่าคนอนุญาตให้ AI เรียกหรือยัง

    การที่แอปประกาศ OpenAPI ไม่ได้แปลว่าเจ้าของยินยอมให้เปิด สคีมาเขียนไว้ให้
    นักพัฒนาอ่าน ไม่ได้เขียนไว้ให้ช่องทางสาธารณะใช้ และบางแอปมีเส้นทางที่คืน
    ข้อมูลซึ่งไม่ควรออกไปไหนเลย เช่น รายการผู้ใช้ ค่าตั้งค่า หรือกุญแจ

    หลักเดียวกับ AppFieldPolicy: การสแกนคือหลักฐาน ไม่ใช่ความยินยอม แถวเกิดใหม่
    เป็น PENDING เสมอ และ PENDING เรียกไม่ได้ ไม่ใช่เรียกได้ไปก่อน

    เก็บ DENIED ไว้ด้วยแทนที่จะลบ เพราะการสแกนรอบหน้าจะเจอเส้นทางเดิมอีก ถ้าลบ
    ทิ้งคนเดิมต้องมาปฏิเสธซ้ำทุกครั้ง แล้วสุดท้ายจะกดผ่าน ๆ ซึ่งทำลายจุดประสงค์
    ของการให้คนตัดสินตั้งแต่ต้น
    """
    __tablename__ = "app_endpoint_exposures"

    id           = Column(Integer, primary_key=True, index=True)
    app_id       = Column(Integer, ForeignKey("apps.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    method       = Column(String(10), default="GET")
    path         = Column(String(500), nullable=False)
    summary      = Column(String(300), default="")
    # openapi = แอปประกาศเอง · manual = คนพิมพ์เอง · probe = iVS ลองเรียกดู
    source       = Column(String(12), default="openapi")
    state        = Column(Enum(EndpointExposure), nullable=False,
                          default=EndpointExposure.PENDING, index=True)
    # เหตุผลที่คนให้ไว้ตอนอนุมัติหรือปฏิเสธ — หลักฐานว่าเคยมีคนคิดเรื่องนี้
    note         = Column(Text, default="")
    decided_by   = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at   = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, default=utcnow)
    last_seen_at  = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("app_id", "method", "path", name="uq_app_endpoint_exposure"),
    )
