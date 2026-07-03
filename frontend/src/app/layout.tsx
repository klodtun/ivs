import type { Metadata } from "next";
import "./globals.css";
import { LangProvider } from "@/components/lang-provider";

export const metadata: Metadata = {
  title: "iVS - Internal Vibe Server",
  description: "Enterprise Gateway for AI Vibe Coding Applications",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="th" suppressHydrationWarning>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased">
        <LangProvider>{children}</LangProvider>
      </body>
    </html>
  );
}
