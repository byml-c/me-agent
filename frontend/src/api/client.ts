import type { ChatResponse, ChatSession, EgoGraph, EventLogItem, LibraryEntry, LibraryFile, MeEdge, MeNode, NodeScriptRunResult, Proposal } from "@/types";

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
    archiveBatch: (nodeIds: string[]) =>
      request<{ nodes: MeNode[] }>("/nodes/batch/archive", { method: "POST", body: JSON.stringify({ node_ids: nodeIds }) }),
    insertBetween: (nodeIds: [string, string], title = "中间节点") =>
      request<{ node: MeNode; edges: MeEdge[]; removed_edge: MeEdge }>("/nodes/graph-actions/insert-between", {
        method: "POST",
        body: JSON.stringify({ node_ids: nodeIds, title })
      }),
    addCutpoint: (nodeIds: string[], title = "割点") =>
      request<{ node: MeNode; edges: MeEdge[]; removed_edges: MeEdge[] }>("/nodes/graph-actions/add-cutpoint", {
        method: "POST",
        body: JSON.stringify({ node_ids: nodeIds, title })
      }),
    runScript: (nodeId: string, scriptId: string, args: Record<string, unknown> = {}, code?: string) =>
      request<NodeScriptRunResult>(`/nodes/${nodeId}/scripts/${scriptId}/run`, {
        method: "POST",
        body: JSON.stringify({ node_id: nodeId, args, code, trigger: "manual_run" })
      }),
    triggerScripts: (nodeId: string, trigger: "enter" | "schedule", args: Record<string, unknown> = {}) =>
      request<{ node_id: string; trigger: string; results: NodeScriptRunResult[] }>(`/nodes/${nodeId}/scripts/trigger`, {
        method: "POST",
        body: JSON.stringify({ trigger, args })
      }),
    fullGraph: () => request<EgoGraph>("/nodes/graph"),
    graph: (id: string, depth = 2) => request<EgoGraph>(`/nodes/${id}/ego-graph?depth=${depth}&limit=50`)
  },
  files: {
    list: (query?: string) => request<LibraryFile[]>(`/files${query ? `?query=${encodeURIComponent(query)}` : ""}`),
    create: (payload: { name: string; description?: string; media_type?: string; source_path?: string; content?: string }) =>
      request<LibraryFile>("/files", { method: "POST", body: JSON.stringify(payload) }),
    get: (id: string) => request<LibraryFile>(`/files/${id}`)
  },
  library: {
    listEntries: (query?: string, kind?: "text" | "file") =>
      request<LibraryEntry[]>(`/library/entries${query || kind ? `?${new URLSearchParams({ ...(query ? { query } : {}), ...(kind ? { kind } : {}) }).toString()}` : ""}`),
    createEntry: (payload: { title: string; description?: string; content: string }) =>
      request<LibraryEntry>("/library/entries", { method: "POST", body: JSON.stringify(payload) }),
    getEntry: (id: string) => request<LibraryEntry>(`/library/entries/${id}`)
  },
  edges: {
    create: (payload: { node_a_id: string; node_b_id: string; weight?: number; is_candidate?: boolean }) =>
      request<MeEdge>("/edges", { method: "POST", body: JSON.stringify(payload) }),
    update: (id: string, payload: Partial<Pick<MeEdge, "node_a_id" | "node_b_id" | "weight" | "is_candidate">>) =>
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
      parent_message_id?: string | null;
    }) => request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(payload) }),
    editMessage: (id: string, content: string) =>
      request<ChatResponse>(`/chat/messages/${id}/edit`, { method: "POST", body: JSON.stringify({ content, context_budget: 12000 }) }),
    regenerate: (id: string, variantTemperature = 0.75) =>
      request<ChatResponse>(`/chat/messages/${id}/regenerate`, {
        method: "POST",
        body: JSON.stringify({ variant_temperature: variantTemperature, context_budget: 12000 })
      })
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
