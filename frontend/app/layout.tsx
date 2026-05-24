import type { Metadata } from "next";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import type { ReactNode } from "react";

import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

const headingFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
});

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Agent Gateway",
  description: "Secure MCP/API layer for business tools.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en" className={`${headingFont.variable} ${bodyFont.variable}`}>
      <body>
        <div className="relative min-h-screen overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(52,211,153,0.18),transparent_30%),radial-gradient(circle_at_top_right,rgba(245,158,11,0.12),transparent_28%),linear-gradient(180deg,rgba(6,17,31,0.95),rgba(15,27,46,0.98))]" />
          <div className="relative mx-auto flex min-h-screen max-w-[1600px] flex-col lg:flex-row">
            <Sidebar />
            <main className="flex-1 px-5 py-6 lg:px-10 lg:py-8">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
