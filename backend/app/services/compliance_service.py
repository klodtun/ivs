"""
Compliance evaluator — "เอกสารนี้ทำอะไรไปแล้วบ้าง ใน 7 เรื่อง"

รวม 3 แหล่งเข้าด้วยกันแล้วออกมาเป็นรายงาน 7 แถว:
  1. โปรไฟล์ที่แช่แข็งไว้กับใบรับรอง  → บอกว่า "ต้องทำอะไรบ้าง"
  2. ข้อเท็จจริงที่ระบบรู้เอง          → ไฟล์/hash/เวลา NTP/ลายเซ็นที่บันทึกไว้
  3. EContractStep ที่บันทึกเข้ามา     → ขั้นตอนที่เกิดนอกระบบ (ตรา/อากร/พิมพ์ออก)

หมายเหตุเรื่องความซื่อสัตย์ต่อผู้ชั่งน้ำหนักพยานหลักฐาน (ม.11): รายงานนี้บอกได้แค่ว่า
"ทำครบตามที่โปรไฟล์กำหนดหรือยัง" — ไม่ใช่คำวินิจฉัยว่าสัญญาสมบูรณ์ตามกฎหมาย
"""
# ต้องมี: รองรับ Python 3.9 (venv ของ dev บางเครื่อง) ที่ยังประเมิน annotation ตอน def
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import EContractCert, EContractSignature, EContractStep, AuditLog
from app.services.profile_service import (
    STEP_KEYS, STEP_META, ASSURANCE_RANK, ASSURANCE_LABEL, resolve,
)

logger = logging.getLogger(__name__)

# ขั้นตอนที่ผู้ใช้บันทึกเองได้ (ระบบไม่รู้เอง เพราะเกิดนอกระบบ)
MANUAL_STEPS = {"e_seal", "e_stamp_duty", "print_out", "e_retention"}

# ช่องทางชำระอากรแสตมป์ — ระบบ อ.ส.9 ของกรมสรรพากรเป็นช่องทางอย่างเป็นทางการ
# สำหรับยื่นขอเสียอากรเป็นตัวเงินสำหรับตราสารอิเล็กทรอนิกส์ (ม.8 วรรคสอง)
STAMP_DUTY_CHANNELS = {
    "rd_efiling_as9": {
        "label_th": "ระบบ อ.ส.9 (e-Filing) กรมสรรพากร",
        "url": "https://efiling.rd.go.th/ef-cms-web/",
        "manual_url": (
            "https://www.dropbox.com/scl/fi/t4zvjiqs7pd9or991q7gb/"
            "User-Manual-WEBSITE-e-Stamp-Duty.pdf"
            "?rlkey=3qt4tl2dnsb88gbjgujfkgtfl&e=1&st=052fyyr4&dl=0"
        ),
        "note_th": "ชำระแล้วจะได้รหัสรับรองการเสียอากรแสตมป์ — นำกลับมาบันทึกในระบบ",
    },
}

# วิธีลงนามที่ระบบรองรับ → ระดับความน่าเชื่อถือที่ได้จริง
METHOD_ASSURANCE = {
    "typed": "general",
    "drawn": "general",
    "otp": "general",
    "clickwrap": "general",
    "pades": "reliable",       # Phase 2
    "pades_ca": "reliable_ca",  # Phase 2
}

# สถานะที่เป็นไปได้ของแต่ละแถว
#   done         ทำแล้ว ครบตามที่กำหนด
#   partial      เริ่มแล้วแต่ยังไม่ครบ
#   pending      ต้องทำ แต่ยังไม่ได้ทำ
#   overdue      ต้องทำ เลยกำหนดเวลาแล้ว
#   not_required โปรไฟล์ระบุว่าไม่ต้องทำ
#   optional     ทำก็ได้ ไม่ทำก็ได้
#   blocked      ทำเป็นอิเล็กทรอนิกส์ไม่ได้ (ม.3)


def _fmt(dt) -> str | None:
    return dt.isoformat() if dt else None


def detect_doc_format(data: bytes, filename: str = "") -> str:
    """เดารูปแบบไฟล์จาก magic bytes — ใช้ตรวจ e-Document ว่าเป็น PDF/A หรือไม่

    PDF/A ประกาศตัวเองผ่าน XMP metadata (`pdfaid:part`) ซึ่งเป็น plain text ในไฟล์
    จึงตรวจแบบหยาบได้โดยไม่ต้อง parse ทั้ง PDF
    """
    head = data[:8]
    if head.startswith(b"%PDF-"):
        # หา pdfaid:part / pdfaid:conformance ใน XMP (อาจอยู่ท้ายไฟล์)
        window = data if len(data) < 4_000_000 else data[:2_000_000] + data[-2_000_000:]
        if b"pdfaid" in window:
            part = conf = ""
            for token in (b"part=", b"pdfaid:part>", b'part="'):
                i = window.find(token)
                if i >= 0:
                    tail = window[i + len(token): i + len(token) + 6]
                    digits = b"".join(c.to_bytes(1, "big") for c in tail if 48 <= c <= 57)
                    if digits:
                        part = digits.decode()
                        break
            for token in (b"conformance>", b'conformance="'):
                i = window.find(token)
                if i >= 0:
                    c = window[i + len(token): i + len(token) + 1]
                    if c.isalpha():
                        conf = c.decode().lower()
                        break
            return f"PDF/A-{part}{conf}" if part else "PDF/A"
        return "PDF"
    if head.startswith(b"PK\x03\x04"):
        low = (filename or "").lower()
        if low.endswith(".docx"):
            return "DOCX"
        if low.endswith(".xlsx"):
            return "XLSX"
        return "ZIP"
    if head.startswith(b"{") or head.startswith(b"["):
        return "JSON"
    ext = (filename.rsplit(".", 1)[-1].upper() if "." in (filename or "") else "")
    return ext or "other"


def _format_ok(required: str, actual: str) -> bool:
    if not required or required == "any":
        return True
    req = required.upper().replace(" ", "")
    act = (actual or "").upper().replace(" ", "")
    if req.startswith("PDF/A"):
        return act.startswith("PDF/A")
    if req == "PDF":
        return act.startswith("PDF")
    return act == req


def effective_profile(cert: EContractCert) -> dict:
    """โปรไฟล์ที่แช่แข็งไว้กับใบรับรอง — ถ้ายังไม่มี (ใบรับรองเก่า) ให้ resolve สด"""
    if cert.effective_profile_json:
        try:
            return json.loads(cert.effective_profile_json)
        except Exception:
            logger.warning(f"effective_profile_json ของ {cert.cert_id} อ่านไม่ได้ — resolve ใหม่")
    try:
        return resolve(cert.profile_key or "generic", sector=cert.profile_sector or None)
    except Exception:
        return resolve("generic")


def evaluate(db: Session, cert: EContractCert) -> dict:
    """รายงาน 7 แถว: ขั้นตอนไหนทำแล้ว ขั้นตอนไหนค้าง และอ้างมาตราอะไร"""
    prof = effective_profile(cert)
    steps_cfg = prof.get("steps") or {}

    sigs = (
        db.query(EContractSignature)
        .filter(EContractSignature.cert_id == cert.cert_id)
        .order_by(EContractSignature.signed_at.asc())
        .all()
    )
    recorded = {
        s.step_key: s
        for s in db.query(EContractStep)
        .filter(EContractStep.cert_id == cert.cert_id)
        .order_by(EContractStep.recorded_at.asc())
        .all()
    }
    audit_count = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == "econtract", AuditLog.resource_id == cert.cert_id)
        .count()
    )

    rows = []
    for key in STEP_KEYS:
        cfg = steps_cfg.get(key) or {}
        meta = STEP_META[key]
        row = {
            "step": key,
            "order": meta["order"],
            "name_th": meta["name_th"],
            "short_th": meta["short_th"],
            "desc_th": meta["desc_th"],
            "sections": meta["sections"],
            "level": cfg.get("level", "POLICY"),
            "required": bool(cfg.get("required")),
            "status": "not_required",
            "summary_th": "",
            "detail": {},
            "next_action_th": "",
            "note_th": cfg.get("note_th") or cfg.get("hint_th") or "",
        }
        if prof.get("blocked"):
            row["status"] = "blocked"
            row["summary_th"] = prof.get("blocked_reason_th", "ทำเป็นอิเล็กทรอนิกส์ไม่ได้")
            rows.append(row)
            continue

        handler = _HANDLERS[key]
        handler(row, cfg, cert, sigs, recorded, audit_count)
        rows.append(row)

    required_rows = [r for r in rows if r["required"]]
    done_rows = [r for r in required_rows if r["status"] == "done"]
    open_rows = [r for r in rows if r["status"] in ("pending", "partial", "overdue")]

    return {
        "cert_id": cert.cert_id,
        "profile": {
            "key": prof.get("key"),
            "name_th": prof.get("name_th"),
            "version": prof.get("version", 1),
            "group": prof.get("group", ""),
            "scenario_ref": prof.get("scenario_ref"),
            "risk_tier": prof.get("risk_tier", ""),
            "blocked": bool(prof.get("blocked")),
            "hash": cert.effective_profile_hash or prof.get("_hash", ""),
            "resolved_from": prof.get("resolved_from", {}),
            "legal": prof.get("legal", {}),
            "warnings": prof.get("warnings", []),
        },
        "steps": rows,
        "summary": {
            "required_total": len(required_rows),
            "required_done": len(done_rows),
            "open_count": len(open_rows),
            "complete": len(open_rows) == 0 and len(done_rows) == len(required_rows),
        },
    }


# ── handler ต่อขั้นตอน ───────────────────────────────────────────────────

def _h_document(row, cfg, cert, sigs, recorded, audit_count):
    want = cfg.get("format", "any")
    actual = cert.doc_format or ""
    row["detail"] = {
        "filename": cert.filename,
        "sha256": cert.sha256,
        "size_bytes": cert.size_bytes,
        "format": actual or "ไม่ทราบ",
        "format_required": want,
        "required_sections": cfg.get("required_sections", []),
    }
    if not row["required"]:
        row["status"] = "optional"
        return
    if not cert.sha256:
        row["status"] = "pending"
        row["next_action_th"] = "อัปโหลดเอกสารเพื่อออกใบรับรอง"
        return
    if want and want != "any" and actual and not _format_ok(want, actual):
        row["status"] = "partial"
        row["summary_th"] = f"เป็น {actual} แต่โปรไฟล์กำหนด {want}"
        row["next_action_th"] = f"แปลงเอกสารเป็น {want} เพื่อการจัดเก็บระยะยาว"
        return
    row["status"] = "done"
    row["summary_th"] = f"{actual or 'ไฟล์'} · SHA-256 {cert.sha256[:16]}…"


def _h_signature(row, cfg, cert, sigs, recorded, audit_count):
    need_n = int(cfg.get("min_signers", 1) or 1)
    need_a = cfg.get("min_assurance", "general")
    got_a = [METHOD_ASSURANCE.get(s.method, "general") for s in sigs]
    weakest = min([ASSURANCE_RANK.get(a, 1) for a in got_a], default=0)

    row["detail"] = {
        "signers": [
            {"name": s.signer_name, "method": s.method, "signed_at": _fmt(s.signed_at),
             "ip": s.ip_address,
             "assurance": METHOD_ASSURANCE.get(s.method, "general")}
            for s in sigs
        ],
        "count": len(sigs),
        "min_signers": need_n,
        "min_assurance": need_a,
        "min_assurance_label": ASSURANCE_LABEL.get(need_a, need_a),
        "identity_binding": cfg.get("identity_binding", []),
    }
    if not row["required"]:
        row["status"] = "optional" if not sigs else "done"
        row["summary_th"] = f"ลงนามแล้ว {len(sigs)} ราย" if sigs else "ไม่บังคับ"
        return
    if not sigs:
        row["status"] = "pending"
        row["next_action_th"] = f"ต้องมีผู้ลงนามอย่างน้อย {need_n} ราย ({ASSURANCE_LABEL.get(need_a, need_a)})"
        return
    if len(sigs) < need_n:
        row["status"] = "partial"
        row["summary_th"] = f"ลงนามแล้ว {len(sigs)} จาก {need_n} ราย"
        row["next_action_th"] = f"รออีก {need_n - len(sigs)} ราย"
        return
    if weakest < ASSURANCE_RANK.get(need_a, 1):
        row["status"] = "partial"
        row["summary_th"] = (
            f"ลงนามครบ {len(sigs)} ราย แต่ยังเป็นลายมือชื่อ{ASSURANCE_LABEL.get('general')} "
            f"ขณะที่โปรไฟล์กำหนด{ASSURANCE_LABEL.get(need_a, need_a)}"
        )
        row["next_action_th"] = "ยกระดับเป็น Digital Signature ที่มีใบรับรอง (อยู่ในแผนพัฒนา Phase 2)"
        return
    row["status"] = "done"
    row["summary_th"] = f"ลงนามครบ {len(sigs)} ราย · {ASSURANCE_LABEL.get(need_a, need_a)}"


def _h_seal(row, cfg, cert, sigs, recorded, audit_count):
    rec = recorded.get("e_seal")
    row["detail"] = {
        "applies_to": cfg.get("applies_to", []),
        "recorded": bool(rec),
        "actor": rec.actor if rec else "",
        "ref": rec.ref if rec else "",
        "recorded_at": _fmt(rec.recorded_at) if rec else None,
    }
    if rec:
        row["status"] = "waived" if rec.status == "waived" else "done"
        row["summary_th"] = (
            f"ประทับตราโดย {rec.actor}" if rec.status != "waived"
            else f"ระบุว่าไม่ต้องประทับตรา: {rec.note or '—'}"
        )
        return
    if not row["required"]:
        row["status"] = "optional" if row["level"] == "POLICY" else "not_required"
        row["summary_th"] = (
            "ไม่บังคับ — ขึ้นกับระเบียบขององค์กร" if row["level"] == "POLICY"
            else cfg.get("reason_th", "ไม่ต้องทำ")
        )
        row["next_action_th"] = "บันทึกการประทับตรา (ถ้าระเบียบกำหนด)" if row["level"] == "POLICY" else ""
        return
    row["status"] = "pending"
    row["next_action_th"] = "บันทึกการประทับตรานิติบุคคล (e-Seal)"


def _h_original(row, cfg, cert, sigs, recorded, audit_count):
    lock_on = cfg.get("lock_on", "all_parties_signed")
    row["detail"] = {
        "lock_on": lock_on,
        "sha256": cert.sha256,
        "system_signature": cert.signature,
        "timestamp": _fmt(cert.ntp_time),
        "timestamp_source": cert.ntp_server_name or cert.ntp_server,
        "timestamp_kind": cfg.get("timestamp", "ntp"),
    }
    if not row["required"]:
        row["status"] = "optional"
        return
    if not cert.signature:
        row["status"] = "pending"
        row["next_action_th"] = "ออกใบรับรองเพื่อล็อกความเป็นต้นฉบับ"
        return
    if lock_on == "all_parties_signed" and not sigs:
        row["status"] = "partial"
        row["summary_th"] = "ล็อกลายนิ้วมือและเวลาแล้ว แต่ยังไม่มีผู้ลงนาม"
        row["next_action_th"] = "ต้องลงนามครบทุกฝ่ายจึงถือเป็นต้นฉบับสมบูรณ์"
        return
    row["status"] = "done"
    row["summary_th"] = (
        f"ล็อกเมื่อ {_fmt(cert.ntp_time)} · {cert.ntp_server_name or 'NTP'}"
    )


def _h_retention(row, cfg, cert, sigs, recorded, audit_count):
    years = int(cfg.get("period_years", 5) or 5)
    must = list(cfg.get("must_store", []))
    keep_until = None
    if cert.ntp_time:
        try:
            keep_until = (cert.ntp_time + timedelta(days=365 * years)).isoformat()
        except Exception:
            keep_until = None

    ret_rec = recorded.get("e_retention")
    have = {
        "audit_trail": audit_count > 0,
        "transmission_log": audit_count > 0,
        "party_identity": any(s.identity_ref for s in sigs),
        "access_log": audit_count > 0,
        "version_accepted": bool(sigs),
        "final_file": False,   # Phase 1 (vault mode) — ยังไม่เก็บไฟล์
        "e_saraban_ref": bool(ret_rec and ret_rec.ref),
    }
    missing = [m for m in must if not have.get(m, False)]

    row["detail"] = {
        "period_years": years,
        "keep_until": keep_until,
        "must_store": must,
        "stored": {m: have.get(m, False) for m in must},
        "missing": missing,
        "audit_entries": audit_count,
        "access_control": cfg.get("access_control", ""),
    }
    if not row["required"]:
        row["status"] = "optional"
        return
    if missing:
        row["status"] = "partial"
        row["summary_th"] = f"เก็บได้ {len(must) - len(missing)} จาก {len(must)} ประเภท"
        if "final_file" in missing:
            row["next_action_th"] = "เปิดโหมดเก็บไฟล์ (vault) เพื่อให้ครบตาม ม.12 — อยู่ในแผน Phase 1"
        else:
            row["next_action_th"] = f"ยังขาด: {', '.join(missing)}"
        return
    row["status"] = "done"
    row["summary_th"] = f"เก็บถึง {keep_until[:10] if keep_until else '—'} · audit {audit_count} รายการ"


def _h_stamp_duty(row, cfg, cert, sigs, recorded, audit_count):
    rec = recorded.get("e_stamp_duty")
    deadline_days = cfg.get("deadline_days")
    deadline = None
    # กำหนดเวลานับจาก "วันที่ทำตราสาร" ไม่ใช่วันที่ออกใบรับรองร่าง — ร่างอาจถูกออก
    # ใบรับรองล่วงหน้าหลายวันก่อนตราสารจะสมบูรณ์ ถ้านับจากวันออกใบรับรองจะเร่งเกินจริง
    basis = cert.instrument_date or cert.ntp_time
    if deadline_days and basis:
        try:
            deadline = basis + timedelta(days=int(deadline_days))
        except Exception:
            deadline = None

    channel = cfg.get("channel", "")
    ch = STAMP_DUTY_CHANNELS.get(channel, {})
    row["detail"] = {
        "instrument_th": cfg.get("instrument_th", ""),
        "channel": channel,
        "channel_label_th": ch.get("label_th", ""),
        "efiling_url": ch.get("url", ""),
        "manual_url": ch.get("manual_url", ""),
        "channel_note_th": ch.get("note_th", ""),
        "condition": cfg.get("condition", ""),
        "deadline_days": deadline_days,
        "deadline": _fmt(deadline),
        "reason_th": cfg.get("reason_th", ""),
        "caveat_th": cfg.get("caveat_th", ""),
        "receipt_ref": rec.ref if rec else "",
        "paid_at": _fmt(rec.recorded_at) if rec else None,
        # มีใบข้อมูลสำหรับยื่นให้ดาวน์โหลดเมื่อสัญญานี้เข้าข่ายต้องเสียอากร
        "worksheet_available": bool(cfg.get("required")),
        "deadline_basis": "instrument_date" if cert.instrument_date else "certified_at",
        "instrument_date": _fmt(cert.instrument_date),
    }
    if rec and rec.status != "waived":
        row["status"] = "done"
        row["summary_th"] = f"ชำระแล้ว · รหัสรับรอง {rec.ref or '—'}"
        return
    if rec and rec.status == "waived":
        row["status"] = "waived"
        row["summary_th"] = f"ระบุว่าไม่เข้าข่าย: {rec.note or '—'}"
        return
    if not row["required"]:
        row["status"] = "not_required"
        row["summary_th"] = cfg.get("reason_th", "ไม่เข้าข่ายตราสารที่ต้องเสียอากร")
        if cfg.get("caveat_th"):
            row["note_th"] = cfg["caveat_th"]
        return

    row["status"] = "pending"
    if cfg.get("condition"):
        row["summary_th"] = f"ต้องเสียอากรเมื่อ {cfg['condition']}"
    if deadline:
        try:
            left = (deadline - datetime.utcnow()).days
        except Exception:
            left = None
        if left is not None and left < 0:
            row["status"] = "overdue"
            row["summary_th"] = f"เลยกำหนด {abs(left)} วัน (ครบ {deadline.date().isoformat()})"
        elif left is not None:
            row["summary_th"] = f"เหลือ {left} วัน (ครบ {deadline.date().isoformat()})"
    row["next_action_th"] = "ยื่นเสียอากรเป็นตัวเงิน (อ.ส.9) ผ่าน e-Filing กรมสรรพากร แล้วบันทึกรหัสรับรอง"


def _h_print_out(row, cfg, cert, sigs, recorded, audit_count):
    rec = recorded.get("print_out")
    row["detail"] = {
        "self_printed_valid": bool(cfg.get("self_printed_valid", True)),
        "certification_text_th": cfg.get(
            "certification_text_th",
            "ขอรับรองว่าเป็นสิ่งพิมพ์ออกที่ถูกต้องตรงกันกับข้อมูลอิเล็กทรอนิกส์ต้นฉบับ",
        ),
        "recorded": bool(rec),
        "actor": rec.actor if rec else "",
        "recorded_at": _fmt(rec.recorded_at) if rec else None,
    }
    if rec:
        row["status"] = "done"
        row["summary_th"] = f"ทำสิ่งพิมพ์ออกโดย {rec.actor or '—'}"
        return
    if row["required"]:
        row["status"] = "pending"
        row["next_action_th"] = "บันทึกการทำสิ่งพิมพ์ออก"
        return
    row["status"] = "optional"
    row["summary_th"] = "ไม่จำเป็น — ใช้ไฟล์อิเล็กทรอนิกส์เป็นต้นฉบับได้เลย"
    row["next_action_th"] = "บันทึกไว้ได้หากมีการพิมพ์ออกเป็นกระดาษ"


_HANDLERS = {
    "e_document": _h_document,
    "e_signature": _h_signature,
    "e_seal": _h_seal,
    "e_original": _h_original,
    "e_retention": _h_retention,
    "e_stamp_duty": _h_stamp_duty,
    "print_out": _h_print_out,
}


# ── ใบข้อมูลสำหรับยื่นขอเสียอากรแสตมป์ (อ.ส.9) ───────────────────────────

def stamp_duty_payload(db: Session, cert: EContractCert) -> dict:
    """รวบรวมข้อมูลที่ระบบรู้ ให้นำไปกรอกในระบบ อ.ส.9 ของกรมสรรพากร

    ระบบรู้: ประเภทตราสาร วันที่ทำ คู่สัญญา ลายนิ้วมือเอกสาร กำหนดเวลา
    ระบบไม่รู้: มูลค่าตราสารและค่าอากร — ผู้ใช้ต้องกรอกเอง (จึงเว้นไว้ ไม่เดา)
    """
    prof = effective_profile(cert)
    cfg = (prof.get("steps") or {}).get("e_stamp_duty") or {}
    ch = STAMP_DUTY_CHANNELS.get(cfg.get("channel", ""), STAMP_DUTY_CHANNELS["rd_efiling_as9"])

    deadline = None
    if cfg.get("deadline_days") and cert.ntp_time:
        try:
            deadline = cert.ntp_time + timedelta(days=int(cfg["deadline_days"]))
        except Exception:
            deadline = None

    sigs = (
        db.query(EContractSignature)
        .filter(EContractSignature.cert_id == cert.cert_id)
        .order_by(EContractSignature.signed_at.asc())
        .all()
    )
    rec = (
        db.query(EContractStep)
        .filter(EContractStep.cert_id == cert.cert_id,
                EContractStep.step_key == "e_stamp_duty")
        .first()
    )

    return {
        "cert_id": cert.cert_id,
        "generated_at": datetime.now().isoformat(),
        "instrument": {
            "profile_key": prof.get("key"),
            "contract_type_th": prof.get("name_th"),
            "instrument_th": cfg.get("instrument_th") or prof.get("name_th"),
            "required": bool(cfg.get("required")),
            "condition": cfg.get("condition", ""),
            "legal_basis_th": (prof.get("legal") or {}).get("tax_th", "ประมวลรัษฎากร"),
        },
        "document": {
            "filename": cert.filename,
            "format": cert.doc_format or "",
            "size_bytes": cert.size_bytes,
            "sha256": cert.sha256,
            "created_at": _fmt(cert.ntp_time),
            "time_source": cert.ntp_server_name or cert.ntp_server,
        },
        "parties": [
            {"name": s.signer_name, "method": s.method, "signed_at": _fmt(s.signed_at)}
            for s in sigs
        ],
        "deadline": {
            "days": cfg.get("deadline_days"),
            "due_at": _fmt(deadline),
        },
        "channel": {
            "key": cfg.get("channel", ""),
            "label_th": ch["label_th"],
            "url": ch["url"],
            "manual_url": ch["manual_url"],
        },
        # ค่าที่ระบบไม่ทราบ — ต้องกรอกเองในระบบกรมสรรพากร
        "to_be_filled": {
            "instrument_value_baht": None,
            "duty_rate": None,
            "duty_amount_baht": None,
            "payer_taxpayer_id": None,
        },
        "payment": {
            "paid": bool(rec and rec.status == "done"),
            "receipt_code": rec.ref if rec else "",
            "paid_at": _fmt(rec.recorded_at) if rec and rec.status == "done" else None,
        },
    }


def stamp_duty_worksheet_text(payload: dict) -> str:
    """ใบข้อมูลแบบอ่านง่าย/พิมพ์ได้ สำหรับถือไปกรอกในระบบ อ.ส.9"""
    i, doc, ch = payload["instrument"], payload["document"], payload["channel"]
    dl, pay = payload["deadline"], payload["payment"]
    L: list[str] = []
    L.append("ข้อมูลสำหรับยื่นขอเสียอากรแสตมป์อิเล็กทรอนิกส์ (อ.ส.9)")
    L.append("ออกโดย iVS e-Contract — ใช้ประกอบการกรอกในระบบของกรมสรรพากร")
    L.append("=" * 70)
    L.append("")
    L.append("[1] ตราสาร")
    L.append(f"    ประเภทสัญญา        : {i['contract_type_th']}")
    L.append(f"    ประเภทตราสาร       : {i['instrument_th']}")
    L.append(f"    ฐานทางกฎหมาย       : {i['legal_basis_th']}")
    if i.get("condition"):
        L.append(f"    เงื่อนไขที่ต้องเสีย : {i['condition']}")
    L.append("")
    L.append("[2] เอกสาร")
    L.append(f"    ชื่อไฟล์            : {doc['filename']}")
    L.append(f"    รูปแบบ              : {doc['format'] or '—'}")
    L.append(f"    ลายนิ้วมือ SHA-256  : {doc['sha256']}")
    L.append(f"    วันเวลาที่รับรอง    : {doc['created_at']}")
    L.append(f"    แหล่งเวลา           : {doc['time_source'] or '—'}")
    L.append(f"    เลขที่ใบรับรอง iVS  : {payload['cert_id']}")
    L.append("")
    L.append("[3] คู่สัญญา / ผู้ลงนาม")
    if payload["parties"]:
        for n, p in enumerate(payload["parties"], 1):
            L.append(f"    {n}. {p['name']}  (วิธี {p['method']} · {p['signed_at']})")
    else:
        L.append("    — ยังไม่มีผู้ลงนามบันทึกไว้ในระบบ —")
    L.append("")
    L.append("[4] กำหนดเวลา")
    if dl.get("days"):
        L.append(f"    ต้องยื่นภายใน       : {dl['days']} วันนับแต่วันที่ทำตราสาร")
        L.append(f"    ครบกำหนด            : {dl['due_at']}")
    else:
        L.append("    ตรวจสอบกำหนดเวลาตามประเภทตราสารที่กรมสรรพากร")
    L.append("")
    L.append("[5] ข้อมูลที่ต้องกรอกเอง (ระบบ iVS ไม่ทราบค่าเหล่านี้)")
    L.append("    มูลค่าตราสาร (บาท)  : ______________________")
    L.append("    อัตราอากร            : ______________________")
    L.append("    ค่าอากรที่ต้องชำระ   : ______________________")
    L.append("    เลขประจำตัวผู้เสียภาษี: ______________________")
    L.append("    ** อัตราอากรให้ยึดตามบัญชีอัตราอากรแสตมป์ท้ายประมวลรัษฎากร **")
    L.append("")
    L.append("[6] ช่องทางยื่น")
    L.append(f"    {ch['label_th']}")
    L.append(f"    ยื่นที่   : {ch['url']}")
    L.append(f"    คู่มือ    : {ch['manual_url']}")
    L.append("")
    L.append("[7] ขั้นตอน")
    L.append(f"    1) เปิด {ch['url']}")
    L.append("    2) ยื่นขอเสียอากรแสตมป์เป็นตัวเงิน (อ.ส.9) โดยใช้ข้อมูลข้างต้น")
    L.append("    3) ชำระเงินตามช่องทางที่กรมสรรพากรกำหนด")
    L.append("    4) รับ 'รหัสรับรองการเสียอากรแสตมป์' เก็บไว้เป็นหลักฐาน")
    L.append("    5) กลับมาบันทึกรหัสรับรองในระบบ iVS")
    L.append(f"       (e-Contract → {payload['cert_id']} → ขั้นตอนที่ 6 e-Stamp Duty)")
    L.append("")
    if pay["paid"]:
        L.append("[สถานะ] ชำระแล้ว")
        L.append(f"    รหัสรับรอง : {pay['receipt_code'] or '—'}")
        L.append(f"    บันทึกเมื่อ : {pay['paid_at']}")
    else:
        L.append("[สถานะ] ยังไม่ได้ชำระ")
    L.append("")
    L.append("-" * 70)
    L.append("อ้างอิง: พ.ร.บ.ว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ พ.ศ. 2544 ม.8 วรรคสอง")
    L.append("        — ชำระอากรด้วยวิธีการทางอิเล็กทรอนิกส์ตามที่กำหนด ให้ถือว่าตราสารนั้น")
    L.append("          ได้ปิดอากรแสตมป์และขีดฆ่าตามกฎหมายแล้ว")
    L.append("")
    L.append("หมายเหตุ: เอกสารนี้เป็นข้อมูลประกอบการยื่นที่ระบบรวบรวมให้เท่านั้น")
    L.append("          ไม่ใช่หลักฐานการเสียอากร และไม่ใช่คำวินิจฉัยทางภาษี")
    return "\n".join(L) + "\n"


# ── บันทึกขั้นตอนที่เกิดนอกระบบ ──────────────────────────────────────────

def record_step(db: Session, cert_id: str, step_key: str, actor: str = "",
                ref: str = "", note: str = "", status: str = "done",
                detail: dict | None = None, recorded_by: int | None = None) -> dict:
    """บันทึกว่าขั้นตอนหนึ่งถูกดำเนินการแล้ว (หรือระบุว่าไม่ต้องทำ)"""
    from app.services.ntp_service import ntp_service

    if step_key not in MANUAL_STEPS:
        raise ValueError(
            f"ขั้นตอน {step_key} ระบบตรวจจากข้อมูลจริงเอง บันทึกด้วยมือไม่ได้"
        )
    if status not in ("done", "waived"):
        raise ValueError("status ต้องเป็น done หรือ waived")
    cert = db.query(EContractCert).filter(EContractCert.cert_id == cert_id).first()
    if not cert:
        raise ValueError("ไม่พบใบรับรอง")

    row = (
        db.query(EContractStep)
        .filter(EContractStep.cert_id == cert_id, EContractStep.step_key == step_key)
        .first()
    )
    if not row:
        row = EContractStep(cert_id=cert_id, step_key=step_key)
        db.add(row)
    row.status = status
    row.actor = (actor or "")[:200]
    row.ref = (ref or "")[:200]
    row.note = note or ""
    row.detail = json.dumps(detail or {}, ensure_ascii=False)
    row.recorded_at = ntp_service.now()
    row.recorded_by = recorded_by
    db.commit()
    db.refresh(row)

    # ต่อเข้าโซ่หลักฐาน — ขั้นตอนเหล่านี้เป็นเอกสารประกอบที่อ้างถึงต้นฉบับ จึงผนวก
    # ต่อท้ายได้แม้ตรึงต้นฉบับแล้ว (อากรแสตมป์ต้องชำระหลังตราสารสมบูรณ์อยู่แล้ว)
    # e_seal ไม่อยู่ในนี้เพราะ apply_seal() ต่อโซ่เองด้วย STEP_SEAL ก่อนตรึงต้นฉบับ
    from app.services import chain_service
    chain_step = {
        "e_stamp_duty": chain_service.STEP_STAMP_DUTY,
        "print_out": chain_service.STEP_PRINT_OUT,
        "e_retention": chain_service.STEP_RETENTION,
    }.get(step_key)
    if chain_step:
        try:
            chain_service.append(db, cert_id, chain_step, {
                "status": row.status, "actor": row.actor, "ref": row.ref,
                "note": row.note, "detail": detail or {}, "recorded_at": row.recorded_at,
            }, created_by=recorded_by)
        except chain_service.ChainError as e:
            logger.warning(f"ต่อโซ่ {chain_step} ของ {cert_id} ไม่สำเร็จ: {e}")
    return step_to_dict(row)


def step_to_dict(row: EContractStep) -> dict:
    try:
        detail = json.loads(row.detail) if row.detail else {}
    except Exception:
        detail = {}
    return {
        "cert_id": row.cert_id,
        "step_key": row.step_key,
        "status": row.status,
        "actor": row.actor,
        "ref": row.ref,
        "note": row.note,
        "detail": detail,
        "recorded_at": _fmt(row.recorded_at),
    }
