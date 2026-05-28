"""
PDPA PII Scanner Service — Scan deployed apps for PII fields and data masking patterns.

Scans source code for:
1. PII field names (name, email, phone, address, etc.)
2. Data masking patterns (mask, redact, ***, anonymize, etc.)
"""
import os
import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── PII Field Patterns ──
# Common field names that indicate personally identifiable information
PII_PATTERNS = {
    "ชื่อ-นามสกุล": [
        r"\bfirst_?name\b", r"\blast_?name\b", r"\bfull_?name\b",
        r"\bname\b", r"\bsurname\b", r"\bnickname\b",
        r"\bชื่อ\b", r"\bนามสกุล\b", r"\bชื่อเล่น\b",
    ],
    "อีเมล": [
        r"\bemail\b", r"\be_?mail\b", r"\bmail_?address\b",
        r"\bอีเมล\b",
    ],
    "เบอร์โทรศัพท์": [
        r"\bphone\b", r"\btel\b", r"\btelephone\b", r"\bmobile\b",
        r"\bcell_?phone\b", r"\bphone_?number\b",
        r"\bเบอร์\b", r"\bโทรศัพท์\b", r"\bมือถือ\b",
    ],
    "ที่อยู่": [
        r"\baddress\b", r"\bstreet\b", r"\bcity\b", r"\bstate\b",
        r"\bzip_?code\b", r"\bpostal\b", r"\bprovince\b",
        r"\bที่อยู่\b", r"\bจังหวัด\b", r"\bรหัสไปรษณีย์\b",
    ],
    "บัตรประชาชน/Passport": [
        r"\bid_?card\b", r"\bnational_?id\b", r"\bcitizen_?id\b",
        r"\bpassport\b", r"\bบัตรประชาชน\b", r"\bเลขบัตร\b",
    ],
    "วันเกิด/อายุ": [
        r"\bbirth_?date\b", r"\bdate_?of_?birth\b", r"\bdob\b",
        r"\bage\b", r"\bวันเกิด\b", r"\bอายุ\b",
    ],
    "LINE ID": [
        r"\bline_?id\b", r"\bline_?account\b",
    ],
    "IP Address": [
        r"\bip_?address\b", r"\bclient_?ip\b", r"\bremote_?addr\b",
        r"\bip\b(?!s\b|_?range)",
    ],
    "Cookie/Session": [
        r"\bcookie\b", r"\bsession_?id\b", r"\bsession_?token\b",
    ],
    "Username/Password": [
        r"\busername\b", r"\bpassword\b", r"\bpasswd\b",
        r"\bcredential\b", r"\blogin\b",
    ],
    "GPS/Location": [
        r"\blatitude\b", r"\blongitude\b", r"\bgps\b",
        r"\blocation\b", r"\bcoordinate\b", r"\bgeo\b",
    ],
    "รูปภาพ/ไบโอเมตริก": [
        r"\bphoto\b", r"\bpicture\b", r"\bavatar\b", r"\bface\b",
        r"\bfingerprint\b", r"\bbiometric\b",
        r"\bรูปภาพ\b", r"\bใบหน้า\b", r"\bลายนิ้วมือ\b",
    ],
    "บัญชีธนาคาร/การเงิน": [
        r"\bbank_?account\b", r"\baccount_?number\b",
        r"\bcredit_?card\b", r"\bcard_?number\b",
        r"\bบัญชี\b", r"\bธนาคาร\b",
    ],
    "MAC Address": [
        r"\bmac_?address\b", r"\bhw_?addr\b",
    ],
    "เลขประจำตัวผู้เสียภาษี": [
        r"\btax_?id\b", r"\btin\b",
        r"\bเลขผู้เสียภาษี\b",
    ],
    "ข้อมูลบริษัท/องค์กร": [
        r"\bcompany_?name\b", r"\borg_?name\b", r"\borganization\b",
        r"\bบริษัท\b", r"\bองค์กร\b",
    ],
}

# ── Masking Patterns ──
# Code patterns indicating data masking/anonymization
MASKING_PATTERNS = [
    r"\bmask\b", r"\bmasked\b", r"\bmasking\b",
    r"\bredact\b", r"\bredacted\b",
    r"\banonymize\b", r"\banonymized\b", r"\banonymise\b",
    r"\bpseudonymize\b",
    r"\bhash_?pii\b", r"\bhash_?data\b",
    r"\*{3,}",  # *** masking pattern
    r"x{3,}",  # xxx masking pattern
    r"\[REDACTED\]", r"\[MASKED\]",
    r"\.replace\(.+,\s*['\"][\*x]+['\"]\)",  # .replace(..., '***')
    r"data_?protect",
    r"\bencrypt\b", r"\bdecrypt\b",
    r"\bgdpr\b", r"\bpdpa\b",
]

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".htm",
    ".vue", ".svelte", ".php", ".rb", ".go", ".java",
    ".json", ".yaml", ".yml", ".env", ".csv",
    ".sql", ".prisma", ".graphql",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "dist",
    "build", "venv", ".venv", "env", ".env",
    "vendor", "bower_components", ".cache",
}

# Max file size to scan (500KB)
MAX_FILE_SIZE = 500 * 1024


def scan_app_for_pii(source_path: str) -> dict:
    """
    Scan an app's source directory for PII fields and masking patterns.

    Returns:
        {
            "pii_fields": ["ชื่อ-นามสกุล", "อีเมล", ...],
            "masking_detected": bool,
            "masking_patterns": ["mask function found in app.py", ...],
            "files_scanned": int,
            "scan_details": [
                {"file": "app.py", "line": 15, "field": "email", "category": "อีเมล"},
                ...
            ]
        }
    """
    if not source_path or not os.path.isdir(source_path):
        return {
            "pii_fields": [],
            "masking_detected": False,
            "masking_patterns": [],
            "files_scanned": 0,
            "scan_details": [],
        }

    found_pii = {}  # category → set of (file, line, match)
    found_masking = []
    files_scanned = 0
    scan_details = []

    for root, dirs, files in os.walk(source_path):
        # Skip irrelevant directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SCANNABLE_EXTENSIONS:
                continue

            fpath = os.path.join(root, fname)

            # Skip too-large files
            try:
                if os.path.getsize(fpath) > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            files_scanned += 1
            rel_path = os.path.relpath(fpath, source_path)

            # Scan for PII fields
            for category, patterns in PII_PATTERNS.items():
                for pattern in patterns:
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        if category not in found_pii:
                            found_pii[category] = set()

                        # Find line number
                        line_num = content[:match.start()].count("\n") + 1
                        key = (rel_path, line_num, match.group())
                        if key not in found_pii[category]:
                            found_pii[category].add(key)
                            scan_details.append({
                                "file": rel_path,
                                "line": line_num,
                                "field": match.group(),
                                "category": category,
                            })

            # Scan for masking patterns
            for pattern in MASKING_PATTERNS:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_num = content[:match.start()].count("\n") + 1
                    found_masking.append({
                        "file": rel_path,
                        "line": line_num,
                        "pattern": match.group(),
                    })

    # Deduplicate PII categories
    pii_categories = sorted(found_pii.keys())

    # Deduplicate masking by file — structured so the frontend can format
    # the sentence per locale ("Found 'X' in Y (line N)" / "X 'P' Y N行目" etc.)
    masking_files = set()
    masking_summary = []
    for m in found_masking:
        key = f"{m['file']}:{m['pattern']}"
        if key not in masking_files:
            masking_files.add(key)
            masking_summary.append({
                "pattern": m["pattern"],
                "file": m["file"],
                "line": m["line"],
            })

    # Limit scan details to most important (max 50 entries)
    scan_details_limited = scan_details[:50]

    return {
        "pii_fields": pii_categories,
        "masking_detected": len(found_masking) > 0,
        "masking_patterns": masking_summary[:20],
        "files_scanned": files_scanned,
        "scan_details": scan_details_limited,
    }


def generate_ropa_markdown(apps_data: list[dict], ntp_info: dict, exporter: str) -> str:
    """
    Generate ROPA report in Markdown format matching the PDF template.

    apps_data: list of {
        app_name, purpose, pii_fields, usage, retention_period,
        security_measures, status
    }
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    lines = []
    lines.append("# บันทึกรายการกิจกรรมการประมวลผลข้อมูลส่วนบุคคล (ROPA)")
    lines.append("")
    lines.append("## Record of Processing Activities")
    lines.append("")
    lines.append(f"- **วันที่ออกรายงาน**: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append(f"- **ผู้ออกรายงาน**: {exporter}")
    lines.append(f"- **ระบบ**: IVS - Internal Vibe Server")
    lines.append(f"- **จำนวนกิจกรรม**: {len(apps_data)}")
    lines.append("")

    # NTP info
    lines.append("## แหล่งเวลาอ้างอิง (NTP)")
    lines.append("")
    lines.append(f"- **NTP Server**: {ntp_info.get('ntp_server', 'N/A')}")
    lines.append(f"- **Server Name**: {ntp_info.get('ntp_server_name', 'N/A')}")
    lines.append(f"- **Offset**: {ntp_info.get('offset_ms', 0)} ms")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ROPA Table
    lines.append("## ส่วนที่ 2: บันทึกรายการกิจกรรม")
    lines.append("")
    lines.append("| ลำดับ | ชื่อกิจกรรม | วัตถุประสงค์ | ข้อมูลส่วนบุคคลที่เก็บรวบรวม | การใช้/เปิดเผย | ระยะเวลา | มาตรการรักษาความปลอดภัย |")
    lines.append("|-------|-------------|-------------|-------------------------------|---------------|---------|------------------------|")

    for i, app in enumerate(apps_data, 1):
        name = app.get("app_name", "-")
        purpose = (app.get("purpose", "") or "-").replace("|", "\\|").replace("\n", " ")
        pii = ", ".join(app.get("pii_fields", [])) or "-"
        usage = app.get("usage", name)
        retention = app.get("retention_period", "") or "-"

        # Security measures
        measures = []
        measures.append("User Management (IVS)")
        measures.append("Audit Log (IVS)")
        if app.get("has_masking"):
            measures.append("Data Masking")
        if app.get("security_notes"):
            measures.append(app["security_notes"])
        security = ", ".join(measures)

        pii_escaped = pii.replace("|", "\\|")
        security_escaped = security.replace("|", "\\|")

        lines.append(f"| {i} | {name} | {purpose} | {pii_escaped} | {usage} | {retention} | {security_escaped} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Security measures detail
    lines.append("## มาตรการรักษาความปลอดภัยของระบบ IVS")
    lines.append("")
    lines.append("- **User Management**: การจัดการสิทธิ์ผู้ใช้ (Admin/Developer/Viewer)")
    lines.append("- **Audit Log**: บันทึกการเข้าถึงและดำเนินการทั้งหมด (NTP-synced timestamps)")
    lines.append("- **Docker Isolation**: แต่ละแอปรันใน container แยก")
    lines.append("- **Network Isolation**: Docker network แยกสำหรับแอป")
    lines.append("")

    # Data subject rights
    lines.append("## สิทธิของเจ้าของข้อมูลส่วนบุคคล")
    lines.append("")
    lines.append("- การใช้สิทธิ์เข้าถึงข้อมูลส่วนบุคคล")
    lines.append("- การเข้าถึงข้อมูลส่วนบุคคล")
    lines.append("- การแก้ไขเปลี่ยนแปลงข้อมูลส่วนบุคคล")
    lines.append("- การระงับ/จำกัดการใช้ข้อมูลส่วนบุคคล")
    lines.append("- การถอนความยินยอม")
    lines.append("- การร้องเรียน")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## กฎหมายอ้างอิง")
    lines.append("")
    lines.append("- พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 (PDPA)")
    lines.append("- พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2550")
    lines.append("")

    return "\n".join(lines)
