import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "面试宝",
  description: "AI interview preparation assistant"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
