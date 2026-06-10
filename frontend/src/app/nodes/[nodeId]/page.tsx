"use client";

import { useParams } from "next/navigation";
import { GraphPanel } from "@/components/GraphPanel";
import { NodeEditor } from "@/components/NodeEditor";

export default function NodePage() {
  const params = useParams<{ nodeId: string }>();
  return (
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Node Detail</h1>
          <div className="mt-2 text-sm text-slate-500">编辑节点正文，查看局部图和关联历史。</div>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <NodeEditor nodeId={params.nodeId} />
        <section className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Local Graph</h2>
          <GraphPanel anchorId={params.nodeId} />
        </section>
      </div>
    </div>
  );
}
