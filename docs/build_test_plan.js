const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, LevelFormat, PageBreak, PageNumber, ExternalHyperlink,
} = require("docx");

// ─── Theme ──────────────────────────────────────────────────────
const BRAND = "4338CA";   // IVS purple
const DARK = "1E293B";
const GRAY = "64748B";
const GREEN = "16A34A";
const RED = "DC2626";
const AMBER = "D97706";
const BLUE = "2563EB";
const LIGHT_BG = "F8FAFC";
const GREEN_BG = "F0FDF4";
const RED_BG = "FEF2F2";
const AMBER_BG = "FFFBEB";
const BLUE_BG = "EFF6FF";
const PURPLE_BG = "F5F3FF";

const border = { style: BorderStyle.SINGLE, size: 1, color: "D1D5DB" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorders = { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } };

// ─── Helpers ────────────────────────────────────────────────────
function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({ heading: level, spacing: { before: 300, after: 150 }, children: [new TextRun({ text, bold: true, font: "Arial" })] });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after || 100 },
    alignment: opts.align,
    children: [new TextRun({ text, font: "Arial", size: opts.size || 22, color: opts.color || DARK, bold: opts.bold, italics: opts.italics })],
  });
}

function bullet(text, ref = "bullets", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: "Arial", size: 22, color: DARK })],
  });
}

function cell(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.bg ? { fill: opts.bg, type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    verticalAlign: "center",
    children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: opts.size || 20, bold: opts.bold, color: opts.color || DARK })] })],
  });
}

function headerCell(text, width) {
  return cell(text, { width, bold: true, color: "FFFFFF", bg: BRAND, size: 20 });
}

// ─── Test Case Table Builder ────────────────────────────────────
function testTable(headers, rows, colWidths) {
  const totalWidth = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => headerCell(h, colWidths[i])) }),
      ...rows.map((row) =>
        new TableRow({
          children: row.map((c, i) => {
            if (typeof c === "object") return cell(c.text, { width: colWidths[i], ...c });
            return cell(c, { width: colWidths[i] });
          }),
        })
      ),
    ],
  });
}

// ─── Checkbox style ─────────────────────────────────────────────
function checkbox(text) {
  return new Paragraph({
    spacing: { after: 40 },
    children: [new TextRun({ text: "☐ " + text, font: "Arial", size: 20, color: DARK })],
  });
}

// ─── Content ────────────────────────────────────────────────────

const COLS4 = [700, 3200, 3800, 1660];
const COLS5 = [600, 2400, 3200, 1660, 1500];
const COL_HDR4 = ["#", "Test Case", "Expected Result", "Priority"];
const COL_HDR5 = ["#", "Test Case", "Expected Result", "Priority", "Status"];

function priorityCell(p) {
  const map = { Critical: { bg: RED_BG, color: RED }, High: { bg: AMBER_BG, color: AMBER }, Medium: { bg: BLUE_BG, color: BLUE }, Low: { bg: GREEN_BG, color: GREEN } };
  const s = map[p] || {};
  return { text: p, bg: s.bg, color: s.color, bold: true };
}

function statusCell() {
  return { text: "☐ Pass / Fail", color: GRAY, size: 18 };
}

// ================================================================
// BUILD
// ================================================================
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: BRAND },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: DARK },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: DARK },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
      ]},
      { reference: "numbers", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
    ],
  },
  sections: [
    // ════════════════ COVER PAGE ════════════════
    {
      properties: {
        page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
      },
      children: [
        new Paragraph({ spacing: { before: 3000 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "IVS", font: "Arial", size: 72, bold: true, color: BRAND }),
        ]}),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
          new TextRun({ text: "Internal Vibe Server", font: "Arial", size: 28, color: GRAY }),
        ]}),
        new Paragraph({ spacing: { before: 600 }, alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "แผนการทดสอบผลิตภัณฑ์", font: "Arial", size: 44, bold: true, color: DARK }),
        ]}),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [
          new TextRun({ text: "Product Test Plan", font: "Arial", size: 28, color: GRAY, italics: true }),
        ]}),
        new Paragraph({ spacing: { before: 400 }, alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "Version 1.0  |  พฤษภาคม 2026", font: "Arial", size: 22, color: GRAY }),
        ]}),
        new Paragraph({ spacing: { before: 600 }, alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "แบ่งเป็น 2 รูปแบบผลิตภัณฑ์:", font: "Arial", size: 24, color: DARK }),
        ]}),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [
          new TextRun({ text: "1. Software License — Docker / On-Premise OS", font: "Arial", size: 22, color: BRAND, bold: true }),
        ]}),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "2. Appliance Bundle — IVS + Synology NAS", font: "Arial", size: 22, color: BRAND, bold: true }),
        ]}),
      ],
    },

    // ════════════════ TABLE OF CONTENTS ════════════════
    {
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      headers: {
        default: new Header({ children: [new Paragraph({ children: [
          new TextRun({ text: "IVS Product Test Plan v1.0", font: "Arial", size: 16, color: GRAY, italics: true }),
        ]})] }),
      },
      footers: {
        default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "Page ", font: "Arial", size: 16, color: GRAY }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: GRAY }),
        ]})] }),
      },
      children: [
        heading("สารบัญ", HeadingLevel.HEADING_1),
        para("ส่วนที่ 1: ภาพรวมและขอบเขต", { bold: true, size: 24 }),
        para("ส่วนที่ 2: Software License — ทดสอบบน Docker / OS", { bold: true, size: 24 }),
        para("  2.1 Functional Testing — ทดสอบฟังก์ชันหลัก"),
        para("  2.2 API Testing — ทดสอบ Backend API"),
        para("  2.3 Security Testing — ทดสอบความปลอดภัย"),
        para("  2.4 Performance Testing — ทดสอบประสิทธิภาพ"),
        para("  2.5 Cross-Platform Testing — ทดสอบข้ามแพลตฟอร์ม"),
        para("  2.6 Upgrade & Migration — ทดสอบการอัปเกรด"),
        para("ส่วนที่ 3: Appliance Bundle — IVS + Synology NAS", { bold: true, size: 24 }),
        para("  3.1 Hardware Compatibility — ทดสอบความเข้ากันของ Hardware"),
        para("  3.2 Installation & Setup — ทดสอบการติดตั้ง"),
        para("  3.3 DSM Integration — ทดสอบร่วมกับ DSM"),
        para("  3.4 Storage & Performance — ทดสอบ Storage"),
        para("  3.5 Network & DNS — ทดสอบเครือข่าย"),
        para("  3.6 Reliability — ทดสอบความเสถียร"),
        para("  3.7 Customer Experience — ทดสอบประสบการณ์ลูกค้า"),
        para("ส่วนที่ 4: Acceptance Criteria — เกณฑ์ผ่านก่อนขาย", { bold: true, size: 24 }),

        new Paragraph({ children: [new PageBreak()] }),

        // ════════════════ PART 1: OVERVIEW ════════════════
        heading("ส่วนที่ 1: ภาพรวมและขอบเขต", HeadingLevel.HEADING_1),

        heading("1.1 สรุปผลิตภัณฑ์ IVS 1.0", HeadingLevel.HEADING_2),
        para("IVS (Internal Vibe Server) คือระบบ Self-hosted App Deployment Platform สำหรับองค์กร ที่ช่วยให้ทีมพัฒนาสามารถ Deploy แอปพลิเคชันจาก Vibe Code (AI-assisted coding) ขึ้นเซิร์ฟเวอร์ภายในได้ง่ายผ่าน Dashboard เพียง Drag & Drop ไฟล์ .zip"),

        heading("1.2 Components ที่ต้องทดสอบ", HeadingLevel.HEADING_2),
        testTable(
          ["Component", "Technology", "Port", "Role"],
          [
            ["Backend API", "FastAPI / Python", "8000", "Core API, Docker management, DB"],
            ["Frontend", "Next.js 14", "3000", "Dashboard UI"],
            ["Caddy", "Caddy 2 Alpine", "80, 443", "Reverse Proxy, Auto-SSL"],
            ["CoreDNS", "CoreDNS 1.11", "53", "Local DNS (*.vibe.local)"],
            ["Gitea", "Gitea 1.22", "3001", "Internal Git Server"],
            ["Docker Engine", "Docker 20.10+", "Socket", "Container Runtime"],
          ],
          [2000, 2400, 1800, 3160]
        ),

        heading("1.3 รูปแบบผลิตภัณฑ์", HeadingLevel.HEADING_2),
        testTable(
          ["รูปแบบ", "Target", "ราคา (ประมาณ)", "รายละเอียด"],
          [
            [{ text: "Software License", bold: true }, "Docker / Linux / macOS / WSL2", "ขายเฉพาะ License", "ลูกค้ามีเครื่องอยู่แล้ว ติดตั้งเอง"],
            [{ text: "Appliance Bundle", bold: true }, "Synology DS225+ / DS925+", "License + NAS", "ขายพร้อม NAS พร้อมใช้งาน"],
          ],
          [2200, 2800, 2000, 2360]
        ),

        heading("1.4 ขอบเขตการทดสอบ", HeadingLevel.HEADING_2),
        para("ทดสอบทั้ง 2 รูปแบบ โดยแบ่งเป็น:"),
        bullet("Functional Testing — ทุกฟีเจอร์ทำงานถูกต้อง"),
        bullet("API Testing — Backend endpoints ตอบสนองถูกต้อง"),
        bullet("Security Testing — Authentication, Authorization, Injection"),
        bullet("Performance Testing — Load, Concurrency, Resource limits"),
        bullet("Cross-Platform — Docker on Linux/macOS/Windows WSL2"),
        bullet("Hardware Compatibility — Synology DS225+, DS925+"),
        bullet("Reliability — Power failure, Container crash recovery"),
        bullet("Customer Experience — Installation, First-time setup, Documentation"),

        new Paragraph({ children: [new PageBreak()] }),

        // ════════════════ PART 2: SOFTWARE LICENSE ════════════════
        heading("ส่วนที่ 2: Software License — ทดสอบบน Docker / OS", HeadingLevel.HEADING_1),

        // 2.1 Functional Testing
        heading("2.1 Functional Testing — ทดสอบฟังก์ชันหลัก", HeadingLevel.HEADING_2),

        heading("2.1.1 Authentication & Authorization", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "Login ด้วย admin/admin123", "ได้ JWT token, redirect ไป Dashboard", priorityCell("Critical"), statusCell()],
          ["2", "Login ด้วย password ผิด", "แสดง error, ไม่ได้ token", priorityCell("Critical"), statusCell()],
          ["3", "สร้าง User ใหม่ (admin, dev, viewer)", "สร้างสำเร็จ แต่ละ role มีสิทธิ์ต่างกัน", priorityCell("High"), statusCell()],
          ["4", "Viewer เข้าถึงแอปที่ไม่ได้ assign", "ถูก block, แสดง 403", priorityCell("High"), statusCell()],
          ["5", "Dev ลบแอป", "ถูก block (เฉพาะ Admin ลบได้)", priorityCell("High"), statusCell()],
          ["6", "Token หมดอายุ", "Redirect ไป login, ไม่เข้าถึง API", priorityCell("Medium"), statusCell()],
        ], COLS5),

        heading("2.1.2 App Deployment (Core Feature)", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "Upload .zip (Static HTML)", "Detect type=static, build สำเร็จ, เข้า URL ได้", priorityCell("Critical"), statusCell()],
          ["2", "Upload .zip (Node.js + package.json)", "Detect type=nodejs, npm install + start", priorityCell("Critical"), statusCell()],
          ["3", "Upload .zip (FastAPI + main.py)", "Detect type=fastapi, pip install + uvicorn", priorityCell("Critical"), statusCell()],
          ["4", "Upload .zip (Streamlit + app.py)", "Detect type=streamlit, run streamlit", priorityCell("High"), statusCell()],
          ["5", "Upload .zip (Fullstack backend+frontend)", "Detect type=fullstack, build ทั้ง 2 ส่วน", priorityCell("High"), statusCell()],
          ["6", "Upload .zip ที่มี custom Dockerfile", "ใช้ Dockerfile ของ user, แจ้ง warning", priorityCell("High"), statusCell()],
          ["7", "Upload .zip ที่มี DB dependency", "แจ้ง ⛔ warning (MySQL/PostgreSQL/MongoDB)", priorityCell("High"), statusCell()],
          ["8", "Upload .zip ที่มีหลาย server files", "แจ้ง warning ให้ตรวจสอบ CMD", priorityCell("Medium"), statusCell()],
          ["9", "Upload ไฟล์ที่ไม่ใช่ .zip", "แสดง error, ปฏิเสธ", priorityCell("Medium"), statusCell()],
          ["10", "Upload .zip ขนาดใหญ่ (>150MB)", "แสดง error, ปฏิเสธ", priorityCell("Medium"), statusCell()],
        ], COLS5),

        heading("2.1.3 App Lifecycle Management", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "Start แอปที่หยุดอยู่", "Container เปลี่ยนเป็น running, เข้า URL ได้", priorityCell("Critical"), statusCell()],
          ["2", "Stop แอปที่กำลังรัน", "Container หยุด, URL ไม่ตอบ", priorityCell("Critical"), statusCell()],
          ["3", "Restart แอป", "Container restart สำเร็จ, ไม่สูญเสีย data", priorityCell("Critical"), statusCell()],
          ["4", "Delete แอป", "Container + image ถูกลบ, DNS record ถูกลบ", priorityCell("High"), statusCell()],
          ["5", "ดู Container logs", "แสดง stdout/stderr ของ container", priorityCell("High"), statusCell()],
          ["6", "ดู Build logs", "แสดง Docker build output ทีละขั้น", priorityCell("Medium"), statusCell()],
          ["7", "Re-deploy (อัปเกรด version)", "สร้าง version ใหม่, container ใหม่", priorityCell("High"), statusCell()],
        ], COLS5),

        heading("2.1.4 Dashboard & System Health", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "แสดง CPU, RAM, Disk usage", "ตัวเลขตรงกับ reality (±5%)", priorityCell("High"), statusCell()],
          ["2", "แสดง apps_running / apps_total", "นับถูกต้องจาก DB (ไม่ใช่ Docker labels)", priorityCell("High"), statusCell()],
          ["3", "WebSocket real-time update", "ค่า CPU/RAM อัปเดตทุก 3 วินาที", priorityCell("Medium"), statusCell()],
          ["4", "Docker status indicator", "แสดงจุดเขียว/แดงตามสถานะจริง", priorityCell("Medium"), statusCell()],
        ], COLS5),

        heading("2.1.5 Tunnel (ngrok Integration)", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "สร้าง Tunnel ให้แอป", "ได้ public URL, เข้าจากภายนอกได้", priorityCell("High"), statusCell()],
          ["2", "ลบ Tunnel", "URL หยุดทำงาน", priorityCell("Medium"), statusCell()],
          ["3", "Tunnel + LINE Webhook", "LINE Verify ผ่าน, ส่ง/รับข้อความได้", priorityCell("High"), statusCell()],
        ], COLS5),

        heading("2.1.6 Vault (Key Management)", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "สร้าง Secret Key", "บันทึกแบบ encrypted, แสดงเฉพาะ masked", priorityCell("High"), statusCell()],
          ["2", "ดู Key (Reveal)", "แสดงค่าจริงเฉพาะ Admin/Dev ที่มีสิทธิ์", priorityCell("High"), statusCell()],
          ["3", "ลบ Key", "ลบสำเร็จ, container ที่ใช้อยู่ไม่ crash", priorityCell("Medium"), statusCell()],
          ["4", "Inject Key to Container", "ENV variable ถูกส่งเข้า container ถูกต้อง", priorityCell("Critical"), statusCell()],
        ], COLS5),

        heading("2.1.7 PDPA Compliance", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "Scan แอปหา personal data", "ตรวจจับ pattern (email, phone, ID card)", priorityCell("High"), statusCell()],
          ["2", "สร้าง Privacy Notice", "แสดง popup ที่ public URL ของแอป", priorityCell("High"), statusCell()],
          ["3", "Export ROPA Report", "ได้ไฟล์ .md พร้อม SHA-256 hash", priorityCell("Medium"), statusCell()],
        ], COLS5),

        heading("2.1.8 Gitea (Git Server)", HeadingLevel.HEADING_3),
        testTable(COL_HDR5, [
          ["1", "เข้า Gitea Dashboard", "เปิด http://git.vibe.local:3001 ได้", priorityCell("High"), statusCell()],
          ["2", "สร้าง Repository", "สร้าง repo + push code สำเร็จ", priorityCell("High"), statusCell()],
          ["3", "Clone ผ่าน HTTP", "git clone สำเร็จ", priorityCell("Medium"), statusCell()],
          ["4", "Clone ผ่าน SSH (port 2222)", "git clone ssh สำเร็จ", priorityCell("Low"), statusCell()],
        ], COLS5),

        new Paragraph({ children: [new PageBreak()] }),

        // 2.2 API Testing
        heading("2.2 API Testing — ทดสอบ Backend API", HeadingLevel.HEADING_2),
        para("ทดสอบทุก endpoint ด้วย HTTP client (curl / Postman / pytest)"),
        testTable(
          ["Module", "Endpoints", "Test Cases", "Priority"],
          [
            ["Auth", "POST /login, /logout, /users, GET /me, /users", "7 endpoints, JWT flow", priorityCell("Critical")],
            ["Apps", "POST /validate, /, /{id}/start|stop|restart, DELETE, GET /logs", "12 endpoints, full lifecycle", priorityCell("Critical")],
            ["System", "GET /health, /resources, /dns-config, WS /ws/health", "10 endpoints + WebSocket", priorityCell("High")],
            ["Vault", "GET, POST, DELETE /vault", "4 endpoints, encryption", priorityCell("High")],
            ["Tunnels", "GET, POST, DELETE /tunnels", "3 endpoints", priorityCell("Medium")],
            ["PDPA", "GET, PUT, POST /scan, /export, /privacy-notice", "10 endpoints", priorityCell("Medium")],
          ],
          [1600, 3200, 2800, 1760]
        ),

        // 2.3 Security
        heading("2.3 Security Testing — ทดสอบความปลอดภัย", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "SQL Injection ใน Login", "ไม่สามารถ inject ได้ (SQLAlchemy parameterized)", priorityCell("Critical"), statusCell()],
          ["2", "XSS ใน App name/description", "HTML entities ถูก escape", priorityCell("Critical"), statusCell()],
          ["3", "Path Traversal ใน file upload", "ไม่สามารถอ่านไฟล์นอก sandbox", priorityCell("Critical"), statusCell()],
          ["4", "API ไม่มี Token", "ทุก endpoint ตอบ 401", priorityCell("Critical"), statusCell()],
          ["5", "Vault key encryption at rest", "ค่าใน SQLite เป็น ciphertext ไม่ใช่ plaintext", priorityCell("Critical"), statusCell()],
          ["6", "Docker socket access control", "เฉพาะ backend container เข้าถึง socket", priorityCell("High"), statusCell()],
          ["7", "Container isolation", "App container A ไม่เข้าถึง container B", priorityCell("High"), statusCell()],
          ["8", "Brute force login", "Rate limit หรือ lockout หลังพยายามหลายครั้ง", priorityCell("Medium"), statusCell()],
          ["9", "CORS policy", "ไม่อนุญาต cross-origin จาก domain อื่น", priorityCell("Medium"), statusCell()],
          ["10", "Audit Log integrity", "ทุก action ถูกบันทึก, export มี SHA-256", priorityCell("High"), statusCell()],
        ], COLS5),

        // 2.4 Performance
        heading("2.4 Performance Testing — ทดสอบประสิทธิภาพ", HeadingLevel.HEADING_2),
        testTable(
          ["#", "Test Scenario", "Target Metric", "Condition"],
          [
            ["1", "Deploy app (Static HTML)", "< 30 วินาที", "ไฟล์ zip 5MB"],
            ["2", "Deploy app (Node.js)", "< 120 วินาที", "ไฟล์ zip 20MB, npm install"],
            ["3", "Deploy app (FastAPI)", "< 90 วินาที", "pip install 10 packages"],
            ["4", "Dashboard load time", "< 2 วินาที", "First contentful paint"],
            ["5", "API response time (health)", "< 500ms", "ไม่มี load"],
            ["6", "Concurrent deploys x3", "ทั้ง 3 สำเร็จ", "Deploy 3 apps พร้อมกัน"],
            ["7", "10 apps running simultaneously", "CPU < 80%, RAM < 90%", "8GB RAM machine"],
            ["8", "Container restart time", "< 5 วินาที", "docker restart"],
            ["9", "Upload 100MB zip", "ไม่ timeout, แสดง progress", "Network 100Mbps"],
            ["10", "WebSocket 10 connections", "ทุก client ได้ข้อมูล real-time", "10 browser tabs"],
          ],
          [600, 3000, 2600, 3160]
        ),

        new Paragraph({ children: [new PageBreak()] }),

        // 2.5 Cross-Platform
        heading("2.5 Cross-Platform Testing — ทดสอบข้ามแพลตฟอร์ม", HeadingLevel.HEADING_2),
        para("ทดสอบ docker-compose up -d บนทุกแพลตฟอร์มเป้าหมาย:"),
        testTable(
          ["Platform", "Docker Engine", "Test Items", "Priority"],
          [
            ["Ubuntu 22.04 LTS", "Docker CE 24+", "Full test suite + production mode", priorityCell("Critical")],
            ["Ubuntu 24.04 LTS", "Docker CE 26+", "Full test suite", priorityCell("High")],
            ["Debian 12", "Docker CE 24+", "Install + Deploy 3 apps", priorityCell("High")],
            ["macOS 14+ (Apple Silicon)", "Docker Desktop 4.x", "Full test suite (dev mode)", priorityCell("High")],
            ["macOS 14+ (Intel)", "Docker Desktop 4.x", "Install + Deploy 3 apps", priorityCell("Medium")],
            ["Windows 11 + WSL2", "Docker Desktop 4.x", "Install + Deploy 3 apps", priorityCell("Medium")],
            ["Rocky Linux 9 / AlmaLinux 9", "Docker CE 24+", "Install + Deploy 3 apps", priorityCell("Low")],
          ],
          [2800, 2200, 2800, 1560]
        ),

        heading("Browser Compatibility", HeadingLevel.HEADING_3),
        testTable(
          ["Browser", "Version", "Test", "Priority"],
          [
            ["Chrome", "120+", "Full UI test + Deploy + WebSocket", priorityCell("Critical")],
            ["Safari", "17+", "Full UI test + Deploy", priorityCell("High")],
            ["Firefox", "120+", "Full UI test + Deploy", priorityCell("Medium")],
            ["Edge", "120+", "Basic UI test", priorityCell("Low")],
          ],
          [2200, 1600, 3800, 1760]
        ),

        // 2.6 Upgrade
        heading("2.6 Upgrade & Migration Testing", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "Upgrade IVS 1.0 → 1.1 (future)", "Data ไม่หาย, apps ยังรันอยู่", priorityCell("High"), statusCell()],
          ["2", "Database migration (SQLite)", "Schema migrate สำเร็จ, data intact", priorityCell("High"), statusCell()],
          ["3", "Backup & Restore", "docker-compose down + up = ข้อมูลครบ", priorityCell("Critical"), statusCell()],
          ["4", "Volume persistence", "Restart machine → data ยังอยู่", priorityCell("Critical"), statusCell()],
        ], COLS5),

        new Paragraph({ children: [new PageBreak()] }),

        // ════════════════ PART 3: SYNOLOGY BUNDLE ════════════════
        heading("ส่วนที่ 3: Appliance Bundle — IVS + Synology NAS", HeadingLevel.HEADING_1),

        para("ทดสอบเฉพาะบน Synology NAS รุ่นที่ขาย ครอบคลุมตั้งแต่ Unbox → Setup → ใช้งานจริง → Maintenance"),

        // 3.1 Hardware Compatibility
        heading("3.1 Hardware Compatibility", HeadingLevel.HEADING_2),
        testTable(
          ["#", "Test Case (DS225+)", "Expected", "Priority", "Status"],
          [
            ["1", "Boot DSM 7.2+ สำเร็จ", "เข้า DSM Dashboard ได้", priorityCell("Critical"), statusCell()],
            ["2", "เพิ่ม RAM เป็น 6GB", "DSM แสดง 6GB, ไม่ error", priorityCell("Critical"), statusCell()],
            ["3", "ติดตั้ง Container Manager", "Install สำเร็จจาก Package Center", priorityCell("Critical"), statusCell()],
            ["4", "docker-compose up -d (IVS)", "ทุก container start สำเร็จ", priorityCell("Critical"), statusCell()],
            ["5", "Deploy 3 apps พร้อมกัน", "ทั้ง 3 รันได้, RAM < 5.5GB", priorityCell("High"), statusCell()],
            ["6", "CPU ไม่เกิน 80% ขณะ idle", "CPU < 30% เมื่อไม่มี deploy", priorityCell("Medium"), statusCell()],
          ],
          COLS5
        ),
        para(""),
        testTable(
          ["#", "Test Case (DS925+)", "Expected", "Priority", "Status"],
          [
            ["1", "Boot DSM 7.2+ / 7.3+", "เข้า DSM Dashboard ได้", priorityCell("Critical"), statusCell()],
            ["2", "RAM 8GB (default + 4GB เพิ่ม)", "DSM แสดง 8GB, ECC ทำงาน", priorityCell("Critical"), statusCell()],
            ["3", "ติดตั้ง Container Manager", "Install สำเร็จ", priorityCell("Critical"), statusCell()],
            ["4", "docker-compose up -d (IVS + Gitea)", "ทุก container start สำเร็จ", priorityCell("Critical"), statusCell()],
            ["5", "Deploy 10 apps พร้อมกัน", "ทั้ง 10 รันได้, RAM < 7GB", priorityCell("High"), statusCell()],
            ["6", "NVMe SSD Cache", "Docker volume อ่าน/เขียนเร็วขึ้น", priorityCell("Medium"), statusCell()],
            ["7", "RAM 16GB upgrade test", "Deploy 15+ apps ได้", priorityCell("Medium"), statusCell()],
          ],
          COLS5
        ),

        // 3.2 Installation
        heading("3.2 Installation & First-Time Setup", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "ทำตามคู่มือติดตั้ง (DOCX) ทุกขั้นตอน", "ติดตั้งสำเร็จภายใน 30 นาที", priorityCell("Critical"), statusCell()],
          ["2", "SSH เข้า NAS + docker-compose up", "ไม่มี error, ทุก service start", priorityCell("Critical"), statusCell()],
          ["3", "เปิด http://nas-ip:3000 ครั้งแรก", "แสดง Login page, login ด้วย admin ได้", priorityCell("Critical"), statusCell()],
          ["4", "Upload .env.example → .env", "ตั้งค่า SECRET_KEY, SERVER_IP สำเร็จ", priorityCell("High"), statusCell()],
          ["5", "ตั้งค่า DNS (CoreDNS)", "*.vibe.local resolve ได้จากเครื่องใน LAN", priorityCell("High"), statusCell()],
          ["6", "เปิด Gitea ครั้งแรก", "Initial setup สำเร็จ, สร้าง admin ได้", priorityCell("Medium"), statusCell()],
        ], COLS5),

        // 3.3 DSM Integration
        heading("3.3 DSM Integration", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "Container Manager แสดง IVS containers", "เห็นทุก container + status", priorityCell("High"), statusCell()],
          ["2", "DSM Firewall ไม่ block IVS ports", "Port 80, 443, 3000, 3001, 8000 เปิดอยู่", priorityCell("High"), statusCell()],
          ["3", "DSM Task Scheduler backup", "ตั้ง scheduled backup ได้", priorityCell("Medium"), statusCell()],
          ["4", "DSM update ไม่กระทบ IVS", "อัปเดต DSM แล้ว containers ยังรัน", priorityCell("High"), statusCell()],
          ["5", "Shared Folder permission", "docker/ivs/ มีสิทธิ์ถูกต้อง", priorityCell("Medium"), statusCell()],
          ["6", "Resource Monitor แสดง Docker usage", "เห็น CPU/RAM ของ containers", priorityCell("Low"), statusCell()],
        ], COLS5),

        new Paragraph({ children: [new PageBreak()] }),

        // 3.4 Storage & Performance
        heading("3.4 Storage & Performance", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "HDD RAID 1 (Mirror) performance", "Deploy app < 180 วินาที", priorityCell("High"), statusCell()],
          ["2", "SSD RAID 1 performance", "Deploy app < 90 วินาที", priorityCell("Medium"), statusCell()],
          ["3", "Docker volume บน Volume 1", "ข้อมูลไม่หายหลัง restart", priorityCell("Critical"), statusCell()],
          ["4", "พื้นที่เก็บข้อมูล > 80%", "แจ้ง warning, ไม่ crash", priorityCell("High"), statusCell()],
          ["5", "HDD ร้อน (> 50°C)", "DSM แจ้ง warning, IVS ยังรันได้", priorityCell("Medium"), statusCell()],
        ], COLS5),

        // 3.5 Network
        heading("3.5 Network & DNS", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "เข้า IVS จาก PC ใน LAN เดียวกัน", "เปิด http://nas-ip:3000 ได้", priorityCell("Critical"), statusCell()],
          ["2", "เข้า IVS จาก WiFi (DHCP)", "DNS resolve *.vibe.local ได้", priorityCell("High"), statusCell()],
          ["3", "เข้า deployed app จาก mobile", "เปิด http://nas-ip:PORT ได้", priorityCell("High"), statusCell()],
          ["4", "ngrok tunnel จาก NAS", "Public URL เข้าถึงได้จากภายนอก", priorityCell("High"), statusCell()],
          ["5", "NAS เปลี่ยน IP (DHCP renew)", "อัปเดต .env + restart แล้วใช้ได้", priorityCell("Medium"), statusCell()],
          ["6", "Caddy auto-SSL (local)", "HTTPS ทำงานกับ self-signed cert", priorityCell("Low"), statusCell()],
        ], COLS5),

        // 3.6 Reliability
        heading("3.6 Reliability & Recovery", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "ดึงปลั๊ก NAS แล้วเปิดใหม่", "DSM boot → IVS containers auto-start", priorityCell("Critical"), statusCell()],
          ["2", "Container crash → auto-restart", "restart policy: unless-stopped ทำงาน", priorityCell("Critical"), statusCell()],
          ["3", "RAM เต็ม (OOM)", "Linux OOM killer ฆ่า container, ไม่ crash NAS", priorityCell("High"), statusCell()],
          ["4", "Disk full", "แจ้ง error, ไม่ corrupt database", priorityCell("High"), statusCell()],
          ["5", "รัน 7 วันต่อเนื่อง (Soak test)", "ไม่มี memory leak, performance คงที่", priorityCell("High"), statusCell()],
          ["6", "HDD fail (RAID 1)", "NAS ทำงานต่อด้วย HDD ที่เหลือ", priorityCell("Critical"), statusCell()],
          ["7", "Backup → Restore → Verify", "ข้อมูลครบ: apps, DB, vault keys, configs", priorityCell("Critical"), statusCell()],
        ], COLS5),

        // 3.7 Customer Experience
        heading("3.7 Customer Experience (UX Testing)", HeadingLevel.HEADING_2),
        testTable(COL_HDR5, [
          ["1", "Unbox → Working ภายใน 1 ชั่วโมง", "ลูกค้าตาม Quick Start Guide ได้เลย", priorityCell("Critical"), statusCell()],
          ["2", "Non-technical user deploy แอป", "Drag & Drop zip สำเร็จ ไม่ต้องใช้ CLI", priorityCell("Critical"), statusCell()],
          ["3", "Error message เข้าใจง่าย", "ข้อความภาษาไทย บอกวิธีแก้ไข", priorityCell("High"), statusCell()],
          ["4", "คู่มือ AI Guide ครบถ้วน", "3 Cases + 5 Prompts + Template", priorityCell("High"), statusCell()],
          ["5", "คู่มือติดตั้ง Synology (DOCX)", "ทำตามได้จริง ไม่มีขั้นตอนขาด", priorityCell("High"), statusCell()],
          ["6", "Dashboard ภาษาไทย/อังกฤษ", "สลับภาษาได้ ข้อความถูกต้อง", priorityCell("Medium"), statusCell()],
          ["7", "Mobile responsive", "ใช้งาน Dashboard บน mobile ได้", priorityCell("Low"), statusCell()],
        ], COLS5),

        new Paragraph({ children: [new PageBreak()] }),

        // ════════════════ PART 4: ACCEPTANCE CRITERIA ════════════════
        heading("ส่วนที่ 4: Acceptance Criteria — เกณฑ์ผ่านก่อนขาย", HeadingLevel.HEADING_1),

        heading("4.1 Software License — เกณฑ์ขั้นต่ำ", HeadingLevel.HEADING_2),
        testTable(
          ["เกณฑ์", "Threshold", "Blocker?"],
          [
            ["Critical test cases ผ่านทั้งหมด", "100%", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["High priority test cases ผ่าน", "> 95%", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["Medium priority ผ่าน", "> 80%", { text: "NO", color: AMBER }],
            ["Security test ผ่าน (Critical + High)", "100%", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["Deploy 5 app types สำเร็จ", "5/5 types", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["Cross-platform: Ubuntu 22.04 + macOS", "2/2 ผ่าน", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["API response < 2 วินาที", "P95 < 2s", { text: "NO", color: AMBER }],
            ["ไม่มี data loss หลัง restart", "0 data loss", { text: "YES", bold: true, color: RED, bg: RED_BG }],
          ],
          [4000, 2500, 2860]
        ),

        heading("4.2 Synology Bundle — เกณฑ์เพิ่มเติม", HeadingLevel.HEADING_2),
        testTable(
          ["เกณฑ์", "Threshold", "Blocker?"],
          [
            ["DS225+ ทุก Critical ผ่าน", "100%", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["DS925+ ทุก Critical ผ่าน", "100%", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["Power failure recovery", "100% auto-start", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["7-day soak test ผ่าน", "ไม่มี memory leak", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["RAID 1 HDD failure recovery", "ไม่สูญเสียข้อมูล", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["Quick Start: Unbox → Working < 1 hr", "ทดสอบกับ 3 คน", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["คู่มือติดตั้งถูกต้อง 100%", "ทุกขั้นตอนทำได้จริง", { text: "YES", bold: true, color: RED, bg: RED_BG }],
            ["NAS อุณหภูมิ < 55°C under load", "Thermal test 24hr", { text: "NO", color: AMBER }],
          ],
          [4000, 2500, 2860]
        ),

        heading("4.3 Sign-off Checklist", HeadingLevel.HEADING_2),
        para("ก่อนส่งมอบผลิตภัณฑ์ ต้องลงนามอนุมัติทุกข้อ:", { bold: true }),
        checkbox("ทดสอบ Functional ครบทุก Critical/High cases"),
        checkbox("ทดสอบ Security ครบทุก Critical/High cases"),
        checkbox("ทดสอบ Performance ผ่านเกณฑ์"),
        checkbox("ทดสอบ Cross-Platform อย่างน้อย 2 OS"),
        checkbox("ทดสอบบน Synology NAS จริง (ถ้าขาย Bundle)"),
        checkbox("Soak test 7 วัน ผ่าน"),
        checkbox("คู่มือทุกฉบับตรวจสอบแล้ว"),
        checkbox("Backup & Restore ทดสอบแล้ว"),
        checkbox("Known issues บันทึกไว้ใน Release Notes"),
        para(""),
        para("ลงนามอนุมัติ: ________________________     วันที่: _______________", { size: 22 }),
        para("ตำแหน่ง:    ________________________", { size: 22 }),

        para(""),
        para(""),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [
          new TextRun({ text: "— End of Test Plan —", font: "Arial", size: 20, color: GRAY, italics: true }),
        ]}),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200 }, children: [
          new TextRun({ text: "IVS — Internal Vibe Server v1.0", font: "Arial", size: 18, color: GRAY }),
        ]}),
      ],
    },
  ],
});

const OUTPUT = "/Users/klod/IVS/docs/IVS_Test_Plan.docx";
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUTPUT, buffer);
  console.log(`Created: ${OUTPUT}`);
  console.log(`Size: ${(buffer.length / 1024).toFixed(1)} KB`);
});
