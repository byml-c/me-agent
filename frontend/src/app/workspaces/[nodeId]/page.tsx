"use client";

import { useParams } from "next/navigation";
import { ChatPanel } from "@/components/ChatPanel";
import { GraphPanel } from "@/components/GraphPanel";
import { NodeEditor } from "@/components/NodeEditor";

export default function WorkspacePage() {
  const params = useParams<{ nodeId: string }>();
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Workspace View</h1>
          <div className="page-subtitle">工作区操作台：局部图、节点内容和 Agent 对话。</div>
        </div>
      </div>
      <div className="grid two">
        <section className="card">
          <h2>Local Graph</h2>
          <GraphPanel anchorId={params.nodeId} />
        </section>
        <NodeEditor nodeId={params.nodeId} />
      </div>
      <div style={{ marginTop: 14 }}>
        <ChatPanel sessionId="new" />
      </div>
    </div>
  );
}
