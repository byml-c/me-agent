"use client";

import { useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { api } from "@/api/client";
import { GraphPanel } from "@/components/GraphPanel";
import { ChatPanel } from "@/components/ChatPanel";
import type { ChatResponse, MeNode, Proposal } from "@/types";

export function GraphChatWorkspace() {
  const [anchorId, setAnchorId] = useState<string | undefined>();
  const [anchorLocked, setAnchorLocked] = useState(false);
  const [graphRefresh, setGraphRefresh] = useState(0);
  const [reviewProposals, setReviewProposals] = useState<Proposal[]>([]);
  const [graphIntent, setGraphIntent] = useState<ChatResponse["graph_intent"]>();
  const [graphBuilding, setGraphBuilding] = useState(false);
  const [nodeEditorCommand, setNodeEditorCommand] = useState<{ action: "edit"; nodeId: string; nonce: number } | null>(null);

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
    <div className="graph-chat-shell">
      <section className="graph-stage" aria-label="Local graph">
        <GraphPanel
          anchorId={anchorId}
          onSelectNode={(node) => {
            if (!anchorLocked) {
              setAnchorId(node.id);
            }
          }}
          compact
          refreshKey={graphRefresh}
          reviewProposals={reviewProposals}
          onCreateNode={openCreatedNode}
        />
      </section>
      {graphBuilding || currentProposal ? (
        <div className={graphBuilding ? "review-dock building" : "review-dock"}>
          <div className="review-copy">
            <strong>{graphBuilding ? "建图中" : "Proposal review"}</strong>
            <span>
              {graphBuilding ? (
                <span className="dock-spinner"><Loader2 size={14} /> 已生成 {pendingCount} 个</span>
              ) : (
                `${pendingCount} pending`
              )}
            </span>
            <span>{graphBuilding ? graphIntent?.direction ?? "模型 B 正在生成 Proposal。" : proposalSummary(reviewProposals)}</span>
          </div>
          {!graphBuilding ? (
            <div className="review-actions">
              <button className="review-button primary" onClick={() => resolveAllProposals(true)} title="全部接受">
                <Check size={15} />
                全部接受
              </button>
              <button className="review-button" onClick={() => resolveAllProposals(false)} title="全部拒绝">
                <X size={15} />
                全部拒绝
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      <ChatPanel
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
  if (proposal.operation === "split_node") {
    return "拆分节点";
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
