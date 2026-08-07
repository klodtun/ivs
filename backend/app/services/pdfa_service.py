"""
PDF/A pipeline — เอกสารที่ยังอ่านได้เหมือนเดิมเมื่อผ่านไปสิบปี

ทำไมต้อง PDF/A ไม่ใช่ PDF ธรรมดา: ม.10(2) กำหนดว่าเอกสารต้นฉบับต้อง "แสดงข้อความนั้น
ในภายหลังได้" และ ม.12 ให้เก็บรักษาโดยความหมายไม่เปลี่ยนแปลง PDF ธรรมดาอ้างอิงฟอนต์
จากเครื่องที่เปิด ถ้าเครื่องนั้นไม่มีฟอนต์ไทยตัวเดิม ข้อความจะเพี้ยนหรือกลายเป็นกล่องว่าง
PDF/A บังคับให้ฝังฟอนต์ทั้งหมด ระบุ colour space ที่ใช้ และมี metadata ที่ค้นได้

เป้าหมายคือ **PDF/A-2b** — ระดับ b (basic) รับประกันการแสดงผลซ้ำได้ ส่วน A-2 อนุญาต
ความโปร่งใสและการบีบอัดสมัยใหม่ที่ A-1 ห้าม จึงเหมาะกับเอกสารที่สร้างจากเว็บ

ภาษาไทยเป็นข้อจำกัดจริงของงานนี้: สระบน/ล่างและวรรณยุกต์ต้องวางตำแหน่งถูก และไทย
ไม่มีช่องว่างระหว่างคำ จึงต้องตัดบรรทัดด้วยพจนานุกรม เราจึงใช้ WeasyPrint ที่วาดผ่าน
Pango ซึ่งจัดการทั้งสองเรื่องนี้ให้ แทนที่จะใช้ไลบรารีที่วางกลีฟตรง ๆ

ฟอนต์: Sarabun (SIL Open Font License) เผยแพร่ซ้ำได้ ต่างจาก TH SarabunPSK ที่ราชการ
ใช้เป็นมาตรฐาน ซึ่งต้องตรวจสิทธิ์ก่อนฝังลง distribution

**ข้อจำกัดที่ทราบ — สระอำ:** ตอน shaping สระอำ (U+0E33) ถูกแยกเป็นนิคหิต (U+0E4D) +
สระอา (U+0E32) เพื่อวางวรรณยุกต์ให้ถูกตำแหน่ง การแสดงผลจึงถูกต้องสมบูรณ์ แต่เวลาคัดลอก
หรือค้นหาข้อความจะได้รูปแยก เช่น "ทำ" ออกมาเป็น "ทํา" ซึ่ง Unicode ถือเป็นคนละสตริง
→ ค้นคำที่มีสระอำต้องใช้รูปแยก เป็นพฤติกรรมปกติของเอกสาร PDF ภาษาไทยทั่วไป
ส่วนอักขระอื่นทั้งหมดคัดลอก/ค้นหาได้ตรง
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "econtract_assets"
)
FONT_DIR = os.path.join(ASSET_DIR, "fonts")
ICC_PATH = os.path.join(ASSET_DIR, "icc", "sRGB-v2-micro.icc")

PDFA_PART = 2
PDFA_CONFORMANCE = "B"


class PdfaUnavailable(RuntimeError):
    """ไลบรารีที่ต้องใช้ยังไม่ได้ติดตั้งบนเครื่องนี้"""


def capability() -> dict:
    """ตรวจว่าเครื่องนี้สร้าง PDF/A ได้หรือไม่

    WeasyPrint ต้องมี pango/cairo ระดับระบบ ซึ่งบางเครื่อง (โดยเฉพาะ dev บน macOS)
    อาจยังไม่มี — ระบบต้องบอกตรง ๆ แทนที่จะพังตอนผู้ใช้กดปุ่ม
    """
    missing, detail = [], {}
    try:
        import weasyprint  # noqa: F401
        detail["weasyprint"] = weasyprint.__version__
    except Exception as e:
        missing.append("weasyprint")
        detail["weasyprint_error"] = str(e)[:200]
    try:
        import pikepdf  # noqa: F401
        detail["pikepdf"] = pikepdf.__version__
    except Exception as e:
        missing.append("pikepdf")
        detail["pikepdf_error"] = str(e)[:200]

    try:
        import fontTools  # noqa: F401
        detail["fonttools"] = fontTools.version
    except Exception as e:
        missing.append("fonttools")
        detail["fonttools_error"] = str(e)[:200]

    fonts_ok = os.path.isfile(os.path.join(FONT_DIR, "Sarabun-Regular.ttf"))
    icc_ok = os.path.isfile(ICC_PATH)
    if not fonts_ok:
        missing.append("fonts")
    if not icc_ok:
        missing.append("icc")

    return {
        "available": not missing,
        "missing": missing,
        "target": f"PDF/A-{PDFA_PART}{PDFA_CONFORMANCE.lower()}",
        "font": "Sarabun (SIL OFL)",
        "detail": detail,
        "note_th": (
            "พร้อมสร้าง PDF/A" if not missing else
            "เครื่องนี้ยังสร้าง PDF/A ไม่ได้ — ขาด: " + ", ".join(missing)
        ),
        "fix_th": _fix_hint(missing, detail),
    }


def _fix_hint(missing: list, detail: dict) -> str:
    """บอกวิธีแก้ที่ทำได้จริง แทนที่จะบอกแค่ว่าขาดอะไร"""
    if not missing:
        return ""
    err = detail.get("weasyprint_error", "")
    # เคสที่พบบ่อยบน macOS: ติดตั้ง weasyprint แล้วแต่ dyld หาไลบรารีของ homebrew ไม่เจอ
    # เพราะ SIP ตัด DYLD_* ออกจาก environment ที่สืบทอดมา ต้องตั้งตอนสั่งรัน
    if "gobject" in err or "cannot load library" in err:
        import sys
        if sys.platform == "darwin":
            return (
                "macOS: ติดตั้ง pango แล้ว (brew install pango) แต่ต้องบอกตำแหน่งไลบรารี "
                "ตอนสั่งรัน — เพิ่ม DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib "
                "หน้าคำสั่ง uvicorn แล้วรีสตาร์ท backend"
            )
        return "ติดตั้งไลบรารีระดับระบบ: libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b"
    pips = [m for m in missing if m in ("weasyprint", "pikepdf", "fonttools")]
    if pips:
        return "ติดตั้งแพ็กเกจ: pip install " + " ".join(pips)
    if "fonts" in missing or "icc" in missing:
        return f"ไฟล์ประกอบหาย — ตรวจโฟลเดอร์ {ASSET_DIR}"
    return ""


def _require():
    cap = capability()
    if not cap["available"]:
        raise PdfaUnavailable(cap["note_th"])


# ── HTML → PDF ───────────────────────────────────────────────────────────

def _font_css() -> str:
    """ฝังฟอนต์ไทยจากไฟล์ในโปรเจกต์ ไม่พึ่งฟอนต์ของเครื่องที่รัน"""
    reg = os.path.join(FONT_DIR, "Sarabun-Regular.ttf")
    bold = os.path.join(FONT_DIR, "Sarabun-Bold.ttf")
    return f"""
    @font-face {{ font-family: Sarabun; font-weight: 400;
                  src: url('file://{reg}') format('truetype'); }}
    @font-face {{ font-family: Sarabun; font-weight: 700;
                  src: url('file://{bold}') format('truetype'); }}
    """


def _glyph_unicode_map(font_path: str) -> dict:
    """สร้างแผนที่ glyph id → ข้อความ Unicode จากตัวไฟล์ฟอนต์

    ใช้ 2 ทาง: (1) ตาราง cmap ของฟอนต์ (2) ชื่อกลีฟแบบ `uniXXXX` หรือ `uniXXXXYYYY`
    ซึ่งกลีฟผสมของไทย (เช่น นิคหิต+วรรณยุกต์) ใช้บอกลำดับอักขระที่ประกอบขึ้นมา
    """
    from fontTools.ttLib import TTFont

    font = TTFont(font_path, lazy=True)
    order = font.getGlyphOrder()
    uni_by_name = {}
    for code, name in font.getBestCmap().items():
        uni_by_name.setdefault(name, chr(code))

    out = {}
    for gid, name in enumerate(order):
        text = uni_by_name.get(name)
        if text is None:
            base = name.split(".")[0]
            if base.startswith("uni") and len(base) > 3 and len(base[3:]) % 4 == 0:
                try:
                    text = "".join(
                        chr(int(base[i:i + 4], 16)) for i in range(3, len(base), 4)
                    )
                except ValueError:
                    text = None
        if text:
            out[gid] = text
    font.close()
    return out


def _repair_tounicode(pdf_bytes: bytes, font_paths: list) -> bytes:
    """เติมช่องว่างใน ToUnicode CMap ที่ WeasyPrint ปล่อยว่างไว้

    ทำไมจำเป็น: Pango แทนที่กลีฟบางตัวผ่าน GSUB (เช่น ท ที่ตามด้วยสระอำ) แล้ว
    WeasyPrint หา Unicode ย้อนกลับไม่เจอ จึงเขียน `<>` — ผลคือเอกสารแสดงผลถูกต้อง
    แต่ **ค้นหาและคัดลอกข้อความไทยไม่ได้** และขัดข้อกำหนดของ PDF/A ที่ต้อง map
    ข้อความกลับเป็น Unicode ได้ (ISO 19005-2 ข้อ 6.2.11.7)

    แก้ได้เพราะ WeasyPrint ทำ subset แบบคง glyph id เดิม จึงเทียบกับตัวไฟล์ฟอนต์ได้ตรง
    """
    import io
    import re
    import pikepdf

    gmap = {}
    for path in font_paths:
        if os.path.isfile(path):
            try:
                gmap.update(_glyph_unicode_map(path))
            except Exception as e:
                logger.warning(f"อ่านฟอนต์ {path} ไม่สำเร็จ: {e}")
    if not gmap:
        return pdf_bytes

    def utf16be_hex(text: str) -> str:
        return text.encode("utf-16-be").hex()

    filled = 0
    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        for obj in pdf.objects:
            try:
                if not (isinstance(obj, pikepdf.Stream)
                        and obj.get("/Type") is None
                        and b"beginbfchar" in bytes(obj.read_bytes())):
                    continue
                raw = bytes(obj.read_bytes()).decode("latin-1")
            except Exception:
                continue
            if "Adobe-Identity-UCS" not in raw:
                continue

            def fix(m):
                nonlocal filled
                src, dst = m.group(1), m.group(2)
                if dst:
                    return m.group(0)
                text = gmap.get(int(src, 16))
                if not text:
                    return m.group(0)
                filled += 1
                return f"<{src}> <{utf16be_hex(text)}>"

            new = re.sub(r"<([0-9a-fA-F]{4})>\s*<([0-9a-fA-F]*)>", fix, raw)
            if new != raw:
                obj.write(new.encode("latin-1"))

        if not filled:
            return pdf_bytes
        out = io.BytesIO()
        pdf.save(out)
        logger.info(f"ToUnicode: เติมกลีฟที่ map ไม่ได้ {filled} ตัว")
        return out.getvalue()


def html_to_pdf(html_body: str, extra_css: str = "") -> bytes:
    """แปลง HTML เป็น PDF (ยังไม่ใช่ PDF/A — ต้องผ่าน to_pdfa ต่อ)"""
    _require()
    import weasyprint

    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    {_font_css()}
    @page {{ size: A4; margin: 18mm 16mm; }}
    body {{ font-family: Sarabun, sans-serif; font-size: 11pt; color: #1a1a1a;
            line-height: 1.55; }}
    h1 {{ font-size: 16pt; margin: 0 0 2mm; }}
    h2 {{ font-size: 12pt; margin: 6mm 0 2mm; border-bottom: 0.4pt solid #999;
          padding-bottom: 1mm; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
    th, td {{ text-align: left; vertical-align: top; padding: 1.4mm 2mm;
              border-bottom: 0.3pt solid #ddd; }}
    th {{ width: 34%; color: #555; font-weight: 400; }}
    .mono {{ font-family: monospace; font-size: 8.5pt; word-break: break-all; }}
    .muted {{ color: #666; font-size: 9pt; }}
    .tiny {{ color: #888; font-size: 8pt; }}
    {extra_css}
    </style></head><body>{html_body}</body></html>"""
    pdf = weasyprint.HTML(string=doc, base_url=ASSET_DIR).write_pdf()
    # ซ่อม ToUnicode ก่อนส่งต่อ — ต้องทำตรงนี้เพราะเป็นจุดเดียวที่รู้แน่ว่าใช้ฟอนต์ใด
    return _repair_tounicode(pdf, [
        os.path.join(FONT_DIR, "Sarabun-Regular.ttf"),
        os.path.join(FONT_DIR, "Sarabun-Bold.ttf"),
    ])


# ── PDF → PDF/A-2b ───────────────────────────────────────────────────────

_XMP = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
      xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:xmp="http://ns.adobe.com/xap/1.0/"
      xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
   <pdfaid:part>{part}</pdfaid:part>
   <pdfaid:conformance>{conformance}</pdfaid:conformance>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>
   <dc:creator><rdf:Seq><rdf:li>{author}</rdf:li></rdf:Seq></dc:creator>
   <xmp:CreatorTool>{producer}</xmp:CreatorTool>
   <xmp:CreateDate>{created}</xmp:CreateDate>
   <xmp:ModifyDate>{created}</xmp:ModifyDate>
   <pdf:Producer>{producer}</pdf:Producer>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

PRODUCER = "iVS e-Contract"


def _esc(s: str) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def to_pdfa(pdf_bytes: bytes, title: str = "", author: str = "",
            created: datetime = None) -> bytes:
    """เติมสิ่งที่ PDF/A-2b บังคับ: XMP ที่ประกาศตัวเอง + OutputIntent (sRGB) + info

    ไม่ได้ "ซ่อม" PDF ที่ผิดหลักอยู่แล้ว — ถ้าไฟล์ต้นทางไม่ฝังฟอนต์ ผลลัพธ์จะยังไม่ผ่าน
    การตรวจแบบเข้มงวด ใช้ check_pdfa() ดูสถานะจริงเสมอ
    """
    _require()
    import io
    import pikepdf

    ts = (created or datetime.now(timezone.utc)).astimezone(timezone.utc)
    iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
        # OutputIntent — บอกว่าเอกสารเตรียมไว้สำหรับ colour space ใด
        with open(ICC_PATH, "rb") as f:
            icc = f.read()
        icc_stream = pdf.make_stream(icc)
        icc_stream["/N"] = 3          # sRGB = 3 ช่องสี
        oi = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/OutputIntent"),
            S=pikepdf.Name("/GTS_PDFA1"),
            OutputConditionIdentifier=pikepdf.String("sRGB IEC61966-2.1"),
            Info=pikepdf.String("sRGB IEC61966-2.1"),
            RegistryName=pikepdf.String("http://www.color.org"),
            DestOutputProfile=icc_stream,
        ))
        pdf.Root[pikepdf.Name("/OutputIntents")] = pdf.make_indirect([oi])

        # XMP ต้องสอดคล้องกับ document info ไม่งั้น validator จะฟ้อง
        xmp = _XMP.format(
            part=PDFA_PART, conformance=PDFA_CONFORMANCE,
            title=_esc(title or "e-Contract document"),
            author=_esc(author or PRODUCER),
            producer=_esc(PRODUCER), created=iso,
        )
        meta = pdf.make_stream(xmp.encode("utf-8"))
        meta[pikepdf.Name("/Type")] = pikepdf.Name("/Metadata")
        meta[pikepdf.Name("/Subtype")] = pikepdf.Name("/XML")
        pdf.Root[pikepdf.Name("/Metadata")] = pdf.make_indirect(meta)

        with pdf.open_metadata(set_pikepdf_as_editor=False) as m:
            m["dc:title"] = title or "e-Contract document"
            m["pdf:Producer"] = PRODUCER
        pdf.docinfo[pikepdf.Name("/Title")] = pikepdf.String(title or "e-Contract document")
        pdf.docinfo[pikepdf.Name("/Author")] = pikepdf.String(author or PRODUCER)
        pdf.docinfo[pikepdf.Name("/Producer")] = pikepdf.String(PRODUCER)
        pdf.docinfo[pikepdf.Name("/CreationDate")] = pikepdf.String(
            ts.strftime("D:%Y%m%d%H%M%SZ")
        )

        out = io.BytesIO()
        pdf.save(out, linearize=False)
        return out.getvalue()


def check_pdfa(pdf_bytes: bytes) -> dict:
    """ตรวจสิ่งที่ตรวจได้เองโดยไม่ต้องพึ่ง validator ภายนอก

    นี่ไม่ใช่การตรวจ conformance เต็มรูปแบบ — การรับรองจริงต้องใช้ veraPDF
    ผลลัพธ์นี้จึงบอกได้แค่ว่า "มีองค์ประกอบที่ PDF/A บังคับครบหรือไม่"
    """
    import io
    try:
        import pikepdf
    except Exception:
        return {"checked": False, "reason_th": "ไม่มี pikepdf บนเครื่องนี้"}

    res = {"checked": True, "declared_part": None, "declared_conformance": None,
           "has_output_intent": False, "fonts_embedded": True,
           "non_embedded_fonts": [], "encrypted": False, "pages": 0}
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            res["pages"] = len(pdf.pages)
            res["encrypted"] = pdf.is_encrypted
            res["has_output_intent"] = "/OutputIntents" in pdf.Root

            raw = bytes(pdf.Root["/Metadata"].read_bytes()) if "/Metadata" in pdf.Root else b""
            txt = raw.decode("utf-8", "ignore")
            for tag, key in (("pdfaid:part", "declared_part"),
                             ("pdfaid:conformance", "declared_conformance")):
                i = txt.find(f"<{tag}>")
                if i >= 0:
                    res[key] = txt[i + len(tag) + 2: txt.find(f"</{tag}>", i)].strip()

            for page in pdf.pages:
                fonts = (page.get("/Resources", {}) or {}).get("/Font", {}) or {}
                for _, f in fonts.items():
                    desc = f.get("/FontDescriptor")
                    if desc is None and f.get("/Subtype") == "/Type0":
                        d = (f.get("/DescendantFonts") or [None])[0]
                        desc = d.get("/FontDescriptor") if d else None
                    embedded = desc is not None and any(
                        k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")
                    )
                    if not embedded:
                        res["fonts_embedded"] = False
                        name = str(f.get("/BaseFont", "?"))
                        if name not in res["non_embedded_fonts"]:
                            res["non_embedded_fonts"].append(name)
    except Exception as e:
        return {"checked": False, "reason_th": f"อ่านไฟล์ไม่ได้: {e}"}

    ok = (res["declared_part"] == str(PDFA_PART) and res["has_output_intent"]
          and res["fonts_embedded"] and not res["encrypted"])
    res["conformant_markers"] = ok
    res["summary_th"] = (
        f"มีองค์ประกอบครบตาม PDF/A-{res['declared_part']}"
        f"{(res['declared_conformance'] or '').lower()} ({res['pages']} หน้า)"
        if ok else
        "ยังไม่ครบ: " + ", ".join(filter(None, [
            None if res["declared_part"] else "ไม่ได้ประกาศ pdfaid",
            None if res["has_output_intent"] else "ไม่มี OutputIntent",
            None if res["fonts_embedded"] else f"ฟอนต์ไม่ได้ฝัง ({', '.join(res['non_embedded_fonts'][:3])})",
            "ไฟล์ถูกเข้ารหัส" if res["encrypted"] else None,
        ]))
    )
    return res


def convert_to_pdfa(pdf_bytes: bytes, title: str = "", author: str = "") -> tuple:
    """แปลงไฟล์ PDF ที่มีอยู่ให้เป็น PDF/A-2b — คืน (bytes, ผลตรวจ)"""
    out = to_pdfa(pdf_bytes, title=title, author=author)
    return out, check_pdfa(out)


# ── ใบรับรองการลงนามต่อท้ายเอกสาร ────────────────────────────────────────

def audit_certificate_html(cert: dict, chain: dict, compliance: dict,
                           signatures: list, attachments: list = None) -> str:
    """หน้าสรุปหลักฐานที่ผนวกท้ายเอกสาร — พิมพ์ออกมาแล้วยังตรวจกลับได้"""
    def row(k, v):
        return f"<tr><th>{_esc(k)}</th><td>{v}</td></tr>"

    prof = (compliance or {}).get("profile", {})
    ver = (chain or {}).get("verification", {})
    summary = (compliance or {}).get("summary", {})

    head = [
        row("เลขที่ใบรับรอง", f'<span class="mono">{_esc(cert.get("cert_id"))}</span>'),
        row("ชื่อไฟล์", _esc(cert.get("filename"))),
        row("ลายนิ้วมือเอกสาร (SHA-256)", f'<span class="mono">{_esc(cert.get("sha256"))}</span>'),
        row("เวลาที่เชื่อถือได้", f'{_esc(cert.get("ntp_time"))}<br><span class="muted">'
                                 f'{_esc(cert.get("ntp_server_name"))}</span>'),
        row("ลายเซ็นระบบ (HMAC)", f'<span class="mono">{_esc(cert.get("signature"))}</span>'),
        row("ประเภทสัญญา", f'{_esc(prof.get("name_th"))} <span class="muted">'
                          f'({_esc(prof.get("key"))} v{_esc(prof.get("version"))})</span>'),
        row("ความครบถ้วน", f'{summary.get("required_done", 0)}/{summary.get("required_total", 0)} '
                          "ขั้นตอนที่บังคับ"),
    ]

    def sig_row(i: int, s: dict) -> str:
        role = s.get("signer_role")
        role_html = f'<br><span class="muted">{_esc(role)}</span>' if role else ""
        return (
            f"<tr><td>{i}</td>"
            f"<td>{_esc(s.get('signer_name'))}{role_html}</td>"
            f"<td>{_esc(s.get('method'))}</td>"
            f"<td>{_esc(s.get('signed_at'))}</td>"
            f'<td class="mono">{_esc(s.get("ip_address"))}</td></tr>'
        )

    sig_rows = "".join(
        sig_row(i, s) for i, s in enumerate(signatures or [], 1)
    ) or '<tr><td colspan="5" class="muted">ไม่มีผู้ลงนามบันทึกไว้</td></tr>'

    chain_rows = "".join(
        f"<tr><td>{l.get('seq')}</td><td>{_esc(l.get('step_th'))}</td>"
        f"<td>{_esc(l.get('recorded_at'))}</td>"
        f"<td class=mono>{_esc(str(l.get('chain_hash'))[:32])}…</td></tr>"
        for l in (chain or {}).get("links", [])
    ) or '<tr><td colspan="4" class="muted">ไม่มีโซ่หลักฐาน</td></tr>'

    att_rows = "".join(
        f"<tr><td>{_esc(a.get('title') or a.get('filename'))}</td>"
        f"<td>{_esc(a.get('kind_th'))}</td>"
        f"<td class=mono>{_esc(str(a.get('sha256'))[:32])}…</td></tr>"
        for a in (attachments or [])
    )
    att_block = (
        f'<h2>หลักฐานที่แนบ</h2><table><tr><th>เอกสาร</th><th>ประเภท</th>'
        f'<th>SHA-256</th></tr>{att_rows}</table>' if att_rows else ""
    )

    verdict = ("✓ " + _esc(ver.get("reason_th"))) if ver.get("valid") else \
              ("✕ " + _esc(ver.get("reason_th", "ตรวจโซ่ไม่ผ่าน")))

    return f"""
    <h1>ใบรับรองการลงนามอิเล็กทรอนิกส์</h1>
    <p class="muted">ออกโดยระบบ iVS e-Contract · เอกสารประกอบสัญญาอิเล็กทรอนิกส์
    ตาม พ.ร.บ. ว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ พ.ศ. 2544</p>

    <h2>ข้อมูลใบรับรอง</h2>
    <table>{''.join(head)}</table>

    <h2>ผู้ลงนาม</h2>
    <table>
      <tr><th style="width:6%">#</th><th style="width:34%">ชื่อ / ฐานะ</th>
          <th style="width:14%">วิธี</th><th style="width:26%">เวลา</th><th>IP</th></tr>
      {sig_rows}
    </table>

    <h2>โซ่หลักฐาน (ลำดับเหตุการณ์)</h2>
    <p class="muted">{verdict}</p>
    <table>
      <tr><th style="width:6%">#</th><th style="width:34%">เหตุการณ์</th>
          <th style="width:26%">เวลา</th><th>chain hash</th></tr>
      {chain_rows}
    </table>

    {att_block}

    <h2>การตรวจสอบย้อนกลับ</h2>
    <p class="muted">นำเลขที่ใบรับรองหรือไฟล์ต้นฉบับไปตรวจที่เมนู e-Contract ของ iVS
    เครื่องที่ออกใบรับรอง หรือเทียบค่า SHA-256 ด้านบนกับไฟล์ที่ถืออยู่</p>

    <p class="tiny">เอกสารนี้เป็นสรุปหลักฐานที่ระบบบันทึกไว้ ไม่ใช่คำวินิจฉัยว่าสัญญา
    สมบูรณ์ตามกฎหมาย · ลายเซ็นระบบเป็น HMAC ของเครื่องที่ออกใบรับรอง ซึ่งเข้าเงื่อนไข
    ลายมือชื่ออิเล็กทรอนิกส์ทั่วไปตามมาตรา 9 แต่ยังไม่ใช่ลายมือชื่อแบบเชื่อถือได้ตาม
    มาตรา 26 ที่ต้องใช้ใบรับรองจากผู้ให้บริการออกใบรับรองอิเล็กทรอนิกส์</p>
    """


def build_final_document(cert: dict, chain: dict, compliance: dict, signatures: list,
                         attachments: list = None, source_pdf: bytes = None) -> tuple:
    """เอกสารฉบับสมบูรณ์: ต้นฉบับ (ถ้ามี) + ใบรับรองการลงนาม แล้วแปลงเป็น PDF/A-2b

    คืน (bytes, ผลตรวจ) — ถ้าไม่มีไฟล์ต้นฉบับ (โหมดเก็บเฉพาะลายนิ้วมือ) จะได้เฉพาะ
    ใบรับรอง ซึ่งยังพิสูจน์เนื้อหาเอกสารไม่ได้ ต้องบอกผู้ใช้ให้ชัด
    """
    _require()
    import io
    import pikepdf

    audit = html_to_pdf(audit_certificate_html(cert, chain, compliance, signatures, attachments))

    if source_pdf and source_pdf[:5] == b"%PDF-":
        merged = io.BytesIO()
        with pikepdf.open(io.BytesIO(source_pdf)) as base:
            with pikepdf.open(io.BytesIO(audit)) as extra:
                base.pages.extend(extra.pages)
            base.save(merged)
        body = merged.getvalue()
        included_source = True
    else:
        body = audit
        included_source = False

    out = to_pdfa(
        body,
        title=f"{cert.get('filename', 'e-Contract')} · {cert.get('cert_id', '')}",
        author=cert.get("signer") or PRODUCER,
    )
    report = check_pdfa(out)
    report["included_source_document"] = included_source
    if not included_source:
        report["note_th"] = (
            "ไม่ได้แนบตัวเอกสารต้นฉบับ เพราะระบบเก็บเฉพาะลายนิ้วมือ — "
            "ไฟล์นี้จึงเป็นใบรับรองการลงนามอย่างเดียว เปิดโหมดเก็บไฟล์แล้วแนบเอกสาร"
            "ตัวจริงจึงจะได้ฉบับสมบูรณ์"
        )
    return out, report
