import os
import hashlib
import socket
import platform
import subprocess
from datetime import datetime, timezone
import psutil
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import asyncio
import json
from app.database import get_db, SessionLocal
from app.models import User, UserRole, App, AppStatus, AuditLog, AuditLogExport, SystemConfig
from app.schemas import SystemHealth, AuditLogResponse, AuditLogExportResponse, DNSConfigUpdate, DNSConfigResponse
from app.middleware.auth import get_current_user, require_role
from app.services.docker_service import docker_service
from app.services.audit_service import create_audit_log
from app.services.ntp_service import ntp_service
from app.services.resource_service import get_current_resources, get_history, generate_report, collect_snapshot
from app.services.mdns_service import mdns_service, DEFAULT_MDNS_HOSTNAME
from app.config import settings

EXPORTS_DIR = os.path.join(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), "exports")

router = APIRouter(prefix="/api/system", tags=["System"])


@router.get("/health", response_model=SystemHealth)
async def get_system_health(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    # Count from database (source of truth) instead of Docker labels
    total = db.query(App).count()
    running = db.query(App).filter(App.status == AppStatus.RUNNING).count()

    # IMPORTANT: psutil.virtual_memory().percent uses (total - available) / total,
    # which on macOS includes inactive/cached pages, while mem.used excludes them.
    # Use (total - available) here so the displayed bytes match the percentage gauge.
    memory_used = mem.total - mem.available

    return SystemHealth(
        cpu_percent=cpu,
        memory_total=mem.total,
        memory_used=memory_used,
        memory_percent=mem.percent,
        disk_total=disk.total,
        disk_used=disk.used,
        disk_percent=disk.percent,
        docker_running=docker_service.is_available(),
        dns_running=True,
        apps_running=running,
        apps_total=total,
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()


@router.post("/audit-logs/export", response_model=AuditLogExportResponse)
async def export_audit_logs(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Export audit logs to .md file with SHA-256 hash for legal evidence."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).all()
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"audit_log_{timestamp}.md"
    filepath = os.path.join(EXPORTS_DIR, filename)

    # Build Markdown content — พ.ร.บ. คอมพิวเตอร์ compliant
    ntp_status = ntp_service.get_status()
    ntp_now = ntp_service.now()
    lines = []
    lines.append("# IVS Audit Log Export")
    lines.append("")
    lines.append("## Export Information")
    lines.append("")
    lines.append(f"- **Export Date**: {ntp_now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
    lines.append(f"- **Exported By**: {user.username} (ID: {user.id})")
    lines.append(f"- **Total Records**: {len(logs)}")
    lines.append(f"- **System**: {settings.APP_NAME} v{settings.APP_VERSION}")
    lines.append("")
    lines.append("## NTP Time Source (แหล่งเวลาอ้างอิง)")
    lines.append("")
    lines.append(f"- **NTP Server**: {ntp_status.get('ntp_server', 'N/A')}")
    lines.append(f"- **Server Name**: {ntp_status.get('ntp_server_name', 'N/A')}")
    lines.append(f"- **Authority**: {ntp_status.get('ntp_authority', 'N/A')}")
    lines.append(f"- **Stratum**: {ntp_status.get('ntp_stratum', 'N/A')}")
    lines.append(f"- **Offset**: {ntp_status.get('offset_ms', 0)} ms")
    lines.append(f"- **Last Sync**: {ntp_status.get('last_sync', 'N/A')}")
    lines.append(f"- **Legal Basis**: พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2550")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("| # | Timestamp (UTC) | Level | User | Action | Resource | Details | IP | Request ID |")
    lines.append("|---|-----------------|-------|------|--------|----------|---------|----|------------|")

    for i, log in enumerate(logs, 1):
        time_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC" if log.created_at else "-"
        resource = f"{log.resource_type}"
        if log.resource_id:
            resource += f"#{log.resource_id}"
        details = (log.details or "").replace("|", "\\|").replace("\n", " ")
        level = getattr(log, 'log_level', 'INFO') or 'INFO'
        username = getattr(log, 'username', None) or f"uid:{log.user_id}" if log.user_id else "-"
        req_id = (getattr(log, 'request_id', None) or "-")[:8]
        lines.append(f"| {i} | {time_str} | {level} | {username} | `{log.action}` | {resource} | {details} | {log.ip_address or '-'} | {req_id} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Integrity Verification")
    lines.append("")
    lines.append("This document was digitally fingerprinted at export time.")
    lines.append("Use the SHA-256 hash stored in the IVS database to verify this file has not been tampered with.")
    lines.append("")

    content = "\n".join(lines)

    # Write file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Compute SHA-256 hash
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Append hash to file
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"- **SHA-256 Hash**: `{sha256}`\n")
        f.write(f"- **Filename**: `{filename}`\n")

    # Save export record
    export = AuditLogExport(
        filename=filename,
        sha256_hash=sha256,
        record_count=len(logs),
        exported_by=user.id,
    )
    db.add(export)
    create_audit_log(
        db, request, user=user, action="export_audit_logs", resource_type="system",
        details=f"Exported {len(logs)} audit logs, SHA-256: {sha256[:16]}...",
    )
    db.commit()
    db.refresh(export)
    return export


@router.get("/audit-logs/exports", response_model=list[AuditLogExportResponse])
async def list_audit_log_exports(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    return db.query(AuditLogExport).order_by(AuditLogExport.created_at.desc()).all()


@router.get("/audit-logs/exports/{export_id}/download")
async def download_audit_log_export(
    export_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    export = db.query(AuditLogExport).filter(AuditLogExport.id == export_id).first()
    if not export:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Export not found")

    filepath = os.path.join(EXPORTS_DIR, export.filename)
    if not os.path.exists(filepath):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Export file not found on disk")

    return FileResponse(
        path=filepath,
        filename=export.filename,
        media_type="text/markdown",
    )


@router.get("/resources")
async def get_resources(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current system resources, capacity analysis, per-app stats, and alerts."""
    return get_current_resources(db)


@router.get("/resources/history")
async def get_resources_history(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get historical resource metrics for charts."""
    return get_history(db, hours)


@router.post("/resources/snapshot")
async def take_resource_snapshot(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Manually trigger a resource snapshot."""
    metric = collect_snapshot(db)
    return {"status": "ok", "snapshot_id": metric.id}


@router.post("/resources/export")
async def export_resource_report(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Generate and export a Markdown resource report for meetings."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    report = generate_report(db)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"resource_report_{timestamp}.md"
    filepath = os.path.join(EXPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    sha256 = hashlib.sha256(report.encode("utf-8")).hexdigest()

    create_audit_log(
        db, request, user=user, action="export_resource_report", resource_type="system",
        details=f"Resource report exported: {filename}, SHA-256: {sha256[:16]}...",
    )
    db.commit()

    return {
        "filename": filename,
        "sha256_hash": sha256,
        "download_url": f"/api/system/resources/export/{filename}",
    }


@router.get("/resources/export/{filename}")
async def download_resource_report(
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download a generated resource report."""
    filepath = os.path.join(EXPORTS_DIR, filename)
    if not os.path.exists(filepath):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(path=filepath, filename=filename, media_type="text/markdown")


@router.get("/dns-config", response_model=DNSConfigResponse)
async def get_dns_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    config = db.query(SystemConfig).filter(SystemConfig.key == "domain_suffix").first()
    domain = config.value if config else settings.DOMAIN_SUFFIX
    return DNSConfigResponse(domain_suffix=domain, server_ip=settings.SERVER_IP)


@router.put("/dns-config", response_model=DNSConfigResponse)
async def update_dns_config(
    req: DNSConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    config = db.query(SystemConfig).filter(SystemConfig.key == "domain_suffix").first()
    old_domain = config.value if config else settings.DOMAIN_SUFFIX

    if config:
        config.value = req.domain_suffix
    else:
        config = SystemConfig(key="domain_suffix", value=req.domain_suffix)
        db.add(config)

    # Update the runtime config
    settings.DOMAIN_SUFFIX = req.domain_suffix

    create_audit_log(
        db, request, user=user, action="update_dns", resource_type="system",
        details=f"Changed domain suffix from '{old_domain}' to '{req.domain_suffix}'",
        log_level="WARNING",
    )
    db.commit()

    return DNSConfigResponse(domain_suffix=req.domain_suffix, server_ip=settings.SERVER_IP)


@router.get("/mdns")
async def get_mdns_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get current mDNS configuration and status."""
    # Check if custom hostname is saved in DB
    config = db.query(SystemConfig).filter(SystemConfig.key == "mdns_hostname").first()
    saved = config.value if config else DEFAULT_MDNS_HOSTNAME
    status = mdns_service.get_status()
    status["saved_hostname"] = saved
    return status


@router.put("/mdns")
async def update_mdns_hostname(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update mDNS hostname."""
    body = await request.json()
    new_hostname = body.get("hostname", "").strip().lower().replace(".local", "")

    if not new_hostname:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Hostname is required")

    old_hostname = mdns_service.current_hostname

    # Save to DB
    config = db.query(SystemConfig).filter(SystemConfig.key == "mdns_hostname").first()
    if config:
        config.value = new_hostname
    else:
        config = SystemConfig(key="mdns_hostname", value=new_hostname)
        db.add(config)

    # Apply the change
    actual_hostname = mdns_service.update_hostname(new_hostname)

    create_audit_log(
        db, request, user=user, action="update_mdns", resource_type="system",
        details=f"Changed mDNS hostname from '{old_hostname}' to '{actual_hostname}'",
        log_level="WARNING",
    )
    db.commit()

    return mdns_service.get_status()


@router.post("/mdns/reset")
async def reset_mdns_hostname(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Reset mDNS hostname to default (ivs)."""
    old_hostname = mdns_service.current_hostname

    # Remove from DB
    config = db.query(SystemConfig).filter(SystemConfig.key == "mdns_hostname").first()
    if config:
        db.delete(config)

    # Apply default
    mdns_service.update_hostname(DEFAULT_MDNS_HOSTNAME)

    create_audit_log(
        db, request, user=user, action="reset_mdns", resource_type="system",
        details=f"Reset mDNS hostname from '{old_hostname}' to default '{DEFAULT_MDNS_HOSTNAME}'",
        log_level="WARNING",
    )
    db.commit()

    return mdns_service.get_status()


@router.get("/network")
async def get_network_info(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get network configuration: IP, gateway, DNS servers, interfaces, mDNS status."""

    # ── Network Interfaces ──
    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    for iface, addr_list in addrs.items():
        # Skip virtual / Docker / macOS internal interfaces
        if iface in ("lo", "lo0") or iface.startswith((
            "docker", "veth", "br-", "virbr",        # Docker / Linux virtual
            "utun", "awdl", "llw", "ap", "anpi",     # macOS internal
            "bridge", "gif", "stf", "ipsec",          # macOS tunnels
        )):
            continue
        info = {"name": iface, "ipv4": None, "netmask": None, "mac": None, "is_up": False, "speed": 0}
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                info["ipv4"] = addr.address
                info["netmask"] = addr.netmask
            elif addr.family == psutil.AF_LINK:
                info["mac"] = addr.address
        if iface in stats:
            info["is_up"] = stats[iface].isup
            info["speed"] = stats[iface].speed  # Mbps
        interfaces.append(info)

    # ── Default Gateway ──
    gateway = None
    try:
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["netstat", "-nr"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if line.strip().startswith("default") and "." in line:
                    parts = line.split()
                    gateway = parts[1]
                    break
        else:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "default" in line:
                    parts = line.split()
                    idx = parts.index("via") + 1 if "via" in parts else 2
                    gateway = parts[idx]
                    break
    except Exception:
        pass

    # ── DNS Servers ──
    dns_servers = []
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("nameserver"):
                    dns_servers.append(stripped.split()[1])
    except Exception:
        pass

    # ── Internet connectivity check ──
    internet_ok = False
    try:
        s = socket.create_connection(("8.8.8.8", 53), timeout=3)
        s.close()
        internet_ok = True
    except Exception:
        pass

    # ── mDNS / Bonjour status ──
    mdns_available = False
    mdns_hostname = None
    mdns_service = None
    try:
        hostname = socket.gethostname()
        if platform.system() == "Darwin":
            # macOS has Bonjour built-in
            result = subprocess.run(
                ["scutil", "--get", "LocalHostName"],
                capture_output=True, text=True, timeout=5,
            )
            local_name = result.stdout.strip() if result.returncode == 0 else hostname
            mdns_hostname = f"{local_name}.local"
            mdns_available = True
            mdns_service = "Bonjour (built-in)"
        else:
            # Linux: check avahi-daemon
            result = subprocess.run(
                ["systemctl", "is-active", "avahi-daemon"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip() == "active":
                mdns_available = True
                mdns_hostname = f"{hostname}.local"
                mdns_service = "Avahi"
            else:
                mdns_service = "Avahi (not running)"
                mdns_hostname = f"{hostname}.local"
    except Exception:
        mdns_service = "Not available"

    return {
        "server_ip": settings.SERVER_IP,
        "hostname": socket.gethostname(),
        "gateway": gateway,
        "dns_servers": dns_servers,
        "interfaces": interfaces,
        "internet": internet_ok,
        "mdns_available": mdns_available,
        "mdns_hostname": mdns_hostname,
        "mdns_service": mdns_service,
        "platform": platform.system(),
    }


@router.websocket("/ws/health")
async def ws_health(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            # Count from database (source of truth) instead of Docker labels
            db = SessionLocal()
            try:
                total = db.query(App).count()
                running = db.query(App).filter(App.status == AppStatus.RUNNING).count()
            finally:
                db.close()

            await websocket.send_json({
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_used": mem.total - mem.available,  # Match percent calculation
                "memory_total": mem.total,
                "disk_percent": disk.percent,
                "disk_used": disk.used,
                "disk_total": disk.total,
                "apps_running": running,
                "apps_total": total,
            })
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
