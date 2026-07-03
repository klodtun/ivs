"""
IVS — Internal Vibe Server (FastAPI entry point).

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.

Unauthorized redistribution, resale, or removal of this notice is prohibited
under EULA §3.3 / §3.5.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models import User, UserRole
from app.middleware.auth import hash_password
from app.routers import auth, apps, system, tunnels, vault, pdpa, enterprise, api_catalog
from app.services.tunnel_service import tunnel_service
from app.services.ntp_service import ntp_service
from app.services.resource_service import collect_snapshot
from app.services.app_log_service import (
    collect_one_pass as collect_app_logs,
    _bootstrap_checkpoints as bootstrap_app_log_checkpoints,
)
from app.services.retention_service import purge_all as purge_all_retention
from app.services.mdns_service import mdns_service, DEFAULT_MDNS_HOSTNAME
from app.models import App, SystemConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def tunnel_cleanup_loop():
    while True:
        try:
            db = SessionLocal()
            await tunnel_service.cleanup_expired(db)
            db.close()
        except Exception as e:
            logger.error(f"Tunnel cleanup error: {e}")
        await asyncio.sleep(30)


async def resource_collection_loop():
    """Collect resource metrics every 60 seconds for historical tracking."""
    while True:
        try:
            db = SessionLocal()
            collect_snapshot(db)
            db.close()
        except Exception as e:
            logger.error(f"Resource collection error: {e}")
        await asyncio.sleep(60)


async def app_log_collection_loop():
    """Mirror each running app's docker logs to the DB every 30 seconds.

    Required for 90-day retention under พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560.
    """
    # Seed checkpoints from existing DB rows so a restart doesn't replay
    db = SessionLocal()
    try:
        bootstrap_app_log_checkpoints(db)
    except Exception as e:
        logger.error(f"App log bootstrap error: {e}")
    finally:
        db.close()

    while True:
        try:
            db = SessionLocal()
            collect_app_logs(db)
            db.close()
        except Exception as e:
            logger.error(f"App log collection error: {e}")
        await asyncio.sleep(30)


async def retention_purge_loop():
    """Daily purge across ALL log tables, using per-type retention configured
    in SystemConfig (audit logs, app logs, resource metrics, export files).

    Reference: พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560 §26
    — minimum 90 days, default 2 years, extendable by competent officer.
    """
    while True:
        try:
            db = SessionLocal()
            purge_all_retention(db)
            db.close()
        except Exception as e:
            logger.error(f"Retention purge error: {e}")
        await asyncio.sleep(86400)  # 24h


def _reassign_orphan_owners():
    from app.models import User, App, UserRole
    db = SessionLocal()
    try:
        admin = (
            db.query(User)
            .filter(User.role == UserRole.ADMIN, User.is_active == True)
            .order_by(User.id.asc())
            .first()
        )
        if not admin:
            return
        valid_ids = {u.id for u in db.query(User.id).all()}
        orphans = db.query(App).filter(~App.owner_id.in_(valid_ids)).all() if valid_ids else []
        if not orphans:
            return
        for app in orphans:
            app.owner_id = admin.id
        db.commit()
        logger.warning(f"Reassigned {len(orphans)} orphaned app(s) to admin {admin.username}")
    finally:
        db.close()


def _apply_lightweight_migrations():
    """Idempotent ALTER TABLE for columns added after the initial schema.

    SQLite doesn't support `ADD COLUMN IF NOT EXISTS` until v3.35, so we
    introspect first via PRAGMA and only add what's missing. This keeps
    existing on-disk databases working without a separate migration tool.
    """
    from sqlalchemy import text
    additions = [
        ("audit_log_exports", "start_date", "DATETIME"),
        ("audit_log_exports", "end_date", "DATETIME"),
        ("audit_log_exports", "file_count", "INTEGER DEFAULT 1"),
        ("apps", "logo_data", "TEXT"),
        ("app_pdpa", "anonymization_mode", "TEXT DEFAULT 'none'"),
    ]
    with engine.begin() as conn:
        for table, column, coldef in additions:
            try:
                existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            except Exception:
                continue
            if column in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}"))
                logger.info(f"Migration: added {table}.{column}")
            except Exception as e:
                logger.warning(f"Migration: could not add {table}.{column}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    _seed_admin()
    _reassign_orphan_owners()
    _sync_app_domains_to_current_ip()
    # Auto-start Docker if not running — deployed apps depend on it.
    # Fire-and-forget so backend boot doesn't block on Docker Desktop
    # cold-start (which can be 30-60s on macOS).
    try:
        from app.services.docker_service import docker_service
        if not docker_service.is_available():
            launch = docker_service.start_daemon()
            logger.warning(f"Docker not running at boot — attempted auto-start: {launch}")
    except Exception as e:
        logger.error(f"Docker auto-start failed: {e}")
    # Start NTP sync with Thai legal NTP servers
    ntp_service.start()
    ntp_status = ntp_service.get_status()
    logger.info(f"NTP synced with {ntp_status['ntp_server']} ({ntp_status['ntp_server_name']}) offset={ntp_status['offset_ms']}ms")
    # Start mDNS broadcasting (default: ivs.local)
    _start_mdns()
    task = asyncio.create_task(tunnel_cleanup_loop())
    resource_task = asyncio.create_task(resource_collection_loop())
    app_log_task = asyncio.create_task(app_log_collection_loop())
    app_log_purge_task = asyncio.create_task(retention_purge_loop())
    # Anti-tamper / copyright integrity check (logs CRITICAL on breach)
    try:
        from app.services.integrity_service import check_on_startup
        check_on_startup()
    except Exception as e:
        logger.warning(f"Integrity check failed: {e}")
    logger.info(f"IVS Backend started - {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("Copyright (C) 2026 IVS Project. Licensed under IVS Proprietary EULA.")
    yield
    ntp_service.stop()
    mdns_service.stop()
    task.cancel()
    resource_task.cancel()
    app_log_task.cancel()
    app_log_purge_task.cancel()


def _seed_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not existing:
            admin = User(
                username=settings.ADMIN_USERNAME,
                email=f"{settings.ADMIN_USERNAME}@ivs.local",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            logger.info(f"Admin user '{settings.ADMIN_USERNAME}' created")
    finally:
        db.close()


def _start_mdns():
    """Start mDNS with saved hostname or default 'ivs'."""
    db = SessionLocal()
    try:
        # Respect the admin's mDNS on/off choice (some LANs block multicast)
        en_row = db.query(SystemConfig).filter(SystemConfig.key == "mdns_enabled").first()
        if en_row and en_row.value == "false":
            logger.info("mDNS disabled by config — skipping broadcast")
            return
        config = db.query(SystemConfig).filter(SystemConfig.key == "mdns_hostname").first()
        hostname = config.value if config else DEFAULT_MDNS_HOSTNAME
        # Use port 80 for production (Caddy), 3000 for dev (Next.js)
        port = 80 if not settings.DEBUG else 3000
        mdns_service.start(hostname, port)
        logger.info(f"mDNS started: {hostname}.local (port {port})")
    except Exception as e:
        logger.error(f"Failed to start mDNS: {e}")
    finally:
        db.close()


def _sync_app_domains_to_current_ip():
    """Auto-update all app domain URLs when server IP changes (DHCP)."""
    import re
    current_ip = settings.SERVER_IP
    db = SessionLocal()
    try:
        apps_list = db.query(App).filter(App.domain.isnot(None)).all()
        updated = 0
        for a in apps_list:
            # Match http://OLD_IP:PORT pattern
            match = re.match(r"http://(\d+\.\d+\.\d+\.\d+):(\d+)", a.domain or "")
            if match:
                old_ip = match.group(1)
                if old_ip != current_ip:
                    port = match.group(2)
                    old_domain = a.domain
                    a.domain = f"http://{current_ip}:{port}"
                    updated += 1
                    logger.info(f"IP sync: {a.slug} domain updated {old_domain} -> {a.domain}")
        if updated:
            db.commit()
            logger.info(f"IP sync complete: {updated} app(s) updated to {current_ip}")
        else:
            logger.info(f"IP sync: all apps already match current IP ({current_ip})")
    finally:
        db.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(apps.router)
app.include_router(system.router)
app.include_router(tunnels.router)
app.include_router(vault.router)
app.include_router(pdpa.router)
app.include_router(enterprise.router)
app.include_router(api_catalog.router)


@app.get("/api/health")
async def health_check():
    ntp_status = ntp_service.get_status()
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "ntp": {
            "synced": ntp_status["synced"],
            "server": ntp_status["ntp_server"],
            "server_name": ntp_status["ntp_server_name"],
            "offset_ms": ntp_status["offset_ms"],
        },
    }


@app.get("/api/ntp-status")
async def ntp_status():
    """สถานะการ sync เวลากับ NTP Server ตามกฎหมายไทย"""
    return ntp_service.get_status()
