# เขตของคุณ — การอัปเกรด iVS จะไม่แตะโฟลเดอร์นี้

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
