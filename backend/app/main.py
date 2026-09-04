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
from app.routers import auth, apps, system, tunnels, vault, pdpa, enterprise, api_catalog, exchange, datamart
from app.services.tunnel_service import tunnel_service
from app.services.ntp_service import ntp_service
from app.services.resource_service import collect_snapshot
from app.services.app_log_service import (
    collect_one_pass as collect_app_logs,
    _bootstrap_checkpoints as bootstrap_app_log_checkpoints,
)
from app.services.retention_service import purge_all as purge_all_retention
from app.services.mdns_service import mdns_service, DEFAULT_MDNS_HOSTNAME
from app.services import custom_loader
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



async def flow_drift_loop():
    """ตรวจทุกวันว่าเส้นทางการทำงานที่คนประกาศไว้ยังจริงอยู่

    ขั้นที่ผูกกับ endpoint หนึ่งอาจยังตอบอยู่ แต่หน้าตา API เปลี่ยนไปแล้ว ระบบ
    แบบนั้นไม่มี error ให้ใครเห็นจนกว่าจะมีคนเรียกจริง ซึ่งมักเป็นวันงาน รอบตรวจ
    นี้จึงมีไว้ให้รู้ก่อน ไม่ใช่ให้รู้ตอนพัง

    รอบแรกหน่วงไว้ก่อน เพราะตอนเพิ่งบูต แอปยังทยอยขึ้น การยิงทันทีจะได้ผลว่า
    ปลายทางไม่ตอบทั้งที่กำลังจะตอบในอีกไม่กี่วินาที
    """
    await asyncio.sleep(300)
    while True:
        try:
            db = SessionLocal()
            from app.services import flow_service
            summary = flow_service.verify_all(db, probe=True)
            db.close()
            if summary["drifted"] or summary["broken"]:
                logger.warning(
                    "Flow drift: %d ขั้นหน้าตาเปลี่ยน, %d ขั้นปลายทางไม่ตอบ",
                    summary["drifted"], summary["broken"],
                )
        except Exception as e:
            logger.error(f"Flow drift check error: {e}")
        await asyncio.sleep(86400)  # 24h


async def datamart_fetch_loop():
    """Fetch each due outside source, and drop records past their retention.

    Outside data is the one kind iVS does not control the shape of, so it runs
    on its own loop with its own retention rather than sharing a schedule with
    log purging — a source that fails does not delay anything else, and data
    that must be deleted is deleted whether or not any fetch succeeded.
    """
    from app.services import datamart_service as mart
    while True:
        try:
            db = SessionLocal()
            try:
                for source in mart.due_sources(db):
                    await mart.fetch_once(db, source)
                mart.purge_expired(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Data mart loop error: {e}")
        await asyncio.sleep(300)  # 5 นาที — ตัวคาบจริงกำหนดที่ตัวแหล่งข้อมูลเอง


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


def _reconcile_app_states():
    """Make the dashboard agree with Docker about what is actually running.

    A deploy that was interrupted — upload cut short, backend restarted
    mid-build — leaves a row behind with no container. Shown as RUNNING or
    BUILDING it sends the user looking for a Docker fault when the truth is
    simply that the deploy never finished, so mark those ERROR at boot.
    """
    from app.models import App, AppStatus
    from app.services.docker_service import docker_service
    if not docker_service.is_available():
        return
    db = SessionLocal()
    try:
        stale = (
            db.query(App)
            .filter(App.status.in_([AppStatus.RUNNING, AppStatus.BUILDING]))
            .all()
        )
        fixed = 0
        for app in stale:
            live = docker_service.resolve_live_container_id(
                app.container_id or "", f"{settings.CONTAINER_PREFIX}{app.slug}"
            )
            if live:
                if live != app.container_id:
                    app.container_id = live
                continue
            app.status = AppStatus.ERROR
            app.container_id = None
            fixed += 1
        if fixed:
            db.commit()
            logger.warning(f"Marked {fixed} app(s) ERROR — no container found for them")
    except Exception as e:
        logger.warning(f"App state reconcile failed: {e}")
    finally:
        db.close()


def _relax_tunnel_expiry():
    """Allow tunnels.expires_at to be NULL (a tunnel with no expiry).

    SQLite cannot ALTER a column's NOT NULL, so the table is rebuilt: create
    the new shape, copy every row, swap. Done inside one transaction and only
    when the old constraint is actually present, so a restart on an
    already-migrated database does nothing.
    """
    from sqlalchemy import text
    with engine.begin() as conn:
        try:
            info = list(conn.execute(text("PRAGMA table_info(tunnels)")))
        except Exception:
            return
        if not info:
            return
        col = next((r for r in info if r[1] == "expires_at"), None)
        if not col or not col[3]:      # r[3] = notnull flag
            return
        logger.info("Migration: rebuilding tunnels so expires_at can be NULL")
        conn.execute(text("""
            CREATE TABLE tunnels_new (
                id INTEGER NOT NULL PRIMARY KEY,
                app_id INTEGER NOT NULL,
                public_url VARCHAR(500),
                status VARCHAR(7),
                expires_at DATETIME,
                permanent_reason TEXT DEFAULT '',
                token_id INTEGER,
                container_id VARCHAR(100),
                created_by INTEGER NOT NULL,
                created_at DATETIME
            )
        """))
        existing = {r[1] for r in info}
        cols = ["id", "app_id", "public_url", "status", "expires_at",
                "container_id", "created_by", "created_at"]
        extra = [c for c in ("permanent_reason", "token_id") if c in existing]
        names = ", ".join(cols + extra)
        conn.execute(text(f"INSERT INTO tunnels_new ({names}) SELECT {names} FROM tunnels"))
        conn.execute(text("DROP TABLE tunnels"))
        conn.execute(text("ALTER TABLE tunnels_new RENAME TO tunnels"))
        logger.info("Migration: tunnels rebuilt")


def _apply_lightweight_migrations():
    """Idempotent ALTER TABLE for columns added after the initial schema.

    SQLite doesn't support `ADD COLUMN IF NOT EXISTS` until v3.35, so we
    introspect first via PRAGMA and only add what's missing. This keeps
    existing on-disk databases working without a separate migration tool.

    This whole list is migration `0001_baseline` — everything the schema
    accumulated before the ledger existed, collapsed into one entry. It stays
    a single step on purpose: splitting it retroactively would claim to know
    which boxes received which piece, and no box recorded that.

    Anything added from here on gets its own numbered id and its own row, so a
    customer's database can say what it has been through. That is the whole
    reason the ledger exists — an upgrade we cannot describe is an upgrade we
    cannot roll back.
    """
    from sqlalchemy import text
    additions = [
        ("audit_log_exports", "start_date", "DATETIME"),
        ("audit_log_exports", "end_date", "DATETIME"),
        ("audit_log_exports", "file_count", "INTEGER DEFAULT 1"),
        ("apps", "logo_data", "TEXT"),
        ("apps", "access_mode", "VARCHAR(20) DEFAULT 'public'"),
        ("app_field_policies", "note", "TEXT DEFAULT ''"),
        # คลังกุญแจ: ขอบเขตตาม namespace และความสามารถระดับใบ
        ("vault_keys", "namespace", "VARCHAR(120) DEFAULT ''"),
        ("vault_keys", "allow_reveal", "BOOLEAN DEFAULT 1"),
        ("vault_keys", "env_override", "VARCHAR(120) DEFAULT ''"),
        # ชื่อตัวแปรต่อสิทธิ์ ไม่ใช่ต่อกุญแจ — ความลับใบเดียวถึงสองระบบด้วยชื่อ
        # ที่แต่ละฝั่งอ่านจริง แทนที่จะต้องสร้างกุญแจซ้ำใบที่สองไว้ให้เพี้ยน
        ("vault_grants", "env_override", "VARCHAR(120) DEFAULT ''"),
        # ขั้นที่ยังไม่ได้เชื่อม ไม่ใช่ขั้นที่คนทำเอง — แยกไว้ไม่ให้งานที่ค้างหายไป
        ("flow_steps", "unbound_kind", "VARCHAR(20) DEFAULT 'manual'"),
        # ROPA อยู่ต่อแม้แอปถูกลบ — ต้องเก็บชื่อไว้ ไม่งั้นเหลือแค่เลขที่แปลไม่ได้
        ("app_pdpa", "app_removed_at", "DATETIME"),
        ("app_pdpa", "app_name_at_removal", "VARCHAR(200) DEFAULT ''"),
        ("app_pdpa", "app_slug_at_removal", "VARCHAR(200) DEFAULT ''"),
        ("tunnels", "permanent_reason", "TEXT DEFAULT ''"),
        ("tunnels", "token_id", "INTEGER"),
        ("api_catalog_entries", "schema_hash", "VARCHAR(64) DEFAULT ''"),
        ("api_catalog_entries", "schema_confirmed", "BOOLEAN DEFAULT 1"),
        ("app_pdpa", "legal_basis", "VARCHAR(30) DEFAULT ''"),
        ("app_pdpa", "data_recipients", "TEXT DEFAULT '[]'"),
        ("app_pdpa", "erasure_right", "VARCHAR(20) DEFAULT 'auto'"),
        ("app_pdpa", "erasure_note", "TEXT DEFAULT ''"),
        ("app_pdpa", "anonymization_mode", "TEXT DEFAULT 'none'"),
        # e-Contract: ชั้นโปรไฟล์ 7 เรื่อง
        ("installation", "variant", "VARCHAR(24) DEFAULT 'base'"),
        ("installation", "variant_changed_at", "DATETIME"),
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

    # Indexes on tables that already exist. `create_all` only builds indexes for
    # tables it creates, so an index added to an existing model needs this pass.
    indexes = [
        ("ix_audit_logs_resource", "audit_logs", "resource_type, resource_id"),
    ]
    with engine.begin() as conn:
        for name, table, cols in indexes:
            try:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})"))
            except Exception as e:
                logger.warning(f"Migration: could not create index {name}: {e}")


def _guard_installation():
    """Confirm this box is still the box it was installed as, before anything
    touches Docker.

    The container prefix is how every lookup finds a deployed app. Change it
    and the dashboard stops seeing twelve running containers, reports the apps
    as missing, and the next deploy builds over them. Nothing in that sequence
    raises an error, which is exactly why it has to be refused up front rather
    than warned about in a log nobody reads on a successful boot.

    Raising here aborts startup. That is the intended outcome: a box that will
    not start is recoverable, and a box that silently adopted the wrong prefix
    is not.
    """
    from app.services import installation_service, custom_loader
    db = SessionLocal()
    try:
        row = installation_service.guard_or_die(db)
        installation_service.run_step(
            db, "0001_baseline", lambda: None,
            checksum=installation_service.checksum_of("pre-ledger schema"),
        )
        # The customer's own migrations share the ledger but not the number
        # series, so an upgrade report shows both in one place while a future
        # core migration can never collide with one they already applied.
        custom_loader.ensure_dirs()
        custom_loader.run_migrations(db, installation_service.run_step)
        # Fingerprint the core files once, and again only when the version
        # moves. Re-recording every boot would overwrite the evidence that the
        # customer changed something, which is the entire point of having it.
        from app.services import baseline_service
        if row.installed_version != settings.APP_VERSION:
            baseline_service.record(db, force=True)
            row.installed_version = settings.APP_VERSION
            db.commit()
        else:
            baseline_service.record(db)
        logger.info(
            "Installation %s · edition %s · prefix %s",
            row.install_id[:8], row.edition, row.container_prefix,
        )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    _guard_installation()
    _relax_tunnel_expiry()
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
    datamart_task = asyncio.create_task(datamart_fetch_loop())
    flow_drift_task = asyncio.create_task(flow_drift_loop())
    # Anti-tamper / copyright integrity check (logs CRITICAL on breach)
    try:
        from app.services.integrity_service import check_on_startup
        check_on_startup()
    except Exception as e:
        logger.warning(f"Integrity check failed: {e}")
    # Put the login back in front of every app marked "protected" — the gates
    # are plain sockets, so they die with the process and must be re-opened.
    _reconcile_app_states()
    try:
        from app.services.app_gate_service import app_gate_manager
        await app_gate_manager.sync_all()
    except Exception as e:
        logger.warning(f"Could not start app gates: {e}")
    logger.info(f"IVS Backend started - {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("Copyright (C) 2026 IVS Project. Licensed under IVS Proprietary EULA.")
    yield
    try:
        from app.services.app_gate_service import app_gate_manager
        await app_gate_manager.stop_all()
    except Exception:
        pass
    ntp_service.stop()
    mdns_service.stop()
    task.cancel()
    resource_task.cancel()
    app_log_task.cancel()
    app_log_purge_task.cancel()
    datamart_task.cancel()


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
app.include_router(exchange.router)
app.include_router(datamart.router)

# The customer's own routers, mounted last and under their own prefix.
#
# Loaded one file at a time so a broken one costs that feature and nothing
# else -- unlike the container-prefix guard, which has to stop the boot,
# because continuing there loses data while continuing here loses an add-on.
# What failed is kept in custom_loader.load_report() rather than only logged,
# since an extension that vanishes silently is one the customer discovers at
# an unhelpful hour.
custom_loader.ensure_dirs()
custom_loader.load_routers(app)


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
