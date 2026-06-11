"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { api } from "@/api/client";
import { GraphPanel } from "@/components/GraphPanel";
import { AgentPanel } from "@/components/ChatPanel";
import type { ChatResponse, MeNode, Proposal } from "@/types";

const GRAPH_SETTINGS_STORAGE_KEY = "me-agent:graph-settings";

export function GraphChatWorkspace() {
  const [anchorId, setAnchorId] = useState<string | undefined>();
  const [anchorLocked, setAnchorLocked] = useState(false);
  const [graphRefresh, setGraphRefresh] = useState(0);
  const [reviewProposals, setReviewProposals] = useState<Proposal[]>([]);
  const [graphIntent, setGraphIntent] = useState<ChatResponse["graph_intent"]>();
  const [graphBuilding, setGraphBuilding] = useState(false);
  const [nodeEditorCommand, setNodeEditorCommand] = useState<{ action: "edit"; nodeId: string; nonce: number } | null>(null);
  const [showDirectedEdges, setShowDirectedEdges] = useState(true);
  const [showCutpointGroups, setShowCutpointGroups] = useState(true);
  const [graphEditMode, setGraphEditMode] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(GRAPH_SETTINGS_STORAGE_KEY);
      if (!raw) {
        return;
      }
      const settings = JSON.parse(raw) as { showDirectedEdges?: boolean; showCutpointGroups?: boolean };
      if (typeof settings.showDirectedEdges === "boolean") {
        setShowDirectedEdges(settings.showDirectedEdges);
      }
      if (typeof settings.showCutpointGroups === "boolean") {
        setShowCutpointGroups(settings.showCutpointGroups);
      }
    } catch {
      // Ignore invalid local settings.
    }
  }, []);

  function updateShowDirectedEdges(value: boolean) {
    setShowDirectedEdges(value);
    saveGraphSettings({ showDirectedEdges: value, showCutpointGroups });
  }

  function updateShowCutpointGroups(value: boolean) {
    setShowCutpointGroups(value);
    saveGraphSettings({ showDirectedEdges, showCutpointGroups: value });
  }

  function saveGraphSettings(settings: { showDirectedEdges: boolean; showCutpointGroups: boolean }) {
    try {
      window.localStorage.setItem(GRAPH_SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    } catch {
      // Ignore storage failures; the setting still applies for this session.
    }
  }

  function handleProposals(response: ChatResponse) {
    const pending = response.proposals.filter((proposal) => proposal.status === "pending");
    setReviewProposals(pending);
    setGraphIntent(response.graph_intent);
    setGraphBuilding(false);
  }

  function handleProposalStream(proposal: Proposal) {
    if (proposal.status !== "pending") {
      return;
    }
    setReviewProposals((items) => {
      if (items.some((item) => item.id === proposal.id)) {
        return items;
      }
      return [...items, proposal];
    });
  }

  function handleGraphChanged() {
    setGraphRefresh((value) => value + 1);
    setReviewProposals([]);
  }

  function refreshGraphOnly() {
    setGraphRefresh((value) => value + 1);
  }

  function openCreatedNode(node: MeNode) {
    setAnchorId(node.id);
    setNodeEditorCommand({ action: "edit", nodeId: node.id, nonce: Date.now() });
  }

  function handleProposalResolved(proposalId: string, accepted: boolean) {
    setReviewProposals((items) => items.filter((proposal) => proposal.id !== proposalId));
    if (accepted) {
      setGraphRefresh((value) => value + 1);
    }
  }

  async function resolveAllProposals(accepted: boolean) {
    const pending = reviewProposals.filter((proposal) => proposal.status === "pending");
    if (!pending.length) {
      return;
    }
    for (const proposal of pending) {
      if (accepted) {
        await api.proposals.accept(proposal.id);
      } else {
        await api.proposals.reject(proposal.id);
      }
    }
    setReviewProposals([]);
    if (accepted) {
      setGraphRefresh((value) => value + 1);
    }
  }

  const currentProposal = reviewProposals[0];
  const pendingCount = reviewProposals.filter((proposal) => proposal.status === "pending").length;

  return (
    <div className="relative h-dvh w-dvw overflow-hidden bg-white">
      <section className="absolute inset-0" aria-label="Local graph">
        <GraphPanel
          anchorId={anchorId}
          onSelectNode={(node) => {
            setAnchorId(node.id);
          }}
          compact
          refreshKey={graphRefresh}
          reviewProposals={reviewProposals}
          onCreateNode={openCreatedNode}
          showDirectedEdges={showDirectedEdges}
          showCutpointGroups={showCutpointGroups}
          editMode={graphEditMode}
        />
      </section>
      {graphBuilding || currentProposal ? (
        <div
          className={[
            "absolute bottom-4 left-1/2 z-20 flex w-[min(760px,calc(100vw-2rem))] -translate-x-1/2 items-center justify-between gap-3 rounded-full border border-slate-200/80 bg-white/90 px-4 py-3 text-slate-800 shadow-[0_20px_60px_rgba(15,23,42,0.12)] backdrop-blur-xl",
            graphBuilding ? "w-[min(560px,calc(100vw-2rem))]" : ""
          ].join(" ")}
        >
          <div className="grid min-w-0 grid-cols-[auto_auto_1fr] items-center gap-3">
            <strong className="text-sm font-semibold text-slate-900">{graphBuilding ? "建图中" : "Proposal review"}</strong>
            <span className="text-sm text-slate-500">
              {graphBuilding ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  已生成 {pendingCount} 个
                </span>
              ) : (
                `${pendingCount} pending`
              )}
            </span>
            <span className="truncate text-sm text-slate-500">
              {graphBuilding ? graphIntent?.direction ?? "Conversation Agent 正在调用图工具。" : proposalSummary(reviewProposals)}
            </span>
          </div>
          {!graphBuilding ? (
            <div className="flex flex-none items-center gap-2">
              <button
                className="inline-flex h-9 items-center gap-2 rounded-full bg-slate-900 px-4 text-sm font-medium text-white transition hover:bg-slate-800"
                onClick={() => resolveAllProposals(true)}
                title="全部接受"
              >
                <Check size={15} />
                全部接受
              </button>
              <button
                className="inline-flex h-9 items-center gap-2 rounded-full bg-slate-100 px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
                onClick={() => resolveAllProposals(false)}
                title="全部拒绝"
              >
                <X size={15} />
                全部拒绝
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      <AgentPanel
        anchorId={anchorId}
        anchorLocked={anchorLocked}
        onAnchorLockChange={setAnchorLocked}
        onAnchorChange={setAnchorId}
        onGraphChanged={handleGraphChanged}
        onNodeChanged={refreshGraphOnly}
        onProposalReview={handleProposals}
        onProposalResolved={handleProposalResolved}
        onGraphIntent={setGraphIntent}
        onGraphBuildStart={(intent) => {
          setGraphIntent(intent);
          setGraphBuilding(true);
          setReviewProposals([]);
        }}
        onGraphBuildDone={() => setGraphBuilding(false)}
        onProposalStream={handleProposalStream}
        nodeEditorCommand={nodeEditorCommand}
        showDirectedEdges={showDirectedEdges}
        onShowDirectedEdgesChange={updateShowDirectedEdges}
        showCutpointGroups={showCutpointGroups}
        onShowCutpointGroupsChange={updateShowCutpointGroups}
        graphEditMode={graphEditMode}
        onGraphEditModeChange={setGraphEditMode}
      />
    </div>
  );
}

function proposalLabel(proposal: Proposal) {
  if (proposal.operation === "create_node") {
    const payload = proposal.payload as { title?: string };
    return `新增节点：${payload.title || "未命名节点"}`;
  }
  if (proposal.operation === "create_edge") {
    return "新增连接";
  }
  if (proposal.operation === "edit_node") {
    return "修改节点";
  }
  if (proposal.operation === "split_node") {
    return "拆分节点";
  }
  if (proposal.operation === "delete_node") {
    return "删除节点";
  }
  if (proposal.operation === "remove_edge") {
    return "断开连接";
  }
  if (proposal.operation === "promote_to_workspace") {
    return "升级为工作区";
  }
  return proposal.operation;
}

function proposalSummary(proposals: Proposal[]) {
  const labels = proposals.slice(0, 3).map(proposalLabel);
  if (!labels.length) {
    return "检查并确认图更新。";
  }
  const suffix = proposals.length > labels.length ? ` 等 ${proposals.length} 项` : "";
  return `${labels.join("、")}${suffix}`;
}
