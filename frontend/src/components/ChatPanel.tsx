"use client";

import { useEffect, useRef, useState } from "react";
import { CornerDownLeft, History, Inbox, Layers3, MessageCircle, Send, X } from "lucide-react";
import { api } from "@/api/client";
import type { ChatResponse, ChatSession, MeNode, Proposal } from "@/types";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type ChatPanelProps = {
  sessionId?: string;
  anchorId?: string;
  onAnchorChange?: (nodeId: string) => void;
  onGraphChanged?: () => void;
};

type ChatWindow = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function ChatPanel({ sessionId, anchorId: externalAnchorId, onAnchorChange, onGraphChanged }: ChatPanelProps) {
  const [nodes, setNodes] = useState<MeNode[]>([]);
  const [anchorId, setAnchorId] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(sessionId === "new" ? null : sessionId ?? null);
  const [loading, setLoading] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [chatWindow, setChatWindow] = useState<ChatWindow>({ x: 0, y: 76, width: 480, height: 720 });
  const dragRef = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);

  useEffect(() => {
    setChatWindow(defaultChatWindow());
    api.nodes.list().then((items) => {
      setNodes(items);
      setAnchorId(externalAnchorId ?? items[0]?.id ?? "");
    }).catch(console.error);
    refreshSessions();
  }, []);

  useEffect(() => {
    if (externalAnchorId) {
      setAnchorId(externalAnchorId);
    }
  }, [externalAnchorId]);

  function refreshSessions() {
    api.chat.sessions().then(setSessions).catch(console.error);
  }

  async function chooseSession(id: string) {
    if (!id) {
      setCurrentSessionId(null);
      setMessages([]);
      setResponse(null);
      return;
    }
    const session = await api.chat.session(id);
    setCurrentSessionId(session.id);
    setMessages(
      (session.messages ?? [])
        .filter((item) => item.role === "user" || item.role === "assistant")
        .map((item) => ({ role: item.role as "user" | "assistant", content: item.content }))
    );
    const nextAnchor = session.current_anchor_node_ids[0];
    if (nextAnchor) {
      setAnchorId(nextAnchor);
      onAnchorChange?.(nextAnchor);
    }
  }

  async function send() {
    if (!message.trim()) {
      return;
    }
    const userMessage = message;
    setMessage("");
    setMessages((items) => [...items, { role: "user", content: userMessage }, { role: "assistant", content: "" }]);
    setLoading(true);
    try {
      const result = await streamChat({
        session_id: currentSessionId,
        message: userMessage,
        anchor_node_ids: anchorId ? [anchorId] : [],
        onMeta: (meta) => {
          setCurrentSessionId(meta.session_id);
          const nextAnchor = meta.used_context.anchor_nodes[0] ?? meta.used_context.context_nodes[0]?.id;
          if (nextAnchor) {
            setAnchorId(nextAnchor);
            onAnchorChange?.(nextAnchor);
          }
        },
        onDelta: (delta) => {
          setMessages((items) => {
            const next = [...items];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + delta };
            }
            return next;
          });
        }
      });
      setCurrentSessionId(result.session_id);
      setResponse(result);
      refreshSessions();
      const nextAnchor = result.used_context.anchor_nodes[0] ?? result.used_context.context_nodes[0]?.id;
      if (nextAnchor) {
        setAnchorId(nextAnchor);
        onAnchorChange?.(nextAnchor);
      }
      if (result.proposals.some((proposal) => proposal.status === "pending")) {
        setContextOpen(true);
      }
      setMessages((items) => {
        const next = [...items];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = { ...last, content: result.assistant_message };
        }
        return next;
      });
    } finally {
      setLoading(false);
    }
  }

  function startDrag(event: React.PointerEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement;
    if (target.closest("button,select,input,textarea")) {
      return;
    }
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: chatWindow.x,
      originY: chatWindow.y
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (!dragRef.current) {
      return;
    }
    const nextX = dragRef.current.originX + event.clientX - dragRef.current.startX;
    const nextY = dragRef.current.originY + event.clientY - dragRef.current.startY;
    setChatWindow((current) => clampWindow({ ...current, x: nextX, y: nextY }));
  }

  function endDrag(event: React.PointerEvent<HTMLDivElement>) {
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <div className="floating-workspace">
      <div className="floating-actions">
        <button className={chatOpen ? "float-button active" : "float-button"} title="对话" onClick={() => setChatOpen((value) => !value)}>
          <MessageCircle size={18} />
        </button>
        <button className={historyOpen ? "float-button active" : "float-button"} title="历史" onClick={() => setHistoryOpen((value) => !value)}>
          <History size={18} />
        </button>
        <button className={contextOpen ? "float-button active" : "float-button"} title="上下文和提案" onClick={() => setContextOpen((value) => !value)}>
          <Layers3 size={18} />
        </button>
      </div>

      {historyOpen ? (
        <aside className="floating-panel history-panel">
          <PanelHead title="历史" onClose={() => setHistoryOpen(false)} />
          <div className="history-list">
            <button className="history-item" onClick={() => chooseSession("")}>
              <strong>新对话</strong>
              <span>从当前图节点开始</span>
            </button>
            {sessions.map((session) => (
              <button key={session.id} className="history-item" onClick={() => chooseSession(session.id)}>
                <strong>{session.title}</strong>
                <span>{session.last_message || session.id}</span>
              </button>
            ))}
          </div>
        </aside>
      ) : null}

      {contextOpen ? (
        <aside className="floating-panel insight-panel">
          <PanelHead title="上下文" onClose={() => setContextOpen(false)} />
          <ContextCard response={response} />
          <ProposalCard proposals={response?.proposals ?? []} onResolved={onGraphChanged} />
        </aside>
      ) : null}

      {chatOpen ? (
      <section
        className="chat-main floating-chat"
        style={{
          left: chatWindow.x,
          top: chatWindow.y,
          width: chatWindow.width,
          height: chatWindow.height
        }}
      >
        <div
          className="chat-window-head"
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <div className="chat-title-controls">
            <span>Chat</span>
            <select className="title-select" value={anchorId} onChange={(event) => setAnchorId(event.target.value)}>
              {nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.title}
                </option>
              ))}
            </select>
            <select className="title-select" value={currentSessionId ?? ""} onChange={(event) => chooseSession(event.target.value)}>
              <option value="">新对话</option>
              {sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))}
            </select>
          </div>
          <button className="ghost-icon" title="关闭" onClick={() => setChatOpen(false)}>
            <X size={16} />
          </button>
        </div>
        <div className="messages">
          {messages.map((item, index) => (
            <div key={`${item.role}-${index}`} className={`message ${item.role}`}>
              {item.content}
            </div>
          ))}
          {loading ? <div className="typing-dot" /> : null}
        </div>
        <div className="composer">
          <textarea
            className="chat-input"
            placeholder="输入消息，Agent 会读取锚点附近的局部图上下文"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                send();
              }
            }}
          />
          <button className="icon-button primary" title="发送" onClick={send} disabled={loading || !message.trim()}>
            <Send size={16} />
            <span className="sr-only">发送</span>
          </button>
        </div>
      </section>
      ) : null}
    </div>
  );
}

function defaultChatWindow(): ChatWindow {
  if (typeof window === "undefined") {
    return { x: 0, y: 76, width: 480, height: 720 };
  }
  const width = Math.min(520, Math.max(420, window.innerWidth * 0.32));
  const height = Math.min(window.innerHeight - 96, Math.max(640, window.innerHeight * 0.82));
  return {
    x: Math.max(16, window.innerWidth - width - 18),
    y: 76,
    width,
    height
  };
}

function clampWindow(windowState: ChatWindow): ChatWindow {
  if (typeof window === "undefined") {
    return windowState;
  }
  const margin = 12;
  const maxX = Math.max(margin, window.innerWidth - 80);
  const maxY = Math.max(margin, window.innerHeight - 80);
  return {
    ...windowState,
    x: Math.min(Math.max(margin, windowState.x), maxX),
    y: Math.min(Math.max(margin, windowState.y), maxY)
  };
}

async function streamChat(payload: {
  session_id: string | null;
  message: string;
  anchor_node_ids: string[];
  onMeta: (meta: Pick<ChatResponse, "session_id" | "used_context" | "episode_node">) => void;
  onDelta: (delta: string) => void;
}): Promise<ChatResponse> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: payload.session_id,
      message: payload.message,
      anchor_node_ids: payload.anchor_node_ids,
      options: { allow_proposals: true, context_budget: 12000 }
    })
  });
  if (!response.ok || !response.body) {
    throw new Error(await response.text());
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let donePayload: ChatResponse | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const event = parseSse(part);
      if (!event) {
        continue;
      }
      if (event.event === "meta") {
        payload.onMeta(event.data as Pick<ChatResponse, "session_id" | "used_context" | "episode_node">);
      }
      if (event.event === "delta") {
        payload.onDelta((event.data as { content: string }).content);
      }
      if (event.event === "done") {
        donePayload = event.data as ChatResponse;
      }
    }
  }

  if (!donePayload) {
    throw new Error("stream ended without done event");
  }
  return donePayload;
}

function parseSse(raw: string): { event: string; data: unknown } | null {
  const eventLine = raw.split("\n").find((line) => line.startsWith("event:"));
  const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) {
    return null;
  }
  return {
    event: eventLine.replace("event:", "").trim(),
    data: JSON.parse(dataLine.replace("data:", "").trim())
  };
}

function PanelHead({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <div className="panel-head">
      <h2>{title}</h2>
      <button className="ghost-icon" title="关闭" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}

function ContextCard({ response }: { response: ChatResponse | null }) {
  return (
    <div className="rail-panel embedded">
      <div className="list">
        {(response?.used_context.context_nodes ?? []).map((node) => (
          <div key={node.id} className="context-item">
            <div>
              <strong>{node.title}</strong>
              <div className="muted">{node.reason}</div>
            </div>
            <span className="pill">{node.activation_score}</span>
          </div>
        ))}
        {!response ? <div className="muted">发送消息后显示本轮上下文节点。</div> : null}
      </div>
    </div>
  );
}

function ProposalCard({ proposals, onResolved }: { proposals: Proposal[]; onResolved?: () => void }) {
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());

  async function resolve(id: string, accept: boolean) {
    if (accept) {
      await api.proposals.accept(id);
      onResolved?.();
    } else {
      await api.proposals.reject(id);
    }
    setResolvedIds((current) => new Set([...current, id]));
  }

  const pendingProposals = proposals.filter((proposal) => proposal.status === "pending" && !resolvedIds.has(proposal.id));

  return (
    <div className="rail-panel embedded">
      <div className="rail-title"><Inbox size={14} /> 提案</div>
      <div className="list">
        {pendingProposals.map((proposal) => (
          <div key={proposal.id} className="proposal-item">
            <div>
              <strong>{proposal.operation}</strong>
              <div className="muted">{proposal.reason}</div>
            </div>
            <div className="proposal-actions">
              <button className="icon-button primary" title="接受" onClick={() => resolve(proposal.id, true)}><CornerDownLeft size={14} /></button>
              <button className="button" onClick={() => resolve(proposal.id, false)}>拒绝</button>
            </div>
          </div>
        ))}
        {!pendingProposals.length ? <div className="muted">暂无待处理提案。</div> : null}
      </div>
    </div>
  );
}
