#!/usr/bin/env python3
"""สร้าง release_manifest.json สำหรับรุ่นที่กำลังจะปล่อย

รันตอนเตรียมปล่อยรุ่น ไม่ใช่ตอนรัน ผลคือเครื่องของลูกค้าที่ได้ไฟล์นี้ไปด้วยจะ
เทียบไฟล์ของตัวเองกับสิ่งที่เราปล่อยจริง แทนที่จะเทียบกับสภาพตัวเองตอนบูตแรก

ความต่างนี้สำคัญกว่าที่เห็น: ฐานแบบบูตแรกบอกได้แค่ว่าเปลี่ยนหลังจากที่เราเริ่มดู
ถ้าลูกค้าให้ AI แก้ระบบก่อนเปิดใช้ครั้งแรก การแก้นั้นจะกลายเป็นค่าตั้งต้นและ
รายงานก่อนอัปเกรดจะบอกว่า "ไม่มีไฟล์ถูกแก้" ทั้งที่มี

    python3 scripts/make-release-manifest.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ย้ายตัวเองไปรันใน venv ของ backend ถ้ายังไม่ได้อยู่ในนั้น
#
# python3 ของเครื่องไม่มี sqlalchemy ซึ่ง baseline_service ต้องใช้ คนที่ปล่อย
# รุ่นจะพิมพ์ `python3 scripts/...` เป็นอย่างแรกเสมอ แล้วเจอ ModuleNotFoundError
# ที่ไม่เกี่ยวกับสิ่งที่เขากำลังทำ การให้สคริปต์หา venv เองจึงถูกกว่าการเขียน
# ไว้ในคู่มือให้คนจำ
_VENV = ROOT / "backend" / "venv" / "bin" / "python"
if _VENV.is_file() and not os.environ.get("IVS_MANIFEST_REEXEC"):
    os.environ["IVS_MANIFEST_REEXEC"] = "1"
    os.execv(str(_VENV), [str(_VENV), str(Path(__file__).resolve()), *sys.argv[1:]])

sys.path.insert(0, str(ROOT / "backend"))

from app.services import baseline_service  # noqa: E402

dest = baseline_service.write_release_manifest()
files = baseline_service.scan()
by_zone = {}
for info in files.values():
    by_zone[info["zone"]] = by_zone.get(info["zone"], 0) + 1

print(f"เขียน {dest}")
print(f"  ไฟล์ทั้งหมด {len(files)}")
for zone in ("core", "gray", "extend"):
    print(f"  {zone:7s} {by_zone.get(zone, 0)}")
print()
print("ไฟล์นี้ต้องไปกับรุ่นที่ปล่อย ไม่ใช่ .gitignore")
