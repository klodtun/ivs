"""
Contract Profile engine — ชั้นที่อธิบาย "7 เรื่อง" ของ e-Contract

วงจร e-Contract ตามประกาศ สพธอ. (21 มิ.ย. 2567) มี 7 ขั้นตอน และ **ไม่จำเป็นต้องทำครบ
ทุกข้อ** — แต่ละประเภทสัญญาทำไม่เท่ากัน. ความต่างระหว่างหน่วยงานจึงเป็น *ค่าใน 7 ช่องนี้*
ไม่ใช่ตัวระบบ. โมดูลนี้เก็บ 7 ช่องเป็น **data (YAML)** แล้ว resolve เป็นโปรไฟล์ที่ใช้จริง

การ resolve มี 3 ชั้น:
    baseline(contract_type)  →  sector overlay (gov/private)  →  tenant overlay (ระเบียบภายใน)

**Monotonic hardening** — invariant ที่ทั้งโมดูลนี้ยึด:
overlay ยกระดับความเข้มงวดได้ แต่ผ่อนให้ต่ำกว่า baseline **ไม่ได้** ถ้า overlay พยายามผ่อน
ระบบจะปฏิเสธพร้อมบอกเหตุผล ไม่ใช่เงียบ ๆ ยอมตาม — เพราะ baseline มาจากตัวบทกฎหมาย
"""
# ต้องมี: iVS รันบน Python 3.9 ในบางเครื่อง (venv ของ dev) ซึ่งยังประเมิน annotation
# ตอน def — `dict | None` จะ TypeError. PEP 563 ทำให้ annotation เป็น string ทั้งหมด
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "econtract_profiles")

# 7 เรื่อง เรียงตามวงจรจริง — ลำดับนี้ใช้แสดงผลทุกที่ ห้ามสลับ
STEP_KEYS = [
    "e_document",
    "e_signature",
    "e_seal",
    "e_original",
    "e_retention",
    "e_stamp_duty",
    "print_out",
]

STEP_META = {
    "e_document":   {"order": 1, "name_th": "จัดทำเป็นข้อมูลอิเล็กทรอนิกส์", "short_th": "e-Document",
                     "sections": ["8"],
                     "desc_th": "เข้าถึงได้ + นำกลับมาใช้ได้ + ความหมายไม่เปลี่ยนแปลง"},
    "e_signature":  {"order": 2, "name_th": "ลงลายมือชื่อด้วยวิธีอิเล็กทรอนิกส์", "short_th": "e-Signature",
                     "sections": ["9", "26"],
                     "desc_th": "ระบุตัวผู้ลงนามได้ + แสดงเจตนายอมรับ + ตรวจสอบย้อนกลับได้"},
    "e_seal":       {"order": 3, "name_th": "ประทับตรานิติบุคคล", "short_th": "e-Seal",
                     "sections": ["9 วรรคท้าย"],
                     "desc_th": "ความสัมพันธ์ระหว่างนิติบุคคลกับข้อมูล — คนละสิ่งกับลายมือชื่อของบุคคล"},
    "e_original":   {"order": 4, "name_th": "ทำให้เป็นต้นฉบับ", "short_th": "e-Original",
                     "sections": ["10"],
                     "desc_th": "รักษาความถูกต้องครบถ้วนตั้งแต่สร้างเสร็จ + แสดงข้อความภายหลังได้"},
    "e_retention":  {"order": 5, "name_th": "เก็บรักษา", "short_th": "e-Retention",
                     "sections": ["11", "12"],
                     "desc_th": "เก็บไฟล์ + แหล่งกำเนิด ต้นทาง ปลายทาง วันเวลาส่ง/รับ"},
    "e_stamp_duty": {"order": 6, "name_th": "อากรแสตมป์อิเล็กทรอนิกส์", "short_th": "e-Stamp Duty",
                     "sections": ["8 วรรคสอง"],
                     "desc_th": "ยื่นเสียอากรเป็นตัวเงิน (อ.ส.9) ผ่าน e-Filing กรมสรรพากร"},
    "print_out":    {"order": 7, "name_th": "สิ่งพิมพ์ออก / แปลงสื่อ", "short_th": "Print out",
                     "sections": ["10 วรรค 4", "12/1"],
                     "desc_th": "เจ้าของข้อมูล/ผู้ควบคุมพิมพ์เองใช้แทนต้นฉบับได้"},
}

# ระดับสิทธิ์การแก้ไข — ตัวเลขต่ำ = แก้ยาก
LEVEL_RANK = {"LOCKED": 0, "BASELINE": 1, "POLICY": 2, "RUNTIME": 3}

# ระดับความน่าเชื่อถือของลายมือชื่อ — ตัวเลขสูง = เข้มกว่า
ASSURANCE_RANK = {"general": 1, "reliable": 2, "reliable_ca": 3}
ASSURANCE_LABEL = {
    "general":     "แบบทั่วไป (ม.9)",
    "reliable":    "แบบเชื่อถือได้ (ม.26)",
    "reliable_ca": "แบบเชื่อถือได้ + ใบรับรองจาก CA (ม.26)",
}


class ProfileError(ValueError):
    """overlay ขัดกับ baseline หรือโปรไฟล์ไม่ถูกต้อง"""


# ── loading ──────────────────────────────────────────────────────────────

_cache: dict[str, Any] = {}


def _read_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_baseline(force: bool = False) -> dict[str, dict]:
    """โปรไฟล์กลางทั้งหมด จาก econtract_profiles/baseline.yaml"""
    if not force and "baseline" in _cache:
        return _cache["baseline"]
    path = os.path.join(PROFILE_DIR, "baseline.yaml")
    try:
        doc = _read_yaml(path)
        profiles = doc.get("profiles") or {}
    except Exception as e:
        logger.error(f"โหลด baseline.yaml ไม่สำเร็จ: {e}")
        profiles = {}
    for key, prof in profiles.items():
        prof.setdefault("key", key)
        prof.setdefault("blocked", False)
    _cache["baseline"] = profiles
    return profiles


def load_overlay(scope: str, scope_ref: str) -> dict | None:
    """overlay จากไฟล์ (sector) — tenant overlay มาจาก DB ผ่าน resolve(tenant_overlay=...)"""
    if scope != "sector":
        return None
    path = os.path.join(PROFILE_DIR, "overlays", f"sector-{scope_ref}.yaml")
    if not os.path.exists(path):
        return None
    cache_key = f"overlay:{scope}:{scope_ref}"
    if cache_key not in _cache:
        try:
            _cache[cache_key] = _read_yaml(path)
        except Exception as e:
            logger.error(f"โหลด overlay {path} ไม่สำเร็จ: {e}")
            return None
    return _cache[cache_key]


def reload_all() -> None:
    _cache.clear()
    load_baseline(force=True)


# ── merge + hardening guard ──────────────────────────────────────────────

def _merge_list(base: list, patch: Any) -> list:
    """รองรับ `[+item]` = เพิ่มเข้าไปในลิสต์เดิม (ไม่ลบของเดิม)

    ใช้กับ must_store เป็นหลัก — overlay เพิ่มสิ่งที่ต้องเก็บได้ แต่ตัดของเดิมออกไม่ได้
    """
    if not isinstance(patch, list):
        return base
    additive = [str(x)[1:] for x in patch if isinstance(x, str) and x.startswith("+")]
    if additive:
        out = list(base)
        for item in additive:
            if item not in out:
                out.append(item)
        return out
    # แทนที่ทั้งลิสต์ — แต่ต้องไม่ทำให้ของเดิมหาย
    merged = list(base)
    for item in patch:
        if item not in merged:
            merged.append(item)
    return merged


def _harden_step(step_key: str, base: dict, patch: dict, source: str) -> dict:
    """merge patch ลง base โดยบังคับ invariant monotonic hardening

    Raises ProfileError เมื่อ overlay พยายามผ่อนให้ต่ำกว่า baseline
    """
    out = copy.deepcopy(base)
    level = base.get("level", "BASELINE")

    for field, new in patch.items():
        if field == "level":
            continue  # overlay เปลี่ยนระดับสิทธิ์ไม่ได้

        old = base.get(field)

        # LOCKED — ห้ามแตะ field ที่มีผลทางกฎหมาย
        # (deadline_days ไม่อยู่ในนี้ เพราะ "ย่นให้สั้นลง" = เข้มขึ้น ทำได้;
        #  การขยายให้ยาวกว่ากฎหมายถูกกันด้วยกฎ monotonic ด้านล่าง)
        if level == "LOCKED" and field in ("required", "condition", "channel"):
            if old != new:
                raise ProfileError(
                    f"[{source}] แก้ {step_key}.{field} ไม่ได้ — ขั้นตอนนี้ถูกกำหนดโดยกฎหมาย "
                    f"(level=LOCKED, ค่าตามกฎหมาย={old!r})"
                )
            continue

        if level in ("LOCKED", "BASELINE"):
            # required: true → false ไม่ได้
            if field == "required" and old is True and new is not True:
                raise ProfileError(
                    f"[{source}] ปิด {step_key} ไม่ได้ — baseline บังคับให้ต้องทำขั้นตอนนี้"
                )
            # min_assurance ลดระดับไม่ได้
            if field == "min_assurance":
                if ASSURANCE_RANK.get(new, 0) < ASSURANCE_RANK.get(old, 0):
                    raise ProfileError(
                        f"[{source}] ลดระดับ {step_key}.min_assurance จาก {old!r} เป็น {new!r} ไม่ได้"
                    )
            # ตัวเลขที่แปลว่า "ความเข้มงวด" ลดไม่ได้
            if field in ("min_signers", "period_years") and isinstance(old, int) and isinstance(new, int):
                if new < old:
                    raise ProfileError(
                        f"[{source}] ลด {step_key}.{field} จาก {old} เป็น {new} ไม่ได้"
                    )
            # deadline สั้นลงได้ (เข้มขึ้น) แต่ยาวขึ้นไม่ได้
            if field == "deadline_days" and isinstance(old, int) and isinstance(new, int):
                if new > old:
                    raise ProfileError(
                        f"[{source}] ขยาย {step_key}.deadline_days จาก {old} เป็น {new} ไม่ได้"
                    )

        if isinstance(old, list):
            out[field] = _merge_list(old, new)
        else:
            out[field] = new

    return out


def resolve(
    profile_key: str,
    sector: str | None = None,
    tenant_overlay: dict | None = None,
    runtime: dict | None = None,
) -> dict:
    """คืนโปรไฟล์ที่ใช้จริง (effective profile) พร้อม hash สำหรับ freeze

    ผลลัพธ์นี้ต้องถูก **แช่แข็งไว้กับสัญญา** ตอนออกใบรับรอง — สัญญาที่ทำวันนี้ต้องถูกประเมิน
    ด้วยกฎชุดของวันนี้ตลอดไป แม้ baseline จะเปลี่ยนในอนาคต
    """
    baseline = load_baseline()
    base = baseline.get(profile_key)
    if not base:
        raise ProfileError(f"ไม่รู้จักประเภทสัญญา: {profile_key}")

    eff = copy.deepcopy(base)
    eff["key"] = profile_key
    eff["resolved_from"] = {"baseline": f"{profile_key} v{base.get('version', 1)}"}

    if eff.get("blocked"):
        eff["steps"] = {}
        eff["_hash"] = _hash_profile(eff)
        return eff

    steps = eff.setdefault("steps", {})
    for k in STEP_KEYS:
        steps.setdefault(k, {"level": "POLICY", "required": False})
        steps[k].setdefault("level", "BASELINE")
        steps[k].setdefault("required", False)

    layers: list[tuple[str, dict]] = []
    if sector:
        ov = load_overlay("sector", sector)
        if ov:
            layers.append((f"sector:{sector}", ov))
            eff["resolved_from"]["sector"] = ov.get("name_th") or sector
    if tenant_overlay:
        layers.append(("tenant", tenant_overlay))
        eff["resolved_from"]["tenant"] = tenant_overlay.get("name_th") or "ระเบียบภายในหน่วยงาน"
    if runtime:
        layers.append(("runtime", {"steps": runtime}))

    for source, layer in layers:
        applies = layer.get("applies_to", "*")
        if applies != "*" and profile_key not in (applies if isinstance(applies, list) else [applies]):
            continue
        for step_key, patch in (layer.get("steps") or {}).items():
            if step_key not in STEP_KEYS or not isinstance(patch, dict):
                continue
            steps[step_key] = _harden_step(step_key, steps[step_key], patch, source)

    eff["_hash"] = _hash_profile(eff)
    return eff


def _hash_profile(eff: dict) -> str:
    body = {k: v for k, v in eff.items() if not k.startswith("_")}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


# ── helpers สำหรับ UI / router ───────────────────────────────────────────

def list_profiles() -> list[dict]:
    """รายการประเภทสัญญาให้ผู้ใช้เลือก (รวมประเภทที่ทำอิเล็กทรอนิกส์ไม่ได้)"""
    out = []
    for key, p in load_baseline().items():
        steps = p.get("steps") or {}
        out.append({
            "key": key,
            "name_th": p.get("name_th", key),
            "summary_th": p.get("summary_th", ""),
            "legal": p.get("legal", {}),
            "warnings": p.get("warnings", []),
            "group": p.get("group", ""),
            "scenario_ref": p.get("scenario_ref"),
            "risk_tier": p.get("risk_tier", ""),
            "blocked": bool(p.get("blocked")),
            "blocked_reason_th": p.get("blocked_reason_th", ""),
            "version": p.get("version", 1),
            "required_steps": [k for k in STEP_KEYS if (steps.get(k) or {}).get("required")],
        })
    out.sort(key=lambda r: (r["blocked"], r["group"], r.get("scenario_ref") or 99))
    return out


# ── คู่มืออ้างอิง (ETDA) ─────────────────────────────────────────────────
# ไฟล์ใหญ่ ~82 MB จึงไม่เก็บใน repo (และ .gitignore กัน *.pdf อยู่แล้ว) — ใช้ลิงก์
# Google Drive เป็นแหล่งหลัก ทุกเครื่องเข้าถึงได้ทันทีโดยไม่ต้องติดตั้งอะไร
#
# ยังรองรับสำเนาในเครื่องเป็นทางเลือก: หน่วยงานที่ไม่ต่ออินเทอร์เน็ต (air-gapped)
# วางไฟล์ไว้ที่ HANDBOOK_DIR แล้วระบบจะเสิร์ฟให้ดาวน์โหลดตรงจาก iVS ได้ด้วย
HANDBOOK_DIR = os.path.join(PROFILE_DIR, "reference")
HANDBOOK_FILENAME = "09_คุณทรงกลด_ตันทรบันฑิตย์.pdf"
HANDBOOK_DRIVE_ID = "1hpEMvwNx5KNqjx9XKuI2O-lihYPcN_XP"
HANDBOOK_META = {
    "title_th": "(ร่าง) คู่มือการจัดทำสัญญาอิเล็กทรอนิกส์ e-Contract สำหรับภาครัฐกับเอกชน SMEs",
    "author_th": "คุณทรงกลด ตันทรบัณฑิตย์",
    "publisher_th": "สำนักงานพัฒนาธุรกรรมทางอิเล็กทรอนิกส์ (สพธอ. / ETDA)",
    "programme_th": "Train the Transformers: e-Contract",
    "pages": 144,
    "download_name": "ETDA_e-Contract_Handbook.pdf",
    "drive_url": f"https://drive.google.com/file/d/{HANDBOOK_DRIVE_ID}/view?usp=sharing",
}


def handbook_path() -> str:
    return os.path.join(HANDBOOK_DIR, HANDBOOK_FILENAME)


def handbook_info() -> dict:
    """ข้อมูลคู่มือ — ลิงก์ Drive เป็นแหล่งหลัก + สำเนาในเครื่อง (ถ้ามี)"""
    path = handbook_path()
    exists = os.path.isfile(path)
    return {
        **HANDBOOK_META,
        "available": True,                 # เข้าถึงได้เสมอผ่านลิงก์
        "local_available": exists,         # มีสำเนาในเครื่องให้ดาวน์โหลดตรงหรือไม่
        "size_bytes": os.path.getsize(path) if exists else 0,
        "local_path": path,
    }


GROUP_LABELS = {
    "A": "ธุรกิจและพาณิชย์",
    "B": "จ้างงานและบริหารงานบุคคล",
    "C": "จัดซื้อจัดจ้างและบริการ",
    "D": "การเงินและหนี้สิน",
    "E": "เช่าและอสังหาริมทรัพย์",
    "F": "ปกป้องข้อมูลและทางกฎหมาย",
    "X": "ทำเป็นอิเล็กทรอนิกส์ไม่ได้ (ม.3)",
}
