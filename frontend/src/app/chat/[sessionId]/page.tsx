"use client";

import { useParams } from "next/navigation";
import { ChatPanel } from "@/components/ChatPanel";

export default function ChatPage() {
  const params = useParams<{ sessionId: string }>();
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Chat</h1>
          <div className="page-subtitle">Agent 会展示本轮使用的上下文和生成的图更新提案。</div>
        </div>
      </div>
      <ChatPanel sessionId={params.sessionId} />
    </div>
  );
}
