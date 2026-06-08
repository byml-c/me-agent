"use client";

import { useState } from "react";
import { GraphPanel } from "@/components/GraphPanel";
import { ChatPanel } from "@/components/ChatPanel";

export function GraphChatWorkspace() {
  const [anchorId, setAnchorId] = useState<string | undefined>();
  const [graphRefresh, setGraphRefresh] = useState(0);

  return (
    <div className="graph-chat-shell">
      <section className="graph-stage" aria-label="Local graph">
        <GraphPanel anchorId={anchorId} onSelectNode={(node) => setAnchorId(node.id)} compact refreshKey={graphRefresh} />
      </section>
      <ChatPanel anchorId={anchorId} onAnchorChange={setAnchorId} onGraphChanged={() => setGraphRefresh((value) => value + 1)} />
    </div>
  );
}
