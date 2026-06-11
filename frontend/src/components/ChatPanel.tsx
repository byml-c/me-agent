"use client";

import { type KeyboardEvent, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronLeft, History, Inbox, Layers3, Lock, MessageCircle, Pencil, RefreshCw, Send, Settings, Unlock, Wrench, X } from "lucide-react";
import { api } from "@/api/client";
import { NODE_ICON_OPTIONS, type NodeIconKey } from "@/lib/nodeIcons";
import { MarkdownContent } from "@/components/MarkdownContent";
import { NodeEditorPane, type NodeEditorDraft } from "@/components/NodeEditor";
import { SharedPanel, type SharedPanelView } from "@/components/SharedPanel";
import type { ChatMessage, ChatResponse, ChatSession, MeNode, NodeAttachments, NodeDatabaseAttachment, NodeFileAttachment, NodeScriptAttachment, NodeScriptRunResult, Proposal } from "@/types";

type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  toolCalls?: ToolCallEvent[];
  variant_index?: number;
};

type ToolCallEvent = {
  name: string;
  arguments?: Record<string, unknown>;
  call_id?: string | null;
  result?: Record<string, unknown>;
};

const AUTO_ANCHOR_VALUE = "__auto__";

type AgentPanelProps = {
  sessionId?: string;
  anchorId?: string;
  anchorLocked?: boolean;
  onAnchorLockChange?: (locked: boolean) => void;
  onAnchorChange?: (nodeId: string) => void;
  onGraphChanged?: () => void;
  onNodeChanged?: () => void;
  onProposalReview?: (response: ChatResponse) => void;
  onProposalResolved?: (proposalId: string, accepted: boolean) => void;
  onGraphIntent?: (graphIntent: ChatResponse["graph_intent"]) => void;
  onGraphBuildStart?: (graphIntent: ChatResponse["graph_intent"]) => void;
  onGraphBuildDone?: () => void;
  onProposalStream?: (proposal: Proposal) => void;
  nodeEditorCommand?: { action: "edit"; nodeId: string; nonce: number } | null;
  showDirectedEdges?: boolean;
  onShowDirectedEdgesChange?: (value: boolean) => void;
  showCutpointGroups?: boolean;
  onShowCutpointGroupsChange?: (value: boolean) => void;
  graphEditMode?: boolean;
  onGraphEditModeChange?: (value: boolean) => void;
};

const floatingButtonClass = "grid h-9 w-9 place-items-center rounded-full text-slate-500 transition hover:bg-slate-900 hover:text-white";
const floatingButtonActiveClass = "bg-slate-900 text-white";
const panelClass = "absolute overflow-hidden rounded-3xl border border-slate-200/80 bg-white/94 shadow-[0_24px_70px_rgba(25,32,29,0.12)] backdrop-blur-2xl";
const ghostButtonClass = "grid h-8 w-8 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900/20";
const messageButtonClass = "grid h-7 w-7 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-100 hover:text-slate-900";
const messageButtonDarkClass = "border-white/15 bg-slate-900 text-white";

export function AgentPanel({
  sessionId,
  anchorId: externalAnchorId,
  anchorLocked = false,
  onAnchorLockChange,
  onAnchorChange,
  onGraphChanged,
  onNodeChanged,
  onProposalReview,
  onProposalResolved,
  onGraphIntent,
  onGraphBuildStart,
  onGraphBuildDone,
  onProposalStream,
  nodeEditorCommand,
  showDirectedEdges = true,
  onShowDirectedEdgesChange,
  showCutpointGroups = true,
  onShowCutpointGroupsChange,
  graphEditMode = false,
  onGraphEditModeChange
}: AgentPanelProps) {
  const [nodes, setNodes] = useState<MeNode[]>([]);
  const [anchorId, setAnchorId] = useState("");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(sessionId === "new" ? null : sessionId ?? null);
  const [loading, setLoading] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [panelView, setPanelView] = useState<SharedPanelView>("chat");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeNode, setActiveNode] = useState<MeNode | null>(null);
  const [nodeDraft, setNodeDraft] = useState<NodeEditorDraft | null>(null);
  const [nodeSaving, setNodeSaving] = useState(false);
  const [scriptResults, setScriptResults] = useState<Record<string, NodeScriptRunResult>>({});
  const [nodeIconPickerOpen, setNodeIconPickerOpen] = useState(false);
  const [nodeIconSearch, setNodeIconSearch] = useState("");
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const nodeTitleRef = useRef<HTMLInputElement | null>(null);
  const nodeIconSearchRef = useRef<HTMLInputElement | null>(null);
  const lastTriggeredAnchorRef = useRef<string>("");
  const nodeEditorOpen = panelView === "node";
  const filteredNodeIconOptions = useMemo(() => {
    const query = nodeIconSearch.trim().toLowerCase();
    if (!query) {
      return NODE_ICON_OPTIONS;
    }
    return NODE_ICON_OPTIONS.filter((option) => option.label.toLowerCase().includes(query) || option.key.toLowerCase().includes(query));
  }, [nodeIconSearch]);

  useEffect(() => {
    api.nodes.list().then((items) => {
      setNodes(items);
      setAnchorId(externalAnchorId ?? items[0]?.id ?? "");
    }).catch(console.error);
    refreshSessions();
  }, []);

  useEffect(() => {
    if (externalAnchorId) {
      void updateAnchor(externalAnchorId);
    }
  }, [externalAnchorId]);

  useEffect(() => {
    if (!nodeEditorOpen || !anchorId) {
      return;
    }
    loadActiveNode(anchorId);
  }, [nodeEditorOpen, anchorId]);

  useEffect(() => {
    if (!nodeEditorOpen) {
      setNodeIconPickerOpen(false);
      setNodeIconSearch("");
    }
  }, [nodeEditorOpen]);

  useEffect(() => {
    if (nodeIconPickerOpen) {
      window.setTimeout(() => nodeIconSearchRef.current?.focus(), 0);
    }
  }, [nodeIconPickerOpen]);

  useEffect(() => {
    if (!nodeEditorCommand) {
      return;
    }
    setChatOpen(true);
    setPanelView("node");
    void (async () => {
      await updateAnchor(nodeEditorCommand.nodeId, "manual");
      await loadActiveNode(nodeEditorCommand.nodeId);
    })();
  }, [nodeEditorCommand?.nonce]);

  useEffect(() => {
    scrollMessagesToBottom();
  }, [messages, loading]);

  function refreshSessions() {
    api.chat.sessions().then(setSessions).catch(console.error);
  }

  async function loadActiveNode(nodeId: string) {
    try {
      const node = await api.nodes.get(nodeId);
      setActiveNode(node);
      setNodeDraft(draftFromNode(node));
      setScriptResults({});
    } catch (error) {
      console.error(error);
    }
  }

  async function autoSaveNodeDraft(node = activeNode, draft = nodeDraft) {
    if (!node || !draft || !draft.title.trim() || !shouldAutoSaveNodeDraft(node, draft)) {
      return null;
    }
    setNodeSaving(true);
    try {
      const updated = await api.nodes.update(node.id, nodeUpdateFromDraft(node, draft));
      setActiveNode((current) => current?.id === updated.id ? updated : current);
      setNodeDraft((current) => current === draft ? draftFromNode(updated) : current);
      setNodes((items) => items.some((node) => node.id === updated.id) ? items.map((node) => (node.id === updated.id ? updated : node)) : [updated, ...items]);
      onNodeChanged?.();
      return updated;
    } finally {
      setNodeSaving(false);
    }
  }

  function commitNodeDraft(draft: NodeEditorDraft) {
    void autoSaveNodeDraft(activeNode, draft);
  }

  async function closeNodeEditor() {
    await autoSaveNodeDraft();
    setPanelView("chat");
  }

  async function closeSharedPanel() {
    if (panelView === "node") {
      await autoSaveNodeDraft();
    }
    setChatOpen(false);
  }

  async function runNodeScript(script: NodeScriptAttachment) {
    if (!activeNode || !nodeDraft || !script.id) {
      return;
    }
    setNodeSaving(true);
    try {
      const result = await api.nodes.runScript(activeNode.id, script.id, {}, script.code);
      setScriptResults((current) => ({ ...current, [script.id]: result }));
    } finally {
      setNodeSaving(false);
    }
  }

  function openNodeEditor() {
    setChatOpen(true);
    setPanelView("node");
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
    setMessages(messagesFromSession(session));
    const nextAnchor = session.current_anchor_node_ids[0];
    if (nextAnchor && !anchorLocked) {
      void updateAnchor(nextAnchor, "manual", false);
    }
  }

  async function refreshCurrentSession(id = currentSessionId) {
    if (!id) {
      return;
    }
    const session = await api.chat.session(id);
    setMessages((current) => mergeTransientReasoning(messagesFromSession(session), current));
    refreshSessions();
  }

  async function triggerAnchorScripts(nodeId: string, trigger: "enter") {
    if (!nodeId || lastTriggeredAnchorRef.current === `${trigger}:${nodeId}`) {
      return;
    }
    lastTriggeredAnchorRef.current = `${trigger}:${nodeId}`;
    try {
      const result = await api.nodes.triggerScripts(nodeId, trigger);
      if (activeNode?.id === nodeId && result.results.length) {
        setScriptResults((current) => {
          const next = { ...current };
          for (const item of result.results) {
            next[item.script_id] = item;
          }
          return next;
        });
      }
    } catch (error) {
      console.error(error);
    }
  }

  async function updateAnchor(nodeId: string, source: "manual" | "ai" = "manual", triggerScripts = true) {
    if (nodeEditorOpen && activeNode?.id !== nodeId) {
      await autoSaveNodeDraft();
    }
    setAnchorId(nodeId);
    onAnchorChange?.(nodeId);
    if (triggerScripts) {
      void triggerAnchorScripts(nodeId, "enter");
    }
  }

  function applyToolAnchor(event: ToolCallEvent) {
    if (anchorLocked) {
      return;
    }
    if (event.name !== "switch_node") {
      return;
    }
    if (event.result && event.result.ok === false) {
      return;
    }
    const nextAnchor =
      typeof event.result?.node_id === "string"
        ? event.result.node_id
        : typeof event.arguments?.node_id === "string"
          ? event.arguments.node_id
          : "";
    if (nextAnchor) {
      void updateAnchor(nextAnchor, "ai");
    }
  }

  function scrollMessagesToBottom() {
    window.requestAnimationFrame(() => {
      const messagesEl = messagesRef.current;
      if (!messagesEl) {
        return;
      }
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  async function send() {
    if (loading || !message.trim()) {
      return;
    }
    const userMessage = message;
    setMessage("");
    const parentMessageId = messages[messages.length - 1]?.id ?? null;
    setMessages((items) => [...items, { role: "user", content: userMessage }, { role: "assistant", content: "" }]);
    setLoading(true);
    try {
      const result = await streamChat({
        session_id: currentSessionId,
        message: userMessage,
        parent_message_id: parentMessageId,
        anchor_node_ids: anchorId ? [anchorId] : [],
        onMeta: (meta) => {
          setCurrentSessionId(meta.session_id);
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
        },
        onReasoningDelta: (delta) => {
          setMessages((items) => {
            const next = [...items];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, reasoning: `${last.reasoning ?? ""}${delta}` };
            }
            return next;
          });
          scrollMessagesToBottom();
        },
        onGraphIntent: (event) => {
          onGraphIntent?.(event.graph_intent);
        },
        onGraphBuilding: (event) => {
          onGraphBuildStart?.(event.graph_intent);
        },
        onToolCall: (event) => {
          applyToolAnchor(event);
          setMessages((items) => {
            const next = [...items];
            const last = next[next.length - 1];
            if (last?.role === "assistant") {
              next[next.length - 1] = { ...last, toolCalls: [...(last.toolCalls ?? []), event] };
            }
            return next;
          });
          scrollMessagesToBottom();
        },
        onProposal: (event) => {
          onProposalStream?.(event.proposal);
        },
        onGraphChanged: () => {
          onNodeChanged?.();
        }
      });
      setCurrentSessionId(result.session_id);
      setResponse(result);
      refreshSessions();
      if (result.proposals.some((proposal) => proposal.status === "pending")) {
        setContextOpen(true);
        onProposalReview?.(result);
      }
      onGraphBuildDone?.();
      setMessages((items) => {
        const next = [...items];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          next[next.length - 1] = { ...last, content: result.assistant_message };
        }
        return next;
      });
      await refreshCurrentSession(result.session_id);
    } finally {
      setLoading(false);
      onGraphBuildDone?.();
    }
  }

  function startEditMessage(item: Message) {
    if (!item.id || loading) {
      return;
    }
    setEditingMessageId(item.id);
    setEditingContent(item.content);
  }

  async function saveEditedMessage() {
    if (!editingMessageId || !editingContent.trim() || loading) {
      return;
    }
    const editedId = editingMessageId;
    const nextContent = editingContent;
    setMessages((items) => {
      const index = items.findIndex((item) => item.id === editedId);
      if (index < 0) {
        return items;
      }
      const next = items.slice(0, index + 1);
      next[index] = { ...next[index], content: nextContent };
      next.push({ role: "assistant", content: "" });
      return next;
    });
    setEditingMessageId(null);
    setEditingContent("");
    setLoading(true);
    try {
      const result = await streamChat({
        endpoint: `/chat/messages/${encodeURIComponent(editedId)}/edit/stream`,
        requestBody: { content: nextContent, context_budget: 12000 },
        onMeta: () => {},
        onDelta: (delta) => {
          setMessages((items) => appendToLastAssistant(items, "content", delta));
        },
        onReasoningDelta: (delta) => {
          setMessages((items) => appendToLastAssistant(items, "reasoning", delta));
          scrollMessagesToBottom();
        },
        onGraphIntent: (event) => {
          onGraphIntent?.(event.graph_intent);
        },
        onGraphBuilding: (event) => {
          onGraphBuildStart?.(event.graph_intent);
        },
        onToolCall: (event) => {
          applyToolAnchor(event);
          setMessages((items) => appendToolCallToLastAssistant(items, event));
          scrollMessagesToBottom();
        },
        onProposal: (event) => {
          onProposalStream?.(event.proposal);
        },
        onGraphChanged: () => {
          onNodeChanged?.();
        }
      });
      setCurrentSessionId(result.session_id);
      setResponse(result);
      if (result.proposals.some((proposal) => proposal.status === "pending")) {
        setContextOpen(true);
        onProposalReview?.(result);
      }
      if (result.auto_applied?.length) {
        onNodeChanged?.();
      }
      await refreshCurrentSession(result.session_id);
    } finally {
      setLoading(false);
    }
  }

  async function regenerateMessage(messageId: string) {
    if (loading) {
      return;
    }
    setMessages((items) => {
      const index = items.findIndex((item) => item.id === messageId);
      if (index < 0) {
        return items;
      }
      return [...items.slice(0, index), { role: "assistant", content: "" }];
    });
    setLoading(true);
    try {
      const result = await streamChat({
        endpoint: `/chat/messages/${encodeURIComponent(messageId)}/regenerate/stream`,
        requestBody: { variant_temperature: 0.65, context_budget: 12000 },
        onMeta: () => {},
        onDelta: (delta) => {
          setMessages((items) => appendToLastAssistant(items, "content", delta));
        },
        onReasoningDelta: (delta) => {
          setMessages((items) => appendToLastAssistant(items, "reasoning", delta));
          scrollMessagesToBottom();
        },
        onGraphIntent: (event) => {
          onGraphIntent?.(event.graph_intent);
        },
        onGraphBuilding: (event) => {
          onGraphBuildStart?.(event.graph_intent);
        },
        onToolCall: (event) => {
          applyToolAnchor(event);
          setMessages((items) => appendToolCallToLastAssistant(items, event));
          scrollMessagesToBottom();
        },
        onProposal: (event) => {
          onProposalStream?.(event.proposal);
        },
        onGraphChanged: () => {
          onNodeChanged?.();
        }
      });
      setCurrentSessionId(result.session_id);
      setResponse(result);
      if (result.proposals.some((proposal) => proposal.status === "pending")) {
        setContextOpen(true);
        onProposalReview?.(result);
      }
      if (result.auto_applied?.length) {
        onNodeChanged?.();
      }
      await refreshCurrentSession(result.session_id);
    } finally {
      setLoading(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.nativeEvent.isComposing || event.key !== "Enter" || event.shiftKey) {
      return;
    }
    event.preventDefault();
    send();
  }

  const currentAnchor = nodes.find((node) => node.id === anchorId);
  const currentAnchorTitle = currentAnchor?.title ?? "当前推断节点";
  const panelHeaderControls = (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_34px_minmax(0,1fr)] items-center gap-2">
      <select
        className="min-w-0 rounded-full border-0 bg-slate-100 px-3 py-2 text-sm text-slate-800 outline-none"
        value={anchorLocked && anchorId ? anchorId : AUTO_ANCHOR_VALUE}
        onChange={(event) => {
          const nextAnchor = event.target.value;
          if (nextAnchor === AUTO_ANCHOR_VALUE) {
            onAnchorLockChange?.(false);
            return;
          }
          onAnchorLockChange?.(true);
          if (nextAnchor) {
            void updateAnchor(nextAnchor);
          }
        }}
      >
        <option value={AUTO_ANCHOR_VALUE}>{`Auto - ${currentAnchorTitle}`}</option>
        {nodes.map((node) => (
          <option key={node.id} value={node.id}>
            {node.title}
          </option>
        ))}
      </select>
      <button
        className={`${ghostButtonClass} ${anchorLocked ? "bg-slate-900 text-white hover:bg-slate-900" : "bg-slate-100"}`}
        title={anchorLocked ? "已锁定当前节点" : "自动跟随推断节点"}
        onClick={() => onAnchorLockChange?.(!anchorLocked)}
        type="button"
      >
        {anchorLocked ? <Lock size={15} /> : <Unlock size={15} />}
      </button>
      <select
        className="min-w-0 rounded-full border-0 bg-slate-100 px-3 py-2 text-sm text-slate-800 outline-none"
        value={currentSessionId ?? ""}
        onChange={(event) => chooseSession(event.target.value)}
      >
        <option value="">新对话</option>
        {sessions.map((session) => (
          <option key={session.id} value={session.id}>
            {session.title}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div className="pointer-events-none absolute inset-0 z-[25]">
      <div className="pointer-events-auto">
        <div className="absolute right-4 top-4 flex gap-2 rounded-full border border-slate-200/80 bg-white/90 p-2 shadow-[0_10px_30px_rgba(25,32,29,0.08)] backdrop-blur-xl">
          <button
            className={`${floatingButtonClass} ${chatOpen ? floatingButtonActiveClass : ""}`}
            title="对话"
            onClick={() => setChatOpen((value) => !value)}
          >
            <MessageCircle size={18} />
          </button>
          <button
            className={`${floatingButtonClass} ${historyOpen ? floatingButtonActiveClass : ""}`}
            title="历史"
            onClick={() => setHistoryOpen((value) => !value)}
          >
            <History size={18} />
          </button>
          <button
            className={`${floatingButtonClass} ${contextOpen ? floatingButtonActiveClass : ""}`}
            title="上下文和提案"
            onClick={() => setContextOpen((value) => !value)}
          >
            <Layers3 size={18} />
          </button>
          <button
            className={`${floatingButtonClass} ${graphEditMode ? floatingButtonActiveClass : ""}`}
            title={graphEditMode ? "退出编辑" : "编辑"}
            onClick={() => onGraphEditModeChange?.(!graphEditMode)}
          >
            <Pencil size={18} />
          </button>
          <button
            className={`${floatingButtonClass} ${settingsOpen ? floatingButtonActiveClass : ""}`}
            title="设置"
            onClick={() => setSettingsOpen((value) => !value)}
          >
            <Settings size={18} />
          </button>
        </div>
      </div>

      {historyOpen ? (
        <aside className={`${panelClass} pointer-events-auto right-4 top-[78px] w-[min(360px,calc(100vw-32px))] max-h-[min(560px,calc(100vh-110px))]`}>
          <PanelHead title="历史" onClose={() => setHistoryOpen(false)} />
          <div className="grid max-h-full gap-2 overflow-auto px-2 pb-3">
            <button
              className="grid gap-1 rounded-2xl border border-transparent bg-transparent p-3 text-left text-slate-900 transition hover:bg-slate-50"
              onClick={() => chooseSession("")}
            >
              <strong className="text-sm font-semibold">新对话</strong>
              <span className="text-xs text-slate-500">从当前图节点开始</span>
            </button>
            {sessions.map((session) => (
              <button
                key={session.id}
                className="grid gap-1 rounded-2xl border border-transparent bg-transparent p-3 text-left text-slate-900 transition hover:bg-slate-50"
                onClick={() => chooseSession(session.id)}
              >
                <strong className="text-sm font-semibold">{session.title}</strong>
                <span className="truncate text-xs text-slate-500">{session.last_message || session.id}</span>
              </button>
            ))}
          </div>
        </aside>
      ) : null}

      {contextOpen ? (
        <aside className={`${panelClass} pointer-events-auto right-4 top-[78px] grid w-[min(390px,calc(100vw-32px))] max-h-[min(680px,calc(100vh-110px))] gap-3 overflow-auto p-3`}>
          <PanelHead title="上下文" onClose={() => setContextOpen(false)} />
          <ContextCard response={response} />
          <ProposalCard
            proposals={response?.proposals ?? []}
            onResolved={(proposalId, accepted) => {
              onProposalResolved?.(proposalId, accepted);
              if (accepted) {
                onGraphChanged?.();
              }
            }}
          />
        </aside>
      ) : null}

      {settingsOpen ? (
        <aside className={`${panelClass} pointer-events-auto right-4 top-[78px] grid w-[min(340px,calc(100vw-32px))] gap-3 p-3`}>
          <PanelHead title="设置" onClose={() => setSettingsOpen(false)} />
          <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <span className="font-semibold text-slate-900">显示有向边</span>
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20"
              checked={showDirectedEdges}
              onChange={(event) => onShowDirectedEdgesChange?.(event.target.checked)}
            />
          </label>
          <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <span className="font-semibold text-slate-900">显示割点分组</span>
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20"
              checked={showCutpointGroups}
              onChange={(event) => onShowCutpointGroupsChange?.(event.target.checked)}
            />
          </label>
        </aside>
      ) : null}

      <SharedPanel
        open={chatOpen}
        view={panelView}
        headerControls={panelHeaderControls}
        onClose={closeSharedPanel}
        onViewChange={(view) => {
          if (view === "node") {
            openNodeEditor();
            return;
          }
          void closeNodeEditor();
        }}
      >
          {panelView === "node" ? (
            <NodeEditorPane
              activeNode={activeNode}
              draft={nodeDraft}
              filteredNodeIconOptions={filteredNodeIconOptions}
              iconPickerOpen={nodeIconPickerOpen}
              iconSearch={nodeIconSearch}
              iconSearchRef={nodeIconSearchRef}
              nodeSaving={nodeSaving}
              nodeTitleRef={nodeTitleRef}
              scriptResults={scriptResults}
              onDraftChange={setNodeDraft}
              onDraftCommit={commitNodeDraft}
              onIconPickerOpenChange={setNodeIconPickerOpen}
              onIconSearchChange={setNodeIconSearch}
              onRunScript={runNodeScript}
            />
          ) : (
            <ChatPanel
              editingContent={editingContent}
              editingMessageId={editingMessageId}
              loading={loading}
              message={message}
              messages={messages}
              messagesRef={messagesRef}
              onCancelEdit={() => setEditingMessageId(null)}
              onComposerKeyDown={handleComposerKeyDown}
              onEditingContentChange={setEditingContent}
              onMessageChange={setMessage}
              onRegenerateMessage={regenerateMessage}
              onSaveEditedMessage={saveEditedMessage}
              onSend={send}
              onStartEditMessage={startEditMessage}
            />
          )}
      </SharedPanel>
    </div>
  );
}

function messagesFromSession(session: ChatSession): Message[] {
  return (session.messages ?? [])
    .filter((item): item is ChatMessage & { role: "user" | "assistant" } => item.role === "user" || item.role === "assistant")
    .map((item) => ({
      id: item.id,
      role: item.role,
      content: item.content,
      variant_index: item.variant_index
    }));
}

function mergeTransientReasoning(fresh: Message[], previous: Message[]): Message[] {
  const previousWithReasoning = previous.filter((item) => item.role === "assistant" && item.reasoning?.trim());
  if (!previousWithReasoning.length) {
    return fresh;
  }
  const used = new Set<number>();
  const next = fresh.map((item) => {
    if (item.role !== "assistant" || item.reasoning) {
      return item;
    }
    const index = previousWithReasoning.findIndex((candidate, candidateIndex) => {
      if (used.has(candidateIndex)) {
        return false;
      }
      return Boolean((item.id && candidate.id === item.id) || candidate.content === item.content);
    });
    if (index < 0) {
      return item;
    }
    used.add(index);
    return { ...item, reasoning: previousWithReasoning[index].reasoning };
  });
  const latestReasoning = previousWithReasoning[previousWithReasoning.length - 1]?.reasoning;
  if (!latestReasoning || next.some((item) => item.reasoning === latestReasoning)) {
    return next;
  }
  let lastAssistantIndex = -1;
  for (let index = next.length - 1; index >= 0; index -= 1) {
    if (next[index].role === "assistant") {
      lastAssistantIndex = index;
      break;
    }
  }
  if (lastAssistantIndex < 0) {
    return next;
  }
  return next.map((item, index) => (index === lastAssistantIndex ? { ...item, reasoning: latestReasoning } : item));
}

function appendToLastAssistant(items: Message[], field: "content" | "reasoning", delta: string): Message[] {
  const next = [...items];
  const last = next[next.length - 1];
  if (last?.role === "assistant") {
    next[next.length - 1] = { ...last, [field]: `${last[field] ?? ""}${delta}` };
  }
  return next;
}

function appendToolCallToLastAssistant(items: Message[], event: ToolCallEvent): Message[] {
  const next = [...items];
  const last = next[next.length - 1];
  if (last?.role === "assistant") {
    next[next.length - 1] = { ...last, toolCalls: [...(last.toolCalls ?? []), event] };
  }
  return next;
}

function toolCallLabel(toolCall: ToolCallEvent) {
  if (toolCall.name === "switch_node") {
    const node = toolCall.result?.node;
    const title = typeof node === "object" && node && "title" in node && typeof node.title === "string" ? node.title : "";
    return title ? `切换到 ${title}` : "切换对话节点";
  }
  return `调用了 ${toolCall.name} 函数`;
}

type ChatPanelViewProps = {
  editingContent: string;
  editingMessageId: string | null;
  loading: boolean;
  message: string;
  messages: Message[];
  messagesRef: RefObject<HTMLDivElement | null>;
  onCancelEdit: () => void;
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onEditingContentChange: (content: string) => void;
  onMessageChange: (message: string) => void;
  onRegenerateMessage: (messageId: string) => void;
  onSaveEditedMessage: () => void;
  onSend: () => void;
  onStartEditMessage: (message: Message) => void;
};

export function ChatPanel({
  editingContent,
  editingMessageId,
  loading,
  message,
  messages,
  messagesRef,
  onCancelEdit,
  onComposerKeyDown,
  onEditingContentChange,
  onMessageChange,
  onRegenerateMessage,
  onSaveEditedMessage,
  onSend,
  onStartEditMessage
}: ChatPanelViewProps) {
  return (
    <div className="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_auto]">
      <div ref={messagesRef} className="grid min-h-0 content-start auto-rows-max gap-3 overflow-auto p-4">
        {messages.map((item, index) => (
          <div
            key={`${item.role}-${index}`}
            className={`group relative h-fit w-fit max-w-[92%] rounded-[18px] px-4 py-3 text-[14px] leading-[1.58] ${item.role === "user" ? "justify-self-end rounded-tr-[8px] bg-slate-900 text-white" : "justify-self-start rounded-tl-[8px] bg-slate-100 text-slate-900"}`}
          >
            {editingMessageId && editingMessageId === item.id ? (
              <div className="grid gap-2">
                <textarea
                  className="min-h-[86px] w-full resize-y rounded-xl border border-slate-200 bg-white/10 p-3 text-inherit outline-none"
                  value={editingContent}
                  onChange={(event) => onEditingContentChange(event.target.value)}
                />
                <div className="flex justify-end gap-1">
                  <button className={messageButtonClass} title="保存并重生成下游" onClick={onSaveEditedMessage} disabled={loading || !editingContent.trim()} type="button">
                    <Check size={14} />
                  </button>
                  <button className={messageButtonClass} title="取消" onClick={onCancelEdit} disabled={loading} type="button">
                    <X size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <>
                {item.reasoning ? (
                  <details className="mb-2 text-xs leading-5 text-slate-500" open={loading && index === messages.length - 1}>
                    <summary className="w-fit cursor-pointer list-none font-semibold">
                      {loading && index === messages.length - 1 ? "思考中" : "思考过程"}
                    </summary>
                    <div className="mt-1 whitespace-pre-wrap break-words">{item.reasoning}</div>
                  </details>
                ) : null}
                <MessageMarkdown content={item.content} />
                {item.toolCalls?.length ? (
                  <div className="mt-2 grid gap-1">
                    {item.toolCalls.map((toolCall, callIndex) => (
                      <div key={`${toolCall.call_id ?? toolCall.name}-${callIndex}`} className="inline-flex w-fit max-w-full items-center gap-1.5 text-xs leading-5 text-slate-500 break-words">
                        <Wrench size={12} />
                        {toolCallLabel(toolCall)}
                      </div>
                    ))}
                  </div>
                ) : null}
                {item.variant_index ? (
                  <span className="absolute -top-2 right-3 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[11px] font-bold text-slate-500">
                    v{item.variant_index}
                  </span>
                ) : null}
                {item.id ? (
                  <div className="absolute -bottom-3 right-2 z-[2] flex gap-1 opacity-0 transition group-hover:opacity-100">
                    {item.role === "user" ? (
                      <button className={messageButtonClass} title="编辑并修改上游" onClick={() => onStartEditMessage(item)} disabled={loading} type="button">
                        <Pencil size={14} />
                      </button>
                    ) : (
                      <button className={messageButtonClass} title="重生成" onClick={() => onRegenerateMessage(item.id!)} disabled={loading} type="button">
                        <RefreshCw size={14} />
                      </button>
                    )}
                  </div>
                ) : null}
              </>
            )}
          </div>
        ))}
        {loading ? <div className="h-6 w-8 rounded-full bg-[radial-gradient(circle_at_10px_11px,#9aa39e_2px,transparent_3px),radial-gradient(circle_at_17px_11px,#9aa39e_2px,transparent_3px),radial-gradient(circle_at_24px_11px,#9aa39e_2px,transparent_3px)] bg-slate-100" /> : null}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 border-t border-slate-200 p-3">
        <textarea
          className="min-h-[54px] max-h-[170px] resize-y rounded-[24px] border-0 bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-900 outline-none focus:ring-1 focus:ring-slate-900/10"
          style={{ resize: "none" }}
          placeholder="输入消息，Agent 会读取锚点附近的局部图上下文"
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          onKeyDown={onComposerKeyDown}
        />
        <button
          className="inline-grid h-12 w-12 place-items-center rounded-full bg-slate-900 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          title="发送"
          onClick={onSend}
          disabled={loading || !message.trim()}
          type="button"
        >
          <Send size={16} />
          <span className="sr-only">发送</span>
        </button>
      </div>
    </div>
  );
}

function MessageMarkdown({ content }: { content: string }) {
  return <MarkdownContent content={content} className="text-[14px]" />;
}

function draftFromNode(node: MeNode): NodeEditorDraft {
  return {
    title: node.title,
    summary: node.summary ?? "",
    body: node.body,
    icon: normalizeNodeIcon(node.memory?.icon),
    attachments: normalizeNodeAttachments(node.memory),
    is_workspace: node.is_workspace,
    status: node.status
  };
}

function normalizeNodeIcon(value: unknown): NodeIconKey {
  if (typeof value !== "string") {
    return "";
  }
  return NODE_ICON_OPTIONS.some((option) => option.key === value) ? (value as NodeIconKey) : "";
}

function nodeUpdateFromDraft(node: MeNode, draft: NodeEditorDraft): Partial<Pick<MeNode, "title" | "body" | "summary" | "memory" | "is_workspace" | "status">> {
  return {
    title: draft.title,
    summary: draft.summary,
    body: draft.body,
    memory: { ...node.memory, icon: draft.icon, attachments: draft.attachments },
    is_workspace: draft.is_workspace,
    status: draft.status
  };
}

function shouldAutoSaveNodeDraft(activeNode: MeNode | null, draft: NodeEditorDraft) {
  if (!activeNode) {
    return false;
  }
  const original = draftFromNode(activeNode);
  return JSON.stringify(original) !== JSON.stringify(draft);
}

function normalizeNodeAttachments(memory: MeNode["memory"]): NodeAttachments {
  const raw = memory.attachments ?? {};
  const databases = normalizeAttachmentList<NodeDatabaseAttachment>(raw.databases).map((item) => ({
    id: item.id,
    entry_id: item.entry_id || "",
    kind: item.kind || "text",
    file_id: item.file_id || "",
    name: item.name || "知识条目",
    description: item.summary || item.description || "",
    content: item.content || "",
    summary: item.summary || item.description || "",
    path: item.path || "",
    media_type: item.media_type || ""
  }));
  const legacyFiles = normalizeAttachmentList<NodeFileAttachment>(raw.files).map((item) => ({
    id: item.id,
    entry_id: "",
    kind: "file" as const,
    file_id: item.file_id || "",
    name: item.name || "文件",
    description: item.summary || item.description || "",
    content: item.content || "",
    summary: item.summary || item.description || "",
    path: item.path || "",
    media_type: item.media_type || "text/plain"
  }));
  const databaseIds = new Set(databases.map((item) => item.id));
  return {
    databases: [...databases, ...legacyFiles.filter((item) => !databaseIds.has(item.id))],
    scripts: normalizeAttachmentList<NodeScriptAttachment>(raw.scripts).map((item) => ({
      id: item.id,
      name: item.name || "Python 脚本",
      language: "python",
      code: item.code || "",
      description: item.description || "",
      trigger_on_enter: Boolean(item.trigger_on_enter),
      trigger_on_ai_switch: Boolean(item.trigger_on_ai_switch),
      schedule_rules: normalizeScheduleRules(item.schedule_rules)
    })),
    files: []
  };
}

function normalizeScheduleRules(value: unknown): NodeScriptAttachment["schedule_rules"] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => {
      const kind = item.kind === "weekly" ? "weekly" : "daily";
      const time = typeof item.time === "string" && /^\d{2}:\d{2}$/.test(item.time) ? item.time : "09:00";
      const weekday = typeof item.weekday === "number" && item.weekday >= 0 && item.weekday <= 6 ? item.weekday : 1;
      return {
        id: String(item.id || newAttachmentId("schedule")),
        kind,
        time,
        ...(kind === "weekly" ? { weekday } : {})
      };
    });
}

function normalizeAttachmentList<T extends { id: string; name: string }>(value: unknown): T[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({ ...item, id: String(item.id || newAttachmentId("attachment")), name: String(item.name || "") } as T));
}

function newAttachmentId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}_${Date.now().toString(36)}`;
}

async function streamChat(payload: {
  endpoint?: string;
  requestBody?: unknown;
  session_id?: string | null;
  message?: string;
  parent_message_id?: string | null;
  anchor_node_ids?: string[];
  onMeta: (meta: Pick<ChatResponse, "session_id" | "used_context" | "episode_node">) => void;
  onDelta: (delta: string) => void;
  onReasoningDelta: (delta: string) => void;
  onGraphIntent: (event: { graph_intent: ChatResponse["graph_intent"] }) => void;
  onGraphBuilding: (event: { graph_intent: ChatResponse["graph_intent"]; message: string }) => void;
  onToolCall: (event: ToolCallEvent) => void;
  onProposal: (event: { proposal: Proposal }) => void;
  onGraphChanged: () => void;
}): Promise<ChatResponse> {
  const requestBody = payload.requestBody ?? {
    session_id: payload.session_id ?? null,
    message: payload.message ?? "",
    parent_message_id: payload.parent_message_id,
    anchor_node_ids: payload.anchor_node_ids ?? [],
    options: { allow_proposals: true, context_budget: 12000 }
  };
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}${payload.endpoint ?? "/chat/stream"}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody)
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
      if (event.event === "reasoning_delta") {
        payload.onReasoningDelta((event.data as { content: string }).content);
      }
      if (event.event === "graph_intent") {
        payload.onGraphIntent(event.data as { graph_intent: ChatResponse["graph_intent"] });
      }
      if (event.event === "graph_building") {
        payload.onGraphBuilding(event.data as { graph_intent: ChatResponse["graph_intent"]; message: string });
      }
      if (event.event === "tool_call") {
        payload.onToolCall(event.data as ToolCallEvent);
      }
      if (event.event === "proposal") {
        payload.onProposal(event.data as { proposal: Proposal });
      }
      if (event.event === "error") {
        throw new Error((event.data as { message?: string }).message || "stream failed");
      }
      if (event.event === "graph_changed") {
        payload.onGraphChanged();
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
    <div className="flex items-center justify-between gap-2 px-4 pt-4">
      <h2 className="m-0 text-sm font-semibold text-slate-900">{title}</h2>
      <button className={ghostButtonClass} title="关闭" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}

function ContextCard({ response }: { response: ChatResponse | null }) {
  return (
    <div className="rounded-[18px] bg-slate-50 p-2">
      <div className="grid gap-2">
        {(response?.used_context.context_nodes ?? []).map((node) => (
          <div key={node.id} className="grid gap-2 rounded-[18px] bg-white p-3">
            <div>
              <strong className="text-sm font-semibold text-slate-900">{node.title}</strong>
              <div className="mt-1 text-sm text-slate-500">{node.reason}</div>
            </div>
            <span className="inline-flex h-6 w-fit items-center rounded-full bg-slate-100 px-3 text-xs font-medium text-slate-500">
              {node.activation_score}
            </span>
          </div>
        ))}
        {!response ? <div className="text-sm text-slate-500">发送消息后显示本轮上下文节点。</div> : null}
      </div>
    </div>
  );
}

function ProposalCard({ proposals, onResolved }: { proposals: Proposal[]; onResolved?: (proposalId: string, accepted: boolean) => void }) {
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());

  async function resolveBatch(items: Proposal[], accept: boolean) {
    await Promise.all(
      items.map(async (proposal) => {
        if (accept) {
          await api.proposals.accept(proposal.id);
        } else {
          await api.proposals.reject(proposal.id);
        }
      })
    );
    items.forEach((proposal) => onResolved?.(proposal.id, accept));
    setResolvedIds((current) => new Set([...current, ...items.map((proposal) => proposal.id)]));
  }

  const pendingProposals = proposals.filter((proposal) => proposal.status === "pending" && !resolvedIds.has(proposal.id));

  return (
    <div className="rounded-[18px] bg-slate-50 p-2">
      <div className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold text-slate-600">
        <span className="inline-flex items-center gap-1.5"><Inbox size={14} /> 提案</span>
        {pendingProposals.length ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              className="inline-flex min-h-7 items-center gap-1.5 rounded-xl bg-slate-900 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-slate-800"
              onClick={() => resolveBatch(pendingProposals, true)}
            >
              <Check size={14} /> 全部确认
            </button>
            <button
              className="inline-flex min-h-7 items-center gap-1.5 rounded-xl bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-200"
              onClick={() => resolveBatch(pendingProposals, false)}
            >
              <X size={14} /> 全部取消
            </button>
          </div>
        ) : null}
      </div>
      <div className="grid gap-2">
        {pendingProposals.map((proposal) => (
          <div key={proposal.id} className="grid gap-2 rounded-[18px] bg-white p-3">
            <div>
              <strong className="text-sm font-semibold text-slate-900">{proposal.operation}</strong>
              <div className="mt-1 text-sm text-slate-500">{proposal.reason}</div>
            </div>
            <span className="inline-flex h-6 w-fit items-center rounded-full bg-slate-100 px-3 text-xs font-medium text-slate-500">{proposal.risk_level}</span>
          </div>
        ))}
        {!pendingProposals.length ? <div className="text-sm text-slate-500">暂无待处理提案。</div> : null}
      </div>
    </div>
  );
}
