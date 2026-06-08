"use client";

import { useEffect, useState } from "react";
import { Archive, Save, Sparkles } from "lucide-react";
import { api } from "@/api/client";
import type { MeNode } from "@/types";

type Props = {
  nodeId?: string;
  onSaved?: (node: MeNode) => void;
};

export function NodeEditor({ nodeId, onSaved }: Props) {
  const [node, setNode] = useState<MeNode | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [isWorkspace, setIsWorkspace] = useState(false);

  useEffect(() => {
    if (!nodeId) {
      setNode(null);
      setTitle("");
      setBody("");
      setIsWorkspace(false);
      return;
    }
    api.nodes.get(nodeId).then((item) => {
      setNode(item);
      setTitle(item.title);
      setBody(item.body);
      setIsWorkspace(item.is_workspace);
    }).catch(console.error);
  }, [nodeId]);

  async function save() {
    const saved = node
      ? await api.nodes.update(node.id, { title, body, is_workspace: isWorkspace })
      : await api.nodes.create({ title, body, is_workspace: isWorkspace });
    setNode(saved);
    onSaved?.(saved);
  }

  async function archive() {
    if (!node) {
      return;
    }
    const saved = await api.nodes.update(node.id, { status: "archived" });
    setNode(saved);
    onSaved?.(saved);
  }

  return (
    <div className="card">
      <h2>{node ? "Node Detail" : "New Node"}</h2>
      <div className="form">
        <input className="input" placeholder="标题" value={title} onChange={(event) => setTitle(event.target.value)} />
        <textarea className="textarea" placeholder="正文" value={body} onChange={(event) => setBody(event.target.value)} />
        <label className="row">
          <span>工作区节点</span>
          <input type="checkbox" checked={isWorkspace} onChange={(event) => setIsWorkspace(event.target.checked)} />
        </label>
        {node ? (
          <div className="muted">
            访问 {node.access_count} 次，状态 {node.status}
          </div>
        ) : null}
        <div className="row">
          <button className="button primary" onClick={save} disabled={!title.trim()}>
            <Save size={16} />
            保存
          </button>
          {node ? (
            <>
              <button className="button" onClick={() => setIsWorkspace(true)}>
                <Sparkles size={16} />
                升级
              </button>
              <button className="button danger" onClick={archive}>
                <Archive size={16} />
                归档
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
