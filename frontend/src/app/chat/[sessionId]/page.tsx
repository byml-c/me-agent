"use client";

import { useParams } from "next/navigation";
import { AgentPanel } from "@/components/ChatPanel";

export default function ChatPage() {
  const params = useParams<{ sessionId: string }>();
  return (
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Chat</h1>
          <div className="mt-2 text-sm text-slate-500">Agent 会展示本轮使用的上下文和生成的图更新提案。</div>
        </div>
      </div>
      <AgentPanel sessionId={params.sessionId} />
    </div>
  );
}
