"use client";
/**
 * ตัวเปิดหน้าจอในเขตของลูกค้า
 *
 * Next.js App Router ต้องการโฟลเดอร์จริงต่อหนึ่งเส้นทาง การให้ลูกค้าเพิ่มหน้าจอ
 * จึงเคยแปลว่าต้องสร้างโฟลเดอร์ในเขตแกน ซึ่งการอัปเกรดจะทับ เส้นทางเดียวที่รับ
 * ทุก slug ตัวนี้จึงมีไว้ให้หน้าที่ประกาศใน custom/pages.ts เปิดได้โดยไม่ต้อง
 * แตะอะไรในแกนเลย
 *
 * ความล้มเหลวถูกแสดงเป็นข้อความ ไม่ใช่จอขาว เพราะจอขาวทำให้คนเข้าใจว่า iVS พัง
 * ทั้งระบบ ทั้งที่พังแค่ไฟล์เดียวที่เขาเพิ่งเขียนเอง
 */
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { customPages } from "@/custom/pages";
import { useLang } from "@/components/lang-provider";

export default function CustomPageHost() {
  const params = useParams();
  const { locale } = useLang();
  const slug = String(params?.slug || "");
  const entry = customPages.find((p) => p.slug === slug);

  const [Loaded, setLoaded] = useState<React.ComponentType<any> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    if (!entry) return;
    entry
      .load()
      .then((m) => {
        if (!alive) return;
        if (!m?.default) throw new Error("ไฟล์นี้ไม่มี export default");
        setLoaded(() => m.default);
      })
      .catch((e) => alive && setError(e?.message || String(e)));
    return () => {
      alive = false;
    };
  }, [entry]);

  if (!entry) {
    return (
      <div className="p-6">
        <h1 className="text-sm font-semibold text-gray-800">
          {locale === "th" ? "ไม่มีหน้าจอนี้" : "No such page"}
        </h1>
        <p className="mt-2 text-xs text-gray-600">
          {locale === "th"
            ? `ไม่พบ "${slug}" ใน custom/pages.ts — เพิ่มรายการที่นั่นก่อน`
            : `"${slug}" is not listed in custom/pages.ts — add it there first.`}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-sm font-semibold text-gray-800">
          {locale === "th" ? "หน้าจอนี้โหลดไม่ขึ้น" : "This page failed to load"}
        </h1>
        <p className="mt-2 text-xs text-gray-600">
          {locale === "th"
            ? `iVS ส่วนที่เหลือยังทำงานปกติ ปัญหาอยู่ที่ custom/pages/${slug}.tsx`
            : `The rest of iVS is unaffected. The fault is in custom/pages/${slug}.tsx`}
        </p>
        <pre className="mt-3 rounded border border-gray-200 bg-gray-50 p-3 text-[11px] text-gray-700 overflow-x-auto">
          {error}
        </pre>
      </div>
    );
  }

  if (!Loaded) {
    return <div className="p-6 text-xs text-gray-500">…</div>;
  }

  return <Loaded />;
}
