import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppNav } from "@/components/AppNav";

export const metadata: Metadata = {
  title: "穿搭信号｜每天少想一件事：穿什么。",
  description: "每天少想一件事：穿什么。根据今天的天气，给你一套轻松可执行的穿搭建议。",
  applicationName: "穿搭信号",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f5f6f7",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <a className="skip-link" href="#main-content">跳到主要内容</a>
        <AppNav />
        <div id="main-content" tabIndex={-1}>{children}</div>
      </body>
    </html>
  );
}
