/**
 * เขตของคุณ — หน้าจอที่คุณเพิ่มเอง การอัปเกรด iVS จะไม่แตะโฟลเดอร์ custom/
 *
 * แถบเมนูด้านข้างของ iVS เป็นรายการตายตัวในไฟล์แกน การเพิ่มเมนูจึงเคยต้องแก้
 * sidebar.tsx ซึ่งเป็นไฟล์ที่การอัปเกรดเขียนทับ งานที่เพิ่มไว้จะหายทุกครั้ง
 *
 * ไฟล์นี้คือทางที่ไม่หาย เพิ่มรายการในอาเรย์ท้ายไฟล์ แล้วสร้างไฟล์หน้าจอไว้ที่
 * custom/pages/<slug>.tsx เมนูจะขึ้นเอง และเปิดได้ที่ /dashboard/custom/<slug>
 *
 * ตัวอย่างรายการหนึ่ง
 *
 *     {
 *       slug: "report",
 *       labelTh: "รายงานของฉัน",
 *       labelEn: "My report",
 *       roles: ["admin"],
 *       load: () => import("./pages/report"),
 *     }
 *
 * และไฟล์ custom/pages/report.tsx ต้อง export default เป็นคอมโพเนนต์
 *
 *     "use client";
 *     export default function Report() {
 *       return <div className="p-6">สวัสดี</div>;
 *     }
 *
 * ข้อควรรู้
 *
 * - roles ที่นี่ซ่อนเมนูเท่านั้น ไม่ใช่การกันข้อมูล หน้าที่ซ่อนไว้ยังเปิดตรงด้วย
 *   URL ได้เสมอ สิทธิ์จริงต้องบังคับที่ router ฝั่งหลังบ้านด้วย require_role
 *   ในไฟล์ backend/app/custom/routers/ ของคุณ
 * - slug ใช้ a-z 0-9 และขีดกลางเท่านั้น เพราะเป็นส่วนหนึ่งของ URL
 * - ถ้าไฟล์หน้าจอพัง จะเห็นข้อความบอกว่าไฟล์ไหนพัง ไม่ใช่จอขาว และส่วนที่เหลือ
 *   ของ iVS ยังทำงานตามปกติ
 */

export type CustomPage = {
  /** ใช้เป็น URL: /dashboard/custom/<slug> */
  slug: string;
  labelTh: string;
  labelEn: string;
  /** บทบาทที่เห็นเมนูนี้ — ซ่อนเมนูเท่านั้น ไม่ใช่การกันสิทธิ์ */
  roles: Array<"admin" | "developer" | "viewer">;
  /** เส้นทาง SVG ของไอคอน ปล่อยว่างได้ */
  icon?: string;
  /** โหลดแบบ dynamic เพื่อไม่ให้หน้าที่ไม่ได้เปิดถ่วงเวลาโหลดของแดชบอร์ด */
  load: () => Promise<{ default: React.ComponentType<any> }>;
};

export const customPages: CustomPage[] = [];
