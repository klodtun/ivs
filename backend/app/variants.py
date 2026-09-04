"""รุ่นย่อยของ iVS — ชุดเมนูที่แจกไปด้วยกัน คนละแกนกับระดับใบอนุญาต

iVS มีสองแกนที่มักถูกเข้าใจว่าเป็นแกนเดียว

    ระดับ (tier)      FREE · LITE · STD · PRO · ENT
                      ตอบว่า "กี่เครื่อง เร็วแค่ไหน ใครรับผิดชอบ"
                      บังคับใน license_service

    รุ่นย่อย (variant) free · hospital · econtract · ...
                      ตอบว่า "กล่องนี้แจกมาเพื่อทำเรื่องอะไร"
                      บังคับที่นี่

**ผลิตภัณฑ์ต่างกันที่ค่าตั้งค่า ไม่ใช่ที่สาขาโค้ด**

นี่คือข้อที่กันความผิดพลาดได้มากที่สุดในไฟล์นี้ ทางเลือกอีกทางคือแยกสาขาแล้วตัด
เมนูออกด้วยมือในแต่ละสาขา ซึ่งอ่านดูง่ายกว่าตอนเริ่ม แต่ผลคือห้าสายโค้ดที่ต้อง
ซิงก์กันเอง บั๊กหนึ่งตัวต้องแก้ห้าที่ และเครื่องของลูกค้าจะบอกไม่ได้ว่าตัวเอง
สืบเชื้อสายมาจากอะไร ซึ่งทำให้ file_baselines กับ schema_migrations ที่สร้างไว้
วัดอะไรไม่ได้เลย เพราะทั้งคู่วัดจาก "รุ่นที่ปล่อย" ซึ่งต้องมีสายเดียว

รายการข้างล่างนี้จึงเป็นแหล่งความจริงแหล่งเดียวว่าแต่ละผลิตภัณฑ์มีเมนูอะไร
แถบเมนูฝั่งหน้าจออ่านจากที่นี่ ไม่ได้ตัดสินเอง

ดู docs/iVS_Repo_And_Variant_Strategy.md
"""

from typing import Dict, List, Set

# ── เมนูที่ทุกรุ่นมีเสมอ ────────────────────────────────────────────────────
#
# ไม่มีรุ่นย่อยไหนปิดได้ เพราะเป็นสิ่งที่ทำให้กล่องหนึ่งเป็น iVS ไม่ใช่ของแถม
# ทะเบียน ROPA บันทึกตรวจสอบ นโยบายเก็บรักษา และคลังกุญแจ อยู่ในทุกกล่องเสมอ
# รวมทั้งรุ่นฟรีล้วน — นั่นคือคำสัญญาที่ประกาศไว้ในหน้าเปรียบเทียบรุ่น
CORE_MENUS = (
    "/dashboard",             # แดชบอร์ด
    "/dashboard/apps",        # แอปพลิเคชัน
    "/dashboard/tunnels",     # อุโมงค์เชื่อมต่อ
    "/dashboard/vault",       # คลัง API Key
    "/dashboard/resources",   # ทรัพยากร
    "/dashboard/settings",    # ตั้งค่า
    "/dashboard/consulting",  # ปรึกษา
)

# ── โมดูลที่เปิดปิดได้ต่อรุ่นย่อย ──────────────────────────────────────────
MODULES: Dict[str, dict] = {
    "system_map": {
        "menu": "/dashboard/system-map",
        "th": "แผนที่ระบบ",
        "what": "แอป เส้นเชื่อม และการส่งออกที่เปิดได้โดยไม่ต้องมี iVS",
    },
    "flows": {
        "menu": "/dashboard/flows",
        "th": "เส้นทางการทำงาน",
        "what": "ขั้นที่ประกาศไว้ ตรวจว่ายังจริงอยู่",
    },
    "iso13485": {
        "menu": "/dashboard/design-controls",
        "th": "บันทึกมาตรฐาน ISO 13485",
        "what": "ความต้องการ ความเสี่ยง การทดสอบ การเปลี่ยนแปลง",
    },
    "econtract": {
        "menu": "/dashboard/econtract",
        "th": "e-Contract",
        "what": "สัญญาอิเล็กทรอนิกส์ตามโปรไฟล์ ETDA",
    },
    "opencli": {
        "menu": "/dashboard/bridge",
        "th": "OpenCLI Bridge",
        "what": "ช่องทางภาษาธรรมชาติสู่ทุกแอปบนกล่องนี้",
    },
    "api_catalog": {
        "menu": "/dashboard/api-catalog",
        "th": "คลัง API สาธารณะ",
        "what": "คลัง API ของแอปที่ดีพลอย",
    },
    # ยังไม่ได้เขียน — ประกาศชื่อไว้ก่อนเพื่อให้คีย์คงที่ตั้งแต่ต้น
    "interop":  {"menu": "", "th": "DICOM · HL7 v2 · FHIR", "what": "(ยังไม่ได้พัฒนา)"},
    "pdpa_org": {"menu": "", "th": "PDPA ระดับองค์กร", "what": "(ยังไม่ได้พัฒนา)"},
    "log_org":  {"menu": "", "th": "บันทึกระดับองค์กร", "what": "(ยังไม่ได้พัฒนา)"},
}

# โมดูลที่ต้องมีใบอนุญาตระดับ Pro ขึ้นไป ต่อให้รุ่นย่อยประกาศไว้ก็ตาม
#
# รุ่นย่อยบอกว่า "กล่องนี้มีโมดูลอะไรติดมา" ระดับบอกว่า "โมดูลนั้นทำงานได้ไหม"
# บนเครื่องนักพัฒนา โมดูลพวกนี้เปิดให้เห็นเพื่อสาธิตได้ แต่ต้องเห็นชัดว่าเป็นการ
# สาธิต ไม่ใช่ของที่แจกไปกับรุ่นฟรี
TIER_GATED: Dict[str, Set[str]] = {
    "opencli": {"PRO", "ENT"},
    "interop": {"PRO", "ENT"},
}

# ── ผลิตภัณฑ์ ──────────────────────────────────────────────────────────────
VARIANTS: Dict[str, dict] = {
    # รีโปสาธารณะ klodtun/ivs — ให้ทุกคนดาวน์โหลดไปทดสอบ
    "free": {
        "label_th": "iVS",
        "label_en": "iVS",
        "public": True,
        "modules": [],
    },
    # ยังไม่เปิดเผย — ทีมพัฒนาภายในตรวจและพัฒนาเท่านั้น
    "hospital": {
        "label_th": "iVS โรงพยาบาล",
        "label_en": "iVS for Hospitals",
        "public": False,
        "modules": ["system_map", "flows", "iso13485", "econtract"],
    },
    "econtract": {
        "label_th": "iVS e-Contract",
        "label_en": "iVS e-Contract",
        "public": False,
        "modules": ["econtract"],
        # เมนู "ทรัพยากร" ของรุ่นนี้ใช้ชื่อเฉพาะ เพราะกล่องนี้ทำเรื่องเดียว
        "menu_labels": {"/dashboard/resources": {"th": "ทรัพยากร e-Contract",
                                                 "en": "e-Contract resources"}},
    },
    "pro": {
        "label_th": "iVS Pro",
        "label_en": "iVS Pro",
        "public": False,
        # Pro = รุ่นปัจจุบันทั้งหมด + OpenCLI + แผนที่วางไว้
        "modules": ["system_map", "flows", "iso13485", "econtract",
                    "opencli", "api_catalog"],
    },
    # ทุกโมดูลเปิดหมด สำหรับเครื่องพัฒนาและการสาธิต ไม่ใช่รุ่นที่แจก
    "all": {
        "label_th": "iVS (รวมทุกโมดูล — สำหรับพัฒนาและสาธิต)",
        "label_en": "iVS (all modules — development and demo)",
        "public": False,
        "modules": [k for k, v in MODULES.items() if v["menu"]],
    },
}

# ชื่อเดิมที่เคยใช้ก่อนกำหนดผลิตภัณฑ์จริง — รับไว้ไม่ให้เครื่องที่ตั้งค่าไว้แล้วพัง
ALIASES = {"base": "free", "logging": "free"}


def resolve(variant: str) -> str:
    v = (variant or "free").strip().lower()
    v = ALIASES.get(v, v)
    return v if v in VARIANTS else "free"


def variant_info(variant: str) -> dict:
    return VARIANTS[resolve(variant)]


def modules_of(variant: str) -> List[str]:
    return list(variant_info(variant)["modules"])


def has_module(variant: str, module: str) -> bool:
    return module in variant_info(variant)["modules"]


def module_state(variant: str, module: str, edition: str) -> str:
    """สถานะของโมดูลหนึ่งบนกล่องหนึ่ง

        active     รุ่นย่อยมี และใบอนุญาตพอ
        demo       รุ่นย่อยมี แต่ใบอนุญาตไม่ถึง — เห็นได้ สาธิตได้ ไม่ใช่ของแจก
        absent     รุ่นย่อยนี้ไม่มีโมดูลนี้ — ไม่มีเมนู

    แยก demo ออกจาก active เพราะการแสดงของที่ยังไม่ได้ขายให้ดูเหมือนของที่แจก
    แล้ว เป็นคำสัญญาที่เราจะผิดเองในภายหลัง
    """
    if not has_module(variant, module):
        return "absent"
    gate = TIER_GATED.get(module)
    if gate and edition.upper() not in gate:
        return "demo"
    return "active"


def visible_menus(variant: str, edition: str) -> List[str]:
    """เมนูทั้งหมดที่กล่องนี้ควรแสดง — แกนบวกโมดูลที่มี

    แถบเมนูฝั่งหน้าจออ่านรายการนี้ ไม่ได้ตัดสินเอง ถ้าปล่อยให้หน้าจอตัดสิน
    หน้าจอกับหลังบ้านจะไม่ตรงกันวันหนึ่ง แล้วจะมีเมนูที่กดแล้ว 403
    """
    out = list(CORE_MENUS)
    for m in modules_of(variant):
        menu = MODULES.get(m, {}).get("menu")
        if menu and module_state(variant, m, edition) != "absent":
            out.append(menu)
    return out


def summary(variant: str, edition: str) -> dict:
    key = resolve(variant)
    info = VARIANTS[key]
    mods = modules_of(key)
    return {
        "variant": key,
        "label_th": info["label_th"],
        "label_en": info["label_en"],
        "public": info.get("public", False),
        "edition": edition,
        "core_menus": list(CORE_MENUS),
        "visible_menus": visible_menus(key, edition),
        "menu_labels": info.get("menu_labels", {}),
        "modules": {
            m: {
                "state": module_state(key, m, edition),
                "menu": MODULES.get(m, {}).get("menu", ""),
                "th": MODULES.get(m, {}).get("th", m),
                "what": MODULES.get(m, {}).get("what", ""),
            }
            for m in mods
        },
        "demo_only": [m for m in mods if module_state(key, m, edition) == "demo"],
    }
