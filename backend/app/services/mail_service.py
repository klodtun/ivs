"""
Mail Service — จดหมายแจ้งเตือนของ iVS เอง (โมดูลจดหมาย ระยะที่ 0)

ระยะนี้ iVS ยังไม่มีเซิร์ฟเวอร์จดหมายของตัวเอง จดหมายทุกฉบับส่งออกผ่าน "ตัวรีเลย์"
ภายนอกที่ผู้ดูแลตั้งค่าไว้ (Gmail, Microsoft 365 หรือ SMTP ทั่วไป) สิ่งที่ไฟล์นี้
วางโครงไว้คือส่วนที่ระยะถัดไปจะใช้ต่อโดยไม่ต้องเขียนใหม่: คิว แม่แบบ การลองซ้ำ
บันทึกตรวจสอบ และทะเบียน ROPA ของกิจกรรมนี้ เมื่อถึงระยะที่ 1 สิ่งเดียวที่เปลี่ยน
คือปลายทางของรีเลย์ชี้มาที่ ivs-mail แทน

หลักสามข้อที่ทุกฟังก์ชันในนี้ยึด

1. ไม่ส่งตรงจาก request handler — เข้าคิวเสมอ (ยกเว้น "ส่งทดสอบ" ซึ่งผู้ดูแล
   ตั้งใจรอดูผลจากเซิร์ฟเวอร์ปลายทางจริง)
2. รหัสผ่านรีเลย์ถูกเข้ารหัสด้วยกุญแจคลัง (VAULT_KEY) ก่อนลง SystemConfig แบบเดียวกับ
   โทเคนอุโมงค์เชื่อมต่อ และไม่ถูกส่งกลับหน้าจอในรูปอ่านได้
3. บันทึกตรวจสอบจดว่า "ส่งถึงใคร เรื่องอะไร ผลเป็นอย่างไร" ไม่จดเนื้อหา
"""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape
from pathlib import Path
from typing import Iterable, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    App, AppStatus, MailOutbox, SystemConfig, Tunnel, TunnelStatus, User, UserRole,
)
from app.services.audit_service import create_audit_log
from app.services.vault_service import vault_service

logger = logging.getLogger(__name__)

# ── คีย์ตั้งค่าใน SystemConfig ───────────────────────────────────────────────
CFG_ENABLED    = "mail.enabled"            # "true" | "false"
CFG_PRESET     = "mail.relay.preset"       # gmail | microsoft365 | custom
CFG_HOST       = "mail.relay.host"
CFG_PORT       = "mail.relay.port"
CFG_SECURITY   = "mail.relay.security"     # starttls | ssl | none
CFG_USERNAME   = "mail.relay.username"
CFG_PASSWORD   = "mail.relay.password"     # เข้ารหัสด้วย vault_service
CFG_FROM_ADDR  = "mail.from_address"
CFG_FROM_NAME  = "mail.from_name"
CFG_LOCALE     = "mail.locale"             # th | en
CFG_RECIPIENTS = "mail.notify_recipients"  # คั่นด้วยจุลภาค ว่าง = ผู้ดูแลทุกคน
CFG_DASH_URL   = "mail.dashboard_url"      # ลิงก์ที่ใส่ท้ายจดหมาย ว่าง = เดาจาก SERVER_IP
CFG_ROPA       = "mail.ropa"               # JSON ทะเบียนกิจกรรมของระบบจดหมาย

# ค่าตั้งต้นของผู้ให้บริการที่พบบ่อย — ผู้ใช้เลือกแล้วไม่ต้องรู้พอร์ตเอง
PRESETS = {
    "gmail": {
        "label": "Gmail / Google Workspace",
        "host": "smtp.gmail.com", "port": 587, "security": "starttls",
        "provider": "Google LLC",
        "hint_th": "ต้องใช้ \"รหัสผ่านสำหรับแอป\" (App Password) ไม่ใช่รหัสผ่านบัญชีปกติ",
        "hint_en": "Use an App Password, not the account password.",
    },
    "microsoft365": {
        "label": "Microsoft 365 / Outlook",
        "host": "smtp.office365.com", "port": 587, "security": "starttls",
        "provider": "Microsoft Corporation",
        "hint_th": "ต้องเปิด SMTP AUTH ให้กล่องจดหมายนั้นในศูนย์ผู้ดูแล Microsoft 365",
        "hint_en": "SMTP AUTH must be enabled for that mailbox in the Microsoft 365 admin center.",
    },
    "custom": {
        "label": "SMTP ทั่วไป",
        "host": "", "port": 587, "security": "starttls",
        "provider": "",
        "hint_th": "กรอกโฮสต์และพอร์ตตามที่ผู้ให้บริการแจ้ง",
        "hint_en": "Enter the host and port your provider gives you.",
    },
}

SECURITY_MODES = ("starttls", "ssl", "none")
LOCALES = ("th", "en")

# ลองซ้ำแบบถอยหลัง หลังครั้งที่สามถือว่าตาย — บันทึกแล้วเลิก
RETRY_DELAYS_SECONDS = (60, 300, 1800)
MAX_ATTEMPTS = len(RETRY_DELAYS_SECONDS) + 1
DEDUPE_WINDOW = timedelta(hours=24)
# แถวที่จบแล้ว (ส่งสำเร็จ/ตาย) เก็บไว้ให้หน้าจอดูย้อนหลัง แล้วลบเมื่อครบกำหนด
# เพราะข้อมูลแม่แบบมีชื่อและที่อยู่จดหมาย ส่วนหลักฐานการส่งอยู่ใน audit_logs
OUTBOX_RETENTION_DAYS = 90
SMTP_TIMEOUT_SECONDS = 20
BATCH_SIZE = 20

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "mail"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,            # เนื้อหาเป็น text/plain เรา escape เองตอนทำ HTML
    undefined=StrictUndefined,   # ตัวแปรหายต้องพังตอนเรนเดอร์ ไม่ใช่ส่งจดหมายที่มีช่องว่าง
    trim_blocks=True,
    lstrip_blocks=True,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── การตั้งค่า ────────────────────────────────────────────────────────────────

def _get(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return row.value if row and row.value is not None and row.value != "" else default


def _set(db: Session, key: str, value: str) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row is None:
        db.add(SystemConfig(key=key, value=value))
    else:
        row.value = value


def is_enabled(db: Session) -> bool:
    return _get(db, CFG_ENABLED, "false") == "true"


def get_config(db: Session) -> dict:
    """การตั้งค่าเต็ม รวมรหัสผ่านที่ถอดแล้ว — ใช้ภายในเท่านั้น ห้ามส่งออก API"""
    enc = _get(db, CFG_PASSWORD)
    try:
        password = vault_service.decrypt(enc) if enc else ""
    except Exception:
        # กุญแจคลังเปลี่ยนหลังบันทึก — ถือว่าไม่มีรหัส ดีกว่าส่งรหัสผิดไปจนบัญชีถูกล็อก
        logger.warning("mail: relay password could not be decrypted (VAULT_KEY changed?)")
        password = ""
    try:
        port = int(_get(db, CFG_PORT, "587"))
    except ValueError:
        port = 587
    security = _get(db, CFG_SECURITY, "starttls")
    if security not in SECURITY_MODES:
        security = "starttls"
    locale = _get(db, CFG_LOCALE, "th")
    if locale not in LOCALES:
        locale = "th"
    return {
        "enabled": is_enabled(db),
        "preset": _get(db, CFG_PRESET, "custom"),
        "host": _get(db, CFG_HOST),
        "port": port,
        "security": security,
        "username": _get(db, CFG_USERNAME),
        "password": password,
        "from_address": _get(db, CFG_FROM_ADDR),
        "from_name": _get(db, CFG_FROM_NAME, "iVS"),
        "locale": locale,
        "recipients_raw": _get(db, CFG_RECIPIENTS),
        "dashboard_url": _get(db, CFG_DASH_URL),
    }


def public_config(db: Session) -> dict:
    """การตั้งค่าสำหรับหน้าจอ — รหัสผ่านไม่ออกไปในรูปใดนอกจาก "ตั้งแล้วหรือยัง" """
    cfg = get_config(db)
    cfg.pop("password")
    cfg["password_configured"] = bool(_get(db, CFG_PASSWORD))
    cfg["recipients_effective"] = notify_recipients(db)
    cfg["presets"] = {
        k: {kk: vv for kk, vv in v.items()} for k, v in PRESETS.items()
    }
    cfg["dashboard_url_effective"] = dashboard_url(db)
    cfg["configured"] = bool(cfg["host"] and cfg["from_address"])
    return cfg


def set_config(
    db: Session, *,
    enabled: Optional[bool] = None,
    preset: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    security: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,      # None = ไม่เปลี่ยน, "" = ล้าง
    from_address: Optional[str] = None,
    from_name: Optional[str] = None,
    locale: Optional[str] = None,
    recipients: Optional[str] = None,
    dashboard_url: Optional[str] = None,
) -> dict:
    if preset is not None:
        if preset not in PRESETS:
            raise ValueError("unknown preset")
        _set(db, CFG_PRESET, preset)
        # เลือกผู้ให้บริการแล้วเติมโฮสต์/พอร์ตให้ ถ้าผู้ใช้ไม่ได้พิมพ์ทับ
        p = PRESETS[preset]
        if p["host"] and host is None:
            host = p["host"]
        if port is None and p["host"]:
            port = p["port"]
        if security is None and p["host"]:
            security = p["security"]
    if host is not None:
        _set(db, CFG_HOST, host.strip())
    if port is not None:
        if not (1 <= int(port) <= 65535):
            raise ValueError("port out of range")
        _set(db, CFG_PORT, str(int(port)))
    if security is not None:
        if security not in SECURITY_MODES:
            raise ValueError("unknown security mode")
        _set(db, CFG_SECURITY, security)
    if username is not None:
        _set(db, CFG_USERNAME, username.strip())
    if password is not None:
        _set(db, CFG_PASSWORD, vault_service.encrypt(password) if password else "")
    if from_address is not None:
        addr = from_address.strip()
        if addr and "@" not in addr:
            raise ValueError("from_address must be an e-mail address")
        _set(db, CFG_FROM_ADDR, addr)
    if from_name is not None:
        _set(db, CFG_FROM_NAME, from_name.strip()[:120])
    if locale is not None:
        if locale not in LOCALES:
            raise ValueError("unknown locale")
        _set(db, CFG_LOCALE, locale)
    if recipients is not None:
        cleaned = ", ".join(_split_addresses(recipients))
        _set(db, CFG_RECIPIENTS, cleaned)
    if dashboard_url is not None:
        _set(db, CFG_DASH_URL, dashboard_url.strip()[:300])
    if enabled is not None:
        _set(db, CFG_ENABLED, "true" if enabled else "false")
    db.commit()
    # ผู้รับข้อมูลภายนอกเปลี่ยนตามรีเลย์ — ROPA ต้องตามให้ทันโดยไม่ต้องมีใครจำ
    _sync_relay_recipient(db)
    return public_config(db)


def _split_addresses(raw: str) -> list[str]:
    out: list[str] = []
    for part in (raw or "").replace(";", ",").replace("\n", ",").split(","):
        a = part.strip()
        if a and "@" in a and a not in out:
            out.append(a)
    return out


def notify_recipients(db: Session) -> list[str]:
    """ใครได้รับการแจ้งเตือนของระบบ

    ถ้าผู้ดูแลระบุรายชื่อไว้ ใช้ตามนั้น ถ้าไม่ ให้ส่งถึงผู้ดูแลระบบทุกคนที่ยังใช้งาน
    และมีที่อยู่จดหมายจริง (ที่อยู่ @ivs.local เป็นค่าที่ระบบตั้งให้ตอนติดตั้ง ไม่มีใครรับ)
    """
    explicit = _split_addresses(_get(db, CFG_RECIPIENTS))
    if explicit:
        return explicit
    admins = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.is_active == True)  # noqa: E712
        .all()
    )
    return [u.email for u in admins if _looks_deliverable(u.email)]


def _looks_deliverable(email: str) -> bool:
    e = (email or "").strip().lower()
    return "@" in e and not e.endswith("@ivs.local") and not e.endswith(".local")


def dashboard_url(db: Session) -> str:
    explicit = _get(db, CFG_DASH_URL)
    if explicit:
        return explicit
    return f"http://{settings.SERVER_IP}:3000"


# ── แม่แบบ ───────────────────────────────────────────────────────────────────

def _template_name(name: str, locale: str) -> str:
    return f"{name}.{locale}.j2"


def available_templates() -> list[str]:
    names = set()
    for p in _TEMPLATE_DIR.glob("*.j2"):
        if p.name.startswith("_"):
            continue
        names.add(p.name.split(".")[0])
    return sorted(names)


def render(db: Session, name: str, context: dict, locale: Optional[str] = None) -> tuple[str, str, str]:
    """คืน (หัวเรื่อง, เนื้อหาตัวอักษร, เนื้อหา HTML)

    แม่แบบหนึ่งไฟล์ต่อภาษา มีสองบล็อก: subject และ body ถ้าภาษาที่ขอไม่มีไฟล์
    ถอยไปใช้ภาษาไทยซึ่งเป็นภาษาหลักของผลิตภัณฑ์
    """
    locale = locale or get_config(db)["locale"]
    try:
        tpl = _env.get_template(_template_name(name, locale))
    except TemplateNotFound:
        tpl = _env.get_template(_template_name(name, "th"))
        locale = "th"
    full = dict(context)
    full.setdefault("box_name", settings.APP_NAME)
    full.setdefault("dashboard_url", dashboard_url(db))
    full.setdefault("now", _now().strftime("%Y-%m-%d %H:%M UTC"))
    ctx = tpl.new_context(full)
    subject = "".join(tpl.blocks["subject"](ctx)).strip()
    body = "".join(tpl.blocks["body"](ctx)).strip()
    footer = _footer(locale, full["dashboard_url"])
    text = f"{body}\n\n{footer}"
    return subject, text, _to_html(subject, body, footer)


def _footer(locale: str, url: str) -> str:
    if locale == "en":
        return (
            "--\n"
            "Sent automatically by iVS (Internal Vibe Server). This message was generated "
            "because of an event in your organisation's iVS box. Personal data in it is "
            "processed under the PDPA and recorded in the box's Record of Processing "
            "Activities (ROPA).\n"
            f"Dashboard: {url}"
        )
    return (
        "--\n"
        "จดหมายฉบับนี้ส่งโดยอัตโนมัติจาก iVS (Internal Vibe Server) เนื่องจากมีเหตุการณ์ใน "
        "ระบบ iVS ของหน่วยงานท่าน ข้อมูลส่วนบุคคลในจดหมายนี้ถูกประมวลผลตาม พ.ร.บ. "
        "คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 และบันทึกไว้ในทะเบียนกิจกรรมการประมวลผล (ROPA) "
        "ของเครื่อง\n"
        f"หน้าจอ iVS: {url}"
    )


def _to_html(subject: str, body: str, footer: str) -> str:
    """แปลงข้อความธรรมดาเป็น HTML อย่างง่าย — ย่อหน้าตามบรรทัดว่าง ไม่มีสคริปต์ ไม่มีรูป"""
    def paragraphs(txt: str) -> str:
        parts = [p.strip() for p in txt.split("\n\n") if p.strip()]
        return "".join(
            "<p style=\"margin:0 0 12px 0;line-height:1.6\">"
            + escape(p).replace("\n", "<br>")
            + "</p>"
            for p in parts
        )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{escape(subject)}</title></head>"
        "<body style=\"margin:0;padding:24px;background:#f8fafc;font-family:-apple-system,"
        "Segoe UI,Roboto,'Noto Sans Thai',sans-serif;color:#1e293b;font-size:15px\">"
        "<div style=\"max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;"
        "border-radius:8px;padding:24px\">"
        "<div style=\"font-weight:700;color:#4338ca;font-size:13px;letter-spacing:.04em;"
        "margin-bottom:16px\">iVS</div>"
        f"<h1 style=\"font-size:18px;margin:0 0 16px 0\">{escape(subject)}</h1>"
        f"{paragraphs(body)}"
        "<hr style=\"border:0;border-top:1px solid #e2e8f0;margin:20px 0\">"
        f"<div style=\"font-size:12px;color:#64748b\">{paragraphs(footer.replace('--', '').strip())}</div>"
        "</div></body></html>"
    )


# ── คิว ──────────────────────────────────────────────────────────────────────

def enqueue(
    db: Session, to_email: str, template: str, context: dict, *,
    locale: Optional[str] = None, dedupe_key: str = "",
    created_by: Optional[int] = None, force: bool = False,
) -> Optional[MailOutbox]:
    """ใส่จดหมายหนึ่งฉบับเข้าคิว คืน None ถ้าไม่ได้ใส่ (โมดูลปิด ที่อยู่ไม่ใช้ได้ หรือซ้ำ)

    `force` ให้ใส่แม้โมดูลปิด — ใช้เฉพาะเส้นทางที่ผู้ดูแลกดเองและคาดหวังผล
    """
    if not force and not is_enabled(db):
        return None
    if not _looks_deliverable(to_email):
        return None
    if dedupe_key:
        since = _now() - DEDUPE_WINDOW
        dup = (
            db.query(MailOutbox)
            .filter(
                MailOutbox.dedupe_key == dedupe_key,
                MailOutbox.to_email == to_email,
                MailOutbox.created_at >= since,
                MailOutbox.status != "dead",
            )
            .first()
        )
        if dup:
            return None
    loc = locale or get_config(db)["locale"]
    try:
        subject, _, _ = render(db, template, context, loc)
    except Exception as e:  # แม่แบบพัง — รู้ตอนเข้าคิว ไม่ใช่ตอนส่ง
        logger.error("mail: template %s failed to render: %s", template, e)
        return None
    row = MailOutbox(
        to_email=to_email.strip(),
        template=template,
        context=json.dumps(context, ensure_ascii=False, default=str),
        locale=loc,
        subject=subject[:500],
        status="queued",
        next_attempt_at=_now(),
        dedupe_key=dedupe_key[:160],
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def notify_admins(db: Session, template: str, context: dict, *, dedupe_key: str = "") -> int:
    """ส่งเหตุการณ์ของระบบถึงผู้รับการแจ้งเตือนทุกคน คืนจำนวนที่เข้าคิวจริง"""
    if not is_enabled(db):
        return 0
    n = 0
    for addr in notify_recipients(db):
        if enqueue(db, addr, template, context, dedupe_key=dedupe_key):
            n += 1
    return n


def requeue(db: Session, row: MailOutbox) -> MailOutbox:
    row.status = "queued"
    row.attempts = 0
    row.next_attempt_at = _now()
    row.last_error = ""
    db.commit()
    return row


# ── การส่งจริง ───────────────────────────────────────────────────────────────

def _smtp_send(cfg: dict, to_email: str, subject: str, text: str, html: str) -> tuple[bool, str]:
    """ส่งหนึ่งฉบับ คืน (สำเร็จ, ข้อความจากเซิร์ฟเวอร์หรือข้อผิดพลาดจริง)

    ข้อความผิดพลาดต้องเป็นของจริงจากปลายทาง เพราะผู้ดูแลใช้มันแก้การตั้งค่า
    ("535 Username and Password not accepted" บอกได้มากกว่า "ส่งไม่สำเร็จ")
    """
    if not cfg["host"]:
        return False, "ยังไม่ได้ตั้งค่าโฮสต์ของตัวรีเลย์"
    if not cfg["from_address"]:
        return False, "ยังไม่ได้ตั้งค่าที่อยู่ผู้ส่ง"

    msg = EmailMessage()
    msg["From"] = formataddr((cfg["from_name"] or "iVS", cfg["from_address"]))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    domain = cfg["from_address"].split("@", 1)[-1] or "ivs.local"
    msg["Message-ID"] = make_msgid(domain=domain)
    msg["X-Mailer"] = f"iVS/{settings.APP_VERSION}"
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    tls = ssl.create_default_context()
    try:
        if cfg["security"] == "ssl":
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=SMTP_TIMEOUT_SECONDS, context=tls)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            server.ehlo()
            if cfg["security"] == "starttls":
                server.starttls(context=tls)
                server.ehlo()
            if cfg["username"]:
                server.login(cfg["username"], cfg["password"])
            server.send_message(msg)
        return True, "250 OK"
    except smtplib.SMTPResponseException as e:
        detail = e.smtp_error.decode(errors="replace") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        return False, f"{e.smtp_code} {detail}".strip()
    except smtplib.SMTPException as e:
        return False, f"SMTP: {e}"
    except (OSError, ssl.SSLError) as e:
        return False, f"{type(e).__name__}: {e}"


def _audit(db: Session, action: str, row: Optional[MailOutbox], to_email: str,
           subject: str, outcome: str, level: str = "INFO") -> None:
    create_audit_log(
        db, None, None, action=action, resource_type="mail",
        resource_id=str(row.id) if row else None,
        details=f"to={to_email} subject={subject[:120]!r} template={row.template if row else 'test'} result={outcome[:300]}",
        log_level=level,
    )


def process_queue(db: Session) -> dict:
    """หยิบจดหมายที่ถึงกำหนดแล้วส่ง — เรียกจากลูปพื้นหลังทุก 30 วินาที"""
    stats = {"sent": 0, "failed": 0, "dead": 0}
    if not is_enabled(db):
        return stats
    cfg = get_config(db)
    now = _now()
    due = (
        db.query(MailOutbox)
        .filter(MailOutbox.status.in_(["queued", "failed"]), MailOutbox.next_attempt_at <= now)
        .order_by(MailOutbox.next_attempt_at.asc())
        .limit(BATCH_SIZE)
        .all()
    )
    for row in due:
        row.status = "sending"
        db.commit()
        try:
            context = json.loads(row.context or "{}")
            subject, text, html = render(db, row.template, context, row.locale)
            ok, message = _smtp_send(cfg, row.to_email, subject, text, html)
        except Exception as e:  # noqa: BLE001 — จดแล้วเดินต่อ ไม่ให้ฉบับเดียวหยุดทั้งคิว
            ok, message, subject = False, f"{type(e).__name__}: {e}", row.subject or row.template
        row.attempts = (row.attempts or 0) + 1
        if ok:
            row.status = "sent"
            row.sent_at = _now()
            row.last_error = ""
            stats["sent"] += 1
            _audit(db, "mail.sent", row, row.to_email, subject, message)
        else:
            row.last_error = message[:2000]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "dead"
                stats["dead"] += 1
                _audit(db, "mail.failed", row, row.to_email, subject,
                       f"gave up after {row.attempts} attempts: {message}", level="WARNING")
            else:
                delay = RETRY_DELAYS_SECONDS[min(row.attempts - 1, len(RETRY_DELAYS_SECONDS) - 1)]
                row.status = "failed"
                row.next_attempt_at = _now() + timedelta(seconds=delay)
                stats["failed"] += 1
                logger.warning("mail: #%s to %s failed (attempt %s): %s — retry in %ss",
                               row.id, row.to_email, row.attempts, message, delay)
        db.commit()
    return stats


def send_test(db: Session, to_email: str, user: User) -> dict:
    """ส่งจดหมายทดสอบทันทีและคืนผลจริงจากเซิร์ฟเวอร์ปลายทาง (ไม่ผ่านคิว)"""
    if not _looks_deliverable(to_email):
        return {"ok": False, "message": "ที่อยู่ผู้รับไม่ถูกต้อง", "elapsed_ms": 0}
    cfg = get_config(db)
    started = time.monotonic()
    try:
        subject, text, html = render(db, "test", {"requested_by": user.username}, cfg["locale"])
        ok, message = _smtp_send(cfg, to_email, subject, text, html)
    except Exception as e:  # noqa: BLE001
        ok, message, subject = False, f"{type(e).__name__}: {e}", "test"
    elapsed = int((time.monotonic() - started) * 1000)
    create_audit_log(
        db, None, user, action="mail.test", resource_type="mail",
        details=f"to={to_email} host={cfg['host']}:{cfg['port']} result={'ok' if ok else 'fail'} {message[:300]}",
        log_level="INFO" if ok else "WARNING",
    )
    db.commit()
    return {"ok": ok, "message": message, "elapsed_ms": elapsed,
            "host": cfg["host"], "port": cfg["port"], "security": cfg["security"]}


# ── เหตุการณ์ที่ระบบตรวจเองเป็นรอบ ─────────────────────────────────────────────

def scan_events(db: Session) -> int:
    """มองหาเหตุการณ์ที่ควรแจ้ง แต่ไม่มีจุดในโค้ดให้แขวน — แอปล้ม, อุโมงค์ใกล้หมดอายุ

    กันซ้ำด้วย dedupe_key ภายใน 24 ชั่วโมง จึงเรียกได้บ่อยโดยไม่สแปม
    """
    if not is_enabled(db):
        return 0
    n = 0
    for app in db.query(App).filter(App.status == AppStatus.ERROR).all():
        n += notify_admins(db, "app_error", {
            "app_name": app.name, "app_slug": app.slug,
            "updated_at": (app.updated_at or _now()).strftime("%Y-%m-%d %H:%M UTC"),
        }, dedupe_key=f"app_error:{app.id}")
    soon = _now() + timedelta(hours=24)
    expiring = (
        db.query(Tunnel)
        .filter(Tunnel.status == TunnelStatus.ACTIVE, Tunnel.expires_at.isnot(None),
                Tunnel.expires_at <= soon, Tunnel.expires_at > _now())
        .all()
    )
    for tun in expiring:
        app = db.query(App).filter(App.id == tun.app_id).first()
        n += notify_admins(db, "tunnel_expiring", {
            "app_name": app.name if app else f"app#{tun.app_id}",
            "public_url": tun.public_url or "-",
            "expires_at": tun.expires_at.strftime("%Y-%m-%d %H:%M UTC"),
        }, dedupe_key=f"tunnel_expiring:{tun.id}")
    return n


def purge_outbox(db: Session) -> int:
    cutoff = _now() - timedelta(days=OUTBOX_RETENTION_DAYS)
    q = db.query(MailOutbox).filter(MailOutbox.status.in_(["sent", "dead"]), MailOutbox.created_at < cutoff)
    n = q.count()
    if n:
        q.delete(synchronize_session=False)
        db.commit()
    return n


def outbox_rows(db: Session, limit: int = 50) -> list[dict]:
    rows = db.query(MailOutbox).order_by(MailOutbox.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id, "to_email": r.to_email, "template": r.template, "subject": r.subject,
            "status": r.status, "attempts": r.attempts, "last_error": r.last_error or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "next_attempt_at": r.next_attempt_at.isoformat() if r.next_attempt_at else None,
        }
        for r in rows
    ]


def status(db: Session) -> dict:
    counts = {s: 0 for s in ("queued", "sending", "failed", "sent", "dead")}
    for s, in db.query(MailOutbox.status).all():
        counts[s] = counts.get(s, 0) + 1
    last = db.query(MailOutbox).filter(MailOutbox.status == "sent").order_by(MailOutbox.sent_at.desc()).first()
    return {
        "enabled": is_enabled(db),
        "configured": bool(_get(db, CFG_HOST) and _get(db, CFG_FROM_ADDR)),
        "counts": counts,
        "last_sent_at": last.sent_at.isoformat() if last and last.sent_at else None,
        "recipients": notify_recipients(db),
        "templates": available_templates(),
    }


# ── ROPA ของกิจกรรม "การแจ้งเตือนทางจดหมาย" ────────────────────────────────────
#
# ตาราง app_pdpa ผูกกับแอปหนึ่งตัว กิจกรรมของตัว iVS เองจึงไม่มีที่ลง บันทึกไว้
# เป็นระเบียน JSON ใน SystemConfig และถูกรวมเข้ารายงาน ROPA ที่ส่งออก ระบบกรอก
# ส่วนที่เป็นกลไกให้ครบ เหลือให้ผู้ควบคุมข้อมูลยืนยันฐานทางกฎหมายและสัญญา
# ประมวลผลข้อมูล (DPA) ของผู้ให้บริการรีเลย์

ROPA_DEFAULT = {
    "activity_th": "การแจ้งเตือนทางจดหมายอิเล็กทรอนิกส์ของระบบ iVS",
    "activity_en": "iVS system e-mail notifications",
    "purpose": (
        "แจ้งเหตุการณ์ของระบบแก่ผู้ดูแลและผู้ใช้ เช่น การสร้างบัญชี ผลการส่งออกบันทึกตรวจสอบ "
        "การดำเนินการตามคำขอลบข้อมูล แอปหยุดทำงาน และอุโมงค์เชื่อมต่อใกล้หมดอายุ"
    ),
    "data_categories": ["ชื่อผู้ใช้", "ที่อยู่จดหมายอิเล็กทรอนิกส์", "บทบาทในระบบ",
                        "เหตุการณ์ของระบบที่เกี่ยวข้องกับผู้ใช้"],
    "legal_basis": "legitimate_interest",
    "retention": f"ข้อมูลแม่แบบในคิว {OUTBOX_RETENTION_DAYS} วัน · หลักฐานการส่งตามนโยบายเก็บรักษาบันทึกตรวจสอบ",
    "recipients": [],
    "status": "draft",
    "needs_review": True,
    "confirmed_by": "",
    "confirmed_at": "",
    "dpa_url": "",
    "dpa_note": "",
}


def get_ropa(db: Session) -> dict:
    raw = _get(db, CFG_ROPA)
    if not raw:
        return dict(ROPA_DEFAULT, created_at=_now().isoformat())
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    merged = dict(ROPA_DEFAULT)
    merged.update(data)
    return merged


def _save_ropa(db: Session, data: dict) -> None:
    _set(db, CFG_ROPA, json.dumps(data, ensure_ascii=False))
    db.commit()


def ensure_ropa(db: Session) -> dict:
    if not _get(db, CFG_ROPA):
        _save_ropa(db, dict(ROPA_DEFAULT, created_at=_now().isoformat()))
    return get_ropa(db)


def _sync_relay_recipient(db: Session) -> None:
    """ตัวรีเลย์ภายนอก = ผู้ประมวลผลข้อมูลที่ต้องอยู่ใน ROPA ใส่ให้เองทุกครั้งที่ตั้งค่า"""
    cfg = get_config(db)
    ropa = ensure_ropa(db)
    others = [r for r in ropa.get("recipients", []) if r.get("role") != "relay"]
    if cfg["host"]:
        preset = PRESETS.get(cfg["preset"], PRESETS["custom"])
        name = f"{cfg['host']}" + (f" ({preset['provider']})" if preset["provider"] else "")
        prev = next((r for r in ropa.get("recipients", []) if r.get("role") == "relay"), None)
        if not prev or prev.get("name") != name:
            ropa["needs_review"] = True
        others.append({
            "kind": "external", "role": "relay", "name": name,
            "purpose": "ส่งต่อจดหมายแจ้งเตือนไปยังผู้รับ (ผู้ประมวลผลข้อมูล)",
            "added_at": (prev or {}).get("added_at") or _now().isoformat(),
        })
    ropa["recipients"] = others
    _save_ropa(db, ropa)


def confirm_ropa(db: Session, user: User, *, legal_basis: str, dpa_url: str = "",
                 dpa_note: str = "", purpose: Optional[str] = None,
                 retention: Optional[str] = None) -> dict:
    from app.services.ropa_service import LEGAL_BASIS
    if legal_basis not in LEGAL_BASIS:
        raise ValueError("unknown legal basis")
    ropa = ensure_ropa(db)
    ropa["legal_basis"] = legal_basis
    ropa["dpa_url"] = (dpa_url or "").strip()[:500]
    ropa["dpa_note"] = (dpa_note or "").strip()[:1000]
    if purpose is not None and purpose.strip():
        ropa["purpose"] = purpose.strip()[:2000]
    if retention is not None and retention.strip():
        ropa["retention"] = retention.strip()[:300]
    ropa["status"] = "confirmed"
    ropa["needs_review"] = False
    ropa["confirmed_by"] = user.username
    ropa["confirmed_at"] = _now().isoformat()
    _save_ropa(db, ropa)
    return ropa


def ropa_as_activity(db: Session) -> Optional[dict]:
    """แปลงเป็นแถวกิจกรรมรูปเดียวกับแอป เพื่อรวมในรายงาน ROPA ที่ส่งออก

    คืน None เมื่อโมดูลยังไม่เคยถูกตั้งค่าเลย — กิจกรรมที่ไม่เคยเกิดไม่ควรอยู่ในทะเบียน
    """
    if not _get(db, CFG_ROPA):
        return None
    from app.services.ropa_service import LEGAL_BASIS
    ropa = get_ropa(db)
    info = LEGAL_BASIS.get(ropa.get("legal_basis", ""))
    if ropa.get("status") != "confirmed":
        erasure = {"erasable": False,
                   "reason_th": "ผู้ควบคุมข้อมูลยังไม่ยืนยันฐานการประมวลผลของกิจกรรมนี้"}
    elif info:
        erasure = {"erasable": info["erasable"], "reason_th": info["why"]}
    else:
        erasure = {"erasable": False, "reason_th": "ยังไม่ระบุฐานการประมวลผล"}
    recipients = list(ropa.get("recipients", []))
    for r in recipients:
        if r.get("role") == "relay" and ropa.get("dpa_url"):
            r["note"] = f"DPA: {ropa['dpa_url']}"
    notes = "ส่งผ่าน TLS · รหัสผ่านรีเลย์เข้ารหัสด้วยกุญแจคลัง · ไม่บันทึกเนื้อหาจดหมายใน audit"
    if ropa.get("status") != "confirmed":
        notes += " · สถานะ: ร่าง รอผู้ควบคุมข้อมูลยืนยัน"
    return {
        "app_name": ropa["activity_th"],
        "removed_at": "",
        "purpose": ropa["purpose"],
        "pii_fields": ropa["data_categories"],
        "usage": "iVS (ระบบเอง)",
        "retention_period": ropa["retention"],
        "has_masking": False,
        "security_notes": notes,
        "legal_basis": ropa.get("legal_basis", ""),
        "recipients": recipients,
        "erasure": erasure,
    }
