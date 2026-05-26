# 🛠️ Project Specification: Internal Vibe Server & Enterprise Gateway

โปรเจกต์นี้คือการสร้างระบบ **Self-Hosted Web Server (Intranet PaaS)** สำหรับหน่วยงานขนาดเล็ก เพื่อรองรับแอปพลิเคชันที่สร้างจาก **AI Vibe Coding** (Cursor, Windsurf, Lovable, v0) ให้สามารถ Deploy, Manage, Share และ Secure ได้อย่างมีประสิทธิภาพโดยไม่ต้องรันบนเครื่อง Local ของพนักงาน

---

## 🏗️ 1. System Architecture Overview

ระบบทำงานในรูปแบบ **Git-backed Platform-as-a-Service (PaaS)** ภายในเครือข่ายแลน (Intranet) รองรับการกู้คืนระบบอัตโนมัติเมื่อเกิดไฟฟ้าขัดข้อง (Resilience Automation) มีระบบจัดการโดเมนจำลองและคัดกรองสิทธิ์การเข้าถึง

```
[ Local PC / Developer ] 
       │
       ├──► (Sign In / Auth Verification)
       │              │
       │              ▼
       ├──► (Drag & Drop .zip / Gitea Push) ──► [ UI / Backend Gateway ]
       │                                                 │
       └──► (Local DNS App URL Request) ─────────────────┼──► [ Coolify / Docker Engine ] ──► [ Running Apps ]
                                                         │
                                                         └──► [ Vault / Public API / Git ]
```

---

## 🔹 2. Backend Specification (ระบบหลังบ้าน)

### 2.1 Core Services & Containerization
* **Engine:** Docker + Docker Compose สำหรับแยก Environment ของแต่ละแอปพลิเคชัน
* **Orchestration/PaaS:** ใช้ API ของ **Coolify** หรือเขียน Wrapper ครอบ Docker Socket (`/var/run/docker.sock`)
* **App Detection Process:** ระบบตรวจจับประเภทซอร์สโค้ดอัตโนมัติ:
    * มีไฟล์ `package.json` -> Build เป็น **Node.js / Next.js**
    * มีไฟล์ `requirements.txt` หรือ `main.py` -> Build เป็น **Python (Streamlit/FastAPI)**
    * มีเพียงไฟล์ `index.html` -> Build เป็น **Static Web (Nginx/Caddy)**

### 2.2 Local DNS & Reverse Proxy Management (ระบบโดเมนจำลองภายในแลน)
* **Local DNS Server:** ติดตั้ง **CoreDNS** หรือ **Dnsmasq** เป็นคอนเทนเนอร์หลัก ทำหน้าที่เป็น Local DNS Server สำหรับแจกจ่ายชื่อโดเมนภายในแลน (เช่น `*.vibe.local` หรือ `*.office.internal`) แทนการจำจดเลข IP Address
* **Automatic Subdomain Binding:** ทุกครั้งที่มีการ Deploy แอปพลิเคชันใหม่ ระบบ Backend ต้องส่งคำสั่งไปอัปเดตไฟล์คอนฟิกของ DNS และ Reverse Proxy (Caddy / Nginx) โดยอัตโนมัติ เพื่อผูกแอปเข้ากับชื่อโดเมนใหม่ทันที (เช่น `http://my-app.vibe.local`)
* **Upstream Forwarding:** ตั้งค่าให้ส่งต่อ (Forward) คำขอเรียกเว็บภายนอก (Internet Requests) ไปยัง Public DNS (เช่น `1.1.1.1` หรือ `8.8.8.8`) เพื่อให้เครื่องพนักงานที่ตั้งค่าชี้ DNS มาที่เซิร์ฟเวอร์นี้ยังคงใช้อินเทอร์เน็ตได้ปกติ

### 2.3 Authentication & Role-Based Access Control (ระบบล็อกอินและสิทธิ์การเข้าถึง)
* **Authentication Engine:** ใช้ **JWT (JSON Web Tokens)** ร่วมกับ HTTP Only Cookies ในการจัดการ Session การล็อกอิน
* **User Identity Registry:** ใช้ฐานข้อมูลภายใน (SQLite / PostgreSQL) หรือรองรับการเชื่อมต่อกับ **Active Directory / LDAP** ของหน่วยงานที่มีอยู่แล้ว
* **Role-Based Access Control (RBAC):** แบ่งระดับสิทธิ์ผู้ใช้ออกเป็นอย่างน้อย 3 ระดับ:
    1. **Admin (ผู้ดูแลระบบ):** จัดการบำรุงรักษาฮาร์ดแวร์, ดูแลปริมาณ Resource, จัดการสิทธิ์ผู้ใช้, และเข้าถึงคลัง API Key ส่วนกลางทั้งหมดได้
    2. **Developer (นักพัฒนา/พนักงานเขียน AI):** มีสิทธิ์สร้าง, อัปเดต (Deploy), Restart หรือสั่ง Rollback แอปพลิเคชันที่ตนเองหรือทีมได้รับมอบหมาย รวมถึงสามารถขอสิทธิ์ใช้ API Key และเปิดใช้งาน Secure Tunnel ได้
    3. **Viewer (ผู้ใช้งานภายใน):** สามารถเข้าดูหน้า Dashboard เพื่อกดลิงก์เข้าไปใช้งานแอปพลิเคชันต่างๆ ที่เปิดบริการอยู่ภายในแลนได้เท่านั้น แต่ไม่มีสิทธิ์แก้ไขหรือเข้าถึงหลังบ้าน

### 2.4 Auto-Start & Resilience Management
* **Restart Policy:** คอนเทนเนอร์แอปพลิเคชันและบริการส่วนกลาง (DNS, Auth) ทั้งหมดต้องถูกกำหนดคอนฟิกเป็น `--restart unless-stopped`
* **Process Monitor:** ใช้ Linux `systemd` ในการควบคุม Service หลักของระบบเพื่อให้เปิดทำงานทันทีหลัง OS บูต

### 2.5 Git-Backed Backup & Rollback Engine
* **Internal Git:** ใช้ **Gitea API** เป็นคลังเก็บโค้ดเบื้องหลัง
* **Deployment Versioning:** ทุกครั้งที่มีการอัปโหลดไฟล์ (Zip หรือ Push) หลังบ้านต้องทำการตัด Commit Code อัตโนมัติ เพื่อรองรับฟังก์ชัน **Rollback (ย้อนเวอร์ชัน)**
* **Data Backup:** ตั้งเวลา (Cron Job) สำรองข้อมูลฐานข้อมูลของระบบและ Source Code ทั้งหมดลงไปยัง Storage ลูกที่ 2 (SATA HDD/SSD) ทุกๆ เที่ยงคืน

### 2.6 Secure Tunnel & Traffic Proxy
* **Tunnel Gateway (Ngrok-like):** ใช้ **Cloudflare Tunnel (cloudflared)** หรือ **Frp (Fast Reverse Proxy)** รันเพื่อส่งแอปออกอินเทอร์เน็ตสาธารณะ
* **Expiration Worker:** มีระบบ Background Task คอยตรวจสอบอายุของ Tunnel เมื่อครบกำหนดเวลา (เช่น 10 นาที, 1 ชม.) ให้สั่งยุติการรันคอนเทนเนอร์ Tunnel ทันที

### 2.7 Enterprise Key Vault & Security
* **Key Storage:** เก็บ API Keys จากภายนอก (OpenAI, Claude) แบบเข้ารหัส (AES-256) 
* **Token Injection:** เมื่อแอปพลิเคชันทำงาน ระบบจะฉีด API Keys เหล่านี้เข้าสู่คลัง Environment Variables (`.env`) ของแอปนั้นๆ โดยตรง พนักงานไม่จำเป็นต้องรับรู้ตัวคีย์จริง

---

## 🔸 3. Frontend Specification (ระบบหน้าจอแดชบอร์ด)

### 3.1 Tech Stack & UI Principles
* **Framework:** Next.js (App Router) หรือ Vue 3 (Nuxt 3)
* **Styling:** Tailwind CSS + Shadcn/ui (เน้นความสะอาดตา ข้อมูลหนาแน่นแต่ไม่รก)
* **Real-time Update:** ใช้ **Websockets** หรือ **Server-Sent Events (SSE)** สำหรับอัปเดตค่า Resource Usage และ Logs

### 3.2 Key UI Components
1.  **Authentication Guard:** หน้าจอสำหรับล็อกอิน (Sign-in Page) และปุ่มสลับบัญชี/ออกจากระบบที่มุมขวาบนของเว็บ พร้อมแสดงสถานะ Role ปัจจุบันของผู้ใช้
2.  **System Health Dashboard:** 
    * กราฟวงกลมหรือแถบความคืบหน้าแสดง CPU, RAM, Storage
    * ไฟสถานะระบบกู้ชีพฮาร์ดแวร์ (BIOS Recovery Status) และสถานะบริการ Local DNS Server
3.  **App Repository Center:**
    * พื้นที่ **Drag & Drop** วางไฟล์โปรเจกต์ `.zip` (แสดงเฉพาะผู้มีสิทธิ์ Developer/Admin)
    * การ์ดแสดงรายชื่อแอป (App Cards) ประกอบด้วย ปุ่มเปิด/ปิด (Start/Stop), ปุ่ม Restart, ปุ่มดูประวัติย้อนกลับ (Rollback) และลิงก์เข้าหน้าเว็บในชื่อโดเมนภายในเครือข่ายแลน (เช่น `http://inventory.vibe.local`)
4.  **Secure Tunnel Manager:**
    * หน้าต่างเปิดแชร์แอปสู่ภายนอก มี Dropdown ให้เลือกเวลาหมดอายุ (1m, 10m, 1h, 3h, 24h)
    * ตารางแสดงสถานะ Tunnel สาธารณะที่กำลังเปิดใช้งาน พร้อมเวลานับถอยหลัง (Countdown Timer) และปุ่มปิดอุโมงค์ทันที (Revoke)
5.  **API Hub & Gateway:**
    * **Enterprise Vault Tab:** แสดงรายการ API Key ส่วนกลาง พร้อมปุ่มคัดลอกในรูปแบบ Prompt AI (ซ่อนค่าคีย์จริงสำหรับผู้ใช้งานทั่วไป แสดงสิทธิ์ให้เฉพาะ Admin หรือ Developer ที่ได้รับอนุญาต)
    * **Public API Explorer Tab:** การ์ดจำลองข้อมูลคลัง API ฟรี แยกตามหมวดหมู่ (AI, Maps, Weather, Finance) มีช่องค้นหา (Search Bar) สำหรับกรองข้อมูลแบบ Real-time

---

## 🔒 4. Future Compliance & Security Roadmap (แผนพัฒนาอนาคต)

1.  **Network Firewall (Cisco/UFW):** บล็อกพอร์ตที่ไม่ได้ใช้งาน จำกัดให้เข้าถึงเฉพาะภายใน Intranet เท่านั้น
2.  **PDPA Data Governance:** 
    * เพิ่มระบบ **Log Auditor** บันทึกประวัติการเข้าใช้งานแอปและการดึงข้อมูล API 
    * เพิ่มระบบ **Data Masking** ซ่อนข้อมูลอ่อนไหวโดยอัตโนมัติก่อนแสดงผลในแอปที่ AI เขียน
3.  **Local LLM Integration:** ติดตั้ง **Ollama** บนเซิร์ฟเวอร์เพื่อให้แอปพลิเคชันจาก AI สามารถเรียกใช้โมเดล (เช่น Llama 3, Mistral) ภายในแลนได้โดยตรง ไม่ต้องส่งข้อมูลออกไปภายนอกองค์กร

---

## 🛠️ 5. Next Steps for AI Development (คำสั่งแนะนำสำหรับสั่ง AI)
> **Prompt แนะนำสำหรับส่งให้ AI พัฒนาต่อ:**
> *"ช่วยสร้างระบบตามสเปกไฟล์นี้ โดยเริ่มจากเขียนระบบสิทธิ์การเข้าถึง (RBAC Auth) และระบบ Backend API (FastAPI) ที่เมื่อทำการรันแอปใหม่แล้ว จะสามารถอัปเดตไฟล์คอนฟิกเพื่อสร้าง Subdomain บนระบบ Local DNS และแจ้งผลการแมปปิ้ง URL กลับมายังหน้า Frontend Dashboard ได้โดยอัตโนมัติ"*
