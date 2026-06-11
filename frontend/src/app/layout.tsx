import type { Metadata } from "next";
import Link from "next/link";
import { Bot, GitBranch, Inbox, LayoutDashboard, Network, ScrollText } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Me.Agent",
  description: "Graph-native personal agent"
};

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/workspaces", label: "Workspaces", icon: GitBranch },
  { href: "/chat/new", label: "Chat", icon: Bot },
  { href: "/proposals", label: "Proposals", icon: Inbox },
  { href: "/timeline", label: "Timeline", icon: ScrollText }
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="h-dvh w-dvw overflow-hidden bg-[radial-gradient(circle_at_top,#f7f8f6_0%,#eef2ee_35%,#e6ebe7_100%)] text-ink antialiased">
        <main className="h-dvh w-dvw overflow-hidden">{children}</main>
      </body>
    </html>
  );
}
