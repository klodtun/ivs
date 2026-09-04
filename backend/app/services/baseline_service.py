"""ลายนิ้วมือของโค้ด — บอกว่าลูกค้าแก้อะไรไปบ้างก่อนที่การอัปเกรดจะทับ

ชั้นที่สามของรอยเท้า สคีมาย้ายได้เพราะเราคุมมันทั้งหมด แต่โค้ดที่ AI ของลูกค้า
แก้ไว้ในไฟล์แกน เราไม่รู้ว่ามีอยู่จนกว่าจะเขียนทับไปแล้ว

สามเขต ประกาศไว้ที่นี่ที่เดียว:

    core    แกนที่เราดูแล การอัปเกรดเขียนทับ ถ้าลูกค้าแก้ต้องเตือนก่อน
    extend  เขตของลูกค้า (custom/) การอัปเกรดไม่แตะตลอดไป
    gray    ตั้งค่าและธีม ต้องรวมสามทาง แจ้งเมื่อชน

ฐานที่ใช้เทียบมีสองแบบ และเชื่อได้ไม่เท่ากัน

    release     มาจาก release_manifest.json ที่แนบมากับรุ่น บอกได้จริงว่าลูกค้า
                แก้อะไร เพราะฐานคือสิ่งที่เราปล่อยออกไป
    first_boot  จดจากสภาพที่พบตอนบูตแรก ถ้าลูกค้าแก้ไปก่อนหน้านั้นแล้ว การแก้
                นั้นจะกลายเป็นค่าตั้งต้นโดยที่ไม่มีใครรู้

ความต่างนี้ต้องขึ้นในรายงาน ไม่ใช่ซ่อนไว้ รายงานที่บอกว่า "ไม่มีไฟล์ถูกแก้"
ทั้งที่วัดจากฐานที่แก้ไปแล้ว เป็นรายงานที่หลอกคนอ่าน และจะถูกเชื่อจนถึงวันที่
การอัปเกรดทับงานเขาจริง ๆ

ดู docs/iVS_Edition_Migration_Design.md
"""

import fnmatch
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models import FileBaseline

logger = logging.getLogger(__name__)

# ราก = โฟลเดอร์โครงการ (ที่มี backend/ กับ frontend/ อยู่ข้างใน)
REPO_ROOT = Path(__file__).resolve().parents[3]

# ไฟล์รายการที่แนบมากับรุ่น ถ้ามี = ฐานที่เชื่อได้
RELEASE_MANIFEST = REPO_ROOT / "release_manifest.json"

# สิ่งที่นับเป็นโค้ด — ไม่รวมของที่สร้างขึ้นเอง ข้อมูล หรือของที่ลูกค้าดีพลอย
_INCLUDE = (
    "backend/app/**/*.py",
    "frontend/src/**/*.ts",
    "frontend/src/**/*.tsx",
    "scripts/*.sh",
)

_EXCLUDE = (
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.next/**",
    "**/venv/**",
    "backend/deployed_apps/**",
    "backend/data/**",
    "backend/uploads/**",
)

# เขต extend — การอัปเกรดต้องไม่แตะ
_EXTEND = (
    "backend/app/custom/**",
    "frontend/src/custom/**",
)

# เขต gray — ตั้งค่าและธีม ต้องรวมสามทางแทนการเขียนทับ
_GRAY = (
    "frontend/src/lib/i18n.ts",
    "frontend/src/lib/features.ts",
    "frontend/tailwind.config.js",
    "backend/app/config.py",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _matches(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def zone_of(rel: str) -> str:
    """เขตของไฟล์หนึ่ง — extend ชนะเสมอ เพราะเป็นคำสัญญาที่แรงที่สุด"""
    if _matches(rel, _EXTEND):
        return "extend"
    if rel in _GRAY:
        return "gray"
    return "core"


def sha256_of(path: Path) -> Tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def scan() -> Dict[str, dict]:
    """เดินหาไฟล์โค้ดทั้งหมดแล้วคืนลายนิ้วมือปัจจุบัน

    คีย์เป็นเส้นทางแบบสัมพัทธ์กับรากโครงการ เพื่อให้เทียบข้ามเครื่องได้ — ลาย
    ที่ผูกกับเส้นทางเต็มจะเทียบกับรายการที่แนบมากับรุ่นไม่ได้เลย
    """
    out: Dict[str, dict] = {}
    for pattern in _INCLUDE:
        for p in REPO_ROOT.glob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO_ROOT).as_posix()
            if _matches(rel, _EXCLUDE):
                continue
            try:
                digest, size = sha256_of(p)
            except OSError as e:
                logger.warning("อ่านไฟล์ไม่ได้ %s: %s", rel, e)
                continue
            out[rel] = {"sha256": digest, "size": size, "zone": zone_of(rel)}
    return out


def load_release_manifest() -> Optional[Dict[str, dict]]:
    """รายการลายที่แนบมากับรุ่น ถ้ามี

    รุ่นที่ปล่อยจริงควรมีไฟล์นี้ เครื่องพัฒนาไม่มี จึงต้องรองรับทั้งสองทางและ
    บอกให้ชัดว่ากำลังใช้ฐานแบบไหน
    """
    if not RELEASE_MANIFEST.is_file():
        return None
    try:
        data = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
        files = data.get("files") or {}
        return {k: v for k, v in files.items() if isinstance(v, dict)}
    except Exception as e:                        # noqa: BLE001
        logger.error("release_manifest.json อ่านไม่ได้: %s", e)
        return None


def record(db: Session, *, force: bool = False) -> dict:
    """บันทึกฐานสำหรับเทียบครั้งหน้า

    เรียกตอนบูตแรก และตอนที่รุ่นเปลี่ยน (หลังอัปเกรดสำเร็จ) ไม่เรียกทุกบูต
    เพราะการบันทึกทับทุกครั้งจะลบหลักฐานว่าลูกค้าแก้อะไรไว้ — ซึ่งเท่ากับไม่มี
    ระบบนี้เลย

    ถ้ามีรายการที่แนบมากับรุ่น ใช้อันนั้นเป็นฐาน ไม่ใช่สภาพบนดิสก์ เพราะสภาพบน
    ดิสก์อาจถูกแก้ไปแล้วก่อนที่เราจะได้ดูครั้งแรก
    """
    existing = db.query(FileBaseline).count()
    if existing and not force:
        return {"recorded": 0, "skipped": existing, "source": "already"}

    manifest = load_release_manifest()
    source = "release" if manifest else "first_boot"
    current = scan()
    base = manifest if manifest else current

    db.query(FileBaseline).delete()
    n = 0
    for rel, info in base.items():
        db.add(
            FileBaseline(
                path=rel,
                zone=info.get("zone") or zone_of(rel),
                sha256=info.get("sha256", ""),
                size=int(info.get("size") or 0),
                version=settings.APP_VERSION,
                source=source,
                recorded_at=_now(),
            )
        )
        n += 1
    db.commit()
    logger.info("File baseline recorded: %d files (source=%s)", n, source)
    return {"recorded": n, "skipped": 0, "source": source}


def drift(db: Session) -> dict:
    """เทียบสภาพปัจจุบันกับฐาน แล้วบอกว่าอะไรเปลี่ยน

    แยกผลตามเขต เพราะความหมายต่างกันสิ้นเชิง ไฟล์ที่แก้ในเขต extend คือการใช้
    ระบบตามที่ออกแบบไว้ ส่วนไฟล์เดียวกันที่แก้ในเขต core คือของที่จะหายตอน
    อัปเกรด สองอย่างนี้ห้ามนับรวมกันเป็นตัวเลขเดียว
    """
    rows = {r.path: r for r in db.query(FileBaseline).all()}
    if not rows:
        return {
            "available": False,
            "reason": "ยังไม่มีฐานให้เทียบ — บันทึกฐานก่อน",
            "source": None,
        }

    source = next(iter(rows.values())).source
    current = scan()

    modified: List[dict] = []
    added: List[dict] = []
    removed: List[dict] = []

    for rel, info in current.items():
        row = rows.get(rel)
        if row is None:
            added.append({"path": rel, "zone": zone_of(rel)})
        elif row.sha256 and row.sha256 != info["sha256"]:
            modified.append({
                "path": rel,
                "zone": row.zone,
                "baseline_version": row.version,
                "baseline_at": row.recorded_at.isoformat() if row.recorded_at else None,
            })

    for rel, row in rows.items():
        if rel not in current:
            removed.append({"path": rel, "zone": row.zone})

    def by_zone(items: List[dict], zone: str) -> List[dict]:
        return [i for i in items if i.get("zone") == zone]

    core_changed = by_zone(modified, "core") + by_zone(removed, "core")
    gray_changed = by_zone(modified, "gray")

    return {
        "available": True,
        "source": source,
        # ฐานแบบ first_boot บอกได้แค่ว่าเปลี่ยนหลังจากที่เราเริ่มดู ไม่ใช่ว่า
        # ต่างจากรุ่นที่เราปล่อย ผู้อ่านต้องเห็นข้อจำกัดนี้ ไม่ใช่เดาเอง
        "trustworthy": source == "release",
        "caveat": (
            ""
            if source == "release"
            else "ฐานนี้จดจากสภาพเครื่องตอนบูตแรก ไม่ใช่จากรุ่นที่ปล่อย "
                 "การแก้ที่เกิดขึ้นก่อนหน้านั้นจะไม่ปรากฏที่นี่"
        ),
        "baseline_files": len(rows),
        "modified": modified,
        "added": added,
        "removed": removed,
        "core_conflicts": core_changed,
        "gray_conflicts": gray_changed,
        "extend_files": len(by_zone(modified, "extend")) + len(by_zone(added, "extend")),
        "counts": {
            "modified": len(modified),
            "added": len(added),
            "removed": len(removed),
            "core_conflicts": len(core_changed),
            "gray_conflicts": len(gray_changed),
        },
    }


def write_release_manifest(dest: Optional[Path] = None) -> Path:
    """สร้างไฟล์รายการลายสำหรับรุ่นที่กำลังจะปล่อย

    รันตอน build ไม่ใช่ตอนรัน ผลคือเครื่องลูกค้าที่ได้ไฟล์นี้ไปด้วยจะเทียบกับ
    สิ่งที่เราปล่อยจริง แทนที่จะเทียบกับสภาพตัวเองตอนบูตแรก
    """
    dest = dest or RELEASE_MANIFEST
    payload = {
        "version": settings.APP_VERSION,
        "generated_at": _now().isoformat(),
        "files": scan(),
    }
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("release_manifest.json written: %d files", len(payload["files"]))
    return dest
