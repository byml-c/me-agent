export type NodeStatus = "active" | "dense" | "archived";

export type MeNode = {
  id: string;
  title: string;
  body: string;
  summary: string | null;
  memory: Record<string, unknown>;
  is_workspace: boolean;
  status: NodeStatus;
  created_at: string;
  updated_at: string;
  last_accessed_at: string | null;
  access_count: number;
  distance?: number;
  include_level?: number;
  activation_score?: number;
  reason?: string;
};

export type MeEdge = {
  id: string;
  node_a_id: string;
  node_b_id: string;
  weight: number;
  access_count: number;
  coactivation_count: number;
  is_candidate: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  last_accessed_at: string | null;
};

export type EgoGraph = {
  nodes: MeNode[];
  edges: MeEdge[];
};

export type Proposal = {
  id: string;
  operation: string;
  target_ids: string[];
  payload: Record<string, unknown>;
  reason: string;
  confidence: number;
  risk_level: "low" | "medium" | "high";
  status: "pending" | "accepted" | "rejected" | "modified" | "expired";
  created_at: string;
  resolved_at: string | null;
};

export type EventLogItem = {
  id: string;
  type: string;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ChatResponse = {
  session_id: string;
  assistant_message: string;
  used_context: {
    anchor_nodes: string[];
    context_nodes: MeNode[];
    context_edges: MeEdge[];
    context_summary: string;
  };
  episode_node: MeNode;
  graph_intent?: {
    should_edit: boolean;
    direction: string;
    operations: string[];
    suggested_anchor_node_id?: string | null;
    suggested_anchor_reason?: string;
  };
  proposals: Proposal[];
  auto_applied?: unknown[];
};

export type ChatSession = {
  id: string;
  title: string;
  current_anchor_node_ids: string[];
  current_workspace_id: string | null;
  created_at: string;
  updated_at: string;
  last_message?: string;
  messages?: {
    id: string;
    session_id: string;
    role: "user" | "assistant" | "system";
    content: string;
    context_node_ids: string[];
    created_at: string;
  }[];
};
