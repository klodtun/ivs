import os
import hashlib
import socket
import platform
import subprocess
from datetime import datetime, timezone
from typing import Optional
import psutil
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import asyncio
import json
from app.database import get_db, SessionLocal
from app.models import User, UserRole, App, AppStatus, AuditLog, AuditLogExport, SystemConfig
from app.schemas import SystemHealth, AuditLogResponse, AuditLogExportResponse, AuditLogExportRequest, DNSConfigUpdate, DNSConfigResponse
from app.middleware.auth import get_current_user, require_role
from app.services.docker_service import docker_service
from app.services.audit_service import create_audit_log
from app.services.ntp_service import ntp_service
from app.services.resource_service import get_current_resources, get_history, generate_report, collect_snapshot
from app.services.app_log_service import get_logs_for_export as get_app_logs_for_export
from app.services import retention_service
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

    # Disk: on macOS APFS, disk.total can include "purgeable" space shared with
    # other volumes — used + free ≠ total. psutil.disk.percent already uses
    # used / (used + free) which matches `df` capacity. Use (used + free) as the
    # displayed total so bytes and percentage stay consistent on every OS.
    disk_total_effective = disk.used + disk.free

    return SystemHealth(
        cpu_percent=cpu,
        memory_total=mem.total,
        memory_used=memory_used,
        memory_percent=mem.percent,
        disk_total=disk_total_effective,
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


def _build_chunk_markdown(
    chunk_logs: list,
    chunk_idx: int,
    total_chunks: int,
    start_idx: int,
    user: "User",
    ntp_status: dict,
    ntp_now: datetime,
    total_records: int,
    start_date: "datetime | None",
    end_date: "datetime | None",
) -> str:
    """Render one chunk's records as a Markdown document.

    Each chunk is self-contained: it has the same legal/NTP header as the
    legacy single-file export so an auditor can read any chunk standalone.
    """
    import zipfile  # noqa: F401  (silences unused-import warning above)
    lines = []
    lines.append(f"# IVS Audit Log Export — Part {chunk_idx} of {total_chunks}")
    lines.append("")
    lines.append("## Export Information")
    lines.append("")
    lines.append(f"- **Export Date**: {ntp_now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
    lines.append(f"- **Exported By**: {user.username} (ID: {user.id})")
    lines.append(f"- **Date Range**: "
                 f"{start_date.isoformat() if start_date else 'beginning of time'} → "
                 f"{end_date.isoformat() if end_date else 'now'}")
    lines.append(f"- **This Chunk**: records {start_idx + 1}–{start_idx + len(chunk_logs)}")
    lines.append(f"- **Total Records (all chunks)**: {total_records}")
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

    for i, log in enumerate(chunk_logs, start_idx + 1):
        time_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC" if log.created_at else "-"
        resource = f"{log.resource_type}"
        if log.resource_id:
            resource += f"#{log.resource_id}"
        details = (log.details or "").replace("|", "\\|").replace("\n", " ")
        level = getattr(log, "log_level", "INFO") or "INFO"
        username = getattr(log, "username", None) or (f"uid:{log.user_id}" if log.user_id else "-")
        req_id = (getattr(log, "request_id", None) or "-")[:8]
        lines.append(
            f"| {i} | {time_str} | {level} | {username} | `{log.action}` | "
            f"{resource} | {details} | {log.ip_address or '-'} | {req_id} |"
        )

    lines.append("")
    return "\n".join(lines)


@router.post("/audit-logs/export", response_model=AuditLogExportResponse)
async def export_audit_logs(
    request: Request,
    body: AuditLogExportRequest = AuditLogExportRequest(),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Export audit logs as a SHA-256-fingerprinted .zip bundle.

    Body (all optional):
        start_date              ISO datetime; defaults to "no lower bound"
        end_date                ISO datetime; defaults to "now"
        max_records_per_file    int; defaults to 5000 records per .md chunk

    Bundle layout (single .zip):
        manifest.json           list of chunks + per-chunk SHA-256
        README.txt              short human-readable overview
        audit_log_part_001.md   chunk 1 (oldest first within range)
        audit_log_part_002.md   chunk 2
        ...
    The DB record stores the SHA-256 of the .zip itself for integrity.
    """
    import zipfile

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    # Build query with optional date filters
    query = db.query(AuditLog)
    if body.start_date:
        query = query.filter(AuditLog.created_at >= body.start_date)
    if body.end_date:
        query = query.filter(AuditLog.created_at <= body.end_date)
    logs = query.order_by(AuditLog.created_at.asc()).all()
    total_records = len(logs)

    max_per_file = max(100, min(body.max_records_per_file, 100000))
    total_chunks = max(1, (total_records + max_per_file - 1) // max_per_file)

    ntp_status = ntp_service.get_status()
    ntp_now = ntp_service.now()

    # Filename — encode the date range so the user can read it at a glance
    def _stamp(d: Optional[datetime]) -> str:
        return d.strftime("%Y%m%d") if d else "all"
    range_label = f"{_stamp(body.start_date)}-to-{_stamp(body.end_date or now)}"
    filename = f"audit_log_{range_label}_{timestamp}.zip"
    zip_path = os.path.join(EXPORTS_DIR, filename)

    # Write zip
    chunk_summary = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for chunk_idx in range(total_chunks):
            start = chunk_idx * max_per_file
            chunk_logs = logs[start:start + max_per_file]
            md_content = _build_chunk_markdown(
                chunk_logs=chunk_logs,
                chunk_idx=chunk_idx + 1,
                total_chunks=total_chunks,
                start_idx=start,
                user=user,
                ntp_status=ntp_status,
                ntp_now=ntp_now,
                total_records=total_records,
                start_date=body.start_date,
                end_date=body.end_date,
            )
            chunk_sha = hashlib.sha256(md_content.encode("utf-8")).hexdigest()
            chunk_name = f"audit_log_part_{chunk_idx + 1:03d}.md"
            # Re-append the chunk's own SHA at the bottom so a standalone
            # reader can verify the chunk without the manifest.
            md_content += f"\n\n---\n- **Chunk SHA-256**: `{chunk_sha}`\n- **Filename**: `{chunk_name}`\n"
            zf.writestr(chunk_name, md_content)
            chunk_summary.append({
                "filename": chunk_name,
                "record_count": len(chunk_logs),
                "sha256": chunk_sha,
            })

        # Per-app container logs — written into apps/<slug>/app_log_part_NNN.md
        # using the same date range and chunk size. Each app gets its own
        # subfolder so the records stay separated by author/owner.
        all_apps = db.query(App).order_by(App.slug.asc()).all()
        app_summaries = []
        total_app_log_records = 0
        for app in all_apps:
            app_logs = get_app_logs_for_export(db, app.id, body.start_date, body.end_date)
            if not app_logs:
                continue
            total_app_log_records += len(app_logs)
            app_chunks_total = max(1, (len(app_logs) + max_per_file - 1) // max_per_file)
            app_chunk_records = []
            for ci in range(app_chunks_total):
                seg = app_logs[ci * max_per_file:(ci + 1) * max_per_file]
                lines = [
                    f"# Container Logs — {app.name} ({app.slug}) — Part {ci + 1} of {app_chunks_total}",
                    "",
                    "## Source",
                    "",
                    f"- **App**: {app.name} (`{app.slug}`, id={app.id})",
                    f"- **Type**: {app.app_type.value if hasattr(app.app_type, 'value') else app.app_type}",
                    f"- **Owner ID**: {app.owner_id}",
                    f"- **Port**: {app.port}",
                    f"- **Date Range**: "
                    f"{body.start_date.isoformat() if body.start_date else 'beginning of time'} → "
                    f"{body.end_date.isoformat() if body.end_date else 'now'}",
                    f"- **This Chunk**: lines {ci * max_per_file + 1}–{ci * max_per_file + len(seg)}",
                    f"- **Total Lines (this app)**: {len(app_logs)}",
                    f"- **Retention Policy**: 90 days (พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560 §26)",
                    "",
                    "---",
                    "",
                    "| # | Timestamp (UTC) | Stream | Line |",
                    "|---|-----------------|--------|------|",
                ]
                base_idx = ci * max_per_file
                for j, entry in enumerate(seg, base_idx + 1):
                    ts_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
                    safe_line = (entry.log_line or "").replace("|", "\\|").replace("\n", " ")
                    lines.append(
                        f"| {j} | {ts_str} | {entry.stream or 'stdout'} | {safe_line} |"
                    )
                md_app = "\n".join(lines)
                app_sha = hashlib.sha256(md_app.encode("utf-8")).hexdigest()
                app_chunk_name = f"apps/{app.slug}/app_log_part_{ci + 1:03d}.md"
                md_app += f"\n\n---\n- **Chunk SHA-256**: `{app_sha}`\n- **Filename**: `{app_chunk_name}`\n"
                zf.writestr(app_chunk_name, md_app)
                app_chunk_records.append({
                    "filename": app_chunk_name,
                    "record_count": len(seg),
                    "sha256": app_sha,
                })
            app_summaries.append({
                "slug": app.slug,
                "name": app.name,
                "app_id": app.id,
                "owner_id": app.owner_id,
                "total_records": len(app_logs),
                "file_count": app_chunks_total,
                "chunks": app_chunk_records,
            })

        # manifest.json
        manifest = {
            "ivs_audit_export_version": 2,  # bumped: now includes per-app logs
            "exported_at": ntp_now.isoformat(),
            "exported_by": {"id": user.id, "username": user.username},
            "ntp_source": {
                "server": ntp_status.get("ntp_server"),
                "authority": ntp_status.get("ntp_authority"),
                "stratum": ntp_status.get("ntp_stratum"),
                "offset_ms": ntp_status.get("offset_ms"),
            },
            "date_range": {
                "start": body.start_date.isoformat() if body.start_date else None,
                "end": body.end_date.isoformat() if body.end_date else None,
            },
            "audit_logs": {
                "total_records": total_records,
                "file_count": total_chunks,
                "chunks": chunk_summary,
            },
            "app_logs": {
                "total_records": total_app_log_records,
                "app_count": len(app_summaries),
                "apps": app_summaries,
            },
            "max_records_per_file": max_per_file,
            "legal_basis": (
                "พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560 "
                "(audit + 90-day container-log retention §26)"
            ),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        # README.txt
        readme = (
            f"IVS Audit + App Log Export\n"
            f"==========================\n\n"
            f"Exported:        {ntp_now.isoformat()}\n"
            f"By:              {user.username}\n"
            f"Range:           {body.start_date.isoformat() if body.start_date else 'beginning of time'}\n"
            f"               → {body.end_date.isoformat() if body.end_date else 'now'}\n"
            f"Audit records:   {total_records} in {total_chunks} chunk(s)\n"
            f"App log records: {total_app_log_records} across {len(app_summaries)} app(s)\n"
            f"Chunk size:      max {max_per_file} records each\n\n"
            f"Bundle layout:\n"
            f"  audit_log_part_NNN.md      System events (login, deploy, delete, ...)\n"
            f"  apps/<slug>/app_log_part_NNN.md  Container logs per app (90-day retention)\n"
            f"  manifest.json              Machine-readable index + per-chunk SHA-256\n\n"
            f"How to verify integrity:\n"
            f"  1. Each .md file embeds its own SHA-256 at the bottom.\n"
            f"  2. manifest.json lists the expected SHA-256 of every chunk.\n"
            f"  3. The IVS database stores the SHA-256 of THIS .zip file.\n\n"
            f"Legal basis: พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560\n"
            f"  §26 — 90-day minimum retention of computer-traffic data.\n"
        )
        zf.writestr("README.txt", readme)

    # Compute SHA-256 of the resulting zip
    h = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    sha256 = h.hexdigest()

    # Save export record (with new date-range / file-count columns)
    export = AuditLogExport(
        filename=filename,
        sha256_hash=sha256,
        record_count=total_records,
        exported_by=user.id,
        start_date=body.start_date,
        end_date=body.end_date,
        file_count=total_chunks,
    )
    db.add(export)
    create_audit_log(
        db, request, user=user, action="export_audit_logs", resource_type="system",
        details=(
            f"Exported {total_records} audit logs in {total_chunks} chunk(s) "
            f"+ {total_app_log_records} app log line(s) across {len(app_summaries)} app(s), "
            f"range={range_label}, SHA-256: {sha256[:16]}..."
        ),
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

    # New exports are .zip bundles; legacy ones are single .md files.
    media_type = "application/zip" if export.filename.endswith(".zip") else "text/markdown"
    return FileResponse(
        path=filepath,
        filename=export.filename,
        media_type=media_type,
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


@router.get("/retention")
async def get_retention_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Read current retention policy for every log type.

    Returns a dict like:
        {
          "audit_logs":       {"days": 730, "default": 730, "min": 90, ...},
          "app_logs":         {"days": 90,  "default": 90,  "min": 90, ...},
          "resource_metrics": {"days": 30,  ...},
          "exports":          {"days": 365, ...},
        }
    """
    return retention_service.get_all_settings(db)


@router.put("/retention")
async def update_retention_settings(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update one or more retention values.

    Body shape (all keys optional, integer days):
        {"audit_logs": 730, "app_logs": 90, "resource_metrics": 30, "exports": 365}

    Each value is clamped to its per-type minimum (90 days for audit and
    app logs per §26) and to MAX_ALLOWED (10 years) to prevent typos
    pinning data forever.
    """
    changes = []
    for log_type, days in payload.items():
        if log_type not in retention_service.DEFAULT_RETENTION_DAYS:
            continue
        try:
            days_int = int(days)
        except (TypeError, ValueError):
            continue
        clamped = retention_service.set_retention_days(db, log_type, days_int)
        changes.append(f"{log_type}={clamped}d")

    if changes:
        create_audit_log(
            db, request, user=user, action="update_retention", resource_type="system",
            details=f"Updated retention policy: {', '.join(changes)}",
            log_level="WARNING",
        )
        db.commit()

    return retention_service.get_all_settings(db)


@router.post("/retention/purge")
async def trigger_retention_purge(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Manually trigger the retention purge that normally runs daily.

    Useful right after lowering a retention value, so the admin doesn't
    have to wait 24h to see disk reclaimed.
    """
    result = retention_service.purge_all(db)
    create_audit_log(
        db, request, user=user, action="trigger_retention_purge", resource_type="system",
        details=f"Manual purge: {result}",
        log_level="WARNING",
    )
    db.commit()
    return result


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
                "disk_total": disk.used + disk.free,  # Effective total (excludes APFS purgeable)
                "apps_running": running,
                "apps_total": total,
            })
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
