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
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Workspaces</h1>
          <div className="page-subtitle">工作区是带有 workspace 标记的普通节点。</div>
        </div>
      </div>
      <section className="card">
        <div className="list">
          {items.map((node) => (
            <Link className="row" key={node.id} href={`/workspaces/${node.id}`}>
              <span>{node.title}</span>
              <span className="pill">{node.access_count} visits</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
