"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/api/client";
import type { MeNode } from "@/types";

export default function WorkspacesPage() {
  const [items, setItems] = useState<MeNode[]>([]);

  useEffect(() => {
    api.workspaces.list().then(setItems).catch(console.error);
  }, []);

  return (
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Workspaces</h1>
          <div className="mt-2 text-sm text-slate-500">工作区是带有 workspace 标记的普通节点。</div>
        </div>
      </div>
      <section className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="grid gap-3">
          {items.map((node) => (
            <Link
              key={node.id}
              href={`/workspaces/${node.id}`}
              className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
            >
              <span className="font-medium text-slate-900">{node.title}</span>
              <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-3 text-xs font-medium text-slate-500">
                {node.access_count} visits
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
