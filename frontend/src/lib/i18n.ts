export type Locale = "th" | "en" | "en-EU" | "ja";

/**
 * `th` and `en` are full dictionaries. `en-EU` and `ja` are OVERLAYS
 * that contain only regulator-specific compliance strings (GDPR, APPI);
 * everything else falls back to `en` via t().
 *
 * Regulatory mapping:
 *   th     — PDPA (พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562)
 *   en     — generic English, refers to PDPA by default
 *   en-EU  — GDPR (Regulation (EU) 2016/679, Privacy by Design Art. 25)
 *   ja     — APPI (個人情報の保護に関する法律, 2003 + 2022 amendments)
 */
const translations: Record<Locale, Record<string, string>> = {
  th: {
    // Sidebar
    "nav.dashboard": "แดชบอร์ด",
    "nav.apps": "แอปพลิเคชัน",
    "nav.tunnels": "อุโมงค์เชื่อมต่อ",
    "nav.vault": "คลัง API Key",
    "nav.resources": "ทรัพยากร",
    "nav.settings": "ตั้งค่า",
    "nav.signout": "ออกจากระบบ",
    "nav.subtitle": "เกตเวย์องค์กร",

    // Login
    "login.title": "Internal Vibe Server",
    "login.subtitle": "เกตเวย์สำหรับแอป Vibe Code ภายในองค์กร",
    "login.username": "ชื่อผู้ใช้",
    "login.password": "รหัสผ่าน",
    "login.submit": "เข้าสู่ระบบ",
    "login.signing_in": "กำลังเข้าสู่ระบบ...",
    "login.default": "ค่าเริ่มต้น: admin / admin123",
    "login.username_placeholder": "กรอกชื่อผู้ใช้",
    "login.password_placeholder": "กรอกรหัสผ่าน",

    // Dashboard
    "dash.title": "แดชบอร์ด",
    "dash.subtitle": "ภาพรวมระบบและจัดการแอปพลิเคชัน",
    "dash.refresh": "รีเฟรช",
    "dash.refreshing": "กำลังรีเฟรช…",
    "dash.last_updated": "อัปเดตล่าสุด",
    "dash.refresh_failed": "รีเฟรชล้มเหลว",
    "dash.health": "สถานะระบบ",
    "dash.apps_count": "แอป",
    "dash.no_apps": "ยังไม่มีแอปพลิเคชัน",
    "dash.no_apps_hint": "อัปโหลดไฟล์ .zip ด้านบนเพื่อเริ่มต้น",
    "dash.applications": "แอปพลิเคชัน",

    // Deploy
    "deploy.title": "ดีพลอยแอปใหม่",
    "deploy.drag": "ลากวางไฟล์ .zip ที่นี่",
    "deploy.browse": "หรือคลิกเพื่อเลือกไฟล์",
    "deploy.name": "ชื่อแอป",
    "deploy.desc": "คำอธิบาย (ไม่บังคับ)",
    "deploy.submit": "ดีพลอยแอปพลิเคชัน",
    "deploy.deploying": "กำลังดีพลอย...",
    "deploy.uploading": "กำลังอัปโหลดและบิลด์...",
    "deploy.success": "ดีพลอยสำเร็จ!",
    "deploy.fail": "ดีพลอยล้มเหลว",
    "deploy.zip_only": "กรุณาอัปโหลดไฟล์ .zip เท่านั้น",
    "deploy.validating": "กำลังตรวจสอบโครงสร้าง...",
    "deploy.valid": "โครงสร้างถูกต้อง — พร้อม Deploy!",
    "deploy.invalid": "โครงสร้างไม่ถูกต้อง",
    "deploy.detected_type": "ตรวจพบ:",
    "deploy.fix_prompt_title": "แนะนำ: ใช้ Prompt นี้ให้ AI สร้างโครงสร้างใหม่",
    "deploy.copy_prompt": "คัดลอก Prompt",
    "deploy.prompt_copied": "คัดลอกแล้ว!",
    "deploy.warnings": "คำเตือน",
    "deploy.issues": "ปัญหาที่พบ",
    "deploy.cancel": "ยกเลิก",
    "deploy.reselect": "เลือกไฟล์ใหม่",
    "deploy.issue.fullstack_no_backend_main": "ไม่พบ backend/main.py",
    "deploy.issue.fullstack_backend_not_fastapi": "backend/main.py ไม่มี FastAPI — ต้องใช้ FastAPI",
    "deploy.issue.fullstack_no_backend_requirements": "ไม่พบ backend/requirements.txt",
    "deploy.issue.fullstack_no_frontend": "ไม่พบ frontend/dist/ หรือ frontend/package.json",
    "deploy.issue.nodejs_no_start_script": "package.json ไม่มี \"start\" script หรือ \"main\" field",
    "deploy.issue.nodejs_invalid_package_json": "package.json อ่านไม่ได้ (JSON ไม่ถูกต้อง)",
    "deploy.issue.fastapi_no_requirements": "ไม่พบ requirements.txt",
    "deploy.issue.streamlit_no_requirements": "ไม่พบ requirements.txt",
    "deploy.issue.python_no_main": "ไม่พบ main.py (entry point)",
    "deploy.issue.python_no_requirements": "ไม่พบ requirements.txt",
    "deploy.issue.unknown_structure": "ไม่พบไฟล์หลัก — ต้องมี index.html, package.json, หรือ main.py",
    "deploy.warn.node_modules_included": "มี node_modules/ อยู่ใน zip — ไม่จำเป็น (ทำให้ไฟล์ใหญ่)",
    "deploy.warn.venv_included": "มี .venv/ หรือ venv/ อยู่ใน zip — ไม่จำเป็น",
    "deploy.warn.git_included": "มี .git/ อยู่ใน zip — ไม่จำเป็น",
    "deploy.warn.nodejs_no_lockfile": "ไม่มี package-lock.json — แนะนำให้ใส่เพื่อความเสถียร",
    "deploy.warn.fastapi_no_uvicorn": "requirements.txt ไม่มี uvicorn — อาจต้องเพิ่ม",
    "deploy.warn.fullstack_no_dist": "ไม่มี frontend/dist/ — IVS จะ build ให้แต่จะช้ากว่า",
    "deploy.warn.vite_prebuilt_detected": "ตรวจพบ Vite app พร้อม dist/ — จะ deploy เป็น Static Web",
    "deploy.warn.vite_preview_detected": "ตรวจพบ Vite app พร้อม vite preview — จะใช้ npm start",
    "deploy.warn.custom_dockerfile": "ใช้ Dockerfile ที่มากับโปรเจค — IVS จะไม่สร้างให้อัตโนมัติ",
    "deploy.warn.dockerfile_cmd_missing_file": "⛔ Dockerfile CMD ชี้ไปไฟล์ที่ไม่มี: {file} — อาจรันไม่ได้",
    "deploy.warn.dockerfile_db_dependency": "⛔ ไฟล์ {file} ใช้ {db} — Docker container ไม่มี Database จะเกิด Connection Error",
    "deploy.warn.multiple_server_files": "มีหลาย server file: {files} — ตรวจสอบว่า Dockerfile CMD ชี้ถูกตัว",
    "deploy.issue.vite_no_start_script": "Vite app ไม่มี start script — เพิ่ม \"start\": \"vite preview --port 3000 --host\" ใน package.json",
    "deploy.file_too_large_title": "⚠️ ไฟล์ขนาดใหญ่เกินไป",
    "deploy.file_too_large_msg": "ไฟล์ของคุณมีขนาดใหญ่เกินไป ({size} MB) กรุณาตรวจสอบว่าได้ลบโฟลเดอร์ node_modules หรือ .venv ออกก่อนบีบอัดไฟล์แล้วหรือไม่ เพื่อป้องกันระบบค้าง",
    "deploy.auto_sanitize": "ยืนยัน — ระบบจะลบไฟล์ขยะอัตโนมัติ",
    "deploy.auto_sanitize_desc": "IVS จะลบ node_modules, .venv, pnpm-lock.yaml อัตโนมัติก่อน Build",
    "deploy.cancel_upload": "ยกเลิก — เลือกไฟล์ใหม่",
    "deploy.build_log_title": "Build Log (Real-time)",
    "deploy.build_timeout": "Build หมดเวลา! เกิน 3 นาที",
    "deploy.build_success": "Build สำเร็จ!",
    "deploy.build_error": "Build ล้มเหลว",
    "deploy.type.static": "Static Web",
    "deploy.type.nodejs": "Node.js",
    "deploy.type.fastapi": "FastAPI",
    "deploy.type.streamlit": "Streamlit",
    "deploy.type.fullstack": "Fullstack",
    "deploy.type.python": "Python",
    "deploy.type.unknown": "ไม่ทราบ",

    // App Card
    "app.start": "เปิด",
    "app.stop": "หยุด",
    "app.restart": "รีสตาร์ท",
    "app.delete": "ลบ",
    "app.delete_confirm": "ยืนยันลบ",
    "app.export": "Export",
    "app.export_tooltip": "ดาวน์โหลดโปรแกรม + ข้อมูล เป็นไฟล์ .zip",
    "app.export_owner_only_tooltip": "เฉพาะผู้ Deploy แอปนี้เท่านั้นที่ Export ได้ (ป้องกันความละเมิดลิขสิทธิ์)",
    "app.privacy_review": "ประกาศแจ้งเตือน",
    "app.privacy_review_tooltip": "ดู / เปลี่ยนการยอมรับประกาศแจ้งเตือน PDPA ของแอปนี้",

    // Export Modal
    "export.title_working": "กำลังสร้างไฟล์ Export…",
    "export.subtitle_working": "กำลังรวบรวมโปรแกรมและข้อมูลของแอป",
    "export.title_done": "Export สำเร็จ",
    "export.subtitle_done": "ดาวน์โหลดไฟล์ .zip เพื่อเก็บไว้สำรอง",
    "export.title_error": "Export ล้มเหลว",
    "export.subtitle_error": "เกิดข้อผิดพลาดระหว่างการ export",
    "export.target_app": "แอปที่จะ Export",
    "export.step1": "1. คัดลอก Dockerfile + source code",
    "export.step2": "2. คัดลอกข้อมูลจาก container (data, uploads, db)",
    "export.step3": "3. บีบอัดเป็นไฟล์ .zip พร้อม metadata และวิธี import กลับ",
    "export.please_wait": "กรุณารอสักครู่ — อาจใช้เวลาประมาณ 10–30 วินาที",
    "export.bundle_size": "ขนาดไฟล์",
    "export.data_paths_copied": "จำนวนพาธข้อมูลที่ export ได้",
    "export.filename": "ชื่อไฟล์",
    "export.no_data_warning": "ไม่พบข้อมูล persistent ใน container — แอปนี้อาจไม่ได้เก็บข้อมูลภายใน หรือ container ไม่ได้รันอยู่",
    "export.warnings": "คำเตือน",
    "export.tip": "เปิดไฟล์ .zip เพื่อดู README.md ที่อธิบายวิธี import แอปกลับเข้า IVS",
    "export.download": "ดาวน์โหลด .zip",
    "export.cancel": "ยกเลิก",
    "export.close": "ปิด",

    // Delete Confirmation Modal
    "delete.title": "ลบแอปพลิเคชันนี้?",
    "delete.subtitle": "การดำเนินการนี้ไม่สามารถย้อนกลับได้",
    "delete.target_app": "แอปที่จะลบ",
    "delete.what_lost_title": "สิ่งที่จะหายไปถาวร:",
    "delete.lost.container": "Container และ Docker image ของแอปนี้",
    "delete.lost.data": "ข้อมูลและไฟล์ทั้งหมดที่แอปสร้างขึ้น (ฐานข้อมูล, uploads, cache)",
    "delete.lost.logs": "ประวัติ build logs และ runtime logs",
    "delete.lost.port": "พอร์ตที่แอปใช้ จะถูกปล่อยให้แอปอื่นใช้แทน",
    "delete.lost.access": "URL ที่ผู้ใช้เคยเข้าถึงจะใช้งานไม่ได้อีก",
    "delete.irreversible": "ไม่มีการ rollback หลังจากกดยืนยัน หากต้องการสำรองข้อมูล กรุณา export ก่อนลบ",
    "delete.type_to_confirm": "พิมพ์ชื่อแอปเพื่อยืนยัน:",
    "delete.cancel": "ยกเลิก",
    "delete.confirm": "ลบถาวร",
    "delete.deleting": "กำลังลบ…",
    "delete.export_first_title": "ยังไม่ได้สำรองข้อมูล?",
    "delete.export_first_desc": "Export โปรแกรม + ข้อมูลไว้ก่อนลบ จะได้ import กลับมาได้ภายหลัง",
    "delete.export_first_button": "Export ก่อนลบ",
    "app.logs": "ดูล็อก",
    "app.hide_logs": "ซ่อนล็อก",
    "app.no_logs": "ไม่มีล็อก",
    "app.status.running": "กำลังทำงาน",
    "app.status.stopped": "หยุดแล้ว",
    "app.status.building": "กำลังบิลด์",
    "app.status.error": "ข้อผิดพลาด",

    // System Health
    "health.docker": "Docker",
    "health.dns": "DNS",
    "health.cpu": "CPU",
    "health.ram": "RAM",
    "health.storage": "พื้นที่เก็บข้อมูล",

    // Apps Page
    "apps.title": "แอปพลิเคชัน",
    "apps.subtitle": "จัดการแอป Vibe Code ที่ดีพลอยแล้ว",
    "apps.search": "ค้นหาแอป...",
    "apps.filter.all": "ทั้งหมด",
    "apps.filter.running": "ทำงาน",
    "apps.filter.stopped": "หยุด",
    "apps.filter.building": "บิลด์",
    "apps.filter.error": "ผิดพลาด",
    "apps.no_match": "ไม่พบแอปตามตัวกรอง",

    // Tunnels
    "tunnel.title": "จัดการอุโมงค์เชื่อมต่อ",
    "tunnel.subtitle": "แชร์แอปสู่อินเทอร์เน็ตด้วยอุโมงค์จำกัดเวลา",
    "tunnel.create": "สร้างอุโมงค์ใหม่",
    "tunnel.app_label": "แอปพลิเคชัน",
    "tunnel.app_select": "เลือกแอป...",
    "tunnel.duration": "ระยะเวลา",
    "tunnel.open": "เปิดอุโมงค์",
    "tunnel.creating": "กำลังสร้าง...",
    "tunnel.active": "อุโมงค์ที่เปิดอยู่",
    "tunnel.none": "ยังไม่มีอุโมงค์",
    "tunnel.revoke": "ปิด",
    "tunnel.privacy": "ประกาศ",
    "tunnel.privacy_tooltip": "ดู / เปลี่ยนการยอมรับประกาศแจ้งเตือน PDPA สำหรับแอปนี้",
    "tunnel.share": "ส่งอีเมล",
    "tunnel.share_tooltip": "ส่งลิงก์ทางอีเมลพร้อมประกาศแจ้งเตือน PDPA และวิธีใช้งาน",
    // Share-by-email modal
    "tunnel.share.title": "ส่งลิงก์อุโมงค์ทางอีเมล",
    "tunnel.share.subtitle": "เนื้อหาประกอบด้วยประกาศ PDPA + ลิงก์ + วิธีใช้งาน + คำเตือนความปลอดภัย",
    "tunnel.share.recipient": "อีเมลผู้รับ (ไม่บังคับ)",
    "tunnel.share.recipient_placeholder": "name@example.com — เว้นว่างถ้าจะกรอกเองในแอปอีเมล",
    "tunnel.share.recipient_hint": "เปิดได้หลายผู้รับโดยคั่นด้วย , (comma)",
    "tunnel.share.extra_note": "หมายเหตุเพิ่มเติม (ไม่บังคับ)",
    "tunnel.share.extra_note_placeholder": "เช่น “กรุณาเข้าใช้งานก่อน 17:00 น.”",
    "tunnel.share.preview": "เนื้อหาที่จะถูกส่ง",
    "tunnel.share.subject_label": "หัวเรื่อง",
    "tunnel.share.loading_notice": "กำลังโหลดประกาศแจ้งเตือน…",
    "tunnel.share.tip": "กดปุ่มล่างจะเปิดแอปอีเมลของท่าน (Mail / Outlook / Gmail บน macOS) พร้อมเนื้อหานี้ — หากแอปไม่เปิดให้ใช้ปุ่ม “คัดลอกเนื้อหา” แทน",
    "tunnel.share.copy": "คัดลอกเนื้อหา",
    "tunnel.share.copied": "คัดลอกแล้ว",
    "tunnel.share.cancel": "ยกเลิก",
    "tunnel.share.open_mail": "เปิดในแอปอีเมล",
    "tunnel.col.app": "แอป",
    "tunnel.col.url": "URL สาธารณะ",
    "tunnel.col.status": "สถานะ",
    "tunnel.col.time": "เวลาเหลือ",
    "tunnel.col.action": "จัดการ",
    "tunnel.dur.1m": "1 นาที",
    "tunnel.dur.10m": "10 นาที",
    "tunnel.dur.1h": "1 ชั่วโมง",
    "tunnel.dur.3h": "3 ชั่วโมง",
    "tunnel.dur.24h": "24 ชั่วโมง",

    // Vault
    "vault.title": "คลัง API Key",
    "vault.subtitle": "จัดการ API Key ขององค์กร (เข้ารหัส AES-256)",
    "vault.add": "+ เพิ่ม Key",
    "vault.cancel": "ยกเลิก",
    "vault.add_title": "เพิ่ม API Key ใหม่",
    "vault.key_name": "ชื่อ Key (เช่น Production API Key)",
    "vault.provider": "ผู้ให้บริการ (เช่น OpenAI, Claude)",
    "vault.category": "หมวดหมู่",
    "vault.key_value": "ค่า API Key",
    "vault.description": "คำอธิบาย (ไม่บังคับ)",
    "vault.save": "บันทึก Key",
    "vault.saving": "กำลังเข้ารหัสและบันทึก...",
    "vault.search": "ค้นหา key...",
    "vault.no_keys": "ยังไม่มี API Key",
    "vault.encrypted": "เข้ารหัสแล้ว",
    "vault.copy": "คัดลอก",
    "vault.copied": "คัดลอกแล้ว",
    "vault.copy_failed": "ผิดพลาด",
    "vault.copy_tooltip": "ถอดรหัส + คัดลอก API key เข้า clipboard (บันทึก audit log)",

    // Privacy Notice popup
    "pn.default_title": "ประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล",
    "pn.default_detail": "แอปพลิเคชันนี้มีการเก็บรวบรวม ใช้ หรือเปิดเผยข้อมูลส่วนบุคคลของท่าน",
    "pn.review_badge": "ดู / เปลี่ยนการยอมรับ",
    "pn.disabled_banner": "แอปนี้ปิดใช้งานประกาศแจ้งเตือน — ไม่มีการขอความยินยอมสำหรับการเข้าใช้งานครั้งต่อไป",
    "pn.current_status": "สถานะปัจจุบัน",
    "pn.status_accepted": "✓ ยอมรับแล้ว",
    "pn.status_declined": "✗ ปฏิเสธ",
    "pn.recorded_at": "บันทึกเมื่อ",
    "pn.link_policy": "นโยบายคุ้มครองข้อมูลส่วนบุคคล (Privacy Policy)",
    "pn.link_full_notice": "ประกาศแจ้งเตือนฉบับเต็ม",
    "pn.accept_current": "✓ ยอมรับแล้ว (สถานะปัจจุบัน)",
    "pn.switch_to_accept": "เปลี่ยนเป็น: ยอมรับ",
    "pn.decline_current": "✗ ปฏิเสธแล้ว (สถานะปัจจุบัน)",
    "pn.switch_to_decline": "เปลี่ยนเป็น: ปฏิเสธ",
    "pn.close": "ปิด",
    "pn.saving": "กำลังบันทึก…",
    "pn.accept_and_enter": "ยอมรับและเข้าใช้งาน",
    "pn.decline": "ปฏิเสธ",
    "pn.legal_footer": "ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 (PDPA) §19 — ท่านสามารถเปลี่ยนการยินยอมได้ทุกเมื่อ",

    // Tunnel share email body
    "tunnel.share.subject_suffix": "ลิงก์เข้าใช้งานพร้อมประกาศ PDPA",
    "tunnel.share.body.greeting": "สวัสดีครับ/ค่ะ,",
    "tunnel.share.body.intro_l1": 'ขอเรียนเชิญใช้งานแอปพลิเคชัน "{app}" ผ่านลิงก์อุโมงค์ชั่วคราว',
    "tunnel.share.body.intro_l2": "กรุณาอ่านประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล (PDPA) ก่อนเข้าใช้งาน",
    "tunnel.share.body.section_notice": "⚠️  ประกาศแจ้งเตือนการเก็บรวบรวมข้อมูลส่วนบุคคล",
    "tunnel.share.body.no_notice": "(แอปนี้ยังไม่ได้ตั้งค่าประกาศแจ้งเตือน PDPA — แนะนำให้ผู้ดูแลตั้งค่าก่อนเปิดให้บุคคลภายนอก)",
    "tunnel.share.body.section_link": "🔗  ลิงก์เข้าใช้งาน (Tunnel)",
    "tunnel.share.body.expires_at": "ลิงก์นี้จะหมดอายุ",
    "tunnel.share.body.section_howto": "📖  วิธีใช้งาน",
    "tunnel.share.body.howto_1": "1. คลิกลิงก์ข้างต้นเพื่อเปิดแอป",
    "tunnel.share.body.howto_2": "2. หากแอปแสดงประกาศแจ้งเตือน PDPA — กรุณาอ่านและพิจารณาก่อนกดยอมรับ",
    "tunnel.share.body.howto_3": "3. การยอมรับ/ปฏิเสธของท่านจะถูกบันทึกในระบบตาม PDPA §19",
    "tunnel.share.body.howto_4": "4. ท่านสามารถเปลี่ยนการยอมรับได้ทุกเมื่อโดยกลับมาที่ลิงก์นี้",
    "tunnel.share.body.section_security": "🔒  ข้อควรระวังด้านความปลอดภัย",
    "tunnel.share.body.security_1": "• ลิงก์นี้เป็นการเข้าถึงระบบภายในผ่านเครือข่ายภายนอก",
    "tunnel.share.body.security_2": "• มีความเสี่ยงที่ข้อมูลอาจรั่วไหลหากใช้งานไม่เหมาะสม",
    "tunnel.share.body.security_3": "• กรุณาใช้งานตามนโยบายของหน่วยงานท่าน",
    "tunnel.share.body.security_4": "• หากพบพฤติกรรมผิดปกติ กรุณาแจ้งผู้ดูแลระบบทันที",
    "tunnel.share.body.section_note": "💬  หมายเหตุจากผู้ส่ง",
    "tunnel.share.body.signoff": "ส่งจาก IVS — Internal Vibe Server",

    // PII suggestion checklist (Settings → PDPA tab)
    "pii.full_name": "ชื่อ-นามสกุล",
    "pii.email": "อีเมล",
    "pii.phone": "เบอร์โทรศัพท์",
    "pii.address": "ที่อยู่",
    "pii.national_id": "บัตรประชาชน/Passport",
    "pii.dob": "วันเกิด/อายุ",
    "pii.line_id": "LINE ID",
    "pii.photo_bio": "รูปภาพ/ไบโอเมตริก",
    "pii.bank_account": "บัญชีธนาคาร/การเงิน",
    "pii.tax_id": "เลขประจำตัวผู้เสียภาษี",
    "pii.org_info": "ข้อมูลบริษัท/องค์กร",

    // Misc inline strings
    "user_delete.reassigned_suffix": "แอปถูกโอนสิทธิ์ไปที่",
    "settings.export_success": "Export สำเร็จ",
    "settings.activities_count": "กิจกรรม",
    "settings.pn_saved": "บันทึก Privacy Notice สำเร็จ",
    "settings.pdpa.found": "พบ",
    "settings.pdpa.not_found": "ไม่พบ",
    "settings.pdpa.add_all_detected": "เพิ่มทั้งหมดที่ตรวจพบ",
    "settings.pn_detail_placeholder": "แอปพลิเคชันนี้มีการเก็บรวบรวม ใช้ หรือเปิดเผยข้อมูลส่วนบุคคลของท่าน เพื่อวัตถุประสงค์ในการให้บริการ...",
    "settings.pn_preview_placeholder": "รายละเอียดจะแสดงที่นี่...",
    "deploy.auto_sanitize_note": "Auto-Sanitize จะลบไฟล์ขยะอัตโนมัติ",
    "deploy.close": "ปิด",
    "datepicker.clear": "ล้าง",
    "datepicker.today": "วันนี้",

    // Vault delete confirmation
    "vault.delete_modal.title": "ลบ API Key",
    "vault.delete_modal.desc_prefix": "ยืนยันลบ key",
    "vault.delete_modal.desc_suffix": "การกระทำนี้ย้อนกลับไม่ได้ กรุณาใส่รหัสผ่านของท่านเพื่อยืนยัน",
    "vault.delete_modal.consequence_1": "Key encrypted value จะถูกลบจากฐานข้อมูลถาวร — ไม่สามารถกู้คืน",
    "vault.delete_modal.consequence_2": "แอปที่ inject key นี้จะใช้งานไม่ได้จนกว่าจะ deploy ใหม่ด้วย key ใหม่",
    "vault.delete_modal.consequence_3": "บันทึก audit log ระดับ WARNING พร้อมชื่อ key และเวลาที่กดยืนยัน",
    "vault.delete_modal.legal_note": "API key เป็นข้อมูลความลับที่อาจมีต้นทุนทางการเงิน — การลบต้องมีหลักฐานยืนยันตัวตน",
    "vault.delete_modal.confirm": "ยืนยันลบ",
    "vault.delete_confirm": "ยืนยันลบ key",

    // Settings
    "settings.title": "ตั้งค่า",
    "settings.subtitle": "จัดการผู้ใช้และประวัติการใช้งาน",
    "settings.tab.users": "จัดการผู้ใช้",
    "settings.tab.logs": "ประวัติการใช้งาน",
    "settings.add_user": "+ เพิ่มผู้ใช้",
    "settings.create_user": "สร้างผู้ใช้ใหม่",
    "settings.username": "ชื่อผู้ใช้",
    "settings.email": "อีเมล",
    "settings.password": "รหัสผ่าน",
    "settings.role": "สิทธิ์",
    "settings.create": "สร้างผู้ใช้",
    "settings.creating": "กำลังสร้าง...",
    "settings.col.user": "ผู้ใช้",
    "settings.col.email": "อีเมล",
    "settings.col.role": "สิทธิ์",
    "settings.col.status": "สถานะ",
    "settings.col.created": "สร้างเมื่อ",
    "settings.col.actions": "จัดการ",
    "settings.active": "ใช้งาน",
    "settings.disabled": "ปิดใช้งาน",
    "settings.disable": "ปิดใช้งาน",
    "settings.enable": "เปิดใช้งาน",
    "settings.ntp.title": "เวลาอ้างอิง NTP (พ.ร.บ. คอมพิวเตอร์)",
    "settings.ntp.authority": "หน่วยงาน",
    "settings.ntp.synced": "Sync แล้ว",
    "settings.log.title_compliance": "บันทึกเหตุการณ์ (พ.ร.บ. คอมพิวเตอร์)",
    "settings.log.compliance_badge": "พ.ร.บ. คอมฯ Compliant",
    "settings.log.time": "เวลา",
    "settings.log.level": "ระดับ",
    "settings.log.user": "ผู้ใช้",
    "settings.log.action": "การดำเนินการ",
    "settings.log.resource": "ทรัพยากร",
    "settings.log.details": "รายละเอียด",
    "settings.log.request_id": "Tracking ID",
    "settings.no_logs": "ยังไม่มีประวัติ",
    "settings.col.app_access": "สิทธิ์เข้าถึงแอป",
    "settings.set_access": "กำหนดสิทธิ์",
    "settings.full_access": "เข้าถึงทั้งหมด",
    "settings.no_access": "ยังไม่กำหนด",
    "settings.apps_assigned": "แอปที่กำหนด",
    "settings.access_title": "กำหนดสิทธิ์เข้าถึงแอป",
    "settings.access_desc": "เลือกแอปที่ผู้ใช้สามารถเข้าถึงได้",
    "settings.access_all": "เข้าถึงแอปทั้งหมด",
    "settings.access_all_desc": "ผู้ใช้สามารถเข้าถึงแอปทั้งหมดในระบบ",
    "settings.access_select": "เลือกแอปที่อนุญาต",
    "settings.apps_selected": "แอปที่เลือก",
    "settings.save_access": "บันทึกสิทธิ์",
    "settings.saving_access": "กำลังบันทึก...",
    "settings.no_apps_to_assign": "ยังไม่มีแอปในระบบ",

    // Settings - Audit Export
    "settings.tab.dns": "DNS & โดเมน",
    "settings.tab.pdpa": "PDPA",
    "settings.tab.gitea": "Gitea",
    "settings.tab.autostart": "Auto-Start",
    "settings.export_logs": "Export .zip",
    "settings.exporting": "กำลัง Export...",
    "settings.export_history": "ประวัติการ Export",
    "settings.export_no_history": "ยังไม่เคย Export",
    // Date-range presets for audit export
    "settings.export_range": "ช่วงเวลา",
    "settings.export_range_7d": "7 วัน",
    "settings.export_range_30d": "30 วัน",
    "settings.export_range_90d": "90 วัน",
    "settings.export_range_all": "ทั้งหมด",
    "settings.export_range_custom": "กำหนดเอง",
    "settings.export_range_from": "ตั้งแต่",
    "settings.export_range_to": "ถึง",
    "settings.export_range_all_label": "ทั้งหมด",
    "settings.export_range_col": "ช่วงเวลา",
    "settings.export_files_col": "ไฟล์",
    "settings.export_chunk_label": "แบ่ง chunk ไฟล์ละ",
    "settings.export_chunk_unit": "records",
    "settings.export_chunk_tip": "ถ้า log เยอะ ระบบจะแบ่งเป็นหลายไฟล์ภายใน .zip เดียวเพื่อเปิดอ่านง่าย",
    "settings.export_chunk_note": "ระบบจะรวมทุกไฟล์ใน .zip เดียว และคำนวณ SHA-256 ของทั้ง bundle เพื่อตรวจสอบความสมบูรณ์",
    "settings.export_history_count_suffix": "รายการในประวัติ",

    // Pagination
    "pagination.showing": "แสดง",
    "pagination.of": "จาก",
    "pagination.per_page": "ต่อหน้า",
    "pagination.first": "หน้าแรก",
    "pagination.prev": "หน้าก่อน",
    "pagination.next": "หน้าถัดไป",
    "pagination.last": "หน้าสุดท้าย",
    "settings.export_date_tooltip": "วันที่และเวลาที่ Export ครั้งนี้ — รูปแบบ ISO พร้อม timezone offset เพื่อใช้อ้างอิงทางกฎหมาย",
    "settings.export_history_item_label": "รายการ",
    "settings.log.time_tooltip": "เวลาที่บันทึก (UTC offset แสดงเพื่อความน่าเชื่อถือทางกฎหมาย)",
    "settings.log.item_label": "บันทึก",
    "settings.log.details_click": "คลิกเพื่อดูรายละเอียดเพิ่มเติม",
    "settings.log.no_detail": "(ไม่มีรายละเอียด)",

    // Audit log detail modal
    "audit_detail.title": "รายละเอียดเหตุการณ์",
    "audit_detail.subtitle": "ข้อมูลครบถ้วนของเหตุการณ์นี้ตาม พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560",
    "audit_detail.user": "ผู้ใช้",
    "audit_detail.user_id": "User ID",
    "audit_detail.resource": "ทรัพยากร",
    "audit_detail.ip_address": "IP Address",
    "audit_detail.request_id": "Request ID",
    "audit_detail.session_id": "Session ID",
    "audit_detail.ntp_source": "แหล่งเวลา NTP",
    "audit_detail.user_agent": "User Agent",
    "audit_detail.details": "รายละเอียดเต็ม",
    "audit_detail.no_details": "(ไม่มีรายละเอียด)",
    "audit_detail.copy": "คัดลอก",
    "audit_detail.copied": "คัดลอกแล้ว",
    "audit_detail.close": "ปิด",
    "audit_detail.legal_note": "บันทึกอ้างอิงเวลาจาก NTP ตามที่ พ.ร.บ. คอมพิวเตอร์ กำหนด",
    "settings.users_item_label": "ผู้ใช้",
    "tunnel.item_label": "tunnels",
    "res.per_app_item_label": "แอป",

    // Retention policy panel
    "retention.title": "นโยบายการเก็บข้อมูล (Data Retention)",
    "retention.subtitle": "กำหนดระยะเวลาเก็บ log แต่ละประเภท ระบบจะลบอัตโนมัติเมื่อเลยกำหนด",
    "retention.subtitle_short": "ตั้งค่าระยะเวลาเก็บ log ตาม พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560",
    "retention.click_to_expand": "คลิกเพื่อขยาย",
    "retention.click_to_collapse": "คลิกเพื่อยุบ",
    "retention.legal_note": "พ.ร.บ. ว่าด้วยการกระทำความผิดเกี่ยวกับคอมพิวเตอร์ พ.ศ. 2560 §26 — กำหนดเก็บข้อมูลจราจรทางคอมพิวเตอร์ขั้นต่ำ 90 วัน ทั่วไป 2 ปี (730 วัน) เจ้าพนักงานอาจสั่งให้เก็บนานกว่านี้",
    "retention.loading": "กำลังโหลด…",
    "retention.days": "วัน",
    "retention.range": "ช่วงที่ตั้งได้",
    "retention.default": "ค่าเริ่มต้น",
    "retention.at_minimum": "ค่าต่ำสุดตามกฎหมาย",
    "retention.over_recommended": "เกิน 2 ปี — ต้องมีคำสั่งเจ้าพนักงาน",
    "retention.save": "บันทึก",
    "retention.saving": "กำลังบันทึก…",
    "retention.saved": "✓ บันทึกแล้ว",
    "retention.reset": "ย้อนกลับ",
    "retention.purge_now": "ลบข้อมูลเก่าเดี๋ยวนี้",
    "retention.purging": "กำลังลบ…",
    "retention.purge_done": "✓ ลบข้อมูลเก่าสำเร็จ",
    "retention.purge_tooltip": "ปกติระบบลบให้อัตโนมัติทุกวัน คลิกถ้าต้องการลบทันที (เช่นหลังลดระยะเวลาเก็บ)",
    "retention.purge_confirm": "ยืนยันลบข้อมูลที่เกินกำหนดเก็บ? การกระทำนี้ย้อนกลับไม่ได้",

    // Password-confirm modal for the manual purge
    "retention.purge_modal_title": "ยืนยันการลบข้อมูล",
    "retention.purge_modal_desc": "การลบข้อมูลทันทีเป็นการกระทำที่ย้อนกลับไม่ได้ และอาจขัดกับข้อกำหนดทางกฎหมายหากระยะเวลาเก็บปัจจุบันยังต่ำกว่าที่กฎหมายกำหนด กรุณาใส่รหัสผ่านของคุณเพื่อยืนยันตัวตนก่อนทำรายการ",
    "retention.purge_modal_consequence_1": "ลบ records ที่เกินระยะเวลาเก็บจาก audit_logs, app_logs, resource_metrics และ exports ทันที",
    "retention.purge_modal_consequence_2": "ลบไฟล์ .zip ของ exports ที่เกินกำหนดออกจาก disk จริง (ไม่อยู่ใน trash)",
    "retention.purge_modal_consequence_3": "บันทึก audit log ระดับ WARNING พร้อมระบุ user, IP, และเวลาที่กดยืนยัน",
    "retention.purge_modal_legal": "พ.ร.บ. คอมพิวเตอร์ พ.ศ. 2560 §26 บังคับให้เก็บข้อมูลจราจรอย่างน้อย 90 วัน หากท่านลดระยะเวลาเก็บต่ำกว่าค่าทางกฎหมาย และลบข้อมูลผ่านปุ่มนี้ ท่านอาจมีความรับผิดทางกฎหมาย",
    "retention.purge_modal_confirm": "ยืนยันลบ",

    // Generic password-confirm modal
    "password_confirm.subtitle": "ต้องยืนยันตัวตนซ้ำก่อนทำรายการ",
    "password_confirm.consequences": "ผลกระทบของการกระทำนี้",
    "password_confirm.label": "รหัสผ่านของคุณ",
    "password_confirm.placeholder": "ใส่รหัสผ่านปัจจุบัน",
    "password_confirm.show": "แสดงรหัสผ่าน",
    "password_confirm.hide": "ซ่อนรหัสผ่าน",
    "password_confirm.cancel": "ยกเลิก",
    "password_confirm.working": "กำลังดำเนินการ…",
    "password_confirm.error_generic": "ไม่สามารถยืนยันได้ กรุณาลองใหม่",
    "password_confirm.forensic_note": "การพยายามยืนยันทุกครั้งจะถูกบันทึก audit log ระดับ WARNING — รวมถึงครั้งที่รหัสผ่านผิด",

    // User disable confirmation
    "user_disable.title": "ปิดใช้งานผู้ใช้",
    "user_disable.desc_prefix": "ยืนยันปิดใช้งานบัญชี",
    "user_disable.desc_suffix": "ผู้ใช้จะไม่สามารถเข้าใช้งาน IVS ได้จนกว่าจะถูกเปิดใช้งานอีกครั้ง กรุณาใส่รหัสผ่านของท่านเพื่อยืนยันตัวตน",
    "user_disable.consequence_1": "ผู้ใช้จะถูก logout ในเซสชันถัดไป และไม่สามารถ login ใหม่ได้",
    "user_disable.consequence_2": "แอปและทรัพยากรของผู้ใช้ยังคงอยู่ — ไม่ถูกลบ การเปิดใช้งานใหม่จะคืนสิทธิ์ทั้งหมด",
    "user_disable.consequence_3": "บันทึก audit log ระดับ WARNING พร้อมระบุผู้กดและเวลา",
    "user_disable.legal_note": "การจำกัดสิทธิ์เข้าใช้งานระบบสารสนเทศต้องมีการ audit trail ที่ตรวจสอบได้ — IVS จะเก็บบันทึกนี้ตาม policy retention",
    "user_disable.confirm": "ยืนยันปิดใช้งาน",

    "settings.delete_user": "ลบ",
    "settings.delete_user_tooltip": "ลบผู้ใช้ถาวร แอปทั้งหมดจะถูกโอนสิทธิ์ให้ Admin",
    "user_delete.title": "ลบผู้ใช้ถาวร",
    "user_delete.desc_prefix": "ยืนยันลบบัญชี",
    "user_delete.desc_suffix": "การดำเนินการนี้ไม่สามารถย้อนกลับได้ กรุณาใส่รหัสผ่านของท่านเพื่อยืนยัน",
    "user_delete.consequence_1": "บัญชีผู้ใช้และข้อมูล credentials จะถูกลบถาวร",
    "user_delete.consequence_2": "แอปที่ User เคย Deploy ไว้จะถูกโอนสิทธิ์ความเป็นเจ้าของให้ท่าน (Admin) อัตโนมัติ — แอปยังคงทำงานต่อ",
    "user_delete.consequence_3": "ประวัติใน Audit Log ยังคงเก็บไว้ตาม retention policy (ไม่ถูกลบ)",
    "user_delete.consequence_4": "ไม่สามารถลบ Admin คนสุดท้าย และไม่สามารถลบตัวเองได้",
    "user_delete.legal_note": "การลบผู้ใช้ต้องมีหลักฐานการโอนความรับผิดชอบที่ตรวจสอบได้ — IVS จะบันทึก audit log การลบและการโอนสิทธิ์แอป",
    "user_delete.confirm": "ยืนยันลบถาวร",
    "retention.purge_result": "ผลการลบ (จำนวน records)",
    // Per-type labels
    "retention.type.audit_logs": "บันทึกเหตุการณ์ระบบ (Audit Logs)",
    "retention.desc.audit_logs": "การล็อกอิน, deploy, ลบแอป, แก้ไข config — ใช้พิสูจน์ทางกฎหมาย",
    "retention.type.app_logs": "Log การทำงานของแอป (App Container Logs)",
    "retention.desc.app_logs": "stdout/stderr จาก container ทุกแอป — ข้อมูลจราจรตาม §26",
    "retention.type.resource_metrics": "ข้อมูลทรัพยากร (CPU/RAM/Disk History)",
    "retention.desc.resource_metrics": "สำหรับกราฟใน Resources page — ไม่ใช่ข้อมูลตามกฎหมาย",
    "retention.type.exports": "ไฟล์ Export .zip ที่สร้างไว้",
    "retention.desc.exports": "ไฟล์ที่ Export ในประวัติ จะถูกลบทั้ง DB record และไฟล์บน disk",
    "retention.type.exports_files_removed": "ไฟล์ที่ลบจาก disk",

    // PDPA
    "settings.pdpa_title": "PDPA — บันทึกรายการกิจกรรม (ROPA)",
    "settings.pdpa_desc": "ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562",
    "settings.pdpa_scan_all": "Scan ทุกแอป",
    "settings.pdpa_scanning": "กำลัง Scan...",
    "settings.pdpa_export": "Export ROPA",
    "settings.pdpa_exporting": "กำลัง Export...",
    "settings.pdpa_no_apps": "ยังไม่มีแอปที่ deploy",
    "settings.pdpa_col_app": "ชื่อกิจกรรม (แอป)",
    "settings.pdpa_col_purpose": "วัตถุประสงค์",
    "settings.pdpa_col_pii": "ข้อมูลส่วนบุคคล",
    "settings.pdpa_col_retention": "ระยะเวลา",
    "settings.pdpa_col_masking": "Data Masking",
    "settings.pdpa_col_status": "สถานะ",
    "settings.pdpa_col_action": "ดำเนินการ",
    "settings.pdpa_status_not_started": "ยังไม่เริ่ม",
    "settings.pdpa_status_partial": "กรอกบางส่วน",
    "settings.pdpa_status_complete": "ครบถ้วน",
    "settings.pdpa_edit": "แก้ไข",
    "settings.pdpa_scan": "Scan PII",
    "settings.pdpa_modal_title": "แก้ไขข้อมูล PDPA",
    "settings.pdpa_purpose_label": "วัตถุประสงค์ของการเก็บข้อมูล",
    "settings.pdpa_purpose_hint": "เช่น การให้บริการลูกค้า, การสนับสนุนลูกค้า",
    "settings.pdpa_pii_label": "ข้อมูลส่วนบุคคลที่เก็บรวบรวม",
    "settings.pdpa_pii_auto": "ตรวจพบอัตโนมัติ",
    "settings.pdpa_pii_manual": "เพิ่มเอง",
    "settings.pdpa_retention_label": "ระยะเวลาเก็บรักษาข้อมูล",
    "settings.pdpa_retention_hint": "เช่น 1 ปี, ตามสัญญา มาตรา 24 (3)",
    "settings.pdpa_security_label": "มาตรการรักษาความปลอดภัยเพิ่มเติม",
    "settings.pdpa_security_hint": "หมายเหตุเพิ่มเติมนอกจาก User Management + Audit Log",
    "settings.pdpa_save": "บันทึก",
    "settings.pdpa_saving": "กำลังบันทึก...",
    "settings.pdpa_cancel": "ยกเลิก",
    "settings.pdpa_scan_result": "ผลการ Scan PII",
    "settings.pdpa_files_scanned": "ไฟล์ที่ scan",
    "settings.pdpa_found_pii": "PII ที่พบ",
    "settings.pdpa_found_masking": "พบ Data Masking",
    "settings.pdpa_no_masking": "ไม่พบ Data Masking",
    "settings.pdpa_masking_warn": "แนะนำเพิ่มการ mask ข้อมูลส่วนบุคคลในแอป",
    "settings.pdpa_security_base": "มาตรการพื้นฐาน IVS: User Management, Audit Log, Docker Isolation",
    "settings.pn_title": "ประกาศแจ้งเตือน (Privacy Notice)",
    "settings.pn_desc": "ตั้งค่าการแจ้งเตือนก่อนเข้าใช้งานแอปพลิเคชัน ตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล",
    "settings.pn_toggle": "เปิดใช้ประกาศแจ้งเตือนของ IVS",
    "settings.pn_toggle_hint": "หากแอปมี Privacy Notice อยู่แล้วสามารถปิดได้",
    "settings.pn_notice_title": "หัวเรื่องประกอบแจ้งเตือน",
    "settings.pn_notice_detail": "รายละเอียดโดยย่อ",
    "settings.pn_notice_detail_hint": "ข้อความแจ้งเตือนที่จะแสดงก่อนเข้าใช้งาน",
    "settings.pn_policy_url": "นโยบายคุ้มครองข้อมูลส่วนบุคคล (Privacy Policy URL)",
    "settings.pn_notice_url": "ประกาศแจ้งเตือนโดยละเอียด (Privacy Notice URL)",
    "settings.pn_enabled": "เปิด",
    "settings.pn_disabled": "ปิด",
    "settings.pn_save": "บันทึก Privacy Notice",
    "settings.pn_saving": "กำลังบันทึก...",
    "settings.pn_col": "Privacy Notice",
    "settings.pn_preview": "ตัวอย่าง",
    "settings.export_filename": "ไฟล์",
    "settings.export_hash": "SHA-256 Hash",
    "settings.export_records": "จำนวนรายการ",
    "settings.export_date": "วันที่ Export",
    "settings.export_download": "ดาวน์โหลด",
    "settings.export_hash_note": "ค่า Hash ใช้เพื่อยืนยันความถูกต้องของเอกสาร สามารถใช้เป็นหลักฐานในศาลได้",

    // Settings - DNS Config
    "settings.dns_title": "ตั้งค่า Local DNS & Port Resolver",
    "settings.dns_desc": "ระบบชื่อโดเมนภายใน LAN เพื่อให้เข้าถึง App ได้ง่ายด้วยชื่อที่จำง่าย",
    "settings.dns_domain": "ชื่อโดเมนหลัก (Domain Suffix)",
    "settings.dns_domain_hint": "เช่น company.local, myorg.th, vibe.local",
    "settings.dns_server_ip": "IP เซิร์ฟเวอร์",
    "settings.dns_save": "บันทึกโดเมน",
    "settings.dns_saving": "กำลังบันทึก...",
    "settings.dns_example": "ตัวอย่าง: ถ้าตั้งเป็น",
    "settings.dns_example2": "แอปชื่อ myapp จะเข้าถึงได้ที่",
    "settings.dns_warning": "หลังเปลี่ยนชื่อโดเมน อาจต้องรีสตาร์ทบริการ DNS และ Proxy",
    "settings.dns_current": "โดเมนปัจจุบัน",

    // Settings - Gitea
    "settings.gitea_title": "Gitea — Git Server ประจำหน่วยงาน",
    "settings.gitea_desc": "ระบบจัดการโค้ดแบบ Self-hosted เหมือน GitHub ส่วนตัว",
    "settings.gitea_url": "URL เข้าใช้งาน Gitea",
    "settings.gitea_open": "เปิด Gitea",
    "settings.gitea_features_title": "ความสามารถหลัก",
    "settings.gitea_f1": "จัดเก็บ Source Code ทุกโปรเจกต์ขององค์กร",
    "settings.gitea_f2": "ระบบ Pull Request, Issues, Wiki ครบถ้วน",
    "settings.gitea_f3": "รองรับ Git LFS สำหรับไฟล์ขนาดใหญ่",
    "settings.gitea_f4": "จัดการสิทธิ์ผู้ใช้แยกตาม Organization / Team",

    // Gitea — How to use
    "settings.gitea_howto_title": "วิธีใช้งาน",
    "settings.gitea_howto_step1": "คลิกปุ่ม “เปิด Gitea” ด้านบนเพื่อเข้าหน้า login (เปิดในแท็บใหม่)",
    "settings.gitea_howto_step2": "กรอก Username / Password ตามที่ตั้งไว้ในบล็อก Credentials ด้านล่าง (ค่าเริ่มต้นต้องเปลี่ยนก่อนใช้งานจริง)",
    "settings.gitea_howto_step3": "สร้าง Repository ใหม่ผ่าน + ที่มุมขวาบน แล้วใส่ชื่อ + คำอธิบาย + ระดับ visibility",
    "settings.gitea_howto_step4": "Clone repo ลงเครื่อง: git clone http://git.<domain>:3001/<user>/<repo>.git — ใช้ user/pass เดียวกัน",
    "settings.gitea_howto_step5": "Push code ตามปกติ — Gitea จะเก็บ history และให้ทีมร่วมพัฒนาผ่าน Pull Request ได้",

    // Gitea credentials card
    "gitea.creds.title": "Credentials เริ่มต้นของ Gitea",
    "gitea.creds.subtitle": "Username/Password สำหรับ login เข้า Gitea — Admin แก้ไขได้",
    "gitea.creds.loading": "กำลังโหลด…",
    "gitea.creds.username": "Username",
    "gitea.creds.password": "Password",
    "gitea.creds.username_hint": "อย่างน้อย 3 ตัวอักษร",
    "gitea.creds.password_hint": "อย่างน้อย 8 ตัวอักษร — แนะนำให้ผสมตัวอักษร ตัวเลข และอักขระพิเศษ",
    "gitea.creds.edit": "แก้ไข",
    "gitea.creds.save": "บันทึก",
    "gitea.creds.saving": "กำลังบันทึก…",
    "gitea.creds.save_failed": "บันทึกล้มเหลว",
    "gitea.creds.cancel": "ยกเลิก",
    "gitea.creds.copy": "คัดลอก",
    "gitea.creds.copied": "คัดลอกแล้ว",
    "gitea.creds.show": "แสดง",
    "gitea.creds.hide": "ซ่อน",
    "gitea.creds.default_warning": "ยังเป็นค่าเริ่มต้น — กรุณาเปลี่ยน Username/Password ก่อนใช้งานจริงเพื่อความปลอดภัย",

    "settings.gitea_backup_title": "การ Backup & Restore",
    "settings.gitea_backup_cmd": "คำสั่ง Backup (รันบน Server)",
    "settings.gitea_restore_cmd": "คำสั่ง Restore",
    "settings.gitea_backup_note": "แนะนำให้ Backup เป็นประจำ และเก็บไฟล์ Backup ไว้ที่ External Drive หรือ Cloud Storage",
    "settings.gitea_backup_external": "Backup สู่ภายนอก",
    "settings.gitea_backup_ext_desc": "คัดลอกไฟล์ Backup ไปยัง USB Drive หรือ Cloud",

    // Settings - Auto-Start
    "settings.autostart_title": "ตั้งค่า Auto-Start เมื่อไฟดับ",
    "settings.autostart_desc": "ตั้งค่า BIOS ให้เครื่องเปิดอัตโนมัติเมื่อไฟฟ้ากลับมา",
    "settings.autostart_step1": "เข้า BIOS Setup",
    "settings.autostart_step1_desc": "กดปุ่ม Del, F2, F10 หรือ F12 ขณะเปิดเครื่อง (แล้วแต่ยี่ห้อ)",
    "settings.autostart_step2": "ค้นหาตั้งค่า AC Power Recovery",
    "settings.autostart_step2_desc": "ค้นหาในหมวด Power Management หรือ Advanced",
    "settings.autostart_step3": "ตั้งค่าเป็น Power On",
    "settings.autostart_step3_desc": "เลือก 'Power On' หรือ 'Last State' แล้วบันทึก",
    "settings.autostart_keywords": "คำค้นหาในแต่ละยี่ห้อ",
    "settings.autostart_brand": "ยี่ห้อ",
    "settings.autostart_setting_name": "ชื่อตั้งค่า",
    "settings.autostart_location": "ตำแหน่งในเมนู",
    "settings.autostart_docker_title": "ตั้งค่า Docker Desktop Auto-Start",
    "settings.autostart_docker_desc": "เปิด Docker Desktop > Settings > General > Start Docker Desktop when you sign in",
    "settings.autostart_ivs_title": "ตั้งค่า IVS Auto-Start",
    "settings.autostart_ivs_desc": "ใช้ docker compose ร่วมกับ restart policy: always",

    // Settings - Network
    "settings.tab.network": "เครือข่าย",
    "settings.net_title": "ข้อมูลเครือข่าย",
    "settings.net_desc": "สถานะการเชื่อมต่อ, IP, Gateway และ DNS ของเครื่อง IVS",
    "settings.net_ip": "IP เซิร์ฟเวอร์",
    "settings.net_hostname": "ชื่อเครื่อง (Hostname)",
    "settings.net_gateway": "Default Gateway",
    "settings.net_dns": "DNS Servers",
    "settings.net_internet": "อินเทอร์เน็ต",
    "settings.net_connected": "เชื่อมต่อแล้ว",
    "settings.net_disconnected": "ไม่ได้เชื่อมต่อ",
    "settings.net_interfaces": "Network Interfaces",
    "settings.net_col_name": "อินเตอร์เฟส",
    "settings.net_col_ip": "IP Address",
    "settings.net_col_mac": "MAC Address",
    "settings.net_col_status": "สถานะ",
    "settings.net_col_speed": "Speed",
    "settings.net_up": "UP",
    "settings.net_down": "DOWN",
    "settings.net_mdns_title": "mDNS / Bonjour — ค้นหา IVS อัตโนมัติ",
    "settings.net_mdns_desc": "ระบบค้นหาเครื่องในเครือข่ายแบบ Zero-Config — ไม่ต้องรู้ IP ก็เข้าถึง IVS ได้",
    "settings.net_mdns_status": "สถานะ mDNS",
    "settings.net_mdns_active": "ทำงานอยู่",
    "settings.net_mdns_inactive": "ไม่ทำงาน",
    "settings.net_mdns_service": "บริการ",
    "settings.net_mdns_hostname": "ชื่อ mDNS",
    "settings.net_mdns_how": "วิธีใช้ mDNS เข้าถึง IVS",
    "settings.net_mdns_step1": "ตรวจสอบว่าเครื่อง Admin และ IVS อยู่วง LAN เดียวกัน",
    "settings.net_mdns_step2": "เปิดเบราว์เซอร์แล้วพิมพ์ชื่อ mDNS ของ IVS",
    "settings.net_mdns_step3": "Windows ต้องติดตั้ง Bonjour Print Services หรือ iTunes ก่อน",
    "settings.net_mdns_linux": "Linux: ติดตั้ง avahi-daemon — sudo apt install avahi-daemon && sudo systemctl enable --now avahi-daemon",
    "settings.net_mdns_edit_title": "ตั้งค่าชื่อ mDNS",
    "settings.net_mdns_edit_desc": "เปลี่ยนชื่อ mDNS เพื่อป้องกันชื่อชนกัน กรณีมี IVS มากกว่า 1 ตัวในเครือข่าย",
    "settings.net_mdns_input_label": "ชื่อ mDNS Hostname",
    "settings.net_mdns_input_hint": "เช่น ivs, ivs-lab1, ivs-office",
    "settings.net_mdns_save": "บันทึก",
    "settings.net_mdns_saving": "กำลังบันทึก...",
    "settings.net_mdns_reset": "คืนค่าเริ่มต้น",
    "settings.net_mdns_resetting": "กำลังคืนค่า...",
    "settings.net_mdns_default_note": "ค่าเริ่มต้น: ivs.local",
    "settings.net_mdns_quick_title": "Quick Setup — เข้าถึง IVS ครั้งแรก",
    "settings.net_mdns_quick_desc": "สำหรับผู้ใช้ครั้งแรก เพียง 3 ขั้นตอนก็เข้าถึง IVS ได้ทันที",
    "settings.net_mdns_quick_step1": "ตรวจสอบว่าเครื่อง Admin และ IVS อยู่วง LAN เดียวกัน (ต่อ Router/Switch เดียวกัน)",
    "settings.net_mdns_quick_step2_pre": "เปิดเบราว์เซอร์แล้วพิมพ์",
    "settings.net_mdns_quick_step3": "Windows ต้องติดตั้ง Bonjour Print Services หรือ iTunes ก่อน",
    "settings.net_mdns_download_bonjour": "Download Bonjour (Windows)",
    "settings.net_mdns_win_note": "macOS และ iOS รองรับ mDNS โดยไม่ต้องติดตั้งเพิ่ม",
    "settings.net_static_title": "คู่มือตั้ง Static IP",
    "settings.net_static_desc": "แนะนำให้ตั้ง Static IP เพื่อให้เข้าถึง IVS ได้แน่นอน ไม่เปลี่ยนแปลง",
    "settings.net_static_why": "ทำไมต้องตั้ง Static IP?",
    "settings.net_static_reason1": "DHCP อาจเปลี่ยน IP ทุกครั้งที่รีบูต ทำให้ DNS ชี้ผิด",
    "settings.net_static_reason2": "Static IP ทำให้อุปกรณ์อื่นเข้าถึง IVS ได้ตลอด",
    "settings.net_static_reason3": "จำเป็นสำหรับ headless server ที่ไม่มีจอ",
    "settings.net_static_ubuntu": "Ubuntu / Debian",
    "settings.net_static_macos": "macOS",
    "settings.net_static_router": "ตั้งที่ Router (DHCP Reservation)",
    "settings.net_static_router_desc": "เข้า Admin Panel ของ Router → DHCP → จอง IP ให้ MAC Address ของ IVS",
    "settings.net_refresh": "รีเฟรช",

    // API Catalog
    "nav.api_catalog": "คลัง API สาธารณะ",
    "api_catalog.title": "คลัง API สาธารณะ",
    "api_catalog.subtitle": "รวม Public API ฟรีจากทั่วโลก สำหรับ Vibe Code Projects",
    "api_catalog.search": "ค้นหา API...",
    "api_catalog.intro": "แหล่งรวม API สาธารณะที่ใหญ่ที่สุดแห่งหนึ่ง เหมาะสำหรับนักพัฒนา นักวิจัย และผู้เริ่มต้น ใช้งานได้ฟรี ไม่ต้องสร้างระบบเบื้องหลังเอง",
    "api_catalog.highlight_title": "จุดเด่น",
    "api_catalog.h1": "รวม API จากหลายแหล่งทั่วโลก",
    "api_catalog.h1_desc": "แบ่งหมวดหมู่ชัดเจน ค้นหาง่าย ไม่ต้องไล่หาตามเว็บทีละเจ้า",
    "api_catalog.h2": "อัปเดตโดยชุมชน GitHub",
    "api_catalog.h2_desc": "มีผู้ใช้งานกว่า 12,000+ Stars และ Fork กว่า 1,100 ครั้ง",
    "api_catalog.h3": "ใช้งานได้จริงทันที",
    "api_catalog.h3_desc": "มี URL, API Key requirement, ราคา และ Documentation link ครบถ้วน",
    "api_catalog.h4": "เหมาะกับทุกระดับ",
    "api_catalog.h4_desc": "มือใหม่, ฟรีแลนซ์, นักวิจัย, นักศึกษา ใช้ได้ทันที",
    "api_catalog.categories_title": "หมวดหมู่ API",
    "api_catalog.visit_github": "เปิด GitHub Repository",
    "api_catalog.free": "ฟรี",
    "api_catalog.freemium": "ฟรี/มีแพ็กเกจ",
    "api_catalog.no_key": "ไม่ต้อง Key",
    "api_catalog.key_required": "ต้องใช้ Key",
    "api_catalog.count_apis": "API",
    "api_catalog.popular_title": "API ยอดนิยมเริ่มต้นใช้งานง่าย",
    "api_catalog.try_it": "ลองใช้",
    "api_catalog.docs": "Docs",
    "api_catalog.tip_title": "เคล็ดลับสำหรับ Vibe Coder",
    "api_catalog.tip_1": "เลือก API ที่ไม่ต้องใช้ Key สำหรับโปรเจกต์ทดลอง จะเริ่มต้นได้เร็ว",
    "api_catalog.tip_2": "เก็บ API Key ที่ได้รับใน คลัง API Key ของ IVS เพื่อความปลอดภัย",
    "api_catalog.tip_3": "ทดสอบ API ด้วย curl หรือ Postman ก่อนเขียนโค้ดจริง",
    "api_catalog.tip_4": "ดู Rate Limit ของแต่ละ API เพื่อไม่ให้โดน Block",

    // Deploy Guide
    "guide.button": "คู่มือ AI",
    "guide.tooltip": "คำแนะนำสำหรับเขียน Prompt และเตรียมไฟล์ก่อน Deploy",
    "guide.title": "คู่มือเตรียมแอปสำหรับ Deploy",
    "guide.subtitle": "Prompt สำหรับ AI + โครงสร้างไฟล์ที่ถูกต้อง",
    "guide.tab_prompts": "AI Prompts & โครงสร้างไฟล์",
    "guide.tab_template": "ivs-app.md Template",
    "guide.file_structure": "โครงสร้างไฟล์",
    "guide.ai_prompt": "Prompt สำหรับ AI",
    "guide.copy": "คัดลอก",
    "guide.copied": "คัดลอกแล้ว!",
    "guide.copy_template": "คัดลอก Template",
    "guide.template_title": "ivs-app.md — ใส่ไว้ในโปรเจค",
    "guide.template_desc": "คัดลอกไฟล์นี้ใส่ไว้ใน root ของโปรเจค เพื่อให้ AI เข้าใจข้อกำหนดของ IVS",

    "guide.type.static": "Static",
    "guide.type.nodejs": "Node.js",
    "guide.type.fastapi": "FastAPI",
    "guide.type.streamlit": "Streamlit",
    "guide.type.fullstack": "Fullstack",

    "guide.structure.static": `my-app/
├── index.html      ← entry point
├── style.css
├── script.js
└── assets/`,
    "guide.structure.nodejs": `my-app/
├── package.json    ← ต้องมี "start" script
├── package-lock.json
├── src/
│   └── index.js
└── public/`,
    "guide.structure.fastapi": `my-app/
├── main.py          ← ต้องมี FastAPI()
├── requirements.txt
└── routers/
    └── api.py`,
    "guide.structure.streamlit": `my-app/
├── app.py           ← entry point
├── requirements.txt ← ต้องมี streamlit
└── pages/
    └── dashboard.py`,
    "guide.structure.fullstack": `my-app/
├── backend/
│   ├── main.py           ← FastAPI backend
│   ├── requirements.txt
│   └── routers/
├── frontend/
│   ├── dist/             ← ต้อง build ก่อน!
│   │   ├── index.html
│   │   └── assets/
│   ├── package.json
│   └── src/
└── (ไม่ต้องมี Dockerfile — IVS สร้างให้)`,

    "guide.prompt.static": `สร้างเว็บไซต์แบบ HTML/CSS/JavaScript ที่มี:
- ไฟล์ index.html เป็น entry point
- CSS แยกเป็นไฟล์ style.css
- JavaScript แยกเป็นไฟล์ script.js
- ใช้ Tailwind CSS CDN สำหรับ styling
- Responsive รองรับ mobile

โครงสร้าง: ไฟล์ทั้งหมดอยู่ที่ root (ไม่มี subfolder)
Deploy: zip ทุกไฟล์แล้วอัปโหลดขึ้น IVS`,
    "guide.prompt.nodejs": `สร้าง Node.js application ที่มี:
- package.json พร้อม "start" script
- ใช้ Express.js สำหรับ HTTP server
- PORT อ่านจาก environment variable:
  const PORT = process.env.PORT || 3000;
- ตอบ health check ที่ GET /
- ใส่ package-lock.json ด้วย

โครงสร้าง: package.json อยู่ที่ root
Deploy: zip ทั้งโฟลเดอร์ (ไม่รวม node_modules)`,
    "guide.prompt.fastapi": `สร้าง FastAPI application ที่มี:
- main.py เป็น entry point มี:
  from fastapi import FastAPI
  app = FastAPI()
- requirements.txt ระบุ package ทั้งหมด
  (fastapi, uvicorn, etc.)
- รับ PORT จาก environment variable
- มี health check endpoint ที่ GET /
- รองรับ CORS

โครงสร้าง: main.py + requirements.txt ที่ root
Deploy: zip ทั้งโฟลเดอร์ (ไม่รวม .venv)`,
    "guide.prompt.streamlit": `สร้าง Streamlit application ที่มี:
- app.py เป็น entry point (ไม่ใช่ main.py)
- requirements.txt ต้องมี streamlit อยู่ในนั้น
- ใช้ st.set_page_config() ตั้งค่าหน้า
- หน้าย่อยใส่ในโฟลเดอร์ pages/

โครงสร้าง: app.py + requirements.txt ที่ root
Deploy: zip ทั้งโฟลเดอร์ (ไม่รวม .venv)`,
    "guide.prompt.fullstack": `สร้าง Fullstack app (FastAPI + Vite React) ที่มี:
โครงสร้าง:
  backend/
    main.py        ← FastAPI app
    requirements.txt
    routers/       ← API routes
  frontend/
    package.json   ← Vite + React
    src/
    dist/          ← สร้างด้วย npm run build

กฎสำคัญ:
- backend ใช้ FastAPI, endpoint อยู่ที่ /api/*
- frontend ใช้ Vite+React+TypeScript
- ต้องรัน: cd frontend && npm run build
  ก่อน zip เพื่อให้ได้ dist/
- IVS จะสร้าง nginx proxy: / → frontend,
  /api → backend อัตโนมัติ

Deploy: zip ทั้ง root (ต้องมี dist/ พร้อม)`,

    "guide.tip.static": "Static site ใช้ nginx:alpine — เบาและเร็วที่สุด เหมาะสำหรับ Landing page, Portfolio, Dashboard แบบ client-side",
    "guide.tip.nodejs": "อย่าลืมใส่ package-lock.json ด้วย และต้องมี \"start\" script ใน package.json ไม่งั้น IVS จะหา dev script หรือ main field แทน",
    "guide.tip.fastapi": "IVS ตรวจจับจากคำว่า \"fastapi\" หรือ \"FastAPI\" ใน main.py ถ้าไม่มีจะถูกจัดเป็น Python ธรรมดา",
    "guide.tip.streamlit": "Entry point ต้องเป็น app.py (ไม่ใช่ main.py) และ requirements.txt ต้องมีคำว่า streamlit",
    "guide.tip.fullstack": "สำคัญ: ต้อง npm run build ก่อน zip! ถ้าไม่มี dist/ IVS จะ build ใน Docker แต่จะช้ากว่ามาก",

    "guide.template": `# ivs-app.md — IVS Deploy Specification

## Deploy Target
- Platform: IVS (Internal Vibe Server)
- Container: Docker (auto-generated Dockerfile)
- Port: อ่านจาก ENV variable "PORT"

## Project Rules
1. ไม่ต้องสร้าง Dockerfile (IVS สร้างให้)
2. ไม่ต้องมี docker-compose.yml
3. อ่า PORT จาก environment variable เสมอ
4. ห้ามใส่ .venv/, node_modules/, .git/ ใน zip

## App Type Detection (auto)
| Type       | Condition                          |
|------------|------------------------------------|
| static     | มี index.html ที่ root             |
| nodejs     | มี package.json ที่ root           |
| python     | มี requirements.txt + main.py     |
| fastapi    | main.py มี "FastAPI"              |
| streamlit  | app.py + streamlit ใน requirements |
| fullstack  | มี backend/ + frontend/ folders   |

## Fullstack Structure (if applicable)
\`\`\`
backend/main.py        → FastAPI app
backend/requirements.txt
frontend/package.json  → Required (build script)
frontend/src/          → Source code
frontend/dist/         → Optional (IVS auto-builds if missing)
\`\`\`

## Environment Variables
- PORT: assigned by IVS automatically
- Vault keys: injected from IVS Vault

## Constraints (v1.0)
- Max upload: ~150MB zip
- No persistent storage (data lost on redeploy)
- No custom domain (use IP:PORT)
- Single container per app`,

    // Case Studies
    "guide.tab_cases": "Case ตัวอย่าง",
    "guide.cases_title": "ปัญหาที่พบบ่อยและวิธีแก้ไข",
    "guide.cases_subtitle": "เคสจริงจากการใช้งาน IVS + Vibe Code",

    "guide.case.line_oa.title": "LINE OA Webhook Error",
    "guide.case.line_oa.problem": "LINE Developers แจ้ง Webhook Error ทั้งที่ container ทำงานปกติ",
    "guide.case.line_oa.cause": "1. Dockerfile CMD ชี้ไปไฟล์ server.js ที่ต้องใช้ MySQL แต่ Docker ไม่มี DB → Connection Error\n2. ควรใช้ local-server.js (JSON file-based) แทน",
    "guide.case.line_oa.fix": "• ตรวจสอบ Dockerfile CMD ว่าชี้ไปไฟล์ที่ถูกต้อง\n• ถ้ามีหลาย server file ให้เลือกตัวที่ไม่พึ่ง Database\n• IVS จะแจ้งเตือน ⛔ อัตโนมัติถ้าพบ DB dependency",
    "guide.case.line_oa.tag": "LINE OA · Webhook · Dockerfile",

    "guide.case.ngrok.title": "ngrok Tunnel ใช้ไม่ได้ (422 Error)",
    "guide.case.ngrok.problem": "ngrok tunnel ส่ง request ได้แต่ได้ HTTP 422 กลับมา ทั้งที่ container ตอบ 200",
    "guide.case.ngrok.cause": "1. ใช้ flag --pooling-enabled ซึ่งสร้าง Cloud Endpoint พร้อม AI Gateway\n2. AI Gateway ดักจับ POST requests ทั้งหมดแล้วคืน 422 (ERR_NGROK_3803)\n3. แม้ลบ flag แล้ว Cloud Endpoint ยังค้างอยู่บน Dashboard",
    "guide.case.ngrok.fix": "• ห้ามใช้ --pooling-enabled กับ webhook/API tunnel\n• ถ้าใช้ไปแล้ว → ไป ngrok Dashboard → Endpoints → ลบ Cloud Endpoint\n• สั่งใหม่: ngrok http PORT --url=your-domain.ngrok-free.dev\n• ถ้า Deploy บน IVS แล้ว ต้องสร้าง Tunnel ใหม่ใน IVS (ไม่ใช้ของ Vibe Code)",
    "guide.case.ngrok.tag": "ngrok · Tunnel · AI Gateway · 422",

    "guide.case.db_deploy.title": "Deploy แอปที่ใช้ MySQL/Database ไม่ได้",
    "guide.case.db_deploy.problem": "แอปรันบนเครื่อง Dev ได้ แต่ Deploy บน IVS แล้ว error เพราะเชื่อมต่อ Database ไม่ได้",
    "guide.case.db_deploy.cause": "1. IVS Docker container ไม่มี Database server (MySQL, PostgreSQL, MongoDB)\n2. แอปที่ require('mysql2') หรือ import mysql จะ crash ทันที\n3. Vibe Code มักสร้าง 2 ไฟล์: server.js (ใช้ DB) กับ local-server.js (ใช้ JSON)",
    "guide.case.db_deploy.fix": "• ใช้ JSON file แทน Database สำหรับ Deploy บน IVS\n• แก้ Dockerfile CMD ให้ชี้ไฟล์ที่ไม่พึ่ง DB:\n  CMD [\"node\", \"src/local-server.js\"]\n• หรือใช้ SQLite (ไฟล์เดียว ไม่ต้อง server)\n• IVS จะแจ้งเตือน ⛔ อัตโนมัติถ้าพบ DB dependency ตอน validate",
    "guide.case.db_deploy.tag": "MySQL · Database · JSON · Dockerfile",

    // Resources
    "res.title": "ทรัพยากรระบบ",
    "res.subtitle": "ตรวจสอบ Hardware, Capacity และประสิทธิภาพแต่ละแอป",
    "res.cpu": "CPU",
    "res.ram": "RAM",
    "res.storage": "พื้นที่เก็บข้อมูล",
    "res.gpu": "GPU",
    "res.gpu_nvidia": "GPU (NVIDIA)",
    "res.gpu_apple": "GPU (Apple Silicon)",
    "res.gpu_none": "ไม่พบ GPU",
    "res.cores": "คอร์",
    "res.used": "ใช้งาน",
    "res.total": "ทั้งหมด",
    "res.free": "ว่าง",
    "res.capacity": "ความจุระบบ",
    "res.apps_running": "แอปทำงาน",
    "res.apps_can_add": "เพิ่มได้อีกประมาณ",
    "res.apps_unit": "แอป",
    "res.ram_per_app": "ใช้ RAM ต่อแอป ~",
    "res.alerts": "การแจ้งเตือน",
    "res.no_alerts": "ไม่มีการแจ้งเตือน — ระบบปกติ",
    "res.per_app": "ทรัพยากรแต่ละแอป",
    "res.no_apps": "ไม่มีแอปทำงานอยู่",
    "res.col_app": "แอป",
    "res.col_type": "ประเภท",
    "res.col_cpu": "CPU",
    "res.col_ram": "RAM (MB)",
    "res.col_port": "พอร์ต",
    "res.history": "กราฟสถิติ 24 ชม.",
    "res.history_cpu": "CPU (%)",
    "res.history_ram": "RAM (MB)",
    "res.history_apps": "แอปทำงาน",
    "res.export": "ส่งออกรายงาน",
    "res.exporting": "กำลังสร้างรายงาน...",
    "res.export_success": "สร้างรายงานสำเร็จ",
    "res.export_download": "ดาวน์โหลด",
    "res.refresh": "รีเฟรช",
    "res.last_updated": "อัปเดตล่าสุด",
    "res.level_ok": "ปกติ",
    "res.level_warn": "เตือน",
    "res.level_crit": "วิกฤต",

    // Roles
    "role.admin": "ผู้ดูแลระบบ",
    "role.developer": "นักพัฒนา",
    "role.viewer": "ผู้ใช้ทั่วไป",

    // Language
    "lang.th": "ไทย",
    "lang.en": "English",
  },

  en: {
    "nav.dashboard": "Dashboard",
    "nav.apps": "Applications",
    "nav.tunnels": "Tunnels",
    "nav.vault": "API Vault",
    "nav.resources": "Resources",
    "nav.settings": "Settings",
    "nav.signout": "Sign Out",
    "nav.subtitle": "Enterprise Gateway",

    "login.title": "Internal Vibe Server",
    "login.subtitle": "Enterprise Gateway for Vibe Code Apps",
    "login.username": "Username",
    "login.password": "Password",
    "login.submit": "Sign In",
    "login.signing_in": "Signing in...",
    "login.default": "Default: admin / admin123",
    "login.username_placeholder": "Enter username",
    "login.password_placeholder": "Enter password",

    "dash.title": "Dashboard",
    "dash.subtitle": "System overview and application management",
    "dash.refresh": "Refresh",
    "dash.refreshing": "Refreshing…",
    "dash.last_updated": "Last updated",
    "dash.refresh_failed": "Refresh failed",
    "dash.health": "System Health",
    "dash.apps_count": "Apps",
    "dash.no_apps": "No applications deployed yet",
    "dash.no_apps_hint": "Upload a .zip file above to get started",
    "dash.applications": "Applications",

    "deploy.title": "Deploy New App",
    "deploy.drag": "Drag & drop .zip file here",
    "deploy.browse": "or click to browse",
    "deploy.name": "App Name",
    "deploy.desc": "Description (optional)",
    "deploy.submit": "Deploy Application",
    "deploy.deploying": "Deploying...",
    "deploy.uploading": "Uploading & building...",
    "deploy.success": "Deployed successfully!",
    "deploy.fail": "Deploy failed",
    "deploy.zip_only": "Please upload a .zip file",
    "deploy.validating": "Validating structure...",
    "deploy.valid": "Structure is valid — Ready to deploy!",
    "deploy.invalid": "Invalid structure",
    "deploy.detected_type": "Detected:",
    "deploy.fix_prompt_title": "Tip: Use this prompt to let AI fix the structure",
    "deploy.copy_prompt": "Copy Prompt",
    "deploy.prompt_copied": "Copied!",
    "deploy.warnings": "Warnings",
    "deploy.issues": "Issues found",
    "deploy.cancel": "Cancel",
    "deploy.reselect": "Choose another file",
    "deploy.issue.fullstack_no_backend_main": "Missing backend/main.py",
    "deploy.issue.fullstack_backend_not_fastapi": "backend/main.py does not use FastAPI",
    "deploy.issue.fullstack_no_backend_requirements": "Missing backend/requirements.txt",
    "deploy.issue.fullstack_no_frontend": "Missing frontend/dist/ or frontend/package.json",
    "deploy.issue.nodejs_no_start_script": "package.json has no \"start\" script or \"main\" field",
    "deploy.issue.nodejs_invalid_package_json": "package.json is not valid JSON",
    "deploy.issue.fastapi_no_requirements": "Missing requirements.txt",
    "deploy.issue.streamlit_no_requirements": "Missing requirements.txt",
    "deploy.issue.python_no_main": "Missing main.py (entry point)",
    "deploy.issue.python_no_requirements": "Missing requirements.txt",
    "deploy.issue.unknown_structure": "No entry file found — need index.html, package.json, or main.py",
    "deploy.warn.node_modules_included": "node_modules/ included in zip — unnecessary (makes file large)",
    "deploy.warn.venv_included": ".venv/ or venv/ included in zip — unnecessary",
    "deploy.warn.git_included": ".git/ included in zip — unnecessary",
    "deploy.warn.nodejs_no_lockfile": "Missing package-lock.json — recommended for stability",
    "deploy.warn.fastapi_no_uvicorn": "requirements.txt missing uvicorn — may need to add",
    "deploy.warn.fullstack_no_dist": "Missing frontend/dist/ — IVS will build but slower",
    "deploy.warn.vite_prebuilt_detected": "Pre-built Vite app with dist/ detected — will deploy as Static Web",
    "deploy.warn.vite_preview_detected": "Vite app with vite preview detected — will use npm start",
    "deploy.warn.custom_dockerfile": "Using project's own Dockerfile — IVS will not auto-generate",
    "deploy.warn.dockerfile_cmd_missing_file": "⛔ Dockerfile CMD points to missing file: {file} — may fail to run",
    "deploy.warn.dockerfile_db_dependency": "⛔ File {file} requires {db} — Docker container has no Database, will cause Connection Error",
    "deploy.warn.multiple_server_files": "Multiple server files found: {files} — verify Dockerfile CMD targets the right one",
    "deploy.issue.vite_no_start_script": "Vite app missing start script — add \"start\": \"vite preview --port 3000 --host\" to package.json",
    "deploy.file_too_large_title": "⚠️ File Too Large",
    "deploy.file_too_large_msg": "Your file is too large ({size} MB). Please check that you've removed node_modules or .venv before compressing to prevent system issues.",
    "deploy.auto_sanitize": "Continue — Auto-sanitize enabled",
    "deploy.auto_sanitize_desc": "IVS will auto-remove node_modules, .venv, pnpm-lock.yaml before build",
    "deploy.cancel_upload": "Cancel — Choose another file",
    "deploy.build_log_title": "Build Log (Real-time)",
    "deploy.build_timeout": "Build timeout! Exceeded 3 minutes",
    "deploy.build_success": "Build successful!",
    "deploy.build_error": "Build failed",
    "deploy.type.static": "Static Web",
    "deploy.type.nodejs": "Node.js",
    "deploy.type.fastapi": "FastAPI",
    "deploy.type.streamlit": "Streamlit",
    "deploy.type.fullstack": "Fullstack",
    "deploy.type.python": "Python",
    "deploy.type.unknown": "Unknown",

    "app.start": "Start",
    "app.stop": "Stop",
    "app.restart": "Restart",
    "app.delete": "Delete",
    "app.delete_confirm": "Delete",
    "app.export": "Export",
    "app.export_tooltip": "Download program + data as a .zip backup",
    "app.export_owner_only_tooltip": "Only the original deployer of this app can export it (copyright protection)",
    "app.privacy_review": "Privacy notice",
    "app.privacy_review_tooltip": "View / change your PDPA consent for this app",

    // Export Modal
    "export.title_working": "Creating export bundle…",
    "export.subtitle_working": "Packaging program and data",
    "export.title_done": "Export complete",
    "export.subtitle_done": "Download the .zip bundle to keep as backup",
    "export.title_error": "Export failed",
    "export.subtitle_error": "An error occurred during export",
    "export.target_app": "App to export",
    "export.step1": "1. Copy Dockerfile + source code",
    "export.step2": "2. Copy data from the container (data, uploads, db)",
    "export.step3": "3. Compress to .zip with metadata and re-import instructions",
    "export.please_wait": "Please wait — this usually takes 10–30 seconds",
    "export.bundle_size": "Bundle size",
    "export.data_paths_copied": "Data paths exported",
    "export.filename": "Filename",
    "export.no_data_warning": "No persistent data found inside the container — this app may not store data internally, or the container is not running.",
    "export.warnings": "Warnings",
    "export.tip": "Open the .zip to find README.md with instructions for re-importing back into IVS.",
    "export.download": "Download .zip",
    "export.cancel": "Cancel",
    "export.close": "Close",

    // Delete Confirmation Modal
    "delete.title": "Delete this application?",
    "delete.subtitle": "This action cannot be undone",
    "delete.target_app": "App to delete",
    "delete.what_lost_title": "What will be permanently lost:",
    "delete.lost.container": "Container and Docker image of this app",
    "delete.lost.data": "All app-generated data and files (databases, uploads, cache)",
    "delete.lost.logs": "Build logs and runtime logs history",
    "delete.lost.port": "Allocated port — will be released for other apps",
    "delete.lost.access": "URLs that users previously accessed will no longer work",
    "delete.irreversible": "There is no rollback after confirmation. If you need a backup, please export the data before deleting.",
    "delete.type_to_confirm": "Type the app name to confirm:",
    "delete.cancel": "Cancel",
    "delete.confirm": "Delete Permanently",
    "delete.deleting": "Deleting…",
    "delete.export_first_title": "Haven't backed up the data?",
    "delete.export_first_desc": "Export the program + data before deleting so you can re-import it later.",
    "delete.export_first_button": "Export first",
    "app.logs": "View Logs",
    "app.hide_logs": "Hide Logs",
    "app.no_logs": "No logs available",
    "app.status.running": "Running",
    "app.status.stopped": "Stopped",
    "app.status.building": "Building",
    "app.status.error": "Error",

    "health.docker": "Docker",
    "health.dns": "DNS",
    "health.cpu": "CPU",
    "health.ram": "RAM",
    "health.storage": "Storage",

    "apps.title": "Applications",
    "apps.subtitle": "Manage deployed Vibe Code applications",
    "apps.search": "Search apps...",
    "apps.filter.all": "All",
    "apps.filter.running": "Running",
    "apps.filter.stopped": "Stopped",
    "apps.filter.building": "Building",
    "apps.filter.error": "Error",
    "apps.no_match": "No apps match your filter",

    "tunnel.title": "Secure Tunnel Manager",
    "tunnel.subtitle": "Share apps to the internet with time-limited tunnels",
    "tunnel.create": "Create New Tunnel",
    "tunnel.app_label": "Application",
    "tunnel.app_select": "Select an app...",
    "tunnel.duration": "Duration",
    "tunnel.open": "Open Tunnel",
    "tunnel.creating": "Creating...",
    "tunnel.active": "Active Tunnels",
    "tunnel.none": "No tunnels created yet",
    "tunnel.revoke": "Revoke",
    "tunnel.privacy": "Notice",
    "tunnel.privacy_tooltip": "View / change your PDPA consent for this app",
    "tunnel.share": "Email",
    "tunnel.share_tooltip": "Share the link by email with the PDPA notice and usage instructions",
    // Share-by-email modal
    "tunnel.share.title": "Share tunnel link by email",
    "tunnel.share.subtitle": "The message includes the PDPA notice + tunnel URL + usage instructions + security warning",
    "tunnel.share.recipient": "Recipient (optional)",
    "tunnel.share.recipient_placeholder": "name@example.com — leave blank to fill in your mail client",
    "tunnel.share.recipient_hint": "Multiple recipients can be added with comma separation",
    "tunnel.share.extra_note": "Extra note (optional)",
    "tunnel.share.extra_note_placeholder": "e.g. 'Please access before 5pm'",
    "tunnel.share.preview": "Preview",
    "tunnel.share.subject_label": "Subject",
    "tunnel.share.loading_notice": "Loading PDPA notice…",
    "tunnel.share.tip": "Clicking the button below opens your mail client (Mail / Outlook / Gmail) pre-filled with this content. If the app doesn't open, use Copy instead.",
    "tunnel.share.copy": "Copy content",
    "tunnel.share.copied": "Copied",
    "tunnel.share.cancel": "Cancel",
    "tunnel.share.open_mail": "Open in mail app",
    "tunnel.col.app": "App",
    "tunnel.col.url": "Public URL",
    "tunnel.col.status": "Status",
    "tunnel.col.time": "Time Left",
    "tunnel.col.action": "Action",
    "tunnel.dur.1m": "1 min",
    "tunnel.dur.10m": "10 min",
    "tunnel.dur.1h": "1 hour",
    "tunnel.dur.3h": "3 hours",
    "tunnel.dur.24h": "24 hours",

    "vault.title": "API Key Vault",
    "vault.subtitle": "Secure enterprise API key management (AES-256 encrypted)",
    "vault.add": "+ Add Key",
    "vault.cancel": "Cancel",
    "vault.add_title": "Add New API Key",
    "vault.key_name": "Key Name (e.g., Production API Key)",
    "vault.provider": "Provider (e.g., OpenAI, Claude)",
    "vault.category": "Category",
    "vault.key_value": "API Key Value",
    "vault.description": "Description (optional)",
    "vault.save": "Save Key",
    "vault.saving": "Encrypting & Saving...",
    "vault.search": "Search keys...",
    "vault.no_keys": "No API keys stored yet",
    "vault.encrypted": "Encrypted",
    "vault.copy": "Copy",
    "vault.copied": "Copied",
    "vault.copy_failed": "Failed",
    "vault.copy_tooltip": "Decrypt + copy API key to clipboard (audit-logged)",

    // Privacy Notice popup
    "pn.default_title": "Personal Data Collection Notice",
    "pn.default_detail": "This application may collect, use, or disclose your personal data.",
    "pn.review_badge": "View / change consent",
    "pn.disabled_banner": "This app has the privacy notice disabled — consent will not be requested on next access",
    "pn.current_status": "Current status",
    "pn.status_accepted": "✓ Accepted",
    "pn.status_declined": "✗ Declined",
    "pn.recorded_at": "Recorded at",
    "pn.link_policy": "Privacy Policy",
    "pn.link_full_notice": "Full Privacy Notice",
    "pn.accept_current": "✓ Accepted (current status)",
    "pn.switch_to_accept": "Change to: Accept",
    "pn.decline_current": "✗ Declined (current status)",
    "pn.switch_to_decline": "Change to: Decline",
    "pn.close": "Close",
    "pn.saving": "Saving…",
    "pn.accept_and_enter": "Accept and enter",
    "pn.decline": "Decline",
    "pn.legal_footer": "Per applicable data-protection law — you may change your consent at any time.",

    // Tunnel share email body
    "tunnel.share.subject_suffix": "access link with PDPA notice",
    "tunnel.share.body.greeting": "Hello,",
    "tunnel.share.body.intro_l1": 'You are invited to access the application "{app}" through a temporary tunnel link.',
    "tunnel.share.body.intro_l2": "Please review the personal-data processing notice below before using.",
    "tunnel.share.body.section_notice": "⚠️  Personal Data Processing Notice",
    "tunnel.share.body.no_notice": "(This app has no privacy notice configured — the operator should set one before sharing externally.)",
    "tunnel.share.body.section_link": "🔗  Access link (Tunnel)",
    "tunnel.share.body.expires_at": "This link expires",
    "tunnel.share.body.section_howto": "📖  How to use",
    "tunnel.share.body.howto_1": "1. Click the link above to open the app",
    "tunnel.share.body.howto_2": "2. If the app shows a privacy notice — please read and consider before accepting",
    "tunnel.share.body.howto_3": "3. Your accept/decline choice will be recorded per the applicable data-protection law",
    "tunnel.share.body.howto_4": "4. You may change your consent at any time by returning to this link",
    "tunnel.share.body.section_security": "🔒  Security warning",
    "tunnel.share.body.security_1": "• This link grants access to an internal system from outside the network",
    "tunnel.share.body.security_2": "• Improper use carries a risk of data leakage",
    "tunnel.share.body.security_3": "• Please use within your organization's policy",
    "tunnel.share.body.security_4": "• Report any unusual behavior to the system administrator immediately",
    "tunnel.share.body.section_note": "💬  Note from the sender",
    "tunnel.share.body.signoff": "Sent from IVS — Internal Vibe Server",

    // PII suggestion checklist (Settings → PDPA tab)
    "pii.full_name": "Full name",
    "pii.email": "Email",
    "pii.phone": "Phone",
    "pii.address": "Address",
    "pii.national_id": "National ID / Passport",
    "pii.dob": "Date of birth / Age",
    "pii.line_id": "Social ID (LINE/etc.)",
    "pii.photo_bio": "Photo / Biometrics",
    "pii.bank_account": "Bank account / Financial",
    "pii.tax_id": "Tax ID",
    "pii.org_info": "Organization info",

    // Misc inline strings
    "user_delete.reassigned_suffix": "app(s) reassigned to",
    "settings.export_success": "Export succeeded",
    "settings.activities_count": "events",
    "settings.pn_saved": "Privacy Notice saved",
    "settings.pdpa.found": "found",
    "settings.pdpa.not_found": "not found",
    "settings.pdpa.add_all_detected": "Add all detected",
    "settings.pn_detail_placeholder": "This application collects, uses, or discloses your personal data for the purpose of providing the service...",
    "settings.pn_preview_placeholder": "Details will appear here...",
    "deploy.auto_sanitize_note": "Auto-Sanitize will strip junk files automatically",
    "deploy.close": "Close",
    "datepicker.clear": "Clear",
    "datepicker.today": "Today",

    // Vault delete confirmation
    "vault.delete_modal.title": "Delete API Key",
    "vault.delete_modal.desc_prefix": "Confirm deleting key",
    "vault.delete_modal.desc_suffix": "This is irreversible. Please re-enter your password to confirm.",
    "vault.delete_modal.consequence_1": "Key's encrypted value is permanently removed from the database — no recovery",
    "vault.delete_modal.consequence_2": "Apps that inject this key will fail until redeployed with a new key",
    "vault.delete_modal.consequence_3": "Writes a WARNING-level audit log with the key name and confirmation timestamp",
    "vault.delete_modal.legal_note": "API keys are sensitive credentials that may carry financial cost — deletion requires identity verification.",
    "vault.delete_modal.confirm": "Confirm delete",
    "vault.delete_confirm": "Delete key",

    "settings.title": "Settings",
    "settings.subtitle": "User management and audit logs",
    "settings.tab.users": "User Management",
    "settings.tab.logs": "Audit Logs",
    "settings.add_user": "+ Add User",
    "settings.create_user": "Create New User",
    "settings.username": "Username",
    "settings.email": "Email",
    "settings.password": "Password",
    "settings.role": "Role",
    "settings.create": "Create User",
    "settings.creating": "Creating...",
    "settings.col.user": "User",
    "settings.col.email": "Email",
    "settings.col.role": "Role",
    "settings.col.status": "Status",
    "settings.col.created": "Created",
    "settings.col.actions": "Actions",
    "settings.active": "Active",
    "settings.disabled": "Disabled",
    "settings.disable": "Disable",
    "settings.enable": "Enable",
    "settings.ntp.title": "NTP Time Reference (legally traceable timestamp)",
    "settings.ntp.authority": "Authority",
    "settings.ntp.synced": "Synced",
    "settings.log.title_compliance": "Audit Log (Compliance)",
    "settings.log.compliance_badge": "Compliant",
    "settings.log.time": "Time",
    "settings.log.level": "Level",
    "settings.log.user": "User",
    "settings.log.action": "Action",
    "settings.log.resource": "Resource",
    "settings.log.request_id": "Tracking ID",
    "settings.log.details": "Details",
    "settings.no_logs": "No audit logs yet",
    "settings.col.app_access": "App Access",
    "settings.set_access": "Set Access",
    "settings.full_access": "Full Access",
    "settings.no_access": "No Access",
    "settings.apps_assigned": "apps assigned",
    "settings.access_title": "Set App Access",
    "settings.access_desc": "Choose which apps this user can access",
    "settings.access_all": "Access All Apps",
    "settings.access_all_desc": "User can access all apps in the system",
    "settings.access_select": "Select Allowed Apps",
    "settings.apps_selected": "apps selected",
    "settings.save_access": "Save Access",
    "settings.saving_access": "Saving...",
    "settings.no_apps_to_assign": "No apps in the system yet",

    // Settings - Audit Export
    "settings.tab.pdpa": "PDPA",
    "settings.tab.dns": "DNS & Domain",
    "settings.tab.gitea": "Gitea",
    "settings.tab.autostart": "Auto-Start",
    "settings.export_logs": "Export .zip",
    "settings.exporting": "Exporting...",
    "settings.export_history": "Export History",
    "settings.export_no_history": "No exports yet",
    // Date-range presets for audit export
    "settings.export_range": "Date range",
    "settings.export_range_7d": "7 days",
    "settings.export_range_30d": "30 days",
    "settings.export_range_90d": "90 days",
    "settings.export_range_all": "All time",
    "settings.export_range_custom": "Custom",
    "settings.export_range_from": "From",
    "settings.export_range_to": "To",
    "settings.export_range_all_label": "All time",
    "settings.export_range_col": "Range",
    "settings.export_files_col": "Files",
    "settings.export_chunk_label": "Chunk size",
    "settings.export_chunk_unit": "records",
    "settings.export_chunk_tip": "If logs are large, they're split into multiple files inside a single .zip for easier viewing",
    "settings.export_chunk_note": "All chunks are bundled in one .zip with a single SHA-256 covering the whole archive — atomic download, no partial failures.",
    "settings.export_history_count_suffix": "exports in history",

    // Pagination
    "pagination.showing": "Showing",
    "pagination.of": "of",
    "pagination.per_page": "Per page",
    "pagination.first": "First page",
    "pagination.prev": "Previous page",
    "pagination.next": "Next page",
    "pagination.last": "Last page",
    "settings.export_date_tooltip": "Timestamp of this export — ISO format with timezone offset, for legal reference",
    "settings.export_history_item_label": "exports",
    "settings.log.time_tooltip": "Event timestamp (timezone offset shown for legal traceability)",
    "settings.log.item_label": "events",
    "settings.log.details_click": "Click to view more details",
    "settings.log.no_detail": "(no details)",

    // Audit log detail modal
    "audit_detail.title": "Event Detail",
    "audit_detail.subtitle": "Complete record per Thai Computer Crime Act B.E. 2560",
    "audit_detail.user": "User",
    "audit_detail.user_id": "User ID",
    "audit_detail.resource": "Resource",
    "audit_detail.ip_address": "IP Address",
    "audit_detail.request_id": "Request ID",
    "audit_detail.session_id": "Session ID",
    "audit_detail.ntp_source": "NTP Source",
    "audit_detail.user_agent": "User Agent",
    "audit_detail.details": "Full Details",
    "audit_detail.no_details": "(no details)",
    "audit_detail.copy": "Copy",
    "audit_detail.copied": "Copied",
    "audit_detail.close": "Close",
    "audit_detail.legal_note": "Timestamps verified via NTP per Thai Computer Crime Act",
    "settings.users_item_label": "users",
    "tunnel.item_label": "tunnels",
    "res.per_app_item_label": "apps",

    // Retention policy panel
    "retention.title": "Data Retention Policy",
    "retention.subtitle": "Configure how long each log type is kept. Expired data is auto-deleted.",
    "retention.subtitle_short": "Configure log retention per applicable data-protection law (default: PDPA)",
    "retention.click_to_expand": "Click to expand",
    "retention.click_to_collapse": "Click to collapse",
    "retention.legal_note": "Thai Computer Crime Act B.E. 2560 §26 — computer-traffic data must be retained for at least 90 days, typically 2 years (730 days), or longer if required by a competent officer.",
    "retention.loading": "Loading…",
    "retention.days": "days",
    "retention.range": "Range",
    "retention.default": "Default",
    "retention.at_minimum": "At legal minimum",
    "retention.over_recommended": "Exceeds 2 years — requires officer order",
    "retention.save": "Save",
    "retention.saving": "Saving…",
    "retention.saved": "✓ Saved",
    "retention.reset": "Reset",
    "retention.purge_now": "Purge now",
    "retention.purging": "Purging…",
    "retention.purge_done": "✓ Purge complete",
    "retention.purge_tooltip": "Normally runs daily. Click to purge immediately (e.g. after lowering retention).",
    "retention.purge_confirm": "Confirm purge of expired data? This cannot be undone.",

    // Password-confirm modal for the manual purge
    "retention.purge_modal_title": "Confirm data purge",
    "retention.purge_modal_desc": "An immediate purge is irreversible and may violate legal requirements if the current retention period is set below the statutory minimum. Please re-enter your password to confirm your identity before proceeding.",
    "retention.purge_modal_consequence_1": "Immediately delete records past the retention window from audit_logs, app_logs, resource_metrics, and exports",
    "retention.purge_modal_consequence_2": "Remove expired .zip export files from disk (not the OS trash)",
    "retention.purge_modal_consequence_3": "Write a WARNING-level audit log capturing user, IP, and the exact time you confirmed",
    "retention.purge_modal_legal": "Thai Computer Crime Act B.E. 2560 §26 mandates a 90-day minimum retention of computer-traffic data. If you have lowered the retention below the legal floor AND used this button to delete data, you may incur personal legal liability.",
    "retention.purge_modal_confirm": "Confirm purge",

    // Generic password-confirm modal
    "password_confirm.subtitle": "Re-authentication required before proceeding",
    "password_confirm.consequences": "What this will do",
    "password_confirm.label": "Your password",
    "password_confirm.placeholder": "Enter your current password",
    "password_confirm.show": "Show password",
    "password_confirm.hide": "Hide password",
    "password_confirm.cancel": "Cancel",
    "password_confirm.working": "Working…",
    "password_confirm.error_generic": "Unable to verify. Please try again.",
    "password_confirm.forensic_note": "Every attempt is recorded as a WARNING-level audit log — including failed password attempts.",

    // User disable confirmation
    "user_disable.title": "Disable user",
    "user_disable.desc_prefix": "Confirm disabling the account",
    "user_disable.desc_suffix": "— the user will be locked out of IVS until re-enabled. Please re-enter your own password to confirm.",
    "user_disable.consequence_1": "User is signed out on their next request and cannot log in again",
    "user_disable.consequence_2": "Their apps and resources remain intact — re-enabling restores full access",
    "user_disable.consequence_3": "Writes a WARNING-level audit log naming you and the timestamp",
    "user_disable.legal_note": "Restricting access to an information system must be audit-traceable — IVS keeps this record per the configured retention policy.",
    "user_disable.confirm": "Confirm disable",

    "settings.delete_user": "Delete",
    "settings.delete_user_tooltip": "Permanently delete user. All their apps are reassigned to you (Admin).",
    "user_delete.title": "Permanently delete user",
    "user_delete.desc_prefix": "Confirm deleting account",
    "user_delete.desc_suffix": "— this is irreversible. Please re-enter your password to confirm.",
    "user_delete.consequence_1": "User account and credentials are permanently deleted",
    "user_delete.consequence_2": "Apps the user deployed are automatically reassigned to you (Admin) — they keep running",
    "user_delete.consequence_3": "Audit log history is retained per the retention policy (not deleted)",
    "user_delete.consequence_4": "Cannot delete the last admin or your own account",
    "user_delete.legal_note": "User deletion requires a verifiable transfer-of-responsibility record — IVS audit-logs the deletion and the app reassignment.",
    "user_delete.confirm": "Confirm delete",
    "retention.purge_result": "Purge result (record counts)",
    // Per-type labels
    "retention.type.audit_logs": "System Audit Logs",
    "retention.desc.audit_logs": "Logins, deploys, deletes, config changes — legal evidence",
    "retention.type.app_logs": "App Container Logs",
    "retention.desc.app_logs": "stdout/stderr from every container — traffic data per §26",
    "retention.type.resource_metrics": "Resource History (CPU/RAM/Disk)",
    "retention.desc.resource_metrics": "Backs the Resources page charts — not legal record",
    "retention.type.exports": "Exported .zip Files",
    "retention.desc.exports": "Files from Export History — both DB row and disk file are removed",
    "retention.type.exports_files_removed": "Files removed from disk",

    // PDPA
    "settings.pdpa_title": "PDPA — Record of Processing Activities (ROPA)",
    "settings.pdpa_desc": "Personal Data Protection Act B.E. 2562 compliance",
    "settings.pdpa_scan_all": "Scan All Apps",
    "settings.pdpa_scanning": "Scanning...",
    "settings.pdpa_export": "Export ROPA",
    "settings.pdpa_exporting": "Exporting...",
    "settings.pdpa_no_apps": "No deployed apps yet",
    "settings.pdpa_col_app": "Activity (App)",
    "settings.pdpa_col_purpose": "Purpose",
    "settings.pdpa_col_pii": "Personal Data",
    "settings.pdpa_col_retention": "Retention",
    "settings.pdpa_col_masking": "Data Masking",
    "settings.pdpa_col_status": "Status",
    "settings.pdpa_col_action": "Action",
    "settings.pdpa_status_not_started": "Not Started",
    "settings.pdpa_status_partial": "Partial",
    "settings.pdpa_status_complete": "Complete",
    "settings.pdpa_edit": "Edit",
    "settings.pdpa_scan": "Scan PII",
    "settings.pdpa_modal_title": "Edit PDPA Record",
    "settings.pdpa_purpose_label": "Purpose of Data Collection",
    "settings.pdpa_purpose_hint": "e.g. Customer service, Customer support",
    "settings.pdpa_pii_label": "Personal Data Collected",
    "settings.pdpa_pii_auto": "Auto-detected",
    "settings.pdpa_pii_manual": "Add manually",
    "settings.pdpa_retention_label": "Data Retention Period",
    "settings.pdpa_retention_hint": "e.g. 1 year, per contract Section 24 (3)",
    "settings.pdpa_security_label": "Additional Security Measures",
    "settings.pdpa_security_hint": "Additional notes beyond User Management + Audit Log",
    "settings.pdpa_save": "Save",
    "settings.pdpa_saving": "Saving...",
    "settings.pdpa_cancel": "Cancel",
    "settings.pdpa_scan_result": "PII Scan Results",
    "settings.pdpa_files_scanned": "Files scanned",
    "settings.pdpa_found_pii": "PII found",
    "settings.pdpa_found_masking": "Data Masking found",
    "settings.pdpa_no_masking": "No Data Masking found",
    "settings.pdpa_masking_warn": "Recommend adding data masking for personal data in this app",
    "settings.pdpa_security_base": "IVS Base: User Management, Audit Log, Docker Isolation",
    "settings.pn_title": "Privacy Notice",
    "settings.pn_desc": "Configure privacy notice displayed before app access per PDPA requirements",
    "settings.pn_toggle": "Enable IVS Privacy Notice",
    "settings.pn_toggle_hint": "Disable if the app already has its own Privacy Notice",
    "settings.pn_notice_title": "Notice Title",
    "settings.pn_notice_detail": "Brief Description",
    "settings.pn_notice_detail_hint": "Notice text shown before app access",
    "settings.pn_policy_url": "Privacy Policy URL",
    "settings.pn_notice_url": "Detailed Privacy Notice URL",
    "settings.pn_enabled": "On",
    "settings.pn_disabled": "Off",
    "settings.pn_save": "Save Privacy Notice",
    "settings.pn_saving": "Saving...",
    "settings.pn_col": "Privacy Notice",
    "settings.pn_preview": "Preview",
    "settings.export_filename": "File",
    "settings.export_hash": "SHA-256 Hash",
    "settings.export_records": "Records",
    "settings.export_date": "Export Date",
    "settings.export_download": "Download",
    "settings.export_hash_note": "Hash values verify document integrity and can be used as court evidence",

    // Settings - DNS Config
    "settings.dns_title": "Local DNS & Port Resolver",
    "settings.dns_desc": "Internal LAN domain name system for easy app access with memorable names",
    "settings.dns_domain": "Domain Suffix",
    "settings.dns_domain_hint": "e.g. company.local, myorg.th, vibe.local",
    "settings.dns_server_ip": "Server IP",
    "settings.dns_save": "Save Domain",
    "settings.dns_saving": "Saving...",
    "settings.dns_example": "Example: if set to",
    "settings.dns_example2": "an app named myapp will be accessible at",
    "settings.dns_warning": "After changing domain, DNS and Proxy services may need to restart",
    "settings.dns_current": "Current Domain",

    // Settings - Gitea
    "settings.gitea_title": "Gitea — Organization Git Server",
    "settings.gitea_desc": "Self-hosted code management like a private GitHub",
    "settings.gitea_url": "Gitea Access URL",
    "settings.gitea_open": "Open Gitea",
    "settings.gitea_features_title": "Key Features",
    "settings.gitea_f1": "Store all organization project source code",
    "settings.gitea_f2": "Full Pull Request, Issues, Wiki support",
    "settings.gitea_f3": "Git LFS support for large files",
    "settings.gitea_f4": "User permission management by Organization / Team",

    // Gitea — How to use
    "settings.gitea_howto_title": "How to use",
    "settings.gitea_howto_step1": "Click 'Open Gitea' above to launch the login page in a new tab",
    "settings.gitea_howto_step2": "Sign in with the Username / Password shown in the Credentials block below (the defaults MUST be changed before production use)",
    "settings.gitea_howto_step3": "Create a new repository from the + icon at the top-right — enter name, description, and visibility",
    "settings.gitea_howto_step4": "Clone locally: git clone http://git.<domain>:3001/<user>/<repo>.git — use the same user/password",
    "settings.gitea_howto_step5": "Push code as usual — Gitea tracks history and lets your team collaborate via Pull Requests",

    // Gitea credentials card
    "gitea.creds.title": "Initial Gitea Credentials",
    "gitea.creds.subtitle": "Username/Password to sign in to Gitea — admin can change them",
    "gitea.creds.loading": "Loading…",
    "gitea.creds.username": "Username",
    "gitea.creds.password": "Password",
    "gitea.creds.username_hint": "At least 3 characters",
    "gitea.creds.password_hint": "At least 8 characters — mix letters, digits, and symbols",
    "gitea.creds.edit": "Edit",
    "gitea.creds.save": "Save",
    "gitea.creds.saving": "Saving…",
    "gitea.creds.save_failed": "Save failed",
    "gitea.creds.cancel": "Cancel",
    "gitea.creds.copy": "Copy",
    "gitea.creds.copied": "Copied",
    "gitea.creds.show": "Show",
    "gitea.creds.hide": "Hide",
    "gitea.creds.default_warning": "Still using defaults — please change Username/Password before production use for security.",

    "settings.gitea_backup_title": "Backup & Restore",
    "settings.gitea_backup_cmd": "Backup Command (run on Server)",
    "settings.gitea_restore_cmd": "Restore Command",
    "settings.gitea_backup_note": "Regular backups recommended. Store backup files on External Drive or Cloud Storage",
    "settings.gitea_backup_external": "External Backup",
    "settings.gitea_backup_ext_desc": "Copy backup files to USB Drive or Cloud",

    // Settings - Auto-Start
    "settings.autostart_title": "Auto-Start on Power Loss",
    "settings.autostart_desc": "Configure BIOS to auto-start when power returns",
    "settings.autostart_step1": "Enter BIOS Setup",
    "settings.autostart_step1_desc": "Press Del, F2, F10 or F12 during boot (varies by brand)",
    "settings.autostart_step2": "Find AC Power Recovery",
    "settings.autostart_step2_desc": "Look under Power Management or Advanced menu",
    "settings.autostart_step3": "Set to Power On",
    "settings.autostart_step3_desc": "Select 'Power On' or 'Last State' then save",
    "settings.autostart_keywords": "Setting Names by Brand",
    "settings.autostart_brand": "Brand",
    "settings.autostart_setting_name": "Setting Name",
    "settings.autostart_location": "Menu Location",
    "settings.autostart_docker_title": "Docker Desktop Auto-Start",
    "settings.autostart_docker_desc": "Open Docker Desktop > Settings > General > Start Docker Desktop when you sign in",
    "settings.autostart_ivs_title": "IVS Auto-Start",
    "settings.autostart_ivs_desc": "Use docker compose with restart policy: always",

    // Settings - Network
    "settings.tab.network": "Network",
    "settings.net_title": "Network Information",
    "settings.net_desc": "Connection status, IP, Gateway, and DNS of the IVS machine",
    "settings.net_ip": "Server IP",
    "settings.net_hostname": "Hostname",
    "settings.net_gateway": "Default Gateway",
    "settings.net_dns": "DNS Servers",
    "settings.net_internet": "Internet",
    "settings.net_connected": "Connected",
    "settings.net_disconnected": "Disconnected",
    "settings.net_interfaces": "Network Interfaces",
    "settings.net_col_name": "Interface",
    "settings.net_col_ip": "IP Address",
    "settings.net_col_mac": "MAC Address",
    "settings.net_col_status": "Status",
    "settings.net_col_speed": "Speed",
    "settings.net_up": "UP",
    "settings.net_down": "DOWN",
    "settings.net_mdns_title": "mDNS / Bonjour — Auto-discover IVS",
    "settings.net_mdns_desc": "Zero-Config network discovery — access IVS without knowing its IP",
    "settings.net_mdns_status": "mDNS Status",
    "settings.net_mdns_active": "Active",
    "settings.net_mdns_inactive": "Inactive",
    "settings.net_mdns_service": "Service",
    "settings.net_mdns_hostname": "mDNS Name",
    "settings.net_mdns_how": "How to access IVS via mDNS",
    "settings.net_mdns_step1": "Ensure the Admin device and IVS are on the same LAN",
    "settings.net_mdns_step2": "Open a browser and type the mDNS hostname of IVS",
    "settings.net_mdns_step3": "Windows requires Bonjour Print Services or iTunes installed",
    "settings.net_mdns_linux": "Linux: Install avahi-daemon — sudo apt install avahi-daemon && sudo systemctl enable --now avahi-daemon",
    "settings.net_mdns_edit_title": "Configure mDNS Name",
    "settings.net_mdns_edit_desc": "Change mDNS name to avoid conflicts when multiple IVS instances exist on the network",
    "settings.net_mdns_input_label": "mDNS Hostname",
    "settings.net_mdns_input_hint": "e.g. ivs, ivs-lab1, ivs-office",
    "settings.net_mdns_save": "Save",
    "settings.net_mdns_saving": "Saving...",
    "settings.net_mdns_reset": "Reset to Default",
    "settings.net_mdns_resetting": "Resetting...",
    "settings.net_mdns_default_note": "Default: ivs.local",
    "settings.net_mdns_quick_title": "Quick Setup — First-time Access",
    "settings.net_mdns_quick_desc": "For first-time users, just 3 steps to access IVS immediately",
    "settings.net_mdns_quick_step1": "Ensure the Admin device and IVS are on the same LAN (same Router/Switch)",
    "settings.net_mdns_quick_step2_pre": "Open a browser and type",
    "settings.net_mdns_quick_step3": "Windows requires Bonjour Print Services or iTunes installed",
    "settings.net_mdns_download_bonjour": "Download Bonjour (Windows)",
    "settings.net_mdns_win_note": "macOS and iOS support mDNS natively without additional software",
    "settings.net_static_title": "Static IP Setup Guide",
    "settings.net_static_desc": "Recommended to set a Static IP so IVS is always reachable at the same address",
    "settings.net_static_why": "Why set a Static IP?",
    "settings.net_static_reason1": "DHCP may change IP on every reboot, causing DNS to point incorrectly",
    "settings.net_static_reason2": "Static IP ensures other devices can always reach IVS",
    "settings.net_static_reason3": "Essential for headless servers without a monitor",
    "settings.net_static_ubuntu": "Ubuntu / Debian",
    "settings.net_static_macos": "macOS",
    "settings.net_static_router": "Set at Router (DHCP Reservation)",
    "settings.net_static_router_desc": "Go to Router Admin Panel > DHCP > Reserve IP for IVS MAC Address",
    "settings.net_refresh": "Refresh",

    // API Catalog
    "nav.api_catalog": "Public APIs",
    "api_catalog.title": "Public API Catalog",
    "api_catalog.subtitle": "Free Public APIs from around the world for Vibe Code Projects",
    "api_catalog.search": "Search APIs...",
    "api_catalog.intro": "One of the largest public API directories. Perfect for developers, researchers, and beginners. Free to use without building backend systems.",
    "api_catalog.highlight_title": "Highlights",
    "api_catalog.h1": "APIs from sources worldwide",
    "api_catalog.h1_desc": "Clearly categorized and easy to search across all domains",
    "api_catalog.h2": "Community-maintained on GitHub",
    "api_catalog.h2_desc": "Over 12,000+ Stars and 1,100+ Forks with active contributors",
    "api_catalog.h3": "Ready to use immediately",
    "api_catalog.h3_desc": "Includes URL, API Key requirements, pricing, and documentation links",
    "api_catalog.h4": "Suitable for all levels",
    "api_catalog.h4_desc": "Beginners, freelancers, researchers, students - start right away",
    "api_catalog.categories_title": "API Categories",
    "api_catalog.visit_github": "Open GitHub Repository",
    "api_catalog.free": "Free",
    "api_catalog.freemium": "Freemium",
    "api_catalog.no_key": "No Key",
    "api_catalog.key_required": "Key Required",
    "api_catalog.count_apis": "APIs",
    "api_catalog.popular_title": "Popular Easy-to-Start APIs",
    "api_catalog.try_it": "Try It",
    "api_catalog.docs": "Docs",
    "api_catalog.tip_title": "Tips for Vibe Coders",
    "api_catalog.tip_1": "Choose no-key APIs for prototype projects - faster to start",
    "api_catalog.tip_2": "Store API Keys in IVS API Vault for security",
    "api_catalog.tip_3": "Test APIs with curl or Postman before writing code",
    "api_catalog.tip_4": "Check Rate Limits of each API to avoid getting blocked",

    // Deploy Guide
    "guide.button": "AI Guide",
    "guide.tooltip": "AI prompts & file structure guide for deploying apps",
    "guide.title": "App Preparation Guide",
    "guide.subtitle": "AI Prompts + correct file structures for IVS deploy",
    "guide.tab_prompts": "AI Prompts & File Structure",
    "guide.tab_template": "ivs-app.md Template",
    "guide.file_structure": "File Structure",
    "guide.ai_prompt": "AI Prompt",
    "guide.copy": "Copy",
    "guide.copied": "Copied!",
    "guide.copy_template": "Copy Template",
    "guide.template_title": "ivs-app.md — Add to your project",
    "guide.template_desc": "Copy this file to your project root so AI understands IVS requirements",

    "guide.type.static": "Static",
    "guide.type.nodejs": "Node.js",
    "guide.type.fastapi": "FastAPI",
    "guide.type.streamlit": "Streamlit",
    "guide.type.fullstack": "Fullstack",

    "guide.structure.static": `my-app/
├── index.html      ← entry point
├── style.css
├── script.js
└── assets/`,
    "guide.structure.nodejs": `my-app/
├── package.json    ← must have "start" script
├── package-lock.json
├── src/
│   └── index.js
└── public/`,
    "guide.structure.fastapi": `my-app/
├── main.py          ← must have FastAPI()
├── requirements.txt
└── routers/
    └── api.py`,
    "guide.structure.streamlit": `my-app/
├── app.py           ← entry point
├── requirements.txt ← must include streamlit
└── pages/
    └── dashboard.py`,
    "guide.structure.fullstack": `my-app/
├── backend/
│   ├── main.py           ← FastAPI backend
│   ├── requirements.txt
│   └── routers/
├── frontend/
│   ├── dist/             ← must build first!
│   │   ├── index.html
│   │   └── assets/
│   ├── package.json
│   └── src/
└── (no Dockerfile needed — IVS generates it)`,

    "guide.prompt.static": `Create an HTML/CSS/JavaScript website with:
- index.html as entry point
- Separate style.css for styles
- Separate script.js for logic
- Use Tailwind CSS CDN for styling
- Responsive mobile support

Structure: all files at root (no subfolders)
Deploy: zip all files and upload to IVS`,
    "guide.prompt.nodejs": `Create a Node.js application with:
- package.json with "start" script
- Express.js for HTTP server
- PORT from environment variable:
  const PORT = process.env.PORT || 3000;
- Health check at GET /
- Include package-lock.json

Structure: package.json at root
Deploy: zip folder (exclude node_modules)`,
    "guide.prompt.fastapi": `Create a FastAPI application with:
- main.py as entry point with:
  from fastapi import FastAPI
  app = FastAPI()
- requirements.txt listing all packages
  (fastapi, uvicorn, etc.)
- Read PORT from environment variable
- Health check endpoint at GET /
- CORS support

Structure: main.py + requirements.txt at root
Deploy: zip folder (exclude .venv)`,
    "guide.prompt.streamlit": `Create a Streamlit application with:
- app.py as entry point (not main.py)
- requirements.txt must include streamlit
- Use st.set_page_config() for page setup
- Sub-pages in pages/ folder

Structure: app.py + requirements.txt at root
Deploy: zip folder (exclude .venv)`,
    "guide.prompt.fullstack": `Create a Fullstack app (FastAPI + Vite React):
Structure:
  backend/
    main.py        ← FastAPI app
    requirements.txt
    routers/       ← API routes
  frontend/
    package.json   ← Vite + React
    src/
    dist/          ← build with npm run build

Important rules:
- Backend uses FastAPI, endpoints at /api/*
- Frontend uses Vite+React+TypeScript
- Must run: cd frontend && npm run build
  before zipping to produce dist/
- IVS auto-creates nginx proxy: / → frontend,
  /api → backend

Deploy: zip root folder (must include dist/)`,

    "guide.tip.static": "Static sites use nginx:alpine — lightest and fastest. Great for landing pages, portfolios, client-side dashboards",
    "guide.tip.nodejs": "Always include package-lock.json, and ensure a \"start\" script exists in package.json. Otherwise IVS will look for dev script or main field",
    "guide.tip.fastapi": "IVS detects FastAPI from the word \"fastapi\" or \"FastAPI\" in main.py. Without it, the app will be classified as plain Python",
    "guide.tip.streamlit": "Entry point must be app.py (not main.py) and requirements.txt must contain the word \"streamlit\"",
    "guide.tip.fullstack": "Important: Run npm run build before zipping! Without dist/, IVS will try to build inside Docker but it will be much slower",

    "guide.template": `# ivs-app.md — IVS Deploy Specification

## Deploy Target
- Platform: IVS (Internal Vibe Server)
- Container: Docker (auto-generated Dockerfile)
- Port: Read from ENV variable "PORT"

## Project Rules
1. No Dockerfile needed (IVS generates it)
2. No docker-compose.yml needed
3. Always read PORT from environment variable
4. Don't include .venv/, node_modules/, .git/ in zip

## App Type Detection (auto)
| Type       | Condition                          |
|------------|------------------------------------|
| static     | index.html at root                 |
| nodejs     | package.json at root               |
| python     | requirements.txt + main.py         |
| fastapi    | main.py contains "FastAPI"         |
| streamlit  | app.py + streamlit in requirements |
| fullstack  | backend/ + frontend/ folders       |

## Fullstack Structure (if applicable)
\`\`\`
backend/main.py        → FastAPI app
backend/requirements.txt
frontend/package.json  → Required (build script)
frontend/src/          → Source code
frontend/dist/         → Optional (IVS auto-builds if missing)
\`\`\`

## Environment Variables
- PORT: assigned by IVS automatically
- Vault keys: injected from IVS Vault

## Constraints (v1.0)
- Max upload: ~150MB zip
- No persistent storage (data lost on redeploy)
- No custom domain (use IP:PORT)
- Single container per app`,

    // Case Studies
    "guide.tab_cases": "Case Studies",
    "guide.cases_title": "Common Problems & Solutions",
    "guide.cases_subtitle": "Real cases from IVS + Vibe Code usage",

    "guide.case.line_oa.title": "LINE OA Webhook Error",
    "guide.case.line_oa.problem": "LINE Developers shows Webhook Error even though the container is running fine",
    "guide.case.line_oa.cause": "1. Dockerfile CMD points to server.js that requires MySQL, but Docker has no DB → Connection Error\n2. Should use local-server.js (JSON file-based) instead",
    "guide.case.line_oa.fix": "• Check Dockerfile CMD points to the correct file\n• If multiple server files exist, choose the one without DB dependency\n• IVS auto-warns ⛔ when DB dependency is detected",
    "guide.case.line_oa.tag": "LINE OA · Webhook · Dockerfile",

    "guide.case.ngrok.title": "ngrok Tunnel Fails (422 Error)",
    "guide.case.ngrok.problem": "ngrok tunnel sends request but gets HTTP 422 back, even though container returns 200",
    "guide.case.ngrok.cause": "1. Used --pooling-enabled flag which creates Cloud Endpoint with AI Gateway\n2. AI Gateway intercepts all POST requests and returns 422 (ERR_NGROK_3803)\n3. Even after removing the flag, Cloud Endpoint persists on Dashboard",
    "guide.case.ngrok.fix": "• Never use --pooling-enabled for webhook/API tunnels\n• If already used → go to ngrok Dashboard → Endpoints → delete Cloud Endpoint\n• Restart: ngrok http PORT --url=your-domain.ngrok-free.dev\n• When deploying on IVS, create a new Tunnel in IVS (don't reuse Vibe Code's)",
    "guide.case.ngrok.tag": "ngrok · Tunnel · AI Gateway · 422",

    "guide.case.db_deploy.title": "Cannot Deploy App with MySQL/Database",
    "guide.case.db_deploy.problem": "App runs on dev machine but crashes on IVS because it can't connect to Database",
    "guide.case.db_deploy.cause": "1. IVS Docker container has no Database server (MySQL, PostgreSQL, MongoDB)\n2. Apps with require('mysql2') or import mysql will crash immediately\n3. Vibe Code often creates 2 files: server.js (uses DB) and local-server.js (uses JSON)",
    "guide.case.db_deploy.fix": "• Use JSON file instead of Database for IVS deploy\n• Fix Dockerfile CMD to point to non-DB file:\n  CMD [\"node\", \"src/local-server.js\"]\n• Or use SQLite (single file, no server needed)\n• IVS auto-warns ⛔ when DB dependency is detected during validation",
    "guide.case.db_deploy.tag": "MySQL · Database · JSON · Dockerfile",

    // Resources
    "res.title": "System Resources",
    "res.subtitle": "Monitor hardware, capacity, and per-app performance",
    "res.cpu": "CPU",
    "res.ram": "RAM",
    "res.storage": "Storage",
    "res.gpu": "GPU",
    "res.gpu_nvidia": "GPU (NVIDIA)",
    "res.gpu_apple": "GPU (Apple Silicon)",
    "res.gpu_none": "No GPU detected",
    "res.cores": "cores",
    "res.used": "Used",
    "res.total": "Total",
    "res.free": "Free",
    "res.capacity": "System Capacity",
    "res.apps_running": "Apps Running",
    "res.apps_can_add": "Can add ~",
    "res.apps_unit": "apps",
    "res.ram_per_app": "Est. RAM per app ~",
    "res.alerts": "Alerts",
    "res.no_alerts": "No alerts — system is healthy",
    "res.per_app": "Per-App Resource Usage",
    "res.no_apps": "No apps currently running",
    "res.col_app": "App",
    "res.col_type": "Type",
    "res.col_cpu": "CPU",
    "res.col_ram": "RAM (MB)",
    "res.col_port": "Port",
    "res.history": "24h Statistics",
    "res.history_cpu": "CPU (%)",
    "res.history_ram": "RAM (MB)",
    "res.history_apps": "Apps Running",
    "res.export": "Export Report",
    "res.exporting": "Generating report...",
    "res.export_success": "Report generated",
    "res.export_download": "Download",
    "res.refresh": "Refresh",
    "res.last_updated": "Last updated",
    "res.level_ok": "OK",
    "res.level_warn": "Warning",
    "res.level_crit": "Critical",

    "role.admin": "Admin",
    "role.developer": "Developer",
    "role.viewer": "Viewer",

    "lang.th": "ไทย",
    "lang.en": "English",
    "lang.en-EU": "English (EU)",
    "lang.ja": "日本語",
  },

  // ───────────────────────────────────────────────────────────
  // GDPR overlay — overrides only compliance-sensitive strings.
  // Falls back to `en` for everything else.
  // ───────────────────────────────────────────────────────────
  "en-EU": {
    "lang.en-EU": "English (EU)",
    "settings.tab.logs": "Audit Logs (GDPR Art. 30)",
    "settings.tab.pdpa": "GDPR (ROPA)",
    "settings.ntp.title": "NTP Time Reference (GDPR Art. 32 integrity)",
    "settings.log.title_compliance": "Audit Log (GDPR Art. 30)",
    "settings.log.compliance_badge": "GDPR Compliant",

    // Privacy notice — GDPR Art. 13/14 information notice
    "settings.pdpa_title": "Records of Processing Activities (GDPR Art. 30)",
    "settings.pdpa_desc": "EU GDPR Regulation 2016/679 compliance",

    // Retention — GDPR Storage Limitation principle (Art. 5(1)(e))
    "retention.title": "Data Retention Policy (GDPR)",
    "retention.subtitle": "Set retention per log type. Expired data is auto-deleted under the Storage Limitation principle.",
    "retention.subtitle_short": "Configure log retention per GDPR Art. 5(1)(e) — Storage Limitation",
    "retention.legal_note": "GDPR Art. 5(1)(e) Storage Limitation — personal data shall be kept no longer than necessary for the stated purpose. The controller defines retention; the supervisory authority may require extension under Art. 17(3).",
    "retention.over_recommended": "Long retention — must justify under purpose limitation",

    // Delete confirmations
    "delete.irreversible": "Irreversible. Personal data deletion under GDPR Art. 17 (Right to Erasure) is final — export the data first if you need it.",

    // Audit detail
    "audit_detail.subtitle": "Complete record per GDPR Art. 30 (Records of Processing) and Art. 32 (Security of Processing)",
    "audit_detail.legal_note": "Timestamps verified via NTP — required under GDPR Art. 32 integrity controls",

    // App log retention reference
    "retention.desc.app_logs": "Container stdout/stderr — anonymized at ingestion (Privacy by Design, Art. 25)",

    // Privacy Notice — GDPR wording
    "pn.default_title": "Information Notice (GDPR Art. 13)",
    "pn.default_detail": "This application processes personal data. Your consent is recorded under GDPR Art. 7 and may be withdrawn at any time under Art. 7(3).",
    "pn.legal_footer": "Under GDPR Art. 7(3) — consent withdrawal must be as easy as giving it. Change at any time.",
    "pn.link_policy": "Privacy Policy (GDPR Art. 13/14)",

    // Tunnel share — GDPR wording
    "tunnel.share.subject_suffix": "access link with GDPR Art. 13 information",
    "tunnel.share.body.intro_l2": "Please review the GDPR Art. 13 information notice below before using this link.",
    "tunnel.share.body.section_notice": "⚠️  Personal Data Processing Notice (GDPR Art. 13)",
    "tunnel.share.body.howto_3": "3. Your consent will be recorded per GDPR Art. 7 — lawful basis and withdrawal rights apply",
    "tunnel.share.body.section_security": "🔒  Security Warning (GDPR Art. 32)",
    "tunnel.share.body.security_3": "• Use within your organization's policy and the GDPR principles of lawfulness, fairness, and transparency",

    // PII suggestions — GDPR Art. 4(1) "personal data" examples
    "pii.national_id": "National ID / Passport (Art. 9 if applicable)",
    "pii.dob": "Date of birth",
    "pii.line_id": "Online identifier (Art. 4(1))",
    "pii.photo_bio": "Photo / Biometric data (Art. 9 special category)",
    "pii.bank_account": "Financial account",
    "pii.tax_id": "Tax / national identifier",
    "pii.org_info": "Organization affiliation",
  },

  // ───────────────────────────────────────────────────────────
  // APPI overlay (個人情報の保護に関する法律). Japanese UI for core
  // compliance + minimal nav strings; rest falls back to `en`.
  // ───────────────────────────────────────────────────────────
  ja: {
    "lang.ja": "日本語",

    // Sidebar
    "nav.dashboard": "ダッシュボード",
    "nav.apps": "アプリ",
    "nav.tunnels": "トンネル",
    "nav.vault": "APIキー保管庫",
    "nav.resources": "システムリソース",
    "nav.settings": "設定",
    "nav.signout": "ログアウト",

    // Login
    "login.title": "Internal Vibe Server",
    "login.username": "ユーザー名",
    "login.password": "パスワード",
    "login.submit": "ログイン",

    // Dashboard
    "dash.title": "ダッシュボード",
    "dash.refresh": "更新",
    "dash.last_updated": "最終更新",

    // Audit logs — APPI Art. 26 (records of processing) equivalent
    "settings.tab.logs": "監査ログ (APPI)",
    "settings.tab.pdpa": "APPI 取扱記録",
    "settings.ntp.title": "NTP時刻参照 (APPI 安全管理措置)",
    "settings.log.title_compliance": "監査ログ — 個人情報保護法対応",
    "settings.log.compliance_badge": "APPI準拠",

    // PDPA tab is shown but worded for APPI
    "settings.pdpa_title": "個人情報取扱記録 (APPI)",
    "settings.pdpa_desc": "個人情報の保護に関する法律 (2003年制定, 2022年改正) 対応",

    // Retention — APPI doesn't specify a minimum, but PIPC guidance
    // recommends keeping security logs for an appropriate period.
    "retention.title": "データ保存ポリシー (APPI)",
    "retention.subtitle": "各ログ種別の保存期間を設定。期限切れデータは自動削除されます",
    "retention.subtitle_short": "個人情報保護法 (APPI) に基づきログ保存期間を設定",
    "retention.legal_note": "個人情報保護法 第19条 (適正な取得) 及び 第23条 (安全管理措置)。委員会の指示によりさらに長期保存を求められる場合があります。",
    "retention.days": "日",
    "retention.default": "デフォルト",
    "retention.save": "保存",
    "retention.cancel": "キャンセル",

    // Delete confirmations
    "delete.irreversible": "取り消せません。APPI 第30条 (利用停止・消去等) に基づく個人情報の削除は最終的なものです。必要に応じて事前にエクスポートしてください。",

    // Audit detail
    "audit_detail.title": "イベント詳細",
    "audit_detail.subtitle": "個人情報保護法に基づく完全な記録",
    "audit_detail.user": "ユーザー",
    "audit_detail.resource": "リソース",
    "audit_detail.details": "詳細",
    "audit_detail.close": "閉じる",
    "audit_detail.legal_note": "NTPによりタイムスタンプ検証済み — APPI 安全管理措置の要件",

    // App log retention reference
    "retention.desc.app_logs": "コンテナ stdout/stderr — 取得時に匿名化 (Privacy by Design)",

    // Roles
    "role.admin": "管理者",
    "role.developer": "開発者",
    "role.viewer": "閲覧者",

    // Pagination
    "pagination.showing": "表示中",
    "pagination.of": "/",
    "pagination.per_page": "ページごと",

    // Privacy Notice — APPI wording
    "pn.default_title": "個人情報の取扱いに関する通知 (APPI)",
    "pn.default_detail": "本アプリケーションは個人情報を取扱います。APPI第18条 (取得時の利用目的通知) に基づきご確認ください。",
    "pn.review_badge": "同意状況の確認・変更",
    "pn.current_status": "現在の状況",
    "pn.status_accepted": "✓ 同意済み",
    "pn.status_declined": "✗ 拒否",
    "pn.recorded_at": "記録日時",
    "pn.link_policy": "個人情報保護方針",
    "pn.link_full_notice": "通知全文",
    "pn.accept_current": "✓ 同意済み (現在の選択)",
    "pn.switch_to_accept": "同意に変更",
    "pn.decline_current": "✗ 拒否 (現在の選択)",
    "pn.switch_to_decline": "拒否に変更",
    "pn.close": "閉じる",
    "pn.saving": "保存中…",
    "pn.accept_and_enter": "同意して利用する",
    "pn.decline": "拒否する",
    "pn.legal_footer": "個人情報保護法に基づき、同意はいつでも変更可能です",

    // Tunnel share — APPI wording
    "tunnel.share.subject_suffix": "APPI 通知付きアクセスリンク",
    "tunnel.share.body.greeting": "ご担当者様",
    "tunnel.share.body.intro_l1": 'アプリケーション "{app}" の一時アクセスリンクをご案内いたします。',
    "tunnel.share.body.intro_l2": "ご利用の前に、下記の個人情報取扱通知 (APPI) をご確認ください。",
    "tunnel.share.body.section_notice": "⚠️  個人情報の取扱いに関する通知 (APPI)",
    "tunnel.share.body.no_notice": "(本アプリは個人情報取扱通知が未設定です — 外部公開前に管理者による設定を推奨します)",
    "tunnel.share.body.section_link": "🔗  アクセスリンク (Tunnel)",
    "tunnel.share.body.expires_at": "リンク有効期限",
    "tunnel.share.body.section_howto": "📖  ご利用方法",
    "tunnel.share.body.howto_1": "1. 上記リンクをクリックしてアプリを開く",
    "tunnel.share.body.howto_2": "2. 個人情報取扱通知が表示された場合は、内容をご確認のうえ同意可否をご判断ください",
    "tunnel.share.body.howto_3": "3. 同意・拒否の選択は個人情報保護法に基づき記録されます",
    "tunnel.share.body.howto_4": "4. 同意状況はいつでもこのリンクから変更できます",
    "tunnel.share.body.section_security": "🔒  セキュリティ上の注意 (APPI 安全管理措置)",
    "tunnel.share.body.security_1": "• 本リンクは外部ネットワークから内部システムへのアクセスを許可するものです",
    "tunnel.share.body.security_2": "• 不適切な利用により情報漏洩のリスクがあります",
    "tunnel.share.body.security_3": "• 貴組織のセキュリティポリシーに従ってご利用ください",
    "tunnel.share.body.security_4": "• 異常を検知した場合は速やかに管理者へご連絡ください",
    "tunnel.share.body.section_note": "💬  送信者からの追記",
    "tunnel.share.body.signoff": "IVS — Internal Vibe Server より送信",

    // PII suggestion checklist — APPI Art. 2 "個人情報" examples
    "pii.full_name": "氏名",
    "pii.email": "メールアドレス",
    "pii.phone": "電話番号",
    "pii.address": "住所",
    "pii.national_id": "マイナンバー / パスポート",
    "pii.dob": "生年月日 / 年齢",
    "pii.line_id": "SNS ID (LINE等)",
    "pii.photo_bio": "顔写真 / 生体情報",
    "pii.bank_account": "金融口座情報",
    "pii.tax_id": "納税者番号",
    "pii.org_info": "所属組織情報",

    // Misc inline strings
    "user_delete.reassigned_suffix": "アプリの所有権を移譲しました:",
    "settings.export_success": "エクスポート完了",
    "settings.activities_count": "件",
    "settings.pn_saved": "通知を保存しました",
    "settings.pdpa.found": "検出",
    "settings.pdpa.not_found": "未検出",
    "settings.pdpa.add_all_detected": "検出されたすべてを追加",
    "settings.pn_detail_placeholder": "本アプリケーションは、サービス提供の目的のために個人情報を収集・利用・開示します...",
    "settings.pn_preview_placeholder": "詳細はここに表示されます...",
    "deploy.auto_sanitize_note": "Auto-Sanitize により不要ファイルが自動削除されます",
    "deploy.close": "閉じる",
    "datepicker.clear": "クリア",
    "datepicker.today": "今日",
  },
};

/**
 * Resolution order: requested locale → en → key itself.
 * EU and JA are overlays — missing strings fall back to en.
 */
export function t(key: string, locale: Locale): string {
  return (
    translations[locale]?.[key] ||
    translations.en[key] ||
    key
  );
}

export function getStoredLocale(): Locale {
  if (typeof window === "undefined") return "th";
  return (localStorage.getItem("ivs_locale") as Locale) || "th";
}

export function setStoredLocale(locale: Locale) {
  if (typeof window !== "undefined") {
    localStorage.setItem("ivs_locale", locale);
  }
}
