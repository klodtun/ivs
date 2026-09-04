"use client";
/**
 * ชิ้นส่วนหน้าจอกลาง — ที่เดียวที่ตัดสินว่าปุ่มโค้งเท่าไร หัวเรื่องสีอะไร
 *
 * ก่อนมีไฟล์นี้ แต่ละหน้าเขียนคลาสของตัวเอง ผลคือปุ่ม 353 ปุ่มใช้ค่ามุมสี่แบบ
 * (rounded · rounded-md · rounded-lg · rounded-full) และสีพื้นสิบเอ็ดตระกูล
 * ม่วง ฟ้า เขียว เหลือง แดง เทา ปนกันโดยไม่มีกฎว่าอันไหนหมายถึงอะไร ผู้ใช้จึง
 * เดาไม่ได้ว่าปุ่มไหนอันตราย ปุ่มไหนปลอดภัย ซึ่งเป็นเรื่องความปลอดภัย ไม่ใช่
 * ความสวยงาม
 *
 * กฎที่ยึด
 *
 *   มุม        rounded-md ทุกปุ่ม ไม่มีข้อยกเว้น
 *   สี         primary = การกระทำหลักของหน้านั้น หนึ่งเดียวต่อหน้าจอ
 *              secondary = ทางเลือกอื่น
 *              danger = ทำแล้วข้อมูลหาย
 *              ghost = ยกเลิก ปิด ย้อนกลับ
 *   คำอธิบาย   ไม่วางเป็นย่อหน้าใต้หัวเรื่อง แต่อยู่ในทูลทิปที่กดดูได้
 *
 * ข้อสุดท้ายมาจากข้อสังเกตของผู้ใช้เอง — คำอธิบายที่ถูกบีบให้สั้นและเล็กจนอ่าน
 * ไม่รู้เรื่อง กินที่หน้าจอโดยไม่ช่วยใคร ย้ายไปทูลทิปแล้วเขียนให้ยาวพอเข้าใจ
 * ได้ดีกว่า
 */
import { ReactNode, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// --------------------------------------------------------------------------- //
// ทูลทิป
// --------------------------------------------------------------------------- //

export function InfoTip({
  text,
  className,
}: {
  text: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // ปิดเมื่อคลิกที่อื่น — ทูลทิปที่ปิดไม่ได้กลายเป็นสิ่งกีดขวาง
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  return (
    <span ref={ref as any} className={cn("relative inline-flex", className)}>
      <button
        type="button"
        aria-label="คำอธิบาย"
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        className="w-4 h-4 rounded-full border border-gray-300 text-gray-400 hover:text-gray-700 hover:border-gray-400 text-[10px] leading-none flex items-center justify-center"
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          onMouseLeave={() => setOpen(false)}
          className="absolute left-0 top-5 z-50 w-72 rounded-md border border-gray-200 bg-white p-2.5 text-[11px] font-normal leading-relaxed text-gray-600 shadow-lg"
        >
          {text}
        </span>
      )}
    </span>
  );
}

// --------------------------------------------------------------------------- //
// หัวเรื่อง
// --------------------------------------------------------------------------- //

export function PageHeader({
  title,
  help,
  right,
}: {
  title: ReactNode;
  /** คำอธิบายของหน้านี้ — อยู่ในทูลทิป ไม่ใช่ย่อหน้าใต้หัวเรื่อง */
  help?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <h1 className="flex items-center gap-1.5 text-lg font-bold text-gray-900">
        {title}
        {help ? <InfoTip text={help} /> : null}
      </h1>
      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  );
}

export function SectionHeader({
  title,
  help,
  right,
  className,
}: {
  title: ReactNode;
  help?: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <h2 className="flex items-center gap-1.5 text-sm font-semibold text-gray-900">
        {title}
        {help ? <InfoTip text={help} /> : null}
      </h2>
      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// ปุ่ม
// --------------------------------------------------------------------------- //

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 border border-transparent",
  secondary:
    "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 hover:border-gray-400",
  // แดงสงวนไว้สำหรับสิ่งที่ทำแล้วข้อมูลหาย ไม่ใช้เป็นสีเน้นทั่วไป
  // ถ้าใช้แดงกับปุ่มธรรมดา วันที่มีปุ่มลบจริงจะไม่มีใครสังเกต
  danger: "bg-red-600 text-white hover:bg-red-700 border border-transparent",
  ghost: "bg-transparent text-gray-600 hover:bg-gray-100 border border-transparent",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "px-2 py-1 text-[11px]",
  md: "px-3 py-1.5 text-xs",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...rest
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={cn(
        "rounded-md font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
        VARIANT[variant],
        SIZE[size],
        className
      )}
    />
  );
}
