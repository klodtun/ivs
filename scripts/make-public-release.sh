#!/usr/bin/env bash
# สร้างทรีของรุ่นสาธารณะ (iVS ฟรี) จากสายพัฒนาภายใน
#
# ทำไมต้องมีสคริปต์ แทนที่จะแยกสาขาแล้วตัดโค้ดด้วยมือ
#
#   ผลิตภัณฑ์ต่างกันที่ค่าตั้งค่า (IVS_VARIANT) ไม่ใช่ที่โค้ด — นั่นคือสิ่งที่ทำ
#   ให้บั๊กหนึ่งตัวแก้ที่เดียว และทำให้ file_baselines เทียบกับ "รุ่นที่ปล่อย"
#   ได้ เพราะมีสายเดียว
#
#   แต่โมดูลบางตัวยังไม่เปิดเผย รีโปสาธารณะจึงเป็น "ผลผลิต" ของสายพัฒนา ไม่ใช่
#   สายพัฒนาที่สอง สร้างใหม่ได้เสมอจาก commit ภายในที่ระบุไว้ และไม่มีใครแก้โค้ด
#   บนรีโปสาธารณะโดยตรง
#
# ใช้: bash scripts/make-public-release.sh <โฟลเดอร์ปลายทาง>

set -euo pipefail
DEST="${1:?ต้องระบุโฟลเดอร์ปลายทาง}"

# โมดูลที่ยังไม่เปิดเผย — ดู backend/app/variants.py ว่ารุ่นไหนมีอะไร
STRIP=(
  # OpenCLI — เป็นของ iVS Pro
  "backend/app/routers/opencli.py"
  "backend/app/services/opencli"
  "backend/app/services/endpoint_exposure_service.py"
  "frontend/src/app/dashboard/bridge"
  "frontend/src/components/opencli-ask.tsx"
  "frontend/src/components/opencli-policy.tsx"
  # e-Contract — รอสรุปโครงการกับหน่วยงานอื่น
  "backend/app/routers/econtract.py"
  "backend/app/services/econtract_service.py"
  "backend/app/services/profile_service.py"
  "backend/app/services/chain_service.py"
  "backend/app/services/compliance_service.py"
  "backend/app/services/pdfa_service.py"
  "backend/app/econtract_profiles"
  "backend/app/econtract_assets"
  "frontend/src/app/dashboard/econtract"
  "frontend/src/components/econtract-guide.tsx"
  # แผนที่ระบบ · เส้นทางการทำงาน · ISO 13485 — เป็นของ iVS โรงพยาบาล
  "frontend/src/app/dashboard/system-map"
  "frontend/src/app/dashboard/flows"
  "frontend/src/app/dashboard/design-controls"
  "frontend/src/components/flow-diagram.tsx"
  "frontend/src/components/system-map-delta.tsx"
  "frontend/src/components/pii-flow-panel.tsx"
  # เอกสารภายใน — ตัดเป็นรายไฟล์ ไม่ตัดทั้ง docs/
  #
  # docs/ มีทั้งคู่มือติดตั้งที่เคยอยู่สาธารณะและควรอยู่ต่อ กับแผนงานภายในที่ไม่
  # ควรเปิด การตัดทั้งโฟลเดอร์เอาคู่มือของผู้ใช้ออกไปด้วย ซึ่งเป็นสิ่งเดียวที่
  # รีโปสาธารณะมีไว้ให้ — เคยพลาดมาแล้วครั้งหนึ่ง
  "docs/AIEAT_ISO13485_STRATEGY.md"
  "docs/EXCHANGE_LAYER.md"
  "docs/iVS_Dashboard_Plan.md"
  "docs/iVS_Edition_Migration_Design.md"
  "docs/iVS_OpenCLI_Plan.md"
  "docs/iVS_Pro_Clinical_Interop_Plan.md"
  "docs/iVS_Repo_And_Variant_Strategy.md"
  "docs/opencli-bridge-architecture.md"
  "design"
  "CLAUDE.md"
  "INTEGRATION-CONTRACT.md"
)

rm -rf "$DEST"
git archive HEAD | (mkdir -p "$DEST" && tar -x -C "$DEST")
for p in "${STRIP[@]}"; do rm -rf "${DEST:?}/$p"; done

# ── ตัดการอ้างอิงที่เหลือในไฟล์แกน ────────────────────────────────────────
#
# ลบไฟล์อย่างเดียวไม่พอ แกนยัง import โมดูลที่หายไป แล้วเซิร์ฟเวอร์จะเปิดไม่ขึ้น
# รีโปสาธารณะที่รันไม่ได้แย่กว่าไม่มีรีโปสาธารณะ ขั้นนี้จึงจบด้วยการตรวจว่ารันได้จริง

# main.py — เอาชื่อโมดูลออกจากบรรทัด import และบรรทัดที่ลงทะเบียน router
python3 - "$DEST" <<'PYEOF'
import re, sys, pathlib
dest = pathlib.Path(sys.argv[1])
GONE = ("opencli", "econtract")

p = dest / "backend/app/main.py"
t = p.read_text()
t = re.sub(r'^(from app\.routers import .*)$',
           lambda m: re.sub(r',\s*(?:%s)\b' % "|".join(GONE), "", m.group(1)), t, flags=re.M)
t = "\n".join(l for l in t.splitlines()
               if not re.search(r'app\.include_router\((?:%s)\.router\)' % "|".join(GONE), l)) + "\n"
p.write_text(t)

# api.ts — ตัดทั้งสมาชิก พร้อมคอมเมนต์ที่นำหน้ามัน
#
# ขอบเขตของสมาชิกคือ "ตั้งแต่บรรทัดที่ประกาศชื่อ ถึงก่อนชื่อถัดไป" ไม่ใช่การนับ
# วงเล็บ เพราะวงเล็บพารามิเตอร์ปิดจบในบรรทัดแรกได้ แล้วตัวนับจะตัดกลางนิยาม
#
# และต้องจำกัดให้อยู่ในอ็อบเจกต์ api เท่านั้น เพราะรูปแบบ "ชื่อ:" ตรงกับฟิลด์ของ
# interface ที่อยู่ท้ายไฟล์ด้วย ถ้าไม่จำกัด ตัวตัดจะไปกินนิยามชนิดข้อมูล
p = dest / "frontend/src/lib/api.ts"
lines = p.read_text().splitlines(keepends=True)

obj_start = next(n for n, l in enumerate(lines) if l.startswith("export const api = {"))
obj_end = next(n for n in range(obj_start + 1, len(lines)) if lines[n].startswith("};"))

START = re.compile(r'^  [A-Za-z_][A-Za-z0-9_]*: ')
starts = [n for n in range(obj_start + 1, obj_end) if START.match(lines[n])]
drop = set()
for idx, s in enumerate(starts):
    e = starts[idx + 1] if idx + 1 < len(starts) else obj_end
    block = "".join(lines[s:e])
    if not re.search(r'/(?:opencli|econtract)[/?"`]|api\.(?:postEContract|opencli)|EContract|OpenCli', block):
        continue
    b = s
    while b > obj_start + 1 and (lines[b - 1].strip().startswith("//") or not lines[b - 1].strip()):
        b -= 1
    drop.update(range(b, e))

# ชนิดข้อมูลของโมดูลที่ตัดออก — ไม่มีใครใช้แล้ว และเปิดเผยรูปร่าง API โดยไม่จำเป็น
TYPE = re.compile(r'^export (?:interface|type) \w*(?:OpenCli|EContract|Bridge)\w*\b')
n = obj_end + 1
while n < len(lines):
    if TYPE.match(lines[n]):
        e = n + 1
        while e < len(lines) and not lines[e].startswith("export ") :
            e += 1
        drop.update(range(n, e))
        n = e
    else:
        n += 1

p.write_text("".join(l for k, l in enumerate(lines) if k not in drop))

# models.py — เอานิยามตารางของโมดูลที่ไม่เปิดเผยออก
#
# ลบไฟล์ router ไปแล้วยังไม่พอ ตารางยังบอกรูปร่างข้อมูลของโมดูลนั้นครบทุกคอลัมน์
# ซึ่งเป็นสิ่งที่ตั้งใจไม่เปิดเผยตั้งแต่ต้น
p = dest / "backend/app/models.py"
lines = p.read_text().splitlines(keepends=True)
CLS = re.compile(r'^class (?:EContract|OpenCli)\w*\b')
ANY = re.compile(r'^(?:class |# ---)')
drop, n = set(), 0
while n < len(lines):
    if CLS.match(lines[n]):
        e = n + 1
        while e < len(lines) and not ANY.match(lines[e]):
            e += 1
        b = n
        while b > 0 and (lines[b - 1].startswith("#") or not lines[b - 1].strip()):
            b -= 1
        drop.update(range(b, e))
        n = e
    else:
        n += 1
p.write_text("".join(l for k, l in enumerate(lines) if k not in drop))

# main.py — แถว migration ของตารางที่ไม่มีแล้ว
p = dest / "backend/app/main.py"
p.write_text("".join(l for l in p.read_text().splitlines(keepends=True)
                     if not re.search(r'\("(?:econtract|opencli)_', l)))

# overview_service.py — การ์ด AI อ่านจากตารางของ OpenCLI
p = dest / "backend/app/services/overview_service.py"
src = p.read_text()
src = src.replace("from app.models import OpenCliLlmModel  # type: ignore",
                  "raise ImportError  # โมดูลนี้ไม่มีในรุ่นนี้")
p.write_text(src)

# sidebar.tsx — เมนูของโมดูลที่ไม่มี
p = dest / "frontend/src/components/sidebar.tsx"
lines = p.read_text().splitlines(keepends=True)
drop, n = set(), 0
while n < len(lines):
    if lines[n].strip() == "{" and n + 1 < len(lines):
        e = n
        while e < len(lines) and lines[e].strip() not in ("},", "];"):
            e += 1
        blk = "".join(lines[n:e + 1])
        if re.search(r'/dashboard/(?:econtract|bridge|system-map|flows|design-controls)', blk):
            drop.update(range(n, e + 1))
            n = e + 1
            continue
    n += 1
p.write_text("".join(l for k, l in enumerate(lines) if k not in drop))
PYEOF

echo "สร้างทรีสาธารณะที่ $DEST"
echo "  ตัดออก ${#STRIP[@]} รายการ · เหลือ $(find "$DEST" -type f | wc -l | tr -d ' ') ไฟล์"
