"""เขตของลูกค้า — โหลดโค้ดที่ลูกค้าเขียนเองโดยไม่ต้องแตะแกน

iVS ชวนให้ผู้ใช้แก้ระบบเองด้วย AI ของตัวเอง ซึ่งเป็นข้อเสนอที่ทำให้คนเลือกใช้
แต่ถ้าไม่มีที่ให้วางของ AI ของลูกค้าจะแก้ลงไปในแกน แล้วการอัปเกรดรุ่นถัดไปจะ
ทับงานนั้นทุกครั้ง ผลที่ตามมาไม่ใช่แค่ไฟล์เสียหาย แต่คือลูกค้าเลิกอัปเกรด ซึ่ง
แย่กว่ามาก เพราะเครื่องที่ไม่อัปเกรดคือเครื่องที่ไม่ได้รับการแก้ช่องโหว่

โมดูลนี้จึงประกาศเขตที่การอัปเกรดจะไม่แตะตลอดไป:

    backend/app/custom/routers/*.py       เส้นทาง API ของลูกค้า
    backend/app/custom/services/*.py      ตรรกะที่ router ของลูกค้าเรียก
    backend/app/custom/migrations/c*.py   การย้ายสคีมาของลูกค้า เลขคนละชุด

หลักสามข้อที่ตัวโหลดนี้ยึด:

1. ของลูกค้าพังต้องไม่ทำให้เครื่องเปิดไม่ขึ้น แต่ละไฟล์ถูกโหลดแยกกัน ความ
   ล้มเหลวถูกจดไว้แล้วเดินต่อ ตรงข้ามกับด่านคำนำหน้าคอนเทนเนอร์ที่ต้องหยุด
   เพราะที่นั่นเดินต่อแล้วข้อมูลหาย ที่นี่เดินต่อแล้วแค่ฟีเจอร์เสริมไม่ทำงาน

2. ความล้มเหลวต้องเห็นได้ ไม่ใช่แค่ไม่พัง สิ่งที่โหลดไม่ขึ้นถูกเก็บไว้ใน
   load_report() ให้หน้าจอและรายงานก่อนอัปเกรดอ่านได้ ของที่เงียบหายคือของที่
   ลูกค้าจะเจอตอนกลางดึกแทน

3. เขตนี้ไม่ได้แปลว่าไม่มีการควบคุม router ของลูกค้าอยู่ใต้ /api/custom/ เสมอ
   เพื่อให้แยกออกในบันทึกตรวจสอบและในกฎไฟร์วอลล์ และไม่มีสิทธิ์อะไรติดมาให้
   ฟรี — ต้องประกาศ require_role เองเหมือนทุก router

ดู docs/iVS_Edition_Migration_Design.md
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# รากของเขตลูกค้า — อยู่ข้าง ๆ แกน แต่ไม่ใช่ส่วนหนึ่งของแกน
CUSTOM_ROOT = Path(__file__).resolve().parent.parent / "custom"

# API ของลูกค้าอยู่ใต้คำนำหน้านี้เสมอ ไม่ให้ตั้งเอง เพราะถ้าลูกค้าตั้ง
# prefix="/api/apps" ทับของแกนได้ ระบบจะเพี้ยนโดยไม่มีใครรู้ว่าทับตรงไหน
CUSTOM_PREFIX = "/api/custom"

_report: Dict[str, Any] = {
    "routers": [],      # [{"module": str, "routes": int, "ok": bool, "error": str}]
    "migrations": [],   # [{"id": str, "ok": bool, "error": str}]
    "scanned_at": None,
}


def ensure_dirs() -> None:
    """สร้างโครงเขตลูกค้าถ้ายังไม่มี พร้อมคำอธิบายในตัว

    สร้างให้ตั้งแต่บูตแรกเพราะโฟลเดอร์ที่ยังไม่มีคือโฟลเดอร์ที่ AI ของลูกค้า
    จะไม่รู้ว่ามีอยู่ แล้วก็จะกลับไปแก้ในแกนตามเดิม
    """
    for sub in ("routers", "services", "migrations"):
        (CUSTOM_ROOT / sub).mkdir(parents=True, exist_ok=True)
        init = CUSTOM_ROOT / sub / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
    root_init = CUSTOM_ROOT / "__init__.py"
    if not root_init.exists():
        root_init.write_text("", encoding="utf-8")
    readme = CUSTOM_ROOT / "README.md"
    if not readme.exists():
        readme.write_text(_README, encoding="utf-8")


def _load_module(path: Path) -> Any:
    """โหลดไฟล์เดียวเป็นโมดูล โดยไม่ผ่าน import ปกติ

    ใช้ชื่อโมดูลที่ขึ้นต้นด้วย ivs_custom_ เพื่อไม่ให้ชนกับแพ็กเกจของแกนหรือของ
    ไลบรารีภายนอกใน sys.modules
    """
    mod_name = f"ivs_custom_{path.parent.name}_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"อ่านไฟล์เป็นโมดูลไม่ได้: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def _files(sub: str, pattern: str = "*.py") -> List[Path]:
    d = CUSTOM_ROOT / sub
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob(pattern) if p.name != "__init__.py")


def load_routers(app) -> List[dict]:
    """โหลด router ของลูกค้าเข้า FastAPI ทีละไฟล์

    แต่ละไฟล์ต้องมีตัวแปรชื่อ `router` เป็น APIRouter เส้นทางทั้งหมดจะถูกวางไว้
    ใต้ /api/custom/<ชื่อไฟล์>/ ไม่ว่าลูกค้าตั้ง prefix อะไรไว้ในไฟล์ก็ตาม
    """
    from fastapi import APIRouter

    results: List[dict] = []
    for path in _files("routers"):
        entry = {"module": path.stem, "routes": 0, "ok": False, "error": ""}
        try:
            module = _load_module(path)
            router = getattr(module, "router", None)
            if not isinstance(router, APIRouter):
                raise AttributeError(
                    "ไฟล์นี้ไม่มีตัวแปร `router` ที่เป็น APIRouter"
                )
            app.include_router(
                router,
                prefix=f"{CUSTOM_PREFIX}/{path.stem}",
                tags=[f"custom:{path.stem}"],
            )
            entry["routes"] = len(router.routes)
            entry["ok"] = True
            logger.info(
                "Custom router %s loaded — %d routes under %s/%s",
                path.stem, len(router.routes), CUSTOM_PREFIX, path.stem,
            )
        except Exception as e:                    # noqa: BLE001 — จดแล้วเดินต่อ
            entry["error"] = str(e)[:500]
            logger.error("Custom router %s failed to load: %s", path.stem, e)
        results.append(entry)

    _report["routers"] = results
    return results


def run_migrations(db, run_step: Callable) -> List[dict]:
    """รัน migration ของลูกค้าผ่านบัญชีเดียวกับของแกน

    ไฟล์ต้องชื่อขึ้นต้นด้วย c แล้วตามด้วยเลข (c0001_เพิ่มตารางของฉัน.py) และมี
    ฟังก์ชัน up(conn) เลขคนละชุดกับของแกนโดยเจตนา ถ้าใช้ชุดเดียวกัน วันหนึ่ง
    เลขของลูกค้าจะชนกับเลขที่เราปล่อยทีหลัง แล้ว migration หนึ่งจะถูกข้ามไปเงียบ
    ๆ เพราะบัญชีเห็นว่า "ลงแล้ว"

    ใช้บัญชีร่วมกันเพื่อให้รายงานก่อนอัปเกรดเห็นทั้งสองชุดในที่เดียว
    """
    from app.database import engine

    results: List[dict] = []
    for path in _files("migrations", "c*.py"):
        mig_id = path.stem
        entry = {"id": mig_id, "ok": True, "error": ""}
        try:
            module = _load_module(path)
            up = getattr(module, "up", None)
            if not callable(up):
                raise AttributeError("ไฟล์นี้ไม่มีฟังก์ชัน up(conn)")

            def _apply(_up=up):
                with engine.begin() as conn:
                    _up(conn)

            run_step(db, mig_id, _apply)
        except Exception as e:                    # noqa: BLE001
            entry["ok"] = False
            entry["error"] = str(e)[:500]
            logger.error("Custom migration %s failed: %s", mig_id, e)
        results.append(entry)

    _report["migrations"] = results
    return results


def load_report() -> Dict[str, Any]:
    """สภาพการโหลดล่าสุด — สำหรับหน้าจอและรายงานก่อนอัปเกรด"""
    failed_r = [r for r in _report["routers"] if not r["ok"]]
    failed_m = [m for m in _report["migrations"] if not m["ok"]]
    return {
        "root": str(CUSTOM_ROOT),
        "prefix": CUSTOM_PREFIX,
        "routers": _report["routers"],
        "migrations": _report["migrations"],
        "files": {
            "routers": len(_files("routers")),
            "services": len(_files("services")),
            "migrations": len(_files("migrations", "c*.py")),
        },
        "healthy": not failed_r and not failed_m,
        "failures": [r["module"] for r in failed_r] + [m["id"] for m in failed_m],
    }


_README = """# เขตของคุณ — การอัปเกรด iVS จะไม่แตะโฟลเดอร์นี้

โค้ดที่คุณหรือ AI ของคุณเขียนเพิ่ม ให้วางที่นี่ ไม่ใช่ในแกน

## ทำไม

การอัปเกรด iVS เขียนทับไฟล์แกน (`app/routers/`, `app/services/`, `app/models.py`)
ถ้าคุณแก้ไฟล์พวกนั้น งานของคุณจะหายตอนอัปเกรดครั้งถัดไป โฟลเดอร์นี้คือที่เดียว
ที่เรารับปากว่าจะไม่แตะ

## วางอะไรตรงไหน

```
custom/routers/<ชื่อ>.py        เส้นทาง API  →  /api/custom/<ชื่อ>/...
custom/services/<ชื่อ>.py       ตรรกะที่ router เรียก
custom/migrations/c0001_*.py   การย้ายสคีมาของคุณ
```

## router ตัวอย่าง

```python
# custom/routers/report.py
from fastapi import APIRouter, Depends
from app.middleware.auth import require_role
from app.models import UserRole

router = APIRouter()

@router.get("/summary")
def summary(user = Depends(require_role(UserRole.ADMIN))):
    return {"ok": True}
```

เรียกได้ที่ `GET /api/custom/report/summary`

**สิทธิ์ไม่ติดมาให้ฟรี** — ถ้าไม่ใส่ `require_role` เส้นทางนั้นเปิดให้ทุกคน
ที่ล็อกอินได้ ต้องประกาศเองเหมือนทุก router ในระบบ

## migration ตัวอย่าง

```python
# custom/migrations/c0001_add_my_table.py
from sqlalchemy import text

def up(conn):
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS my_table (
            id INTEGER PRIMARY KEY,
            note TEXT DEFAULT ''
        )
    '''))
```

เลขขึ้นต้นด้วย `c` เสมอ เพื่อไม่ให้ชนกับเลขของ iVS เอง (`0001`, `0002`, …)
ลงครั้งเดียวแล้วจดไว้ในตาราง `schema_migrations` เหมือนของแกน

**เพิ่มอย่างเดียว อย่าลบหรือแก้ชนิดคอลัมน์ของตารางแกน** — การอัปเกรดคาดหวังว่า
คอลัมน์เดิมยังอยู่

## ถ้าไฟล์ในนี้พัง

เครื่องยังบูตขึ้น ฟีเจอร์นั้นจะไม่ทำงานและถูกรายงานไว้ที่
`GET /api/system/custom-zone` ดูที่นั่นก่อนเมื่อของที่เขียนไว้หายไป
"""
