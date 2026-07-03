"""
Enterprise machine registry — CRUD + LAN auto-discovery.

In IVS Free: exposes only /self (register this machine) and GET list.
In IVS Enterprise: full fleet management, group assignment, remote health checks.

Auto-discovery uses Zeroconf (mDNS) to find _http._tcp.local. services
advertising the IVS product string on the same LAN segment.
"""
import logging
import socket
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models import MachineRegistry, User, UserRole
from app.services import license_service
from app.services.audit_service import create_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class MachineOut(BaseModel):
    id: int
    fingerprint: str
    serial: Optional[str]
    hostname: Optional[str]
    ip_address: Optional[str]
    port: int
    edition: str
    group_name: Optional[str]
    notes: Optional[str]
    is_self: bool
    discovery_source: str
    last_seen: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class MachineAddRequest(BaseModel):
    fingerprint: str
    serial: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    port: int = 3000
    group_name: Optional[str] = None
    notes: Optional[str] = None


class MachinePatchRequest(BaseModel):
    group_name: Optional[str] = None
    notes: Optional[str] = None
    hostname: Optional[str] = None


class DiscoveredMachine(BaseModel):
    hostname: Optional[str]
    ip_address: str
    port: int
    product: Optional[str]
    version: Optional[str]
    fingerprint: Optional[str]  # only if machine exposes /api/system/license
    already_registered: bool


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _utcnow():
    return datetime.now(timezone.utc)


def _self_fingerprint() -> str:
    try:
        return license_service.compute_fingerprint()
    except Exception:
        return "UNKNOWN"


def _ensure_self_registered(db: Session) -> MachineRegistry:
    """Lazily create the self row on first access."""
    fp = _self_fingerprint()
    existing = db.query(MachineRegistry).filter_by(fingerprint=fp, is_self=True).first()
    if existing:
        existing.last_seen = _utcnow()
        db.commit()
        return existing

    info = license_service.get_license_info()
    ip = _get_local_ip()
    row = MachineRegistry(
        fingerprint=fp,
        serial=info.get("serial"),
        hostname=socket.gethostname(),
        ip_address=ip,
        port=3000,
        edition=info.get("edition", "FREE"),
        is_self=True,
        discovery_source="self",
        last_seen=_utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@router.get("/machines", response_model=List[MachineOut])
async def list_machines(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all machines in the registry (self + manually added + discovered)."""
    _ensure_self_registered(db)
    return db.query(MachineRegistry).order_by(MachineRegistry.created_at).all()


@router.get("/machines/self", response_model=MachineOut)
async def get_self(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Return this machine's registry entry (creates it if first time)."""
    row = _ensure_self_registered(db)
    return row


@router.post("/machines", response_model=MachineOut, status_code=201)
async def add_machine(
    body: MachineAddRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Manually register a remote IVS machine by fingerprint."""
    fp = body.fingerprint.upper().strip()
    if len(fp) != 16:
        raise HTTPException(status_code=422, detail="fingerprint must be exactly 16 hex chars")

    existing = db.query(MachineRegistry).filter_by(fingerprint=fp).first()
    if existing:
        raise HTTPException(status_code=409, detail="Machine with this fingerprint already registered")

    row = MachineRegistry(
        fingerprint=fp,
        serial=body.serial,
        hostname=body.hostname,
        ip_address=body.ip_address,
        port=body.port,
        group_name=body.group_name,
        notes=body.notes,
        is_self=False,
        discovery_source="manual",
        last_seen=None,
        added_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    create_audit_log(
        db, request, user,
        action="add_machine",
        resource_type="machine_registry",
        details=f"Added machine fingerprint={fp} hostname={body.hostname}",
        log_level="INFO",
    )
    return row


@router.patch("/machines/{fingerprint}", response_model=MachineOut)
async def patch_machine(
    fingerprint: str,
    body: MachinePatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update group, notes, or hostname for a registered machine."""
    fp = fingerprint.upper().strip()
    row = db.query(MachineRegistry).filter_by(fingerprint=fp).first()
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found")

    if body.group_name is not None:
        row.group_name = body.group_name
    if body.notes is not None:
        row.notes = body.notes
    if body.hostname is not None:
        row.hostname = body.hostname

    db.commit()
    db.refresh(row)
    return row


@router.delete("/machines/{fingerprint}", status_code=204)
async def remove_machine(
    fingerprint: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Remove a machine from the registry. Cannot remove self."""
    fp = fingerprint.upper().strip()
    row = db.query(MachineRegistry).filter_by(fingerprint=fp).first()
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found")
    if row.is_self:
        raise HTTPException(status_code=400, detail="Cannot remove self from registry")

    db.delete(row)
    db.commit()
    create_audit_log(
        db, request, user,
        action="remove_machine",
        resource_type="machine_registry",
        details=f"Removed machine fingerprint={fp}",
        log_level="WARNING",
    )


@router.get("/machines/discover", response_model=List[DiscoveredMachine])
async def discover_machines(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Scan the LAN for IVS instances via mDNS (_http._tcp.local.).

    Returns machines that advertise the IVS product string.
    Marks each as already_registered if their IP is already in the registry.
    Timeout: 3 seconds (Zeroconf browse window).
    """
    discovered: List[DiscoveredMachine] = []

    try:
        from zeroconf import Zeroconf, ServiceBrowser
        import time

        known_ips = {
            r.ip_address
            for r in db.query(MachineRegistry).all()
            if r.ip_address
        }

        found = {}

        class _Listener:
            def add_service(self, zc, stype, name):
                info = zc.get_service_info(stype, name, timeout=2000)
                if not info:
                    return
                props = {
                    k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in (info.properties or {}).items()
                }
                # Filter: only IVS instances
                if "IVS" not in props.get("product", ""):
                    return
                try:
                    ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
                except Exception:
                    ip = None
                if not ip:
                    return
                found[ip] = {
                    "hostname": props.get("hostname"),
                    "ip_address": ip,
                    "port": info.port,
                    "product": props.get("product"),
                    "version": props.get("version"),
                }

            def remove_service(self, zc, stype, name):
                pass

            def update_service(self, zc, stype, name):
                pass

        zc = Zeroconf()
        listener = _Listener()
        browser = ServiceBrowser(zc, "_http._tcp.local.", listener)
        time.sleep(3)
        zc.close()

        for ip, data in found.items():
            discovered.append(DiscoveredMachine(
                hostname=data["hostname"],
                ip_address=ip,
                port=data["port"],
                product=data["product"],
                version=data["version"],
                fingerprint=None,  # would require HTTP call to /api/system/license
                already_registered=ip in known_ips,
            ))

    except ImportError:
        raise HTTPException(status_code=503, detail="zeroconf not installed — mDNS discovery unavailable")
    except Exception as e:
        logger.warning(f"mDNS discovery error: {e}")
        raise HTTPException(status_code=503, detail=f"Discovery failed: {e}")

    return discovered
