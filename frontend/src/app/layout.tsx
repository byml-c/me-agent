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
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <Link className="brand" href="/">
              <span className="brand-mark">M</span>
              <span>Me.Agent</span>
            </Link>
            <nav>
              {nav.map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.href} className="nav-item" href={item.href}>
                    <Icon size={18} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
          <main className="main-panel">{children}</main>
        </div>
      </body>
    </html>
  );
}
