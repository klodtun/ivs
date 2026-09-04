"""ภาพรวมสำหรับหน้าแรก — สิ่งที่ควรรู้ ไม่ใช่สิ่งที่ต้องกด

Copyright © 2026 IVS Project. All Rights Reserved.
Licensed under the IVS Proprietary EULA. See LICENSE in the project root.

ทำไมต้องมีโมดูลนี้
-----------------
หน้าแรกเดิมแสดงการ์ดแอปชุดเดียวกับหน้าแอปพลิเคชัน สองหน้าจึงตอบคำถามเดียวกัน
และไม่มีหน้าไหนตอบคำถามที่คนเปิดหน้าแรกมาถามจริง — *"ตอนนี้มีอะไรที่ฉันควรรู้"*

ตัวเลขทุกตัวที่นี่มีอยู่ในฐานข้อมูลอยู่แล้ว กระจายอยู่คนละหน้า งานของโมดูลนี้คือ
เอามาวางให้เห็นพร้อมกัน ไม่ใช่เก็บข้อมูลใหม่

กฎสามข้อ
--------
**ไม่แตะ Docker** ทุกค่าอ่านจากตารางที่ลูปเบื้องหลังเขียนไว้แล้ว หน้าที่เรียก
Docker ตอนโหลดจะช้าลงทุกครั้งที่มีแอปเพิ่ม และหน้าแรกคือหน้าที่เปิดบ่อยที่สุด

**กรองตามสิทธิ์เสมอ** ผู้ใช้ที่เห็นแอปได้ 3 ตัว ต้องไม่เห็นตัวเลขที่รวมอีก 13 ตัว
ไม่งั้นตัวเลขบนหน้าแรกจะกลายเป็นการบอกว่ามีอะไรอยู่ในระบบบ้าง กับคนที่ไม่มีสิทธิ์รู้

**นับเฉพาะของที่ยังมีอยู่** คลัง API เก็บรายการของแอปที่ถูกลบไปแล้วไว้ด้วย ถ้านับรวม
หน้าแรกจะมีเลขแดงถาวรที่ไม่มีใครแก้ได้ แล้วทุกคนจะเลิกเชื่อธงทั้งหมดบนหน้านี้ —
บทเรียนเดียวกับตอนที่ตัวตรวจรายงานว่าแอปที่แข็งแรงติดต่อไม่ได้
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    ApiCatalogEntry, App, AppDependency, AppFieldPolicy, AppPdpa, AppStatus,
    AuditLog, ChangeRecord, ExchangeToken, FlowStep, FlowStepStatus,
    ResourceMetric, Tunnel, TunnelStatus, User, UserAppAccess, VaultGrant, VaultKey,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# รายการที่ยาวเกินไปทำให้กล่องยาวจนอ่านไม่ได้ และส่งข้อมูลเปล่า ๆ ทุกครั้งที่โหลด
# หน้าแรก จำกัดไว้แล้วบอกจำนวนที่เหลือ ดีกว่าตัดเงียบ ๆ ให้คนนับเองไม่ตรง
_DETAIL_CAP = 25


def _cap(items: List[str]) -> List[str]:
    """เรียงแล้วตัดความยาว — ไม่ตัดรายการซ้ำ

    เคยยุบรายการที่ข้อความเหมือนกัน ทำให้ตัวเลขกับรายการไม่ตรง: การเปลี่ยนแปลง
    สองรายการที่รหัสและคำอธิบายเหมือนกันเป็นคนละแถวจริง ๆ นับ 6 แต่กางออกมา 5
    ซึ่งทำลายเหตุผลทั้งหมดของการกางรายการ — คนกางมาเพื่อตรวจว่าตัวเลขถูก
    """
    items = sorted(items)
    if len(items) <= _DETAIL_CAP:
        return items
    return items[:_DETAIL_CAP] + [f"… +{len(items) - _DETAIL_CAP}"]


def visible_apps(db: Session, user: User) -> List[App]:
    """แอปที่ผู้ใช้คนนี้เห็นได้ — กฎเดียวกับหน้ารายการแอป

    เขียนซ้ำที่นี่แทนการ import จาก router เพื่อไม่ให้ service พึ่ง router
    ถ้ากฎเปลี่ยน ต้องแก้ทั้งสองที่ และความจริงข้อนี้เขียนไว้ตรงนี้ให้เห็น
    """
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role == "admin":
        return db.query(App).all()

    records = db.query(UserAppAccess).filter(UserAppAccess.user_id == user.id).all()
    access_all = any(r.access_all for r in records)
    assigned = {r.app_id for r in records if r.app_id is not None}

    if role == "developer":
        if access_all:
            return db.query(App).all()
        return db.query(App).filter(
            (App.owner_id == user.id) | (App.id.in_(assigned or {-1}))
        ).all()

    # ผู้ชม: เฉพาะแอปที่ได้รับมอบหมายและกำลังทำงานอยู่
    q = db.query(App).filter(App.status == AppStatus.RUNNING)
    if access_all:
        return q.all()
    return q.filter(App.id.in_(assigned or {-1})).all()


# --------------------------------------------------------------------------- #
# ประสิทธิภาพ
# --------------------------------------------------------------------------- #

def _performance(db: Session, apps: List[App], ids: set) -> Dict:
    latest = db.query(ResourceMetric).order_by(ResourceMetric.created_at.desc()).first()

    since = _utcnow() - timedelta(hours=24)
    trend = []
    for m in db.query(ResourceMetric).filter(
            ResourceMetric.created_at >= since).order_by(ResourceMetric.created_at).all():
        trend.append({
            "at": m.created_at.isoformat() if m.created_at else None,
            "cpu": round(m.cpu_percent or 0, 1),
            "mem": round(100 * (m.memory_used_mb or 0) / (m.memory_total_mb or 1), 1),
        })
    # เส้นแนวโน้มไม่ต้องละเอียดระดับนาที — ย่อให้เหลือราว 96 จุด (ทุก 15 นาที)
    # ข้อมูลดิบ 24 ชม. คือ 1,440 จุด ซึ่งวาดแล้วอ่านไม่ออกและส่งเปล่า ๆ
    if len(trend) > 96:
        step = len(trend) // 96 + 1
        trend = trend[::step]

    # ผลตรวจล่าสุดจากคลัง API — เฉพาะรายการของแอปที่ยังมีอยู่และผู้ใช้เห็นได้
    entries = [e for e in db.query(ApiCatalogEntry).filter(
        ApiCatalogEntry.discovery_source == "auto").all() if e.app_id in ids]

    by_app = {a.id: a for a in apps}
    slowest = sorted(
        [e for e in entries if e.last_test_status == "OK" and e.last_test_latency_ms],
        key=lambda e: -(e.last_test_latency_ms or 0),
    )[:3]

    # แอปที่กินทรัพยากรมากที่สุด — อ่านจากภาพนิ่งล่าสุดที่ลูปเก็บไว้
    #
    # ตอบคำถาม "ใครกินเครื่อง" โดยไม่ต้องไล่เปิดการ์ดทีละใบ และไม่ต้องถาม Docker
    # เรียงตามหน่วยความจำ ไม่ใช่ CPU เพราะ CPU ณ วินาทีเดียวกระโดดตลอดเวลา
    # ส่วนหน่วยความจำเปลี่ยนช้าพอที่ค่าเดียวจะมีความหมาย
    top: List[Dict] = []
    if latest and latest.per_app_json:
        try:
            rows = json.loads(latest.per_app_json) or []
        except Exception:
            rows = []
        by_slug = {a.slug: a for a in apps}
        rows = [r for r in rows if r.get("slug") in by_slug]
        rows.sort(key=lambda r: -(r.get("memory_mb") or 0))
        top = [{
            "slug": r.get("slug"),
            "memory_mb": round(r.get("memory_mb") or 0),
            "cpu_percent": round(r.get("cpu_percent") or 0, 1),
        } for r in rows[:3]]

    return {
        "top_consumers": top,
        "cpu_percent": round(latest.cpu_percent, 1) if latest and latest.cpu_percent is not None else None,
        "memory_percent": (
            round(100 * (latest.memory_used_mb or 0) / (latest.memory_total_mb or 1), 1)
            if latest else None
        ),
        "disk_percent": (
            round(100 * (latest.disk_used_gb or 0) / (latest.disk_total_gb or 1), 1)
            if latest else None
        ),
        "measured_at": latest.created_at.isoformat() if latest and latest.created_at else None,
        "trend": trend,
        "apps_total": len(apps),
        "apps_stopped": sum(1 for a in apps if a.status != AppStatus.RUNNING),
        "unreachable": sum(1 for e in entries if e.last_test_status not in ("OK", None, "")),
        "never_tested": sum(1 for e in entries if not e.last_test_status),
        # รายการจริงเบื้องหลังตัวเลข — เปิดดูได้เพื่อตรวจว่าตัวเลขมาจากอะไร
        "details": {
            "apps_running": _cap([a.slug for a in apps if a.status == AppStatus.RUNNING]),
            "apps_stopped": _cap([a.slug for a in apps if a.status != AppStatus.RUNNING]),
            "unreachable": _cap([
                f"{by_app[e.app_id].slug if e.app_id in by_app else '?'} — {e.last_test_message or e.last_test_status}"
                for e in entries if e.last_test_status not in ("OK", None, "")
            ]),
        },
        "slowest": [{
            "slug": by_app[e.app_id].slug if e.app_id in by_app else "?",
            "ms": e.last_test_latency_ms,
        } for e in slowest],
    }


# --------------------------------------------------------------------------- #
# ข้อมูลส่วนบุคคล
# --------------------------------------------------------------------------- #

def _privacy(db: Session, apps: List[App], ids: set) -> Dict:
    policies = [p for p in db.query(AppFieldPolicy).all() if p.app_id in ids]
    pdpa = {p.app_id: p for p in db.query(AppPdpa).all() if p.app_id in ids}

    no_purpose, no_retention = [], []
    for a in apps:
        row = pdpa.get(a.id)
        if not row or not (row.purpose or "").strip():
            no_purpose.append(a.slug)
        if not row or not (row.retention_period or "").strip():
            no_retention.append(a.slug)

    edges = [d for d in db.query(AppDependency).all() if d.from_app_id in ids]
    external = [d for d in edges if d.to_app_id is None]

    by_id = {a.id: a for a in apps}
    return {
        "fields_total": len(policies),
        "fields_unconfirmed": sum(1 for p in policies if not p.confirmed),
        "apps_no_purpose": len(no_purpose),
        "apps_no_purpose_examples": sorted(no_purpose)[:5],
        "apps_no_retention": len(no_retention),
        "external_targets": len({d.external_ref for d in external if d.external_ref}),
        "details": {
            "apps_no_purpose": _cap(no_purpose),
            "apps_no_retention": _cap(no_retention),
            # ชื่อฟิลด์คู่กับแอป — ชื่อฟิลด์ลอย ๆ ไม่บอกว่าต้องไปตรวจที่ไหน
            "fields_unconfirmed": _cap([
                f"{by_id[p.app_id].slug if p.app_id in by_id else '?'} — {p.field_name}"
                for p in policies if not p.confirmed
            ]),
            "external_targets": _cap([d.external_ref for d in external if d.external_ref]),
        },
    }


# --------------------------------------------------------------------------- #
# ความเสี่ยง
# --------------------------------------------------------------------------- #

def _risk(db: Session, apps: List[App], ids: set) -> Dict:
    edges = [d for d in db.query(AppDependency).all()
             if d.from_app_id in ids and (d.to_app_id is None or d.to_app_id in ids)]
    linked = set()
    for d in edges:
        linked.add(d.from_app_id)
        if d.to_app_id is not None:
            linked.add(d.to_app_id)

    steps = db.query(FlowStep).all()
    changes = [c for c in db.query(ChangeRecord).all() if c.app_id in ids]

    by_id = {a.id: a for a in apps}

    def edge_label(d: AppDependency) -> str:
        src = by_id[d.from_app_id].slug if d.from_app_id in by_id else "?"
        dst = by_id[d.to_app_id].slug if d.to_app_id in by_id else (d.external_ref or "?")
        return f"{src} → {dst}"

    return {
        "edges_total": len(edges),
        "edges_unconfirmed": sum(1 for d in edges if not d.confirmed),
        "apps_without_edges": sum(1 for a in apps if a.id not in linked),
        "steps_broken": sum(1 for s in steps if s.status == FlowStepStatus.BROKEN),
        "steps_drifted": sum(1 for s in steps if s.status == FlowStepStatus.DRIFTED),
        "steps_planned": sum(1 for s in steps if (s.unbound_kind or "manual") == "planned"),
        # ISO 13485 ข้อ 7.3.9 — การเปลี่ยนแปลงที่ยังไม่มีใครประเมินผลกระทบ
        "changes_unassessed": sum(1 for c in changes if c.reverify_needed),
        "details": {
            "edges_unconfirmed": _cap([edge_label(d) for d in edges if not d.confirmed]),
            "apps_without_edges": _cap([a.slug for a in apps if a.id not in linked]),
            "steps_planned": _cap([
                f"{s.flow_key} · {s.label}" for s in steps
                if (s.unbound_kind or "manual") == "planned"
            ]),
            "steps_broken": _cap([
                f"{s.flow_key} · {s.label} — {s.drift_note or ''}".strip(" —")
                for s in steps
                if s.status in (FlowStepStatus.BROKEN, FlowStepStatus.DRIFTED)
            ]),
            "changes_unassessed": _cap([
                f"{c.code or f'#{c.id}'} · {(c.description or '')[:60]}"
                for c in changes if c.reverify_needed
            ]),
        },
    }


# --------------------------------------------------------------------------- #
# ความปลอดภัยและการปฏิบัติตาม
# --------------------------------------------------------------------------- #

def _security(db: Session, apps: List[App], ids: set) -> Dict:
    now = _utcnow()
    soon = now + timedelta(days=14)

    tokens = [t for t in db.query(ExchangeToken).filter(
        ExchangeToken.revoked_at.is_(None)).all() if t.target_app_id in ids]
    expiring = []
    for t in tokens:
        exp = _aware(t.expires_at)
        if exp and now <= exp <= soon:
            expiring.append({"label": (t.label or "").strip() or f"#{t.id}",
                             "caller": t.caller_name,
                             "expires_at": t.expires_at.isoformat()})

    keys = db.query(VaultKey).all()
    granted_ids = {g.vault_key_id for g in db.query(VaultGrant).filter(
        VaultGrant.revoked_at.is_(None)).all()}

    week = now - timedelta(days=7)
    warnings = db.query(AuditLog).filter(
        AuditLog.log_level == "WARNING", AuditLog.created_at >= week).count()

    open_tunnels = [t for t in db.query(Tunnel).filter(
        Tunnel.status == TunnelStatus.ACTIVE).all() if t.app_id in ids]

    granted_key_ids = {g.vault_key_id for g in db.query(VaultGrant).filter(
        VaultGrant.revoked_at.is_(None)).all()}
    return {
        "details": {
            "keys_ungranted": _cap([k.name for k in keys if k.id not in granted_key_ids]),
            "keys_revealable": _cap([k.name for k in keys if getattr(k, "allow_reveal", True)]),
            "tunnels_open": _cap([
                (db.query(App).filter(App.id == t.app_id).first().slug
                 if db.query(App).filter(App.id == t.app_id).first() else f"app#{t.app_id}")
                for t in open_tunnels
            ]),
            "apps_public": _cap([a.slug for a in apps if (a.access_mode or "public") == "public"]),
            "tokens_expiring": _cap([f"{e['caller']} · {e['expires_at'][:10]}" for e in expiring]),
        },
        "tokens_active": len(tokens),
        "tokens_expiring": len(expiring),
        "tokens_expiring_list": sorted(expiring, key=lambda x: x["expires_at"])[:5],
        # กุญแจไม่ผูกกับแอป จึงไม่กรองตามสิทธิ์แอป — แต่เห็นได้เฉพาะผู้ดูแล
        "keys_total": len(keys),
        "keys_ungranted": sum(1 for k in keys if k.id not in granted_ids),
        "keys_revealable": sum(1 for k in keys if getattr(k, "allow_reveal", True)),
        "audit_warnings_7d": warnings,
        "tunnels_open": len(open_tunnels),
        "apps_public": sum(1 for a in apps if (a.access_mode or "public") == "public"),
    }


# --------------------------------------------------------------------------- #
# ปัญญาประดิษฐ์ในระบบ
# --------------------------------------------------------------------------- #

def _registered_models(db: Session) -> List[Dict]:
    """โมเดลที่มีคนลงทะเบียนไว้ พร้อมปลายทางที่มันถูกเรียกจริง

    ตารางโมเดลมากับส่วนเสริมที่ยังไม่ได้เปิดใช้ทุกที่ หน้าแรกจึงต้องทำงานได้แม้
    ไม่มีตารางนี้ — รูปแบบเดียวกับที่ change_service ใช้กับชั้นสอบกลับ ถ้าไม่มี
    ก็คืนรายการว่าง ไม่ใช่ทำให้ทั้งหน้าล้ม
    """
    try:
        raise ImportError  # โมดูลนี้ไม่มีในรุ่นนี้
    except Exception:
        return []
    try:
        rows = db.query(OpenCliLlmModel).all()
    except Exception:
        return []

    out = []
    for m in rows:
        out.append({
            "label": (m.label or m.model or "").strip(),
            "provider": (m.provider or "").strip(),
            "model": (m.model or "").strip(),
            # ปลายทางบอกว่าข้อมูลถูกส่งไปที่ใด ซึ่งเป็นคำถามแรกของงานที่มีข้อมูล
            # ผู้ป่วยเข้ามาเกี่ยว — ชื่อโมเดลอย่างเดียวไม่ตอบว่าประมวลผลที่ไหน
            "base_url": (m.base_url or "").strip(),
            "has_key": bool(m.vault_key_id),
        })
    return sorted(out, key=lambda r: r["label"])


def _ai(db: Session, apps: List[App], ids: set, is_admin: bool) -> Dict:
    """AI ที่มีอยู่จริงในระบบ — โมเดล กุญแจ และใครเรียกอะไรได้

    สำหรับงานที่เกี่ยวกับเครื่องมือแพทย์ คำถามไม่ได้จบที่ "ใช้ AI ไหม" แต่คือ
    ใช้โมเดลใด ประมวลผลที่ใด แอปใดเข้าถึงได้ และช่องทางนั้นเพิกถอนได้หรือไม่
    ทุกข้อตอบได้จากตารางที่มีอยู่แล้ว
    """
    models = _registered_models(db)

    keys = db.query(VaultKey).filter(VaultKey.category == "ai").all()
    key_ids = {k.id for k in keys}
    grants = [g for g in db.query(VaultGrant).filter(VaultGrant.revoked_at.is_(None)).all()
              if g.vault_key_id in key_ids]
    apps_with_ai = {g.app_id for g in grants if g.app_id in ids}

    # ผู้เรียกที่เป็น AI — โมเดลหรือเอเจนต์ที่ได้รับโทเคนให้เรียกแอปผ่านเกตเวย์
    # ต่างจากแอปที่ *ใช้* AI ตรงทิศทาง: อันนี้คือ AI ที่เข้ามาอ่านข้อมูลของเรา
    callers, callers_revoked = [], 0
    for t in db.query(ExchangeToken).filter(ExchangeToken.caller_kind == "ai").all():
        if t.target_app_id not in ids:
            continue
        target = db.query(App).filter(App.id == t.target_app_id).first()
        if t.revoked_at is not None:
            callers_revoked += 1
            continue
        callers.append({
            "caller": t.caller_name,
            "target": target.slug if target else "?",
            "scope": t.scope.value if hasattr(t.scope, "value") else str(t.scope),
        })

    out = {
        "details": {
            "models": _cap([
                f"{m['label']} · {m['base_url'] or 'ไม่ระบุปลายทาง'}" for m in models
            ]),
            "apps_with_ai": _cap([
                a.slug for a in apps if a.id in apps_with_ai
            ]),
            "ai_callers": _cap([f"{c['caller']} → {c['target']} ({c['scope']})" for c in callers]),
        },
        "models": models[:6],
        "models_count": len(models),
        "models_without_key": sum(1 for m in models if not m["has_key"]),
        "apps_with_ai": len(apps_with_ai),
        "apps_total": len(apps),
        "ai_callers": callers[:4],
        "ai_callers_count": len(callers),
        "ai_callers_revoked": callers_revoked,
    }
    if is_admin:
        # จำนวนกุญแจบอกขนาดของสิ่งที่มีอยู่ จึงอยู่ใต้ด่านเดียวกับการ์ดความปลอดภัย
        granted = {g.vault_key_id for g in grants}
        out["keys"] = len(keys)
        out["keys_ungranted"] = sum(1 for k in keys if k.id not in granted)
        out["details"]["keys_ungranted"] = _cap([k.name for k in keys if k.id not in granted])
    return out


# --------------------------------------------------------------------------- #
# แต่ละเมนูมีอะไรอยู่ข้างใน
# --------------------------------------------------------------------------- #

def _count(db: Session, model_path: str) -> Optional[int]:
    """นับแถวของตารางที่อาจไม่มีอยู่ในทุกการติดตั้ง

    e-Contract และ OpenCLI เป็นส่วนเสริม การนับต้องล้มเหลวแบบเงียบเป็น None
    ไม่ใช่ทำให้หน้าแรกล้ม และ None ต่างจาก 0 — อันหนึ่งแปลว่า "ไม่ได้เปิดใช้"
    อีกอันแปลว่า "เปิดใช้แล้วแต่ยังไม่มีข้อมูล" ซึ่งหน้าจอต้องแสดงต่างกัน
    """
    try:
        import app.models as m
        model = getattr(m, model_path, None)
        if model is None:
            return None
        return db.query(model).count()
    except Exception:
        return None


def _menus(db: Session, apps: List[App], ids: set, is_admin: bool) -> List[Dict]:
    """สรุปว่าแต่ละเมนูในแถบข้างมีของอยู่เท่าไร

    อ้างด้วย href เดียวกับแถบข้าง เพื่อให้ชื่อเมนูมาจากพจนานุกรมชุดเดียวกัน —
    ถ้าเปลี่ยนชื่อเมนู การ์ดนี้เปลี่ยนตาม ไม่กลายเป็นรายการที่ค่อย ๆ เพี้ยน

    ตัวเลขที่เลือกคือ "ของที่ใช้อยู่จริง" ไม่ใช่ยอดสะสม — อุโมงค์ 17 รายการใน
    ประวัติแต่เปิดอยู่ 0 คนอ่านต้องเห็น 0 ไม่ใช่ 17
    """
    tunnels_all = db.query(Tunnel).all()
    tunnels_open = [t for t in tunnels_all if t.status == TunnelStatus.ACTIVE and t.app_id in ids]

    flows = {s.flow_key for s in db.query(FlowStep).all()}
    edges = [d for d in db.query(AppDependency).all() if d.from_app_id in ids]

    since = _utcnow() - timedelta(hours=24)
    snapshots = db.query(ResourceMetric).filter(ResourceMetric.created_at >= since).count()

    rows: List[Dict] = [
        {"href": "/dashboard/apps", "count": len(apps), "unit": "apps",
         "items": _cap([a.slug for a in apps])},
        {"href": "/dashboard/tunnels", "count": len(tunnels_open), "unit": "tunnels",
         "note": f"{len(tunnels_all)}", "items": _cap([
             (db.query(App).filter(App.id == t.app_id).first() or App()).slug or f"app#{t.app_id}"
             for t in tunnels_open])},
        {"href": "/dashboard/system-map", "count": len(edges), "unit": "edges"},
        {"href": "/dashboard/flows", "count": len(flows), "unit": "flows",
         "items": _cap(list(flows))},
        {"href": "/dashboard/design-controls", "count": sum(
            x or 0 for x in (_count(db, "Requirement"), _count(db, "RiskItem"),
                             _count(db, "TestRecord"), _count(db, "ChangeRecord"))),
         "unit": "records"},
    ]

    if is_admin:
        rows.append({"href": "/dashboard/vault",
                     "count": db.query(VaultKey).count(), "unit": "keys"})
        rows.append({"href": "/dashboard/resources", "count": snapshots, "unit": "snapshots"})
        rows.append({"href": "/dashboard/settings",
                     "count": db.query(User).count(), "unit": "users"})

    # ส่วนเสริม — ไม่มีตารางก็ไม่แสดงบรรทัด ไม่ใช่แสดงศูนย์
    for href, cls, unit in (("/dashboard/econtract", "EContractCert", "certs"),
                            ("/dashboard/bridge", "OpenCliProject", "projects")):
        n = _count(db, cls)
        if n is not None:
            rows.append({"href": href, "count": n, "unit": unit})

    # เหลือเฉพาะเมนูที่รุ่นย่อยนี้มีจริง
    #
    # การ์ดนี้สรุป "แต่ละเมนูมีของเท่าไร" ถ้ามันนับเมนูที่แถบข้างไม่แสดง ผู้ใช้จะ
    # เห็นตัวเลขของหน้าที่เปิดไม่ได้ แล้วเข้าใจว่าเมนูหาย ทั้งที่ผลิตภัณฑ์นี้ไม่มี
    # เมนูนั้นตั้งแต่ต้น — เป็นอาการเดียวกับที่แถบข้างเคยตัดสินเอง คือสองที่คิด
    # เรื่องเดียวกันแล้วไม่ตรงกัน
    from app import variants
    from app.services import installation_service
    from app.config import settings
    inst = installation_service.ensure_installation(db)
    allowed = set(variants.visible_menus(settings.IVS_VARIANT, inst.edition or "FREE"))
    return [r for r in rows if r["href"] in allowed]


# --------------------------------------------------------------------------- #

def build(db: Session, user: User) -> Dict:
    """ภาพรวมทั้งหน้าในคำขอเดียว

    รวมมาครั้งเดียวเพราะหน้าต้องวาดพร้อมกันทั้งหน้า การยิงสี่คำขอแยกกันทำให้
    ตัวเลขทยอยโผล่ทีละกลุ่ม ซึ่งอ่านยากกว่ารอพร้อมกันรอบเดียว
    """
    apps = visible_apps(db, user)
    ids = {a.id for a in apps}
    role = user.role.value if hasattr(user.role, "value") else user.role

    out = {
        "generated_at": _utcnow().isoformat(),
        "role": role,
        "performance": _performance(db, apps, ids),
        "privacy": _privacy(db, apps, ids),
        "risk": _risk(db, apps, ids),
        "ai": _ai(db, apps, ids, role == "admin"),
        "menus": _menus(db, apps, ids, role == "admin"),
    }
    # คลังกุญแจและบันทึกตรวจสอบเป็นเรื่องระดับระบบ ไม่ใช่ระดับแอป ผู้ที่ไม่ได้ดูแล
    # ระบบจึงไม่ควรเห็นแม้แต่จำนวน — จำนวนกุญแจก็บอกขนาดของสิ่งที่มีอยู่
    if role == "admin":
        out["security"] = _security(db, apps, ids)
    return out


# --------------------------------------------------------------------------- #
# การ์ดเฉพาะแอป
# --------------------------------------------------------------------------- #

def app_overview(db: Session, user: User, app_id: int) -> Optional[Dict]:
    """หกมุมมองเดียวกัน แต่ของแอปตัวเดียว

    การ์ดรวมตอบว่าทั้งระบบเป็นอย่างไร คำถามถัดไปที่คนถามเสมอคือ "แล้วตัวนี้ล่ะ"
    ซึ่งเดิมต้องเปิดหกหน้าแล้วประกอบเอง

    คืน None เมื่อผู้ใช้ไม่มีสิทธิ์เห็นแอปนี้ — ตอบ 404 ที่ชั้น router ดีกว่า 403
    เพราะการบอกว่า "มีแอปนี้อยู่แต่คุณดูไม่ได้" ก็เป็นการบอกว่ามีอะไรอยู่ในระบบ
    """
    apps = visible_apps(db, user)
    app = next((a for a in apps if a.id == app_id), None)
    if not app:
        return None

    role = user.role.value if hasattr(user.role, "value") else user.role
    is_admin = role == "admin"

    # ประสิทธิภาพ — จากภาพนิ่งล่าสุดและผลตรวจล่าสุด ไม่ถาม Docker
    entry = db.query(ApiCatalogEntry).filter_by(
        app_id=app.id, discovery_source="auto").first()
    latest = db.query(ResourceMetric).order_by(ResourceMetric.created_at.desc()).first()
    mem = cpu = None
    if latest and latest.per_app_json:
        try:
            for r in json.loads(latest.per_app_json) or []:
                if r.get("slug") == app.slug:
                    mem = round(r.get("memory_mb") or 0)
                    cpu = round(r.get("cpu_percent") or 0, 1)
                    break
        except Exception:
            pass

    # ข้อมูลส่วนบุคคล
    policies = db.query(AppFieldPolicy).filter_by(app_id=app.id).all()
    pdpa = db.query(AppPdpa).filter_by(app_id=app.id).first()

    # ความเสี่ยง — เส้นเข้าและออกคนละความหมาย: ออกคือแอปนี้พึ่งใคร
    # เข้าคือใครพัง ถ้าแอปนี้หยุด ซึ่งเป็นคำถามที่ถามก่อน redeploy
    out_edges = db.query(AppDependency).filter_by(from_app_id=app.id).all()
    in_edges = db.query(AppDependency).filter_by(to_app_id=app.id).all()
    steps = [s for s in db.query(FlowStep).all() if s.app_id == app.id]
    changes = db.query(ChangeRecord).filter_by(app_id=app.id).all()

    def edge_label(d: AppDependency, incoming: bool) -> str:
        other_id = d.from_app_id if incoming else d.to_app_id
        other = db.query(App).filter(App.id == other_id).first() if other_id else None
        name = other.slug if other else (d.external_ref or "?")
        return f"{'← ' if incoming else '→ '}{name}"

    data: Dict = {
        "app_id": app.id,
        "slug": app.slug,
        "name": app.name,
        "status": app.status.value if hasattr(app.status, "value") else str(app.status),
        "version": app.current_version,
        "port": app.port,
        "access_mode": app.access_mode or "public",
        # โลโก้ที่ผู้ใช้อัปโหลดไว้ — ใช้แยกการ์ดแอปออกจากการ์ดภาพรวมด้วยสายตา
        # ว่างได้ หน้าจอจึงต้องมีตัวแทนเสมอ ไม่ใช่ปล่อยช่องโหว่
        "logo_data": app.logo_data or "",
        "app_type": app.app_type.value if hasattr(app.app_type, "value") else str(app.app_type or "unknown"),
        "performance": {
            "memory_mb": mem,
            "cpu_percent": cpu,
            "reach_status": (entry.last_test_status if entry else None) or None,
            "reach_ms": entry.last_test_latency_ms if entry else None,
            "reach_message": (entry.last_test_message if entry else "") or "",
        },
        "privacy": {
            "fields_total": len(policies),
            "fields_unconfirmed": sum(1 for p in policies if not p.confirmed),
            "fields": _cap([p.field_name for p in policies if not p.confirmed]),
            "has_purpose": bool(pdpa and (pdpa.purpose or "").strip()),
            "retention": (pdpa.retention_period if pdpa else "") or "",
            "legal_basis": (pdpa.legal_basis if pdpa else "") or "",
        },
        "risk": {
            "edges_out": len(out_edges),
            "edges_in": len(in_edges),
            "edges_unconfirmed": sum(1 for d in out_edges + in_edges if not d.confirmed),
            "edges": _cap([edge_label(d, False) for d in out_edges]
                          + [edge_label(d, True) for d in in_edges]),
            "flow_steps": len(steps),
            "steps": _cap([f"{s.flow_key} · {s.label}" for s in steps]),
            "changes_unassessed": sum(1 for c in changes if c.reverify_needed),
        },
    }

    if is_admin:
        from app.services import vault_scope_service
        pairs = vault_scope_service.granted_pairs(db, app.id)
        ai_keys = [k for _, k in pairs if (k.category or "") == "ai"]
        tokens = db.query(ExchangeToken).filter(
            ExchangeToken.target_app_id == app.id,
            ExchangeToken.revoked_at.is_(None)).all()
        tunnel = db.query(Tunnel).filter(
            Tunnel.app_id == app.id, Tunnel.status == TunnelStatus.ACTIVE).first()
        data["security"] = {
            "keys": len(pairs),
            "key_names": _cap([grant_env_name_safe(k, g) for g, k in pairs]),
            "ai_keys": len(ai_keys),
            "tokens": len(tokens),
            "token_names": _cap([f"{t.caller_name} ({t.caller_kind})" for t in tokens]),
            "tunnel_open": bool(tunnel),
        }
    return data


def grant_env_name_safe(key: VaultKey, grant) -> str:
    """ชื่อตัวแปรที่แอปนี้จะได้รับ — เรียกผ่านชั้นเดียวกับตอน deploy จริง

    ไม่คำนวณเองซ้ำ เพราะถ้าสูตรสองที่ไม่ตรงกัน หน้าจอจะบอกชื่อหนึ่ง แต่คอนเทนเนอร์
    ได้อีกชื่อ ซึ่งเป็นความผิดพลาดที่หาสาเหตุยากที่สุดแบบหนึ่ง
    """
    from app.services import vault_scope_service
    return vault_scope_service.grant_env_name(key, grant)
