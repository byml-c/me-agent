import type { ChatResponse, ChatSession, EgoGraph, EventLogItem, MeEdge, MeNode, Proposal } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  nodes: {
    list: () => request<MeNode[]>("/nodes"),
    create: (payload: { title: string; body?: string; summary?: string; is_workspace?: boolean }) =>
      request<MeNode>("/nodes", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: string, payload: Partial<Pick<MeNode, "title" | "body" | "summary" | "memory" | "is_workspace" | "status">>) =>
      request<MeNode>(`/nodes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    get: (id: string) => request<MeNode>(`/nodes/${id}`),
    fullGraph: () => request<EgoGraph>("/nodes/graph"),
    graph: (id: string, depth = 2) => request<EgoGraph>(`/nodes/${id}/ego-graph?depth=${depth}&limit=50`)
  },
  edges: {
    create: (payload: { node_a_id: string; node_b_id: string; weight?: number; is_candidate?: boolean }) =>
      request<MeEdge>("/edges", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: string, payload: Partial<Pick<MeEdge, "weight" | "is_candidate">>) =>
      request<MeEdge>(`/edges/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    delete: (id: string) => request<void>(`/edges/${id}`, { method: "DELETE" })
  },
  workspaces: {
    list: () => request<MeNode[]>("/workspaces")
  },
  chat: {
    sessions: () => request<ChatSession[]>("/chat/sessions"),
    session: (id: string) => request<ChatSession>(`/chat/sessions/${id}`),
    send: (payload: {
      session_id?: string | null;
      message: string;
      anchor_node_ids?: string[];
      workspace_id?: string | null;
    }) => request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(payload) })
  },
  proposals: {
    list: (status?: string) => request<Proposal[]>(`/proposals${status ? `?status=${status}` : ""}`),
    accept: (id: string) => request<{ proposal: Proposal; applied: unknown }>(`/proposals/${id}/accept`, { method: "POST" }),
    reject: (id: string) => request<Proposal>(`/proposals/${id}/reject`, { method: "POST" })
  },
  events: {
    list: () => request<EventLogItem[]>("/events?limit=100")
  }
};
