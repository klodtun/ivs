import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models import User, UserRole
from app.middleware.auth import hash_password
from app.routers import auth, apps, system, tunnels, vault, pdpa
from app.services.tunnel_service import tunnel_service
from app.services.ntp_service import ntp_service
from app.services.resource_service import collect_snapshot
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
    _sync_app_domains_to_current_ip()
    # Start NTP sync with Thai legal NTP servers
    ntp_service.start()
    ntp_status = ntp_service.get_status()
    logger.info(f"NTP synced with {ntp_status['ntp_server']} ({ntp_status['ntp_server_name']}) offset={ntp_status['offset_ms']}ms")
    # Start mDNS broadcasting (default: ivs.local)
    _start_mdns()
    task = asyncio.create_task(tunnel_cleanup_loop())
    resource_task = asyncio.create_task(resource_collection_loop())
    logger.info(f"IVS Backend started - {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    ntp_service.stop()
    mdns_service.stop()
    task.cancel()
    resource_task.cancel()


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
