"""
Audit Log Service — พ.ร.บ. คอมพิวเตอร์ (Computer Crime Act) Compliant

องค์ประกอบที่บันทึก:
1. Timestamp     — วันเวลาระดับมิลลิวินาที + Timezone (UTC)
                   Sync กับ NTP Server ตามกฎหมายไทย (time.navy.mi.th)
2. Log Level     — INFO / WARNING / ERROR / DEBUG
3. Identifier    — Request ID (UUID) + Session ID (JWT hash)
4. Message       — User ID, Username, Action, Resource, Details, IP, User-Agent
"""

import uuid
import hashlib
from typing import Optional
from datetime import datetime, timezone
from fastapi import Request
from sqlalchemy.orm import Session
from app.models import AuditLog, User
from app.services.ntp_service import ntp_service


def _extract_client_ip(request: Request) -> str:
    """Extract real client IP (supports reverse proxy X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _extract_session_id(request: Request) -> Optional[str]:
    """Hash JWT token to create a trackable session ID."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if token:
        return hashlib.sha256(token.encode()).hexdigest()[:16]
    return None


def create_audit_log(
    db: Session,
    request: Request,
    user: Optional[User],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: str = "",
    log_level: str = "INFO",
) -> AuditLog:
    """
    สร้าง Audit Log ตามมาตรฐาน พ.ร.บ. คอมพิวเตอร์

    Args:
        db: Database session
        request: FastAPI Request object (for IP, User-Agent, Session)
        user: User who performed the action (None for failed attempts)
        action: Action performed (login, deploy, delete, etc.)
        resource_type: Type of resource (auth, app, vault, tunnel, system, user)
        resource_id: ID of the affected resource
        details: Human-readable description
        log_level: INFO / WARNING / ERROR / DEBUG
    """
    ip_address = _extract_client_ip(request)
    user_agent = (request.headers.get("User-Agent") or "")[:500]
    request_id = str(uuid.uuid4())
    session_id = _extract_session_id(request)

    # ใช้เวลาจาก NTP Server (time.navy.mi.th) แทน system clock
    ntp_now = ntp_service.now()
    ntp_status = ntp_service.get_status()
    ntp_source = ntp_status.get("ntp_server") or "system_clock"

    log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        log_level=log_level,
        request_id=request_id,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        ntp_server=ntp_source,
        created_at=ntp_now,
    )
    db.add(log)
    return log
