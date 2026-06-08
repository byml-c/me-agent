"use client";

import { useParams } from "next/navigation";
import { GraphPanel } from "@/components/GraphPanel";
import { NodeEditor } from "@/components/NodeEditor";

export default function NodePage() {
  const params = useParams<{ nodeId: string }>();
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Node Detail</h1>
          <div className="page-subtitle">编辑节点正文，查看局部图和关联历史。</div>
        </div>
      </div>
      <div className="grid two">
        <NodeEditor nodeId={params.nodeId} />
        <section className="card">
          <h2>Local Graph</h2>
          <GraphPanel anchorId={params.nodeId} />
        </section>
      </div>
    </div>
  );
}
